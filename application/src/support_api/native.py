"""One owned CPU server per explicit request. No benchmark/evaluation imports."""
from pathlib import Path
import json,socket,subprocess,threading,time
from support_document_assistant.gguf_preflight_memory import snapshot
from support_document_assistant.qwen3_followup120_transport import DeadlineClient120
from support_document_assistant.gguf_preflight_adapter import RequestFailure

class NativeRuntime:
    def __init__(self,root,cfg,folder):
        self.root,self.cfg,self.folder=Path(root),cfg,Path(folder)
        self.process=None;self.log=None;self.thread=None;self.trigger=None
        self.samples=[];self.done=threading.Event();self.lock=threading.RLock()
        self.client=DeadlineClient120(cfg["host"],cfg["port"]);self.detail={"closed":False}

    def stop(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                try:self.process.terminate()
                except OSError:pass

    def ensure(self):
        if self.trigger:raise RequestFailure(self.trigger["code"],self.trigger["detail"])
        if self.process is None or self.process.poll() is not None:
            raise RequestFailure("native_stopped","Owned native server is not running")

    def monitor(self):
        while not self.done.is_set():
            if self.process.poll() is not None:return
            try:
                value=snapshot(self.process.pid);self.samples.append({"seconds":time.perf_counter()-self.started,**value})
                if max(value["working_set_bytes"],value["os_peak_working_set_bytes"])>self.cfg["memory_limit_bytes"]:
                    self.trigger={"code":"native_ram_limit","detail":"Owned native server exceeded 8GiB"}
            except (OSError,ValueError,AttributeError) as exc:
                if self.process.poll() is None:self.trigger={"code":"memory_sampling_unavailable","detail":"Native memory monitoring failed"}
            if self.trigger:self.stop();return
            self.done.wait(self.cfg["memory_sample_interval_seconds"])

    def __enter__(self):
        cfg=self.cfg
        try:
            with socket.socket() as probe:probe.bind((cfg["host"],cfg["port"]))
            args=[str(self.root/cfg["template_file"]) if a=="{official_template_file}" else a for a in cfg["runtime_arguments"]]
            command=[str(self.root/cfg["server_executable"]),"--model",str(self.root/cfg["model_path"]),*args]
            import os
            env={k:v for k,v in os.environ.items() if not k.startswith(("LLAMA_ARG_","GGML_"))}
            self.log=(self.folder/"server.log").open("xb");self.started=time.perf_counter()
            self.process=subprocess.Popen(command,cwd=(self.root/cfg["server_executable"]).parent,env=env,
                stdout=self.log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            self.detail.update(pid=self.process.pid,command=command)
            self.thread=threading.Thread(target=self.monitor,name="api-native-memory",daemon=True);self.thread.start()
            deadline=self.started+cfg["startup_timeout_seconds"]
            while time.perf_counter()<deadline:
                self.ensure()
                try:
                    if self.client.request("GET","/health",timeout=min(1,max(.01,deadline-time.perf_counter())))["value"].get("status")=="ok":break
                except RequestFailure:pass
                time.sleep(.05)
            else:raise RequestFailure("startup_timeout","Native startup exceeded 60 seconds")
            self.detail["startup_seconds"]=time.perf_counter()-self.started
            props=self.client.request("GET","/props",timeout=cfg["metadata_timeout_seconds"])["value"]
            if props.get("total_slots")!=1 or props.get("default_generation_settings",{}).get("n_ctx")!=4096:
                raise RequestFailure("runtime_configuration","Unexpected native context/slot settings")
            if props.get("chat_template")!=(self.root/cfg["template_file"]).read_bytes().decode():
                raise RequestFailure("runtime_template","Unexpected native chat template")
            self.ensure();return self
        except BaseException:
            self.close();raise

    def close(self):
        self.done.set()
        if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=2)
        with self.lock:
            if self.detail["closed"]:return
            self.stop()
            if self.process:
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
                self.detail["exit_code"]=self.process.poll()
            if self.log:self.log.close()
            self.detail.update(closed=True,completion_calls=self.client.completion_calls,memory_trigger=self.trigger,
                memory_samples=self.samples,native_peak_bytes=max((s["os_peak_working_set_bytes"] for s in self.samples),default=None))
            with (self.folder/"runtime.json").open("x",encoding="utf-8") as f:json.dump(self.detail,f,indent=2)

    def __exit__(self,*args):self.close()
