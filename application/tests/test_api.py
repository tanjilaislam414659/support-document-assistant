"""Offline API contracts and workflow; no model weights or benchmark questions."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock,patch
import asyncio,json,threading,unittest
from fastapi.testclient import TestClient
from support_api import __version__
from support_api.app import create_app,Settings
from support_api.errors import AppError
from support_api.generation import GenerationManager
from support_api.store import TicketStore
from fixtures import corpus,QUESTION

class FakeEngine:
    def __init__(self):
        self.started=threading.Event();self.release=threading.Event();self.block=False;self.error=None;self.closed=False
    def availability(self):return {"enabled":True,"available":True,"state":"synthetic_test"}
    def answer(self,q,c):
        self.started.set()
        if self.block:self.release.wait(3)
        if self.error:raise self.error
        return {"request_id":"synthetic","application_version":"0.1.0","experimental":True,"unverified":True,
            "model_status":"insufficient_evidence","application_validation_outcome":"validated_insufficient_evidence",
            "raw_output":'{"status":"insufficient_evidence","answer":"Seven.","citations":[]}',
            "validated_response":{"status":"insufficient_evidence","answer":"Seven.","citations":[]},"finish_reason":"eos",
            "supplied_passages":[],"omitted_blocks":[],"identifiers":{"model":"synthetic"},"timings":{},
            "error":None,"limitations":["Unverified; not an approved answer or successful abstention."]}
    def close(self):self.closed=True;self.release.set()

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.path=Path(self.tmp.name);self.engine=FakeEngine()
    def tearDown(self):self.tmp.cleanup()
    def client(self,loader=corpus,experimental=False,engine=None):
        return TestClient(create_app(Settings(Path.cwd(),self.path,experimental),corpus_loader=loader,
            generation_factory=lambda:engine or self.engine))

    def test_default_no_optional_model_factory_and_openapi(self):
        factory=Mock(side_effect=AssertionError("Model must not load"))
        app=create_app(Settings(Path.cwd(),self.path),corpus_loader=corpus,generation_factory=factory)
        with TestClient(app) as c:
            self.assertEqual(c.get("/health").status_code,200)
            self.assertEqual(c.get("/ready").status_code,200)
            self.assertFalse(c.get("/metadata").json()["experimental_generation"]["enabled"])
            self.assertEqual(c.post("/experimental/answer",json={"question":QUESTION}).status_code,403)
            self.assertEqual(c.get("/openapi.json").json()["info"]["version"],__version__)
        factory.assert_not_called()

    def test_search_exact_mapping_and_bounds(self):
        expected=corpus()
        with self.client() as c:
            r=c.post("/search",json={"question":QUESTION,"top_k":1});self.assertEqual(r.status_code,200)
            value=r.json();p=value["results"][0]["passages"][0]
            self.assertEqual(p,expected.passages[p["passage_id"]])
            self.assertTrue(p["source_url"].endswith("#L1-L3"))
            self.assertTrue(value["unverified"])
            for body in ({"question":" "},{"question":QUESTION,"top_k":0},{"question":QUESTION,"top_k":True},
                         {"question":QUESTION,"top_k":11},{"question":"x"*4097},{"question":"bad\u0000"},{"question":QUESTION,"gold":"forbidden"}):
                self.assertEqual(c.post("/search",json=body).status_code,422)
            self.assertEqual(c.post("/tickets/draft",content=b"x"*65537).status_code,413)

    def test_missing_corrupt_corpus_preserves_health_and_user_only_drafts(self):
        def broken():raise ValueError("synthetic corrupt artifact")
        with self.client(loader=broken) as c:
            self.assertEqual(c.get("/health").status_code,200)
            self.assertEqual(c.get("/ready").status_code,503)
            self.assertEqual(c.post("/search",json={"question":QUESTION}).status_code,503)
            r=c.post("/tickets/draft",json={"issue":"User report only"});self.assertEqual(r.status_code,201)
            self.assertEqual(c.get("/tickets/"+r.json()["ticket_id"]).status_code,200)

    def test_missing_weights_cannot_break_search_or_drafts(self):
        def unavailable():raise FileNotFoundError("no weights")
        a=create_app(Settings(Path.cwd(),self.path,True),corpus_loader=corpus,generation_factory=unavailable)
        with TestClient(a) as c:
            self.assertEqual(c.get("/ready").status_code,200)
            self.assertEqual(c.post("/search",json={"question":QUESTION}).status_code,200)
            self.assertEqual(c.post("/experimental/answer",json={"question":QUESTION}).status_code,503)
            self.assertEqual(c.post("/tickets/draft",json={"issue":"Synthetic"}).status_code,201)

    def test_corruption_after_load_changes_readiness(self):
        cfixture=corpus();file=self.path/"artifact";file.write_text("a")
        from support_api.corpus import digest
        cfixture.watched={file:digest(file)}
        with self.client(loader=lambda:cfixture) as c:
            file.write_text("b")
            self.assertEqual(c.get("/ready").status_code,503)
            self.assertEqual(c.post("/search",json={"question":QUESTION}).status_code,503)

    def test_draft_edit_review_stale_and_persistence(self):
        with self.client() as c:
            result=c.post("/search",json={"question":QUESTION}).json()
            p=result["results"][0]["passages"][0]
            body={"issue":"My invented indicator flickers.","environment":{"OS":"explicit fixture"},
                "selected_sources":[{"source_id":p["source_id"],"passage_id":p["passage_id"]}]}
            r=c.post("/tickets/draft",json=body);self.assertEqual(r.status_code,201);t=r.json();tid=t["ticket_id"]
            self.assertEqual(t["documentation"][0]["text"],p["text"])
            self.assertEqual(t["review_state"],"unreviewed")
            base="/tickets/"+tid
            t=c.post(base+"/review",json={"expected_revision":1,"confirm_review":True,"reviewer_label":"User claim"}).json()
            self.assertEqual(t["review_state"],"review_recorded")
            self.assertFalse(t["review_events"][0]["identity_authenticated"])
            r=c.patch(base,json={"expected_revision":1,"human_notes":"Edited by user"});self.assertEqual(r.status_code,200)
            t=r.json();self.assertEqual(t["revision"],2);self.assertEqual(t["review_state"],"unreviewed")
            self.assertFalse(t["review_events"][0]["current_revision"])
            self.assertEqual(c.post(base+"/review",json={"expected_revision":1,"confirm_review":True}).status_code,409)
            self.assertEqual(c.patch(base,json={"expected_revision":1,"issue":"stale"}).status_code,409)
            self.assertEqual(c.patch(base,json={"expected_revision":2,"review_state":"review_recorded"}).status_code,422)
            self.assertEqual(c.patch(base,json={"expected_revision":2,"issue":" "}).status_code,422)
            self.assertEqual(c.post(base+"/review",json={"expected_revision":2,"confirm_review":True}).status_code,200)
            self.assertEqual(c.post(base+"/submit").status_code,404)
            self.assertEqual(c.post(base+"/review",json={"expected_revision":2,"confirm_review":1}).status_code,422)
        with self.client() as c:
            t=c.get(base).json();self.assertEqual(len(t["history"]),2);self.assertEqual(len(t["review_events"]),2)
            self.assertEqual(t["review_state"],"review_recorded")

    def test_corrupt_saved_content_returns_clear_store_error(self):
        with self.client() as c:
            ticket=c.post("/tickets/draft",json={"issue":"Synthetic"}).json()
            import sqlite3
            from contextlib import closing
            with closing(sqlite3.connect(self.path/"tickets.sqlite3")) as db:
                db.execute("UPDATE revisions SET content_json='{}'");db.commit()
            self.assertEqual(c.get("/tickets/"+ticket["ticket_id"]).status_code,503)

    def test_unknown_mismatched_duplicate_sources_and_model_insertion(self):
        p=next(iter(corpus().passages.values()));s={"source_id":p["source_id"],"passage_id":p["passage_id"]}
        with self.client() as c:
            for picks in ([{"source_id":"invented","passage_id":s["passage_id"]}],
                [{"source_id":s["source_id"],"passage_id":"invented"}],[s,s]):
                self.assertEqual(c.post("/tickets/draft",json={"issue":"Synthetic","selected_sources":picks}).status_code,422)
            self.assertEqual(c.post("/tickets/draft",json={"issue":"Synthetic","model_output":"unverified"}).status_code,422)

    def test_experimental_output_remains_unverified_and_never_ticket_content(self):
        with self.client(experimental=True) as c:
            r=c.post("/experimental/answer",json={"question":QUESTION});self.assertEqual(r.status_code,200)
            self.assertTrue(r.json()["unverified"])
            self.assertEqual(r.json()["model_status"],"insufficient_evidence")
            ticket=c.post("/tickets/draft",json={"issue":"User issue only","missing_information":[]}).json()
            self.assertNotIn("Seven.",ticket["rendered_text"])

    def test_busy_health_and_search_remain_responsive(self):
        self.engine.block=True
        with self.client(experimental=True) as c:
            result=[]
            worker=threading.Thread(target=lambda:result.append(c.post("/experimental/answer",json={"question":QUESTION})))
            worker.start();self.assertTrue(self.engine.started.wait(2))
            self.assertEqual(c.post("/experimental/answer",json={"question":QUESTION}).status_code,409)
            self.assertEqual(c.get("/health").status_code,200)
            self.assertEqual(c.post("/search",json={"question":QUESTION}).status_code,200)
            self.engine.release.set();worker.join(3);self.assertEqual(result[0].status_code,200)
        self.assertTrue(self.engine.closed)

    def test_timeout_latches_only_generation_and_cleans_up_on_shutdown(self):
        self.engine.error=AppError(504,"request_timeout","Invented timeout")
        with self.client(experimental=True) as c:
            self.assertEqual(c.post("/experimental/answer",json={"question":QUESTION}).status_code,504)
            self.assertEqual(c.post("/experimental/answer",json={"question":QUESTION}).status_code,503)
            self.assertEqual(c.get("/health").status_code,200)
        self.assertTrue(self.engine.closed)

class CancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnected_client_does_not_free_native_slot(self):
        engine=FakeEngine();engine.block=True
        manager=GenerationManager(True,lambda:engine)
        task=asyncio.create_task(manager.answer(QUESTION,corpus()))
        await asyncio.to_thread(engine.started.wait,2)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        with self.assertRaises(AppError) as busy:await manager.answer(QUESTION,corpus())
        self.assertEqual(busy.exception.status,409)
        await manager.close();self.assertTrue(engine.closed)

if __name__=="__main__":unittest.main()
