"""Corpus-only source catalog. No references, evaluation runners or model imports."""
from copy import deepcopy
from pathlib import Path
import hashlib,json
from ._frozen_core.retrieval import BM25Retriever
from .errors import AppError

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class Corpus:
    def __init__(self,retriever,chunks,sources,metadata,watched=None):
        self.retriever,self.sources,self.metadata=retriever,sources,metadata
        self.build_id=retriever.corpus_build_id or "synthetic"
        self.chunks={c["chunk_id"]:deepcopy(c) for c in chunks}
        self.watched=watched or {}
        self.passages={}
        for c in chunks:
            if hashlib.sha256(sources[c["source_id"]]["text"].encode()).hexdigest()!=c["source_sha256"]:
                raise ValueError("Source identity mismatch")
            for i,seg in enumerate(c["segments"],1):
                a,b=seg["source_char_range"];x,y=seg["chunk_char_range"]
                text=sources[c["source_id"]]["text"][a:b]
                if text!=c["text"][x:y]:raise ValueError("Source mapping mismatch")
                pid=c["chunk_id"]+":b"+str(i);first,last=seg["source_lines"]
                self.passages[pid]={"passage_id":pid,"parent_chunk_id":c["chunk_id"],
                    **{k:c[k] for k in ("source_id","source_path","product_version","commit","immutable_url","source_sha256")},
                    "source_url":c["immutable_url"]+f"#L{first}-L{last}",
                    "text":text,"text_sha256":hashlib.sha256(text.encode()).hexdigest(),
                    "source_lines":seg["source_lines"],"source_char_range":[a,b],"parent_char_range":[x,y]}

    @classmethod
    def load(cls,root):
        from support_document_assistant.serving import load_bm25
        from support_document_assistant.ingestion import current_chunks
        root=Path(root);retriever=load_bm25(root);chunks=current_chunks(root)
        registry=json.loads((root/"config/sources.json").read_bytes())
        sources={};metadata={}
        for s in registry["sources"]:
            raw=(root/s["local_path"]).read_bytes().decode("utf-8")
            sources[s["source_id"]]={"text":raw,"source_id":s["source_id"],"source_path":s["path"],
                "product_version":s["product_version"],"commit":registry["commit"],
                "immutable_url":s["immutable_url"],"source_sha256":hashlib.sha256(raw.encode()).hexdigest()}
            metadata[s["source_id"]]=s
        pointer=json.loads((root/"data/processed/current.json").read_bytes())
        assets=json.loads((root/"data/assets.json").read_bytes())
        paths=["config/sources.json","config/retrieval.json","config/chunking.json","config/source-exclusions.json",
            "data/assets.json","data/processed/current.json"]
        paths += ["data/processed/"+pointer["build_id"]+"/"+p for p in ("manifest.json","chunks.jsonl","exclusions.json","report.json")]
        paths += [a["local_path"] for a in assets["assets"]]
        watched={root/p:digest(root/p) for p in paths}
        return cls(retriever,chunks,sources,metadata,watched)

    def check(self):
        for path,expected in self.watched.items():
            if digest(path)!=expected:raise ValueError("Corpus artifact changed")

    def search(self,question,top_k):
        self.check()
        hits=self.retriever.search(question,top_k=top_k)
        return [{"rank":h.rank,"score":h.score,"chunk_id":h.chunk["chunk_id"],"text":h.chunk["text"],
            "section_titles":h.chunk["section_titles"],"passages":[deepcopy(self.passages[h.chunk["chunk_id"]+":b"+str(i)])
                for i in range(1,len(h.chunk["segments"])+1)]} for h in hits]

    def select(self,selections):
        self.check();result=[];seen=set()
        for item in selections:
            source_id,pid=item["source_id"],item["passage_id"]
            p=self.passages.get(pid)
            if not p or p["source_id"]!=source_id:raise AppError(422,"unknown_source","Selected source/passage is not in the loaded corpus")
            if pid in seen:raise AppError(422,"duplicate_source","Select each passage once")
            seen.add(pid);result.append(deepcopy(p))
        return result
