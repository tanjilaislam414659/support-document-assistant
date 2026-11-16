
"""Windows memory counters for the single spawned portable server, not Python."""
import ctypes,threading,time
from ctypes import wintypes

def snapshot(pid):
    class Counters(ctypes.Structure):
        _fields_=[("cb",wintypes.DWORD),("PageFaultCount",wintypes.DWORD)]+[
            (name,ctypes.c_size_t) for name in ("PeakWorkingSetSize","WorkingSetSize",
            "QuotaPeakPagedPoolUsage","QuotaPagedPoolUsage","QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage","PagefileUsage","PeakPagefileUsage")]
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000|0x10,False,pid)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    try:
        api=ctypes.WinDLL("psapi",use_last_error=True).GetProcessMemoryInfo
        api.argtypes=[wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        api.restype=wintypes.BOOL
        value=Counters();value.cb=ctypes.sizeof(value)
        if not api(handle,ctypes.byref(value),value.cb):raise ctypes.WinError(ctypes.get_last_error())
        return {"working_set_bytes":value.WorkingSetSize,"os_peak_working_set_bytes":value.PeakWorkingSetSize,
                "pagefile_usage_bytes":value.PagefileUsage,"page_fault_count":value.PageFaultCount}
    finally:kernel.CloseHandle(handle)

class ServerMemory:
    def __init__(self,pid,interval=0.1):
        self.pid,self.interval=pid,interval
        self.samples=[];self.errors=[];self.stop_event=threading.Event();self.thread=None
    def sample(self):
        try:self.samples.append({"offset_seconds":time.perf_counter()-self.start_time,**snapshot(self.pid)})
        except (OSError,AttributeError) as exc:self.errors.append(str(exc))
    def start(self):
        self.start_time=time.perf_counter();self.sample()
        def loop():
            while not self.stop_event.wait(self.interval):self.sample()
        self.thread=threading.Thread(target=loop,name="portable-server-memory",daemon=True);self.thread.start()
    def stop(self):
        self.stop_event.set()
        if self.thread:self.thread.join()
        self.sample()
        return {"pid":self.pid,"scope":"one spawned llama-server process; excludes Python controller",
            "interval_seconds":self.interval,"samples":self.samples,"errors":sorted(set(self.errors)),
            "os_peak_working_set_bytes":max((s["os_peak_working_set_bytes"] for s in self.samples),default=None)}
