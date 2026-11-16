
"""Bounded internal loopback transport, exact ChatML and independent validation."""
import http.client,json,re,socket,threading,time
from copy import deepcopy
from .assets import sha256
from .generation_parser_v2 import revalidate,citation_diagnostics

ROUTES={"/health","/props","/apply-template","/tokenize","/completion"}
class RequestFailure(RuntimeError):
    def __init__(self,code,detail,*,raw_body=None,http_status=None,duration=None):
        super().__init__(detail)
        self.record={"code":code,"detail":detail,"raw_http_body":raw_body,
                     "http_status":http_status,"request_seconds":duration}

class LoopbackClient:
    def __init__(self,host,port):
        if host!="127.0.0.1" or type(port) is not int or not 1<=port<=65535:
            raise ValueError("Only literal loopback transport is allowed")
        self.host,self.port=host,port
        self.completion_calls=0

    def request(self,method,path,payload=None,timeout=10):
        if path not in ROUTES or method not in ("GET","POST") or not 0<timeout<=60:
            raise ValueError("Unapproved internal endpoint or timeout")
        if path=="/completion":self.completion_calls+=1
        body=json.dumps(payload,ensure_ascii=True,separators=(",",":")).encode() if payload is not None else None
        start=time.perf_counter();deadline=start+timeout;expired=threading.Event()
        connection=http.client.HTTPConnection(self.host,self.port,timeout=timeout)
        raw=bytearray();status=None
        def abort():
            expired.set()
            if connection.sock:
                try:connection.sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
            connection.close()
        timer=threading.Timer(timeout,abort);timer.daemon=True;timer.start()
        def remaining():
            value=deadline-time.perf_counter()
            if value<=0 or expired.is_set():raise TimeoutError("Absolute request deadline exceeded")
            if connection.sock:connection.sock.settimeout(value)
            return value
        try:
            remaining()
            connection.request(method,path,body=body,headers={"Content-Type":"application/json","Connection":"close"})
            remaining();response=connection.getresponse();status=response.status
            while True:
                remaining()
                block=response.read1(65536)
                if not block:break
                raw.extend(block)
                if len(raw)>2_000_000:raise RequestFailure("response_size","Native response exceeds bound")
            remaining()
            text=raw.decode("utf-8")
            if status!=200:raise RequestFailure("http_error","Native endpoint returned HTTP "+str(status),
                raw_body=text,http_status=status,duration=time.perf_counter()-start)
            try:value=json.loads(text)
            except (ValueError,RecursionError) as exc:
                raise RequestFailure("invalid_http_json",str(exc),raw_body=text,http_status=status)
            return {"value":value,"raw_http_body":text,"http_status":status,
                    "request_seconds":time.perf_counter()-start}
        except RequestFailure as exc:
            if exc.record["request_seconds"] is None:exc.record["request_seconds"]=time.perf_counter()-start
            raise
        except (TimeoutError,socket.timeout,OSError,http.client.HTTPException,UnicodeError) as exc:
            code="request_timeout" if expired.is_set() or isinstance(exc,(TimeoutError,socket.timeout)) else "transport_error"
            raise RequestFailure(code,str(exc),raw_body=raw.decode("utf-8",errors="replace") or None,
                http_status=status,duration=time.perf_counter()-start) from exc
        finally:
            timer.cancel();connection.close()

def source_context(passages):
    checked=[];seen=set()
    if not isinstance(passages,list) or len(passages)>6:raise ValueError("Invalid passage collection")
    for p in passages:
        pid=p.get("passage_id")
        if not isinstance(pid,str) or not re.fullmatch(r"[A-Z][A-Z0-9_-]{0,19}",pid) or pid in seen:
            raise ValueError("Invalid/duplicate passage ID")
        seen.add(pid)
        if type(p.get("eligible_for_citation")) is not bool or not isinstance(p.get("text"),str) or not p["text"]:
            raise ValueError("Invalid passage text or eligibility")
        text=p["text"]
        checked.append({**deepcopy(p),"text_sha256":sha256(text.encode()),"origin":"project-authored synthetic preflight",
            "source_lines":[1,len(text.splitlines())],"source_char_range":[0,len(text)],
            "provenance":{"source_id":"synthetic-preflight","source_path":"evaluation/gguf-preflight-synthetic.json",
                "product_version":"invented fixture","commit":None,"immutable_url":None,"source_sha256":sha256(text.encode())},
            "parent_chunk_id":None,"parent_char_range":None})
    return {"selected_units":[{"unit_id":"synthetic-preflight","passages":checked}]}

