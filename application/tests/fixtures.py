"""Invented documentation only; never loads benchmark questions or approved corpus."""
from hashlib import sha256
from support_api._frozen_core.retrieval import BM25Retriever
from support_api.corpus import Corpus

QUESTION="What blink count is stated for the fictional Harbor laboratory indicator?"

def corpus():
    raw="Fictional Harbor support lab.\nThe Harbor indicator blinks seven times.\nThis fixture does not prescribe a device action.\n"
    text=raw.rstrip("\n");digest=sha256(raw.encode()).hexdigest();sid="fictional-harbor"
    chunk={"chunk_id":"chunk-"+sha256(text.encode()).hexdigest(),"source_id":sid,"source_path":"harbor.rst",
        "product_version":"3.13.0 synthetic fixture","commit":"f"*40,"immutable_url":"https://fixture.invalid/harbor.rst",
        "source_sha256":digest,"text_sha256":sha256(text.encode()).hexdigest(),"eligible_for_answer_support":True,
        "text":text,"character_count":len(text),"section_titles":["Invented support fixture"],
        "segments":[{"source_lines":[1,3],"source_char_range":[0,len(text)],"chunk_char_range":[0,len(text)],"kind":"paragraph"}]}
    sources={sid:{"text":raw,**{k:chunk[k] for k in ("source_id","source_path","product_version","commit","immutable_url","source_sha256")}}}
    metadata={sid:{"title":"Invented support fixture","platform_scope":"Fictional laboratory; no production scope"}}
    return Corpus(BM25Retriever([chunk],corpus_build_id="synthetic-harbor-v1"),[chunk],sources,metadata)
