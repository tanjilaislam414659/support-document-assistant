"""Default-distribution checks; synthetic API requests only, no model or benchmark access."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib,json,shutil,unittest
from fastapi.testclient import TestClient
from support_api.app import create_app,Settings
from support_api.bundle import load_bundle,RESOURCES
from ui_fixture import corpus,LITERAL,QUESTION

class PortableTests(unittest.TestCase):
    def test_bundle_integrity_mappings_and_no_audit_serving(self):
        c=load_bundle();c.check()
        self.assertEqual(len(c.chunks),40);self.assertEqual(len(c.sources),4);self.assertEqual(len(c.passages),182)
        for p in c.passages.values():
            raw=c.sources[p["source_id"]]["text"];a,b=p["source_char_range"]
            self.assertEqual(raw[a:b],p["text"])
            self.assertEqual(hashlib.sha256(p["text"].encode()).hexdigest(),p["text_sha256"])
            if p["source_id"]=="py-installing":
                self.assertTrue(p["source_lines"][1]<58 or p["source_lines"][0]>64)
        self.assertFalse(any("whatsnew" in p["source_path"] for p in c.passages.values()))

    def test_missing_corrupt_and_changed_bundle(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/"corpus";shutil.copytree(RESOURCES/"corpus",root)
            c=load_bundle(root)
            path=root/"data/raw/py-venv.rst";path.write_bytes(path.read_bytes()+b"corrupt")
            with self.assertRaises(ValueError):c.check()
            with self.assertRaises(ValueError):load_bundle(root)
            path.unlink()
            with self.assertRaises(OSError):load_bundle(root)

    def test_manifest_anchor_rejects_rewritten_identity(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)/"corpus";shutil.copytree(RESOURCES/"corpus",root)
            (root/"bundle.json").write_bytes(b"{}")
            with self.assertRaises(ValueError):load_bundle(root)

    def test_copied_runtime_source_hashes(self):
        for name,record in json.loads((RESOURCES/"frozen-core.json").read_bytes()).items():
            path=RESOURCES.parent/"_frozen_core"/name
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),record["sha256"])

    def test_static_local_assets_csp_literal_contract_and_container_metadata(self):
        with TemporaryDirectory() as tmp:
            app=create_app(Settings(Path.cwd(),Path(tmp),distribution="portable-default"),corpus_loader=corpus)
            with TestClient(app) as c:
                home=c.get("/");self.assertEqual(home.status_code,200)
                self.assertIn("script-src 'self'",home.headers["content-security-policy"])
                self.assertIn('/assets/app.js',home.text)
                for url in ("/assets/style.css","/assets/app.js","/assets/icon.svg","/docs"):
                    self.assertEqual(c.get(url).status_code,200)
                js=c.get("/assets/app.js").text
                for forbidden in ("innerHTML","outerHTML","insertAdjacentHTML","eval("):
                    self.assertNotIn(forbidden,js)
                self.assertIn(LITERAL,c.post("/search",json={"question":QUESTION}).json()["results"][0]["text"])
                meta=c.get("/metadata").json()["experimental_generation"]
                self.assertFalse(meta["enabled"]);self.assertEqual(meta["state"],"unsupported_distribution")
                self.assertEqual(c.post("/experimental/answer",json={"question":QUESTION}).status_code,403)
                self.assertEqual(c.get("/assets/../app.py").status_code,404)

    def test_missing_default_artifact_liveness_and_readiness(self):
        def bad():raise FileNotFoundError("synthetic")
        with TemporaryDirectory() as tmp:
            with TestClient(create_app(Settings(Path.cwd(),Path(tmp)),corpus_loader=bad)) as c:
                self.assertEqual(c.get("/health").status_code,200);self.assertEqual(c.get("/ready").status_code,503)
if __name__=="__main__":unittest.main()
