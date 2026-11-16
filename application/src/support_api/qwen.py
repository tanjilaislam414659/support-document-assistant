"""Application-only frozen-inference adapter. Never imports benchmark runners/data."""
from pathlib import Path
from copy import deepcopy
from time import perf_counter
import hashlib,json,re,threading,uuid
from jinja2.sandbox import ImmutableSandboxedEnvironment
from support_document_assistant.block_packing_v2 import pack_blocks,validate_view
from support_document_assistant.generation_context import parent_unit
from support_document_assistant.gguf_preflight_adapter import RequestFailure,response_schema,validate_native
from .native import NativeRuntime
from .errors import AppError
from . import __version__

APP_DIR=Path(__file__).resolve().parents[2]
BRIDGE_SHA="8a68f3d5617d1de2a67a31fbd38f5b194c3dfc8faa8461c630e611777284edd6"
PREFIX="<|im_start|>assistant\n<think>\n\n</think>\n\n"

def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()

def render(template,messages,thinking):
    env=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True,extensions=["jinja2.ext.loopcontrols"])
    def fail(msg):raise ValueError(msg)
    env.globals["raise_exception"]=fail
    return env.from_string(template).render(messages=deepcopy(messages),tools=None,bos_token="",eos_token="<|im_end|>",
        add_generation_prompt=True,enable_thinking=thinking)

def prepare(context,cfg,template,client):
    messages=context["messages"];prompt=render(template,messages,False)
    thinking=render(template,messages,True)
    if not prompt.endswith(PREFIX) or prompt==thinking or thinking.endswith(PREFIX):
        raise RequestFailure("thinking_template","Non-thinking assistant prefix verification failed")
    actual=client.request("POST","/apply-template",{"messages":messages,
        "chat_template_kwargs":{"enable_thinking":False},"reasoning_effort":"none"},cfg["metadata_timeout_seconds"])
    if actual["value"].get("prompt")!=prompt:raise RequestFailure("template_mismatch","Native/official render mismatch")
    tokens=client.request("POST","/tokenize",{"content":prompt,"add_special":False,"parse_special":True},cfg["metadata_timeout_seconds"])["value"].get("tokens")
    if not isinstance(tokens,list) or not tokens or any(type(t) is not int or t<0 for t in tokens):
        raise RequestFailure("tokenizer_result","Invalid native token IDs")
    if len(tokens)+192>4096:raise RequestFailure("input_overflow","Full prompt plus reserve exceeds4096; no truncation")
    prefix=client.request("POST","/tokenize",{"content":PREFIX,"add_special":False,"parse_special":True},cfg["metadata_timeout_seconds"])["value"].get("tokens")
    if not prefix or tokens[-len(prefix):]!=prefix:raise RequestFailure("tokenizer_prefix","Closed-thinking prefix not retained")
    schema=response_schema([],cfg)
    ids=[p["passage_id"] for u in context["selected_units"] for p in u["passages"] if p["eligible_for_citation"]]
    if len(ids)!=len(set(ids)):raise ValueError("Duplicate eligible passage IDs")
    schema["properties"]["citations"]["maxItems"]=3 if ids else 0
    if ids:schema["properties"]["citations"]["items"]={"type":"string","enum":ids}
    schema["properties"]={k:schema["properties"][k] for k in ("answer","citations","status")}
    request={**cfg["sampling"],"prompt":tokens,"json_schema":schema,"n_predict":192,"n_cmpl":1,"id_slot":0,
        "cache_prompt":False,"stream":False,"return_tokens":True,"stop":[],"ignore_eos":False,"n_keep":0,"timings_per_token":True}
    return request,len(tokens)