def response_schema(passages,cfg):
    context=source_context(passages)
    eligible=[p["passage_id"] for p in context["selected_units"][0]["passages"] if p["eligible_for_citation"]]
    citations={"type":"array","minItems":0,"maxItems":cfg["max_citations"] if eligible else 0,
               "items":{"type":"string","enum":eligible} if eligible else {"type":"string"}}
    return {"type":"object","properties":{
        "status":{"type":"string","enum":["answered","insufficient_evidence"]},
        "answer":{"type":"string","minLength":1,"maxLength":cfg["max_answer_characters"]},
        "citations":citations},"required":["status","answer","citations"],"additionalProperties":False}

def messages_for(question,passages,prompt,cfg):
    if not isinstance(question,str) or not question.strip() or len(question)>cfg["max_question_characters"]:
        raise ValueError("Invalid or oversized question")
    context=source_context(passages)
    if any(len(p["text"])>cfg["max_evidence_characters"] for p in passages):
        raise ValueError("Evidence exceeds frozen bound; no truncation")
    payload={"question":question,"passages":[{k:p[k] for k in ("passage_id","eligible_for_citation","text")}
                for p in context["selected_units"][0]["passages"]]}
    body=json.dumps(payload,ensure_ascii=True,separators=(",",":")).replace("<","\\u003c").replace(">","\\u003e")
    messages=[{"role":"system","content":prompt},{"role":"user","content":body}]
    if sum(len(m["content"]) for m in messages)>cfg["max_input_characters"]:
        raise ValueError("Input characters exceed bound; no truncation")
    return messages,context

def chatml(messages):
    if [m["role"] for m in messages]!=["system","user"]:raise ValueError("Expected system/user roles")
    return "".join("<|im_start|>"+m["role"]+"\n"+m["content"]+"<|im_end|>\n" for m in messages)+"<|im_start|>assistant\n"

def prepare(question,passages,prompt,cfg,client):
    messages,context=messages_for(question,passages,prompt,cfg)
    expected=chatml(messages)
    formatted=client.request("POST","/apply-template",{"messages":messages},cfg["metadata_timeout_seconds"])
    if formatted["value"].get("prompt")!=expected:
        raise RequestFailure("template_mismatch","Runtime template differs from official plain Qwen ChatML")
    tokenized=client.request("POST","/tokenize",{"content":expected,"add_special":False,"parse_special":True},cfg["metadata_timeout_seconds"])
    ids=tokenized["value"].get("tokens")
    if not isinstance(ids,list) or not ids or any(type(x) is not int or x<0 for x in ids):
        raise RequestFailure("tokenizer_result","Invalid native tokenizer result")
    if ids[0]!=151644 or ids[-3:]!=[151644,77091,198]:
        raise RequestFailure("tokenizer_prefix","Unexpected official assistant prefix or start token")
    if len(ids)>cfg["max_input_tokens"] or len(ids)+cfg["output_token_cap"]>cfg["context_tokens"]:
        raise RequestFailure("input_budget","Complete prompt plus output reserve exceeds bound; no truncation")
    schema=response_schema(passages,cfg)
    request={**cfg["sampling"],"prompt":ids,"json_schema":schema,"n_predict":cfg["output_token_cap"],
        "n_cmpl":1,"id_slot":0,"cache_prompt":False,"stream":False,"return_tokens":True,
        "stop":[],"ignore_eos":False,"n_keep":0,"timings_per_token":True}
    return {"messages":messages,"formatted_prompt":expected,"formatted_prompt_sha256":sha256(expected.encode()),
        "input_token_ids":ids,"input_tokens":len(ids),"output_reserve":cfg["output_token_cap"],
        "total_with_reserve":len(ids)+cfg["output_token_cap"],"context":context,"request":request,
        "formatting_seconds":formatted["request_seconds"],"tokenization_seconds":tokenized["request_seconds"]}

