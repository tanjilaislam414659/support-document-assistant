"""Offline content/evidence audit. Never imports retrieval or model execution."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return (json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
def audit():
    listed=subprocess.check_output(["git","ls-files","-z"],cwd=ROOT).decode().split("\0")
    files=[p for p in listed if p]
    if not files:raise ValueError("Stage the proposed allowlist first")
    forbidden_parts={".venv","__pycache__","models",".app-data",".local-tmp","node_modules"}
    forbidden_ext={".gguf",".safetensors",".exe",".dll",".sqlite",".sqlite3",".db",".pyc",".pt",".bin",".pkl"}
    unexpected=[];findings=[]
    secrets=[r"(?m)^-----BEGIN [A-Z ]*PRIVATE KEY-----$",r"github_pat_[A-Za-z0-9_]{30,}",r"gh[pousr]_[A-Za-z0-9]{30,}",r"AKIA[0-9A-Z]{16}",r"sk-[A-Za-z0-9]{32,}"]
    # The upstream tutorial's public example address/path are licensed source material.
    allowed_email={"95691705+tanjilaislam414659@users.noreply.github.com","me@kennethreitz.com"}
    email_counts={}
    bundle_root=ROOT/"application/src/support_api/resources/corpus"
    bundle_manifest=json.loads((bundle_root/"bundle.json").read_bytes())
    attributed={"application/src/support_api/resources/corpus/"+p:r["sha256"] for p,r in bundle_manifest["files"].items()}
    for relative in files:
        p=ROOT/relative
        if any(x in forbidden_parts for x in p.relative_to(ROOT).parts) or p.suffix.lower() in forbidden_ext:
            unexpected.append(relative);continue
        b=p.read_bytes()
        if p.suffix==".png":
            assert b.startswith(b"\x89PNG\r\n\x1a\n") and relative.startswith("docs/images/"),relative
            continue
        try:text=b.decode("utf-8")
        except UnicodeDecodeError:unexpected.append(relative);continue
        for pattern in secrets:
            if re.search(pattern,text):findings.append({"path":relative,"kind":"credential/private-key pattern"})
        if re.search(r"[A-Za-z]:[\\/]+Users[\\/]",text):
            findings.append({"path":relative,"kind":"developer path"})
        for email in re.findall(r"[A-Za-z0-9.+_-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",text):
            if email not in allowed_email and not (relative in attributed and sha(b)==attributed[relative]):findings.append({"path":relative,"kind":"unexpected email","value":email})
            email_counts[email]=email_counts.get(email,0)+1
    if unexpected or findings:raise ValueError(json.dumps({"excluded_or_binary":unexpected,"findings":findings}))
    origin=json.loads((ROOT/"docs/publication-origin.json").read_bytes())
    for record in origin["files"]:
        assert sha((ROOT/record["destination"]).read_bytes())==record["publication_sha256"],record["destination"]
    cfg=json.loads((ROOT/"application/frozen-inference.json").read_bytes())
    for path,digest in cfg["frozen_code"].items():assert sha((ROOT/path).read_bytes())==digest,path
    assert sha((ROOT/cfg["prompt_file"]).read_bytes())==cfg["prompt_sha256"]
    assert sha((ROOT/cfg["template_file"]).read_bytes())==cfg["template_sha256"]
    assert sha((ROOT/"application/frozen-inference.json").read_bytes())=="8a68f3d5617d1de2a67a31fbd38f5b194c3dfc8faa8461c630e611777284edd6"
    human=json.loads((ROOT/"research/results/human-review.original.json").read_bytes())
    count=0;bindings=0;mapped=0
    resources=ROOT/"application/src/support_api/resources/corpus"
    registry=json.loads((resources/"config/sources.json").read_bytes())
    sources={s["source_id"]:(resources/s["local_path"]).read_bytes().decode() for s in registry["sources"]}
    for h in human["records"]:
        d=json.loads((ROOT/"research/results/contexts"/(h["context_id"]+".json")).read_bytes());b=h["binding"]
        assert d["curation"]["original_record_sha256"]==b["source_record_sha256"]
        pairs=[(d["raw_output"].encode(),b["raw_output_sha256"]),(canonical(d["parsed_object"]),b["model_object_sha256"]),
            (canonical(d["response"]),b["resolved_response_sha256"]),(canonical(d["supplied_units"]),b["supplied_units_sha256"]),
            (canonical(d["omitted_blocks"]),b["omitted_blocks_sha256"]),(d["question"].encode(),b["question_sha256"])]
        for raw,expected in pairs:assert sha(raw)==expected,(h["context_id"],expected);bindings+=1
        assert sha(d["formatted_prompt"].encode())==d["formatted_prompt_sha256"]
        for unit in d["supplied_units"]:
            for p in unit["passages"]:
                assert sha(p["text"].encode())==p["text_sha256"]
                if p["eligible_for_citation"]:
                    sid=p["provenance"]["source_id"];a,z=p["source_char_range"]
                    assert sources[sid][a:z]==p["text"],(h["context_id"],p["passage_id"])
                    mapped+=1
        count+=1
    assert count==20
    workflow=(ROOT/".github/workflows/application.yml").read_text(encoding="utf-8")
    actions=re.findall(r"uses:\s*([^\s#]+)",workflow)
    assert actions and all(re.fullmatch(r"[^@]+@[0-9a-f]{40}",a) for a in actions)
    assert "contents: read" in workflow and "persist-credentials: false" in workflow
    assert not re.search(r"(?i)push\s*:\s*true|permissions:\s*write-all",workflow)
    links=0
    for relative in files:
        if not relative.endswith(".md"):continue
        p=ROOT/relative
        for url in re.findall(r"\]\(([^)]+)\)",p.read_text(encoding="utf-8")):
            if url.startswith(("https://","http://","#","mailto:")):continue
            target=(p.parent/url.split("#")[0]).resolve()
            assert target.is_relative_to(ROOT) and target.exists(),(relative,url)
            links+=1
    refs=subprocess.check_output(["git","tag"],cwd=ROOT,text=True).strip()
    assert not refs or refs.splitlines()==["v0.2.0"],"Only the explicitly approved release tag is allowed"
    remotes=subprocess.check_output(["git","remote"],cwd=ROOT,text=True).strip()
    assert not remotes or remotes=="origin","Unexpected remote"
    if remotes:
        url=subprocess.check_output(["git","remote","get-url","origin"],cwd=ROOT,text=True).strip()
        assert url=="https://github.com/tanjilaislam414659/support-document-assistant.git","Unexpected publication destination"
    commit_info=subprocess.run(["git","log","--all","--format=%H%x09%an%x09%ae%x09%cn%x09%ce%x09%P"],cwd=ROOT,capture_output=True,text=True)
    commits=[]
    if commit_info.returncode==0:
        for row in commit_info.stdout.splitlines():
            parts=row.split("\t");assert parts[1:5]==["Tanjila Islam","95691705+tanjilaislam414659@users.noreply.github.com"]*2
            commits.append(parts[0])
        # There must be a fresh root; original development snapshot is never an object in this history.
        original="05c266c2cb3dbe50504b416597d2726bae6acd78"
        assert subprocess.run(["git","cat-file","-e",original+"^{commit}"],cwd=ROOT,capture_output=True).returncode!=0
    history_blob_count=0
    if commits:
        objects=subprocess.check_output(["git","rev-list","--objects","--all"],cwd=ROOT,text=True).splitlines()
        names={row.split(" ",1)[0]:row.split(" ",1)[1] for row in objects if " " in row}
        payload=("\n".join(names)+"\n").encode()
        raw=subprocess.check_output(["git","cat-file","--batch"],input=payload,cwd=ROOT)
        at=0
        while at<len(raw):
            end=raw.index(b"\n",at);oid,kind,size=raw[at:end].decode().split();size=int(size)
            body=raw[end+1:end+1+size];at=end+1+size+1
            if kind!="blob":continue
            history_blob_count+=1;name=names[oid]
            assert not any(x in forbidden_parts for x in Path(name).parts) and Path(name).suffix.lower() not in forbidden_ext,name
            if name.endswith(".png"):assert body.startswith(b"\x89PNG\r\n\x1a\n");continue
            txt=body.decode("utf-8")
            for pattern in secrets:assert not re.search(pattern,txt),(name,"historical credential pattern")
            if name!="tools/audit_publication.py":
                assert not re.search(r"[A-Za-z]:[\\/]+Users[\\/]",txt),(name,"historical local path")
        roots=subprocess.check_output(["git","rev-list","--max-parents=0","--all"],cwd=ROOT,text=True).splitlines()
        assert len(roots)==1,"Fresh history must have one root"
    return {"tracked_files":len(files),"bytes":sum((ROOT/p).stat().st_size for p in files),
        "context_records":count,"retained_binding_checks":bindings,"eligible_source_mappings":mapped,
        "local_document_links":links,"pinned_actions":actions,"fresh_public_commits":commits,"history_blobs_scanned":history_blob_count,
        "credential_findings":0,"unexpected_local_paths":0,"excluded_binaries":0,"remote_configured":bool(remotes),
        "third_party_public_email_occurrences":email_counts.get("me@kennethreitz.com",0),
        "real_inference_requests":0,"retrieval_queries":0}
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path);a=p.parse_args();r=audit()
    if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_bytes(canonical(r))
    print(json.dumps(r))
