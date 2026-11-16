"""Owned synthetic server for screenshots. No experimental engine or model."""
from pathlib import Path
import argparse
import uvicorn
from fastapi.responses import HTMLResponse
from support_api.app import Settings,create_app
from demo_fixture import corpus
def main():
    p=argparse.ArgumentParser();p.add_argument("--port",type=int,required=True);p.add_argument("--data",type=Path,required=True);a=p.parse_args()
    app=create_app(Settings(Path.cwd(),a.data),corpus_loader=corpus)
    app.router.routes=[r for r in app.router.routes if getattr(r,"path",None)!="/"]
    from support_api import app as module
    text=(Path(module.__file__).with_name("static")/"index.html").read_text(encoding="utf-8")
    text=text.replace('<body>','<body><aside class="notice" role="note">SYNTHETIC DEMONSTRATION · Fictional Orbit lab · No real ticket data or model output</aside>')
    @app.get("/",include_in_schema=False)
    def demo():return HTMLResponse(text)
    uvicorn.run(app,host="127.0.0.1",port=a.port,workers=1,access_log=False)
if __name__=="__main__":main()