class QwenEngine:
    def __init__(self,root,data_directory,*,runtime_factory=NativeRuntime,tokenizer_factory=None):
        self.root,self.data_directory=Path(root),Path(data_directory)
        path=APP_DIR/"frozen-inference.json"
        if file_hash(path)!=BRIDGE_SHA:raise ValueError("Application inference bridge changed")
        self.cfg=json.loads(path.read_bytes());self.runtime_factory=runtime_factory;self.tokenizer_factory=tokenizer_factory
        self.tokenizer=None;self.runtime=None;self.closing=threading.Event();self.owner_lock=threading.RLock()

    def availability(self):
        cfg=self.cfg
        needed=[(self.root/cfg["model_path"],cfg["model_bytes"]), (self.root/cfg["server_executable"],None),
            (self.root/cfg["template_file"],None)]
        ok=all(p.is_file() and (n is None or p.stat().st_size==n) for p,n in needed)
        return {"enabled":True,"available":ok and not self.closing.is_set(),
            "state":"available_not_loaded" if ok else "artifacts_unavailable",
            "reason":"Full identity checks occur on the explicit request" if ok else "Required local inference files unavailable"}

    def close(self):
        self.closing.set()
        with self.owner_lock:
            if self.runtime is not None:self.runtime.stop()

    def _verify(self):
        c=self.cfg
        for name,digest in c["frozen_code"].items():
            if file_hash(self.root/name)!=digest:raise ValueError("Frozen inference code changed")
        for name,digest in ((c["model_path"],c["model_sha256"]),(c["prompt_file"],c["prompt_sha256"]),(c["template_file"],c["template_sha256"])):
            if file_hash(self.root/name)!=digest:raise ValueError("Pinned inference file unavailable/corrupt")
        for item in c["runtime_files"]:
            p=self.root/item["path"]
            if p.stat().st_size!=item["bytes"] or file_hash(p)!=item["sha256"]:raise ValueError("Pinned runtime changed")

    def answer(self,question,corpus):
        start=perf_counter();rid=uuid.uuid4().hex;cfg=self.cfg;runtime=None;context=None;result=None
        try:
            self._verify()
            if self.tokenizer is None:
                if self.tokenizer_factory:self.tokenizer=self.tokenizer_factory()
                else:
                    from support_document_assistant.generator_backend import QwenTokenizer
                    self.tokenizer=QwenTokenizer(self.root,cfg["packing_config"])
            if self.closing.is_set():raise AppError(503,"generation_closing","Application is shutting down")
            mark=perf_counter();hits=corpus.retriever.search(question,top_k=3);retrieval_seconds=perf_counter()-mark
            units=[parent_unit(h,corpus.sources) for h in hits]
            prompt=(self.root/cfg["prompt_file"]).read_bytes().decode()
            mark=perf_counter();context=pack_blocks(question,units,self.tokenizer,cfg["packing_config"],prompt,corpus.metadata)
            validate_view(context,cfg["packing_config"],{k:v["text"] for k,v in corpus.sources.items()})
            packing_seconds=perf_counter()-mark
            if context["status"]=="overflow":
                return self._response(rid,corpus,context,None,None,"packing_overflow",{},start)
            folder=self.data_directory/"generation"/rid;folder.mkdir(parents=True,exist_ok=False)
            with self.owner_lock:
                if self.closing.is_set():raise AppError(503,"generation_closing","Application is shutting down")
                runtime=self.runtime_factory(self.root,cfg,folder);self.runtime=runtime
            with runtime:
                request,count=prepare(context,cfg,(self.root/cfg["template_file"]).read_bytes().decode(),runtime.client)
                runtime.ensure()
                reply=runtime.client.request("POST","/completion",request,120);native=reply["value"]
                if not isinstance(native,dict) or not isinstance(native.get("content"),str):
                    raise RequestFailure("runtime_response_error","Native response must contain string content")
                checked=validate_native(native,context,cfg)
                grammar=native.get("generation_settings",{}).get("grammar","")
                match=re.search(r"^root ::= (.+)$",grammar,re.M)
                order=re.findall(r"\b(answer|citations|status)-kv\b",match.group(1)) if match else []
                if order!=["answer","citations","status"]:raise RequestFailure("runtime_grammar_mismatch","Compiled grammar order changed")
                runtime.ensure()
                timing={"retrieval_seconds":retrieval_seconds,"packing_seconds":packing_seconds,
                    "input_tokens":float(count),"completion_request_seconds":reply["request_seconds"]}
                for key in ("prompt_ms","predicted_ms"):
                    if isinstance(native.get("timings",{}).get(key),(int,float)):timing[key]=float(native["timings"][key])
                result=self._response(rid,corpus,context,checked,native,None,timing,start)
            if getattr(runtime,"trigger",None):
                raise RequestFailure(runtime.trigger["code"],runtime.trigger["detail"])
            return result
        except RequestFailure as exc:
            if exc.record["code"]=="input_overflow":
                return self._response(rid,corpus,context,None,None,"input_overflow",{},start)
            status=504 if exc.record["code"] in ("request_timeout","startup_timeout") else 502
            raise AppError(status,exc.record["code"],"Experimental native request failed; no retry performed") from exc
        except (OSError,ValueError,KeyError,TypeError) as exc:
            raise AppError(503,"inference_artifacts_or_adapter","Pinned inference artifacts/adapter unavailable; no model fallback") from exc
        finally:
            cleanup=perf_counter()
            if runtime is not None:runtime.close()
            with self.owner_lock:self.runtime=None
            if result is not None:
                result["timings"]["cleanup_seconds"]=perf_counter()-cleanup
                result["timings"]["pipeline_seconds"]=perf_counter()-start

    def _response(self,rid,corpus,context,checked,native,error,timings,start):
        checked=checked or {};native=native or {}
        obj=(checked.get("parser_result") or {}).get("parsed_object")
        status=obj.get("status") if isinstance(obj,dict) else None
        err=checked.get("error")
        return {"request_id":rid,"application_version":__version__,"experimental":True,"unverified":True,
            "model_status":status,
            "application_validation_outcome":checked.get("outcome","generation_validation_error"),
            "raw_output":checked.get("raw_output"),"validated_response":checked.get("response"),
            "finish_reason":checked.get("finish_reason"),
            "supplied_passages":[p for u in (context or {}).get("selected_units",[]) for p in u["passages"]],
            "omitted_blocks":(context or {}).get("omitted_blocks",[]),
            "identifiers":{"corpus_build_id":corpus.build_id,"candidate_id":self.cfg["candidate_id"],
                "model_revision":self.cfg["model_revision"],"runtime_commit":self.cfg["runtime_commit"],
                "prompt_sha256":self.cfg["prompt_sha256"],"bridge_sha256":BRIDGE_SHA},
            "timings":{**timings,"pipeline_seconds":perf_counter()-start},
            "error":{"code":error or err["code"],"message":"Output rejected; not an approved answer or successful abstention"} if error or err else None,
            "limitations":["Unverified experimental output; application acceptance is not factual correctness.",
                "Model insufficient_evidence is not a verified abstention.", "Never automatically inserted into a ticket.",
                "Historical Python3.13.0 scope; original prompt/schema mismatch retained."]}
