"""Actual Chrome screenshots using clean invented data. No model or benchmark calls."""
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse,hashlib,json,socket,subprocess,sys,time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
TESTS=Path(__file__).resolve().parents[1]/"tests"
sys.path.insert(0,str(TESTS))
from demo_fixture import QUESTION
def main(output,channel):
    output=output.resolve()
    if output.exists():raise FileExistsError("Choose a new output directory; existing screenshots are preserved")
    output.mkdir(parents=True)
    with TemporaryDirectory() as tmp:
        with socket.socket() as s:s.bind(("127.0.0.1",0));port=s.getsockname()[1]
        process=subprocess.Popen([sys.executable,str(TESTS/"demo_server.py"),"--port",str(port),"--data",tmp],
            stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for _ in range(100):
                try:
                    if urlopen(f"http://127.0.0.1:{port}/ready",timeout=.3).status==200:break
                except OSError:time.sleep(.1)
            else:raise RuntimeError("Demo server unavailable")
            with sync_playwright() as p:
                b=p.chromium.launch(channel=channel,headless=True);page=b.new_page(viewport={"width":1440,"height":1050})
                page.goto(f"http://127.0.0.1:{port}");expect(page.locator("#connection")).to_contain_text("ready")
                expect(page.locator("#generate-button")).to_be_hidden()
                page.locator("#question").fill(QUESTION);page.locator("#search-button").click()
                expect(page.locator("#results .passage")).to_have_count(1);page.locator("[data-passage]").check()
                page.locator("#title").fill("Synthetic demo · Orbit indicator report")
                page.locator("#issue").fill("In this fictional demonstration, the Orbit dashboard shows an amber indicator.")
                page.locator("#environment").fill("OS: Synthetic lab Windows 11\nPython: 3.13.0 demo\nDevice: Fictional Orbit")
                page.locator("#missing").fill("Exact fictional status message\nDemonstration device version")
                page.locator("#human-notes").fill("Synthetic demonstration only. No real support request.")
                page.locator("#save-button").click();expect(page.locator("#ticket-state")).to_contain_text("revision 1")
                page.locator("#human-notes").fill("Synthetic demonstration only. Quoted source checked for the draft workflow.")
                page.locator("#save-button").click();expect(page.locator("#ticket-state")).to_contain_text("revision 2")
                page.locator("#reviewer").fill("Synthetic demo reviewer")
                page.locator("#review-note").fill("Automated demonstration action; not a human answer-quality review.")
                page.locator("#confirm-review").check();page.locator("#review-button").click()
                expect(page.locator("#review-badge")).to_have_text("Review recorded")
                page.evaluate("document.activeElement.blur(); window.scrollTo(0,0)")
                page.screenshot(path=str(output/"desktop-workflow.png"))
                page.locator("#saved-details").evaluate("(e)=>e.open=true")
                # Panel capture includes the genuine synthetic revision/review state.
                page.locator(".draft-panel").screenshot(path=str(output/"reviewed-revision.png"))
                page.locator("#saved-details").evaluate("(e)=>e.open=false")
                page.set_viewport_size({"width":390,"height":844});page.evaluate("window.scrollTo(0,0)")
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(output/"mobile-workflow.png"),full_page=True)
                page.set_viewport_size({"width":1440,"height":1050});page.locator("#limitations-tab").click()
                page.evaluate("window.scrollTo(0,0)");page.screenshot(path=str(output/"evaluation-limitations.png"))
                version=b.version;b.close()
            data={"kind":"Actual screenshots of an explicitly labelled synthetic demonstration",
                "browser":version,"viewports":{"desktop":[1440,1050],"mobile":[390,844]},
                "model_output":False,"real_inference_requests":0,"benchmark_questions":0,
                "fixture":"synthetic-orbit-demo-v1","review_event":"automated synthetic workflow action, not research human review",
                "files":{f.name:{"bytes":f.stat().st_size,"sha256":hashlib.sha256(f.read_bytes()).hexdigest()} for f in output.glob("*.png")}}
            (output/"capture.json").write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8",newline="\n")
            print(json.dumps(data))
        finally:
            process.terminate()
            try:process.wait(5)
            except subprocess.TimeoutExpired:process.kill();process.wait(5)
            process.stderr.close()
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);p.add_argument("--channel",default="chrome");a=p.parse_args();main(a.output,a.channel)
