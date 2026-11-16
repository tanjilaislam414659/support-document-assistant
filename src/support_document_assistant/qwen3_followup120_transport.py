"""Separately versioned 120-second transport; original 60-second transport unchanged."""
import http.client,json,socket,threading,time
from .gguf_preflight_adapter import LoopbackClient,RequestFailure,ROUTES

class DeadlineClient120(LoopbackClient):
    def request(self,method,path,payload=None,timeout=10):
        if path not in ROUTES or method not in ("GET","POST") or not 0<timeout<=120:
            raise ValueError("Unapproved internal endpoint or deadline")
        if path=="/completion":self.completion_calls+=1
        body=json.dumps(payload,ensure_ascii=True,separators=(",",":")).encode() if payload is not None else None
        start=time.perf_counter();deadline=start+timeout;expired=threading.Event()
        connection=http.client.HTTPConnection(self.host,self.port,timeout=timeout)
        held=[];raw=bytearray();status=None
        def abort():
            expired.set()
            for sock in held:
                try:sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                try:sock.close()
                except OSError:pass
            connection.close()
        timer=threading.Timer(timeout,abort);timer.daemon=True;timer.start()
        def remaining():
            left=deadline-time.perf_counter()
            if left<=0 or expired.is_set():raise TimeoutError("Absolute request deadline exceeded")
            if held and held[0].fileno()>=0:held[0].settimeout(left)
        try:
            connection.connect();held.append(connection.sock);remaining()
            connection.request(method,path,body=body,headers={"Content-Type":"application/json","Connection":"close"})
            remaining();response=connection.getresponse();status=response.status
            while True:
                remaining()
                block=response.read1(65536)
                if not block:break
                raw.extend(block)
                if len(raw)>2_000_000:raise RequestFailure("response_size","Native response exceeds bound")
            remaining();text=raw.decode("utf-8")
            if status!=200:raise RequestFailure("http_error","Native HTTP "+str(status),
                raw_body=text,http_status=status)
            try:value=json.loads(text)
            except (ValueError,RecursionError) as exc:
                raise RequestFailure("invalid_http_json",str(exc),raw_body=text,http_status=status) from exc
            return {"value":value,"raw_http_body":text,"http_status":status,"request_seconds":time.perf_counter()-start}
        except RequestFailure as exc:
            if exc.record["request_seconds"] is None:exc.record["request_seconds"]=time.perf_counter()-start
            raise
        except (TimeoutError,socket.timeout,OSError,http.client.HTTPException,UnicodeError) as exc:
            code="request_timeout" if expired.is_set() or isinstance(exc,(TimeoutError,socket.timeout)) else "transport_error"
            raise RequestFailure(code,str(exc),raw_body=raw.decode("utf-8",errors="replace") or None,
                http_status=status,duration=time.perf_counter()-start) from exc
        finally:
            timer.cancel();connection.close()
            for sock in held:
                try:sock.close()
                except OSError:pass
