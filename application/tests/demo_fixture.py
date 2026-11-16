"""Clean, explicitly fictional portfolio demonstration; never the research corpus."""
from hashlib import sha256
from support_api._frozen_core.retrieval import BM25Retriever
from support_api.corpus import Corpus
QUESTION="What details belong in a fictional Orbit support request?"
def corpus():
    raw=("SYNTHETIC DEMONSTRATION — Fictional Orbit support lab\n"
         "Include the indicator colour, device version and exact status message in a support request.\n"
         "The demonstration indicator pulses amber.\n"
         "This project-authored fixture is not CPython documentation or real device guidance.\n")
    text=raw.rstrip("\n");sid="synthetic-orbit-demo"
    chunk={"chunk_id":"chunk-"+sha256(text.encode()).hexdigest(),"source_id":sid,"source_path":"synthetic/orbit-support.rst",
        "product_version":"3.13.0 · synthetic demo","commit":"d"*40,
        "immutable_url":"https://example.invalid/synthetic-demo/"+("d"*40)+"/orbit-support.rst",
        "source_sha256":sha256(raw.encode()).hexdigest(),"text_sha256":sha256(text.encode()).hexdigest(),
        "eligible_for_answer_support":True,"text":text,"section_titles":["Synthetic demonstration","Orbit support request"],
        "segments":[{"source_lines":[1,4],"source_char_range":[0,len(text)],"chunk_char_range":[0,len(text)],"kind":"paragraph"}]}
    source={sid:{"text":raw,**{k:chunk[k] for k in ("source_id","source_path","product_version","commit","immutable_url","source_sha256")}}}
    return Corpus(BM25Retriever([chunk],corpus_build_id="synthetic-orbit-demo-v1"),[chunk],source,{sid:{"title":"Synthetic Orbit demonstration"}})
