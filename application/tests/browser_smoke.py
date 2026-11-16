"""Real Chromium workflow with invented evidence only; no model calls."""
import argparse,json,os,socket,subprocess,sys,time
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen
from playwright.sync_api import sync_playwright,expect
from ui_fixture import QUESTION,LITERAL

def run(output,channel=None):
    output.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory() as tmp:
        with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
        server=subprocess.Popen([sys.executable,str(Path(__file__).with_name("fixture_server.py")),"--port",str(port),"--data",tmp,"--fake-generation"],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        checks=[];errors=[]
        def record(name):checks.append(name)
        base=f"http://127.0.0.1:{port}"
        try:
            for _ in range(100):
                if server.poll() is not None:raise RuntimeError(server.stderr.read().decode())
                try:
                    with urlopen(base+"/ready",timeout=.3) as r:
                        if r.status==200:break
                except OSError:time.sleep(.1)
            else:raise RuntimeError("Fixture server did not become ready")
            with sync_playwright() as p:
                browser=p.chromium.launch(channel=channel,headless=True)
                context=browser.new_context(viewport={"width":1440,"height":1000},permissions=["clipboard-read","clipboard-write"])
                page=context.new_page();page.on("pageerror",lambda e:errors.append(str(e)))
                page.goto(base);expect(page.locator("#connection")).to_contain_text("ready")
                page.keyboard.press("Tab");expect(page.locator(".skip")).to_be_focused();page.keyboard.press("Enter");expect(page.locator("#main")).to_be_focused();record("keyboard_skip_link")
                page.locator("#question").fill(QUESTION)
                page.locator("#question").focus();page.keyboard.press("Tab");expect(page.locator("#top-k")).to_be_focused();page.keyboard.press("Tab");expect(page.locator("#search-button")).to_be_focused();page.keyboard.press("Enter")
                expect(page.locator("#results .passage")).to_have_count(1)
                expect(page.locator("#results pre")).to_contain_text(LITERAL)
                assert page.locator("#results img").count()==0 and page.evaluate("window.fixtureExecuted") is None;record("search_literal_document_text_and_keyboard")
                page.locator("[data-passage]").focus();page.keyboard.press("Space");expect(page.locator("#selected-count")).to_have_text("1 passage selected")
                page.locator("#title").fill("Fictional Lantern indicator")
                page.locator("#issue").fill("My test lamp displays "+LITERAL)
                page.locator("#environment").fill("OS: Invented lab OS\nDevice: Lantern fixture")
                page.locator("#human-notes").fill("Human note only; do not run any document command.")
                page.locator("#save-button").click();expect(page.locator("#ticket-state")).to_contain_text("revision 1")
                page.locator("#human-notes").fill("Human revised note "+LITERAL);page.locator("#save-button").click();expect(page.locator("#ticket-state")).to_contain_text("revision 2")
                page.locator("#confirm-review").check();page.locator("#review-button").click();expect(page.locator("#review-badge")).to_have_text("Review recorded")
                page.locator("#saved-details").evaluate("(n)=>n.open=true")
                expect(page.locator("#saved-text")).to_contain_text(LITERAL);assert page.locator("#saved-text img").count()==0;record("select_create_edit_review_and_safe_ticket_text")
                page.locator("#copy-button").click();expect(page.locator("#notice")).to_contain_text("Copied saved draft")
                copied=page.evaluate("navigator.clipboard.readText()");assert "Revision: 2" in copied and "Review state: review_recorded" in copied;record("copy_includes_saved_review_state")
                page.locator("#saved-details").evaluate("(n)=>n.open=false")
                page.screenshot(path=str(output/"desktop.png"),full_page=True)
                page.locator("#human-notes").fill("Edited after review")
                expect(page.locator("#review-button")).to_be_disabled();expect(page.locator("#copy-button")).to_be_disabled()
                page.locator("#save-button").click();expect(page.locator("#review-badge")).to_have_text("Unreviewed")
                expect(page.locator("#history")).to_contain_text("Review of revision 2 · superseded");record("edit_invalidates_review_and_keeps_history")
                # Genuine API conflict: another client edits the same revision.
                tid=page.locator("#ticket-id").input_value()
                patch=context.request.patch(base+"/tickets/"+tid,data={"expected_revision":3,"human_notes":"Another local tab edited this."});assert patch.status==200
                page.locator("#human-notes").fill("Keep these local unsaved edits")
                page.locator("#save-button").click();expect(page.locator("#notice")).to_contain_text("changed elsewhere")
                expect(page.locator("#human-notes")).to_have_value("Keep these local unsaved edits")
                page.locator("#reload-ticket").click();expect(page.locator("#ticket-state")).to_contain_text("revision 4");record("real_stale_revision_recovery")
                page.locator("#generate-button").click();expect(page.locator("#model-output")).to_contain_text("UNVERIFIED EXPERIMENTAL OUTPUT")
                expect(page.locator("#model-output")).to_contain_text("insufficient_evidence")
                assert page.locator("#model-output img").count()==0
                assert LITERAL not in page.locator("#human-notes").input_value();record("fake_generation_unverified_separate_and_literal")
                # Hold one request to observe a real pending UI, then fulfill synthetic empty/error responses.
                held=[]
                page.route("**/search",lambda route:held.append(route))
                page.locator("#search-button").click()
                expect(page.locator("#search-button")).to_have_text("Searching…");expect(page.locator("#search-button")).to_be_disabled()
                page.wait_for_function("document.querySelector('#results').getAttribute('aria-busy') === 'true'")
                page.wait_for_timeout(50)
                assert held;held.pop().fulfill(status=200,json={"results":[]})
                expect(page.locator("#results")).to_contain_text("No matching passages");page.unroute("**/search");record("loading_and_empty_states")
                page.route("**/search",lambda route:route.fulfill(status=503,json={"error":{"code":"corpus_unavailable","message":"Synthetic corpus unavailable"}}))
                page.locator("#search-button").click();expect(page.locator("#notice")).to_contain_text("Synthetic corpus unavailable")
                expect(page.locator("#results")).to_contain_text("Search unavailable");page.unroute("**/search");record("search_error_state")
                # Narrow viewport: no horizontal overflow and controls remain usable.
                page.set_viewport_size({"width":390,"height":844})
                page.locator("#question").fill(QUESTION);page.locator("#search-button").click();expect(page.locator("#results .passage")).to_have_count(1)
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                page.screenshot(path=str(output/"mobile.png"),full_page=True);record("mobile_390px_no_horizontal_overflow")
                page.locator("#limitations-tab").click();expect(page.locator("#limitations-view")).to_be_visible();expect(page.locator("#limitations-view")).to_contain_text("3/6")
                expect(page.locator("#limitations-view")).to_contain_text("strict source-span");record("saved_limitations_view")
                special={"title":"API\nTitle","issue":"Invented multiline environment record","environment":{"detail:key":"one\ntwo"}}
                created=context.request.post(base+"/tickets/draft",data=special).json()
                page.locator("#workspace-tab").click();page.locator("#ticket-id").fill(created["ticket_id"]);page.locator("#load-button").click()
                expect(page.locator("#ticket-state")).to_contain_text(created["ticket_id"])
                page.locator("#human-notes").fill("Edit only this note");page.locator("#save-button").click()
                expect(page.locator("#ticket-state")).to_contain_text("revision 2")
                preserved=context.request.get(base+"/tickets/"+created["ticket_id"]).json()["content"]
                assert preserved["title"]==special["title"] and preserved["environment"]==special["environment"]
                record("partial_ui_edit_preserves_unedited_api_values")
                m=context.request.get(base+"/metadata").json();m["experimental_generation"]={"enabled":False,"available":False,"state":"disabled","reason":"Synthetic default-mode metadata"}
                page.route("**/metadata",lambda r:r.fulfill(status=200,json=m));page.reload()
                expect(page.locator("#connection")).to_contain_text("ready");expect(page.locator("#generate-button")).to_be_hidden()
                record("default_metadata_hides_generation_action");page.unroute("**/metadata")
                page.route("**/ready",lambda r:r.fulfill(status=503,json={"ready":False,"corpus_ready":False,"store_ready":True}))
                page.route("**/metadata",lambda r:r.abort())
                page.reload();expect(page.locator("#notice")).to_contain_text("unavailable");expect(page.locator("#generate-button")).to_be_hidden();expect(page.locator("#retry")).to_be_visible();record("unavailable_metadata_hides_generation")
                assert not errors,errors
                report={"browser":browser.version,"channel":channel or "bundled Chromium","checks":checks,"count":len(checks),"page_errors":errors,"real_model_requests":0,"corpus":"invented-lantern-ui-v1","viewport_desktop":[1440,1000],"viewport_mobile":[390,844]}
                browser.close()
            (output/"browser.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
            print(json.dumps(report))
        finally:
            server.terminate()
            try:server.wait(5)
            except subprocess.TimeoutExpired:server.kill();server.wait(5)
            if server.stderr:server.stderr.close()
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--output",type=Path,required=True);p.add_argument("--channel",default=os.environ.get("SUPPORT_BROWSER_CHANNEL"));a=p.parse_args();run(a.output,a.channel)