def structure_valid(parsed,cfg):
    if not isinstance(parsed,dict) or set(parsed)!={"status","answer","citations"}:return False
    answer,ids=parsed["answer"],parsed["citations"]
    return (parsed["status"] in ("answered","insufficient_evidence")
        and isinstance(answer,str) and bool(answer.strip()) and len(answer)<=cfg["max_answer_characters"]
        and not any((ord(c)<32 and c not in "\n\r\t") or 0xD800<=ord(c)<=0xDFFF for c in answer)
        and isinstance(ids,list) and len(ids)<=cfg["max_citations"]
        and all(isinstance(i,str) for i in ids) and len(ids)==len(set(ids)))


def validate_native(native,context,cfg):
    raw=native.get("content") if isinstance(native,dict) else None
    finish=native.get("stop_type") if isinstance(native,dict) else None
    timings=native.get("timings",{}) if isinstance(native,dict) else {}
    predicted=timings.get("predicted_n",native.get("tokens_predicted")) if isinstance(native,dict) else None
    completed=(finish=="eos" and native.get("stop") is True and native.get("truncated") is False
        and type(predicted) is int and 0<predicted<=cfg["output_token_cap"])
    # Inspect syntax/schema/citations independently even if EOS/cap validation fails.
    # The outer completion gate still forces error + response=None for every incomplete result.
    parser=revalidate(raw,context,cfg,reached_cap_without_eos=False)
    parsed=parser["parsed_object"]
    diagnostics=citation_diagnostics(parsed,context)
    ids=parsed.get("citations") if isinstance(parsed,dict) else None
    typed_ids=isinstance(ids,list) and all(isinstance(x,str) for x in ids)
    citation={"diagnostics":diagnostics,"all_ids_eligible":all(d["resolution"]=="eligible_supplied" for d in diagnostics) if typed_ids else None,
              "distinct":len(ids)==len(set(ids)) if typed_ids else None,
              "answered_has_citation":bool(ids) if typed_ids and parsed.get("status")=="answered" else None}
    structural=structure_valid(parsed,cfg)
    accepted=parser["validation"]["accepted"]
    outcome=parser["outcome"] if completed else "generation_validation_error"
    response=parser["response"] if completed and accepted else None
    error=None
    if not completed:error={"code":"incomplete_generation","detail":"Require EOS completion, no truncation and bounded token count","finish_reason":finish}
    elif not accepted:error={"code":parser["validation"]["error_code"],"detail":parser["validation"]["detail"]}
    return {"raw_output":raw,"finish_reason":finish,"completion_valid":completed,
        "structural_valid":structural,"parser_result":parser,"citation_eligibility":citation,
        "outcome":outcome,"response":response,"error":error,"native_timings":timings,
        "human_semantic_review":{"status":"pending","reviewer":None,"reviewed_on":None,"quality_labels":None}}

def one_attempt(question,passages,prompt,cfg,client):
    start=time.perf_counter();prepared=None;reply=None
    try:
        prepared=prepare(question,passages,prompt,cfg,client)
        reply=client.request("POST","/completion",prepared["request"],cfg["timeout_seconds"])
        checked=validate_native(reply["value"],prepared["context"],cfg)
        return {**checked,"prepared":prepared,"http_response":reply,"attempt_seconds":time.perf_counter()-start}
    except (RequestFailure,ValueError,KeyError,TypeError) as exc:
        error=exc.record if isinstance(exc,RequestFailure) else {"code":"adapter_input_or_runtime_error","detail":str(exc)}
        return {"outcome":"generation_validation_error","response":None,"error":error,"prepared":prepared,
            "http_response":reply,"raw_output":None,"finish_reason":None,"completion_valid":False,
            "structural_valid":None,"parser_result":None,"citation_eligibility":None,
            "attempt_seconds":time.perf_counter()-start,
            "human_semantic_review":{"status":"pending","reviewer":None,"reviewed_on":None,"quality_labels":None}}
