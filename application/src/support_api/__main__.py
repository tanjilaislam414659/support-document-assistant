import argparse
from pathlib import Path
import uvicorn
from .app import create_app,Settings

def main():
    p=argparse.ArgumentParser(description="Local source-first support API 0.2.0")
    p.add_argument("--project-root",type=Path,default=Path.cwd())
    p.add_argument("--port",type=int,default=8010)
    p.add_argument("--data-directory",type=Path)
    p.add_argument("--portable",action="store_true",help="Use the packaged read-only corpus (no research checkout needed)")
    p.add_argument("--experimental",action="store_true",help="Enable lazy unverified Qwen3 endpoint")
    args=p.parse_args()
    if args.portable and args.experimental:p.error("Portable distribution does not support generation")
    if not 1<=args.port<=65535:p.error("Invalid port")
    from .bundle import load_bundle
    uvicorn.run(create_app(Settings(args.project_root.resolve(),data_directory=args.data_directory or args.project_root.resolve()/"application/.app-data",experimental=args.experimental,
        distribution="portable-default" if args.portable else "native"),
        corpus_loader=load_bundle),
        host="127.0.0.1",port=args.port,workers=1,access_log=False)
if __name__=="__main__":main()
