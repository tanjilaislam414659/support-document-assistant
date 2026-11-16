"""Committed invented corpus and fake generator, never an approved research question."""
from hashlib import sha256
from support_api import __version__
from support_api._frozen_core.retrieval import BM25Retriever
from support_api.corpus import Corpus

QUESTION="What does the fictional Lantern label say?"
LITERAL='<img src=x onerror="window.fixtureExecuted=true">'

def corpus():
    raw="Fictional Lantern laboratory\nThe Lantern label reads "+LITERAL+".\nThe Lantern indicator blinks seven times.\n"
    text=raw.rstrip("\n");sid="fictional-lantern"
    c={"chunk_id":"chunk-"+sha256(text.encode()).hexdigest(),"source_id":sid,"source_path":"lantern.rst",
        "product_version":"3.13.0 synthetic","commit":"a"*40,"immutable_url":"https://fixture.invalid/blob/"+("a"*40)+"/lantern.rst",
        "source_sha256":sha256(raw.encode()).hexdigest(),"text_sha256":sha256(text.encode()).hexdigest(),
        "eligible_for_answer_support":True,"text":text,"section_titles":["Fictional Lantern laboratory"],
        "segments":[{"source_lines":[1,3],"source_char_range":[0,len(text)],"chunk_char_range":[0,len(text)],"kind":"paragraph"}]}
    sources={sid:{"text":raw,**{k:c[k] for k in ("source_id","source_path","product_version","commit","immutable_url","source_sha256")}}}
    return Corpus(BM25Retriever([c],corpus_build_id="invented-lantern-ui-v1"),[c],sources,{sid:{"title":"Synthetic fixture"}})

class FakeEngine:
    def availability(self):return {"enabled":True,"available":True,"state":"synthetic_fake","reason":"Fake generation; no model or native server"}
    def answer(self,question,loaded):
        return {"request_id":"fake-ui","application_version":__version__,"model_status":"insufficient_evidence",
            "application_validation_outcome":"validated_insufficient_evidence",
            "raw_output":'{"status":"insufficient_evidence","answer":"'+LITERAL.replace('"','\\"')+'","citations":[]}',
            "validated_response":{"status":"insufficient_evidence","answer":LITERAL,"citations":[]},
            "finish_reason":"synthetic","supplied_passages":[],"omitted_blocks":[],"identifiers":{"model":"fake"},
            "timings":{},"error":None,"limitations":["Unverified fake output, not an approved answer or successful abstention."]}
    def close(self):pass
