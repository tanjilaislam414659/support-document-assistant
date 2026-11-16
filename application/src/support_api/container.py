"""Default Linux entrypoint only. No experimental generator is distributed."""
import os
from pathlib import Path
import uvicorn
from .app import Settings,create_app
from .bundle import load_bundle

def main():
    app=create_app(Settings(Path("/app"),Path(os.environ.get("SUPPORT_DATA_DIRECTORY","/var/lib/support")),
        distribution="portable-default"),
        corpus_loader=lambda:load_bundle(os.environ.get("SUPPORT_BUNDLE_DIRECTORY")))
    uvicorn.run(app,host="0.0.0.0",port=8010,workers=1,access_log=False)
if __name__=="__main__":main()
