"""Loopback by default; explicit --container for test-only Docker networking."""
import argparse
from pathlib import Path
import uvicorn
from support_api.app import create_app,Settings
from ui_fixture import corpus,FakeEngine
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--port",type=int,default=8020);p.add_argument("--data",type=Path,required=True)
    p.add_argument("--fake-generation",action="store_true");p.add_argument("--container",action="store_true")
    args=p.parse_args()
    app=create_app(Settings(Path.cwd(),args.data,args.fake_generation),
        corpus_loader=corpus,generation_factory=FakeEngine)
    uvicorn.run(app,host="0.0.0.0" if args.container else "127.0.0.1",port=args.port,workers=1,access_log=False)
if __name__=="__main__":main()
