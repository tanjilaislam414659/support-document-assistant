"""Actual Docker default distribution checks. Uses only owned UUID-named resources."""
import argparse,json,shutil,subprocess,time,uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

def docker(*args,check=True):
    r=subprocess.run(["docker",*map(str,args)],capture_output=True,text=True,encoding="utf-8",timeout=90)
    if check and r.returncode:raise RuntimeError(r.stderr or r.stdout)
    return r.stdout.strip()

def request(base,path,method="GET",data=None):
    q=Request(base+path,data=json.dumps(data).encode() if data is not None else None,method=method,
        headers={"Content-Type":"application/json"} if data is not None else {})
    try:
        with urlopen(q,timeout=5) as r:return r.status,json.load(r)
    except HTTPError as e:return e.code,json.load(e)

def run(image,output):
    started=time.perf_counter();token="sda-pub-"+uuid.uuid4().hex[:10];containers=[];volumes=[]
    checks=[];records={};root=Path(__file__).resolve().parents[2]
    def mark(name):checks.append(name)
    def launch(label,volume,extra=(),command=()):
        name=token+"-"+label;containers.append(name);t=time.perf_counter()
        docker("run","-d","--name",name,"--label","support.publication="+token,
            "--read-only","--cap-drop","ALL","--security-opt","no-new-privileges:true",
            "--tmpfs","/tmp:size=16m,mode=1777","-p","127.0.0.1::8010",
            "--mount","type=volume,source="+volume+",target=/var/lib/support",*extra,image,*command)
        info=json.loads(docker("inspect",name))[0];binding=info["HostConfig"]["PortBindings"]["8010/tcp"][0]
        assert binding["HostIp"]=="127.0.0.1" and info["HostConfig"]["ReadonlyRootfs"]
        actual=info["NetworkSettings"]["Ports"]["8010/tcp"][0];base="http://127.0.0.1:"+actual["HostPort"]
        for _ in range(100):
            try:
                if request(base,"/health")[0]==200:break
            except (OSError,URLError):time.sleep(.1)
        else:raise RuntimeError("Container health unavailable: "+docker("logs",name))
        return name,base,time.perf_counter()-t
    try:
        volume=token+"-tickets";volumes.append(volume);docker("volume","create","--label","support.publication="+token,volume)
        name,base,startup=launch("default",volume)
        assert request(base,"/ready")[0]==200
        meta=request(base,"/metadata")[1];assert len(meta["sources"])==4
        assert meta["experimental_generation"]["state"]=="unsupported_distribution" and not meta["experimental_generation"]["enabled"]
        assert request(base,"/experimental/answer","POST",{"question":"Invented Lantern query"})[0]==403
        with urlopen(base+"/",timeout=5) as r:assert b"Support Desk" in r.read()
        mark("actual_default_health_readiness_ui_and_generation_disabled")
        code="""import os,json,importlib.util,pathlib,importlib.metadata
import support_api
root=pathlib.Path(support_api.__file__).parent
assert os.getuid()==10001
for module in ('torch','transformers','support_document_assistant','support_api.qwen','support_api.native'):
 assert importlib.util.find_spec(module) is None,module
assert not list(pathlib.Path('/usr/local').rglob('*.exe'))
bad=[str(p) for p in root.rglob('*') if p.suffix in ('.exe','.gguf','.safetensors') or p.name in ('evaluation','reports','benchmarks')]
assert not bad,bad
for path in (root/'app.py',root/'resources/corpus/data/raw/py-venv.rst',pathlib.Path('/app/requirements-runtime.txt')):
 try:
  with path.open('a') as f:f.write('must not write')
 except OSError:pass
 else:raise AssertionError('Writable protected file')
print(json.dumps({'uid':os.getuid(),'installed':{d.metadata['Name']:d.version for d in importlib.metadata.distributions()},'protected_paths_readonly':True,'forbidden_artifacts':bad}))
"""
        identity=json.loads(docker("exec",name,"python","-c",code))
        assert docker("exec",name,"python","-m","pip","check")=="No broken requirements found."
        mark("nonroot_readonly_files_no_ml_runtime_or_research_package")
        for _ in range(30):
            health=json.loads(docker("inspect",name))[0]["State"]["Health"]["Status"]
            if health=="healthy":break
            time.sleep(.5)
        assert health=="healthy";mark("configured_readiness_healthcheck_healthy")
        docker("rm","-f",name)
        with TemporaryDirectory() as tmp:
            fixture=Path(tmp)/"verification";fixture.mkdir()
            for filename in ("fixture_server.py","ui_fixture.py"):shutil.copyfile(Path(__file__).with_name(filename),fixture/filename)
            options=("--mount","type=bind,source="+str(fixture.resolve())+",target=/verification,readonly")
            command=("python","/verification/fixture_server.py","--container","--port","8010","--data","/var/lib/support")
            name,base,fixture_startup=launch("fixture",volume,options,command)
            code,result=request(base,"/search","POST",{"question":"What does the fictional Lantern label say?","top_k":1})
            assert code==200;p=result["results"][0]["passages"][0]
            assert "<img" in p["text"] and p["source_url"].endswith("#L1-L3")
            code,t=request(base,"/tickets/draft","POST",{"issue":"Invented indicator problem","environment":{"OS":"Fictional"},
                "selected_sources":[{"source_id":p["source_id"],"passage_id":p["passage_id"]}]})
            assert code==201 and t["documentation"][0]==p;tid=t["ticket_id"];path="/tickets/"+tid
            code,t=request(base,path,"PATCH",{"expected_revision":1,"human_notes":"Human fixture edit"});assert code==200
            code,t=request(base,path+"/review","POST",{"expected_revision":2,"confirm_review":True});assert code==200 and t["review_state"]=="review_recorded"
            code,t=request(base,path,"PATCH",{"expected_revision":2,"human_notes":"Post-review edit"});assert code==200 and t["review_state"]=="unreviewed"
            assert request(base,path+"/review","POST",{"expected_revision":2,"confirm_review":True})[0]==409
            mark("synthetic_search_select_draft_edit_review_invalidation_and_stale_rejection")
            docker("rm","-f",name)
            name,base,_=launch("recreated",volume,options,command)
            code,reopened=request(base,path);assert code==200 and reopened==t and len(reopened["review_events"])==1
            mark("sqlite_content_revisions_reviews_persist_after_container_recreation")
            docker("rm","-f",name)
            # Hash rejection and missing-file handling using altered copies, never original source artifacts.
            from support_api.bundle import RESOURCES
            bundle=Path(tmp)/"corpus";shutil.copytree(RESOURCES/"corpus",bundle)
            src=bundle/"data/raw/py-venv.rst";original=src.read_bytes();src.write_bytes(original+b"corrupt")
            opt=("--mount","type=bind,source="+str(bundle.resolve())+",target=/test-corpus,readonly","-e","SUPPORT_BUNDLE_DIRECTORY=/test-corpus")
            for label in ("corrupt","missing"):
                if label=="missing":src.unlink()
                name,base,_=launch(label,volume,opt)
                assert request(base,"/health")[0]==200 and request(base,"/ready")[0]==503
                assert request(base,"/search","POST",{"question":"Invented Lantern query"})[0]==503
                docker("rm","-f",name);mark(label+"_artifact_health_live_readiness_and_search_503")
        compose=json.loads(subprocess.check_output(["docker","compose","config","--format","json"],cwd=root,text=True))
        service=compose["services"]["support"]
        assert service["ports"][0]["host_ip"]=="127.0.0.1" and service["ports"][0]["published"]=="8010" and service["read_only"]
        mark("compose_loopback_readonly_and_dedicated_named_volume_contract")
        project=token+"-compose"
        try:
            subprocess.run(["docker","compose","-p",project,"up","--no-build","-d"],cwd=root,check=True,capture_output=True,timeout=60)
            for _ in range(100):
                try:
                    if request("http://127.0.0.1:8010","/ready")[0]==200:break
                except (OSError,URLError):time.sleep(.1)
            else:raise RuntimeError("Compose service not ready")
            actual=json.loads(subprocess.check_output(["docker","inspect",project+"-support-1"],text=True))[0]
            assert actual["HostConfig"]["PortBindings"]["8010/tcp"][0]["HostIp"]=="127.0.0.1"
            assert actual["HostConfig"]["ReadonlyRootfs"] and actual["Config"]["User"]=="10001:10001"
            mark("actual_compose_start_ready_and_host_loopback_8010")
        finally:
            # The UUID project is created above exclusively for this test. Never the user's default compose project.
            subprocess.run(["docker","compose","-p",project,"down","--volumes"],cwd=root,check=True,capture_output=True,timeout=60)
        im=json.loads(docker("image","inspect",image))[0]
        records={"checks":checks,"count":len(checks),"image":image,"image_id":im["Id"],"image_size_bytes":im["Size"],
            "default_time_to_process_health_seconds":startup,"fixture_time_to_health_seconds":fixture_startup,
            "elapsed_seconds":time.perf_counter()-started,"linux":identity,"query_corpus":"invented-lantern-ui-v1",
            "real_model_requests":0,"production_corpus_queries":0,"cleanup":"owned UUID containers and volume only"}
    finally:
        for name in containers:docker("rm","-f",name,check=False)
        for name in volumes:docker("volume","rm",name,check=False)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(records,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(records))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--image",default="support-document-assistant:0.2.0");p.add_argument("--output",type=Path,required=True);a=p.parse_args();run(a.image,a.output)
