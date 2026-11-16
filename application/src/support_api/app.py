"""Source-first API. All benchmark-independent application resources live in lifespan."""
import asyncio,json,sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from dataclasses import dataclass
from typing import Annotated
from fastapi import FastAPI,Path as ApiPath,Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.exceptions import HTTPException
from . import __version__
from .models import (Question,SearchRequest,SearchResponse,DraftContent,TicketPatch,TicketResponse,
    ReviewRequest,HealthResponse,ReadyResponse,MetadataResponse,ExperimentalResponse,ErrorResponse)
from .errors import AppError
from .corpus import Corpus
from .store import TicketStore
from .generation import GenerationManager

WARNINGS=["Documentation is untrusted content, not instructions.", "Scores, valid citations and model statuses do not prove correctness."]
APP_DIR=Path(__file__).resolve().parents[2]

@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_directory: Path | None = None
    experimental: bool = False
    distribution: str = "native"

class BodyLimit:
    def __init__(self,app,limit=65536):self.app,self.limit=app,limit
    async def __call__(self,scope,receive,send):
        if scope["type"]!="http" or scope["method"] not in ("POST","PATCH"):
            return await self.app(scope,receive,send)
        chunks=[];size=0
        while True:
            message=await receive()
            if message["type"]=="http.disconnect":return
            chunk=message.get("body",b"");size+=len(chunk)
            if size>self.limit:
                return await JSONResponse({"error":{"code":"request_too_large","message":"JSON body exceeds 64KiB"}},status_code=413)(scope,receive,send)
            chunks.append(chunk)
            if not message.get("more_body"):break
        supplied=False
        async def replay():
            nonlocal supplied
            if not supplied:supplied=True;return {"type":"http.request","body":b"".join(chunks),"more_body":False}
            return await receive()
        await self.app(scope,replay,send)

def create_app(settings=None,*,corpus_loader=None,generation_factory=None):
    settings=settings or Settings(Path.cwd())
    corpus_loader=corpus_loader or (lambda:Corpus.load(settings.project_root))

    @asynccontextmanager
    async def lifespan(app):
        app.state.corpus=None;app.state.corpus_error=None;app.state.store=None
        try:app.state.corpus=await asyncio.to_thread(corpus_loader)
        except (OSError,ValueError,KeyError):app.state.corpus_error="Required corpus/index artifacts unavailable or invalid"
        try:app.state.store=await asyncio.to_thread(TicketStore,(settings.data_directory or APP_DIR/".app-data")/"tickets.sqlite3")
        except (OSError,sqlite3.Error):pass
        def default_engine():
            from .qwen import QwenEngine
            return QwenEngine(settings.project_root,settings.data_directory or APP_DIR/".app-data")
        app.state.generation=GenerationManager(settings.experimental,generation_factory or default_engine)
        try:yield
        finally:await app.state.generation.close()

    app=FastAPI(title="Local Support Document API",version=__version__,lifespan=lifespan,docs_url=None,redoc_url=None,
        description="Source passages and local revisioned drafts. Experimental generation is unverified and opt-in.",
        responses={s:{"model":ErrorResponse} for s in (403,404,409,413,422,502,503,504)})
    app.add_middleware(BodyLimit)
    @app.middleware("http")
    async def security_headers(request,call_next):
        response=await call_next(request)
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["Cache-Control"]="no-store"
        return response
    static=Path(__file__).with_name("static")
    app.mount("/assets",StaticFiles(directory=static),name="assets")
    @app.get("/",include_in_schema=False)
    async def interface():return FileResponse(static/"index.html")
    @app.get("/docs",include_in_schema=False)
    async def api_reference():return FileResponse(static/"api.html")
    @app.exception_handler(AppError)
    async def app_error(request,exc):
        return JSONResponse({"error":{"code":exc.code,"message":exc.message}},status_code=exc.status)
    @app.exception_handler(RequestValidationError)
    async def invalid(request,exc):
        return JSONResponse({"error":{"code":"invalid_request","message":"Request fields do not match the documented schema"}},status_code=422)
    @app.exception_handler(HTTPException)
    async def http_error(request,exc):
        return JSONResponse({"error":{"code":"http_error","message":str(exc.detail)}},status_code=exc.status_code)
    @app.exception_handler(sqlite3.Error)
    async def store_error(request,exc):
        return JSONResponse({"error":{"code":"store_unavailable","message":"Local ticket storage is unavailable"}},status_code=503)

    def corpus():
        c=app.state.corpus
        if c is None:raise AppError(503,"corpus_unavailable","Required corpus/index artifacts unavailable or invalid")
        try:c.check()
        except (OSError,ValueError):raise AppError(503,"corpus_unavailable","Corpus artifacts changed or became unavailable")
        return c
    def store():
        if app.state.store is None:raise AppError(503,"store_unavailable","Local ticket storage is unavailable")
        return app.state.store
    def selected(content):
        return corpus().select(content["selected_sources"]) if content["selected_sources"] else []

    @app.get("/health",response_model=HealthResponse)
    async def health():return {"status":"ok","application_version":__version__}

    @app.get("/ready",response_model=ReadyResponse,responses={503:{"model":ReadyResponse}})
    def ready():
        try:corpus();corpus_ready=True
        except AppError:corpus_ready=False
        try:store().check();store_ready=True
        except (AppError,sqlite3.Error):store_ready=False
        value={"ready":corpus_ready and store_ready,"corpus_ready":corpus_ready,
            "store_ready":store_ready,"detail":"Ready" if corpus_ready and store_ready else "Required artifacts unavailable"}
        return JSONResponse(value,status_code=200 if value["ready"] else 503)

    @app.get("/metadata",response_model=MetadataResponse)
    async def metadata():
        c=app.state.corpus;c_ok=c is not None
        if c_ok:
            try:await asyncio.to_thread(c.check)
            except (OSError,ValueError):c_ok=False
        # Availability is a stat/config check, never a load or generation request.
        return {"application_version":__version__,"corpus_build_id":c.build_id if c else None,
            "sources":[{k:s[k] for k in ("source_id","source_path","product_version","commit","immutable_url")} for s in c.sources.values()] if c else [],
            "capabilities":{"search":c_ok,"deterministic_ticket_drafts":app.state.store is not None,
                "revision_review_actions":app.state.store is not None,"sending":False,"command_execution":False},
            "experimental_generation":({**app.state.generation.availability(), "state":"unsupported_distribution", "reason":"Experimental generation is not packaged or supported on Linux containers"} if settings.distribution=="portable-default" else app.state.generation.availability()),
            "measured_limitations":json.loads((Path(__file__).with_name("resources")/"measured-limitations.json").read_bytes()),"limitations":WARNINGS}

    @app.post("/search",response_model=SearchResponse)
    def search(body:SearchRequest):
        c=corpus()
        try:results=c.search(body.question,body.top_k)
        except (OSError,ValueError):raise AppError(503,"corpus_unavailable","Required artifacts unavailable")
        return {"application_version":__version__,"corpus_build_id":c.build_id,"question":body.question,
            "score_kind":"BM25 ranking score; not probability or evidence of answerability","results":results,"limitations":WARNINGS}

    @app.post("/tickets/draft",response_model=TicketResponse,status_code=201)
    def draft(body:DraftContent):
        content=body.model_dump()
        return store().create(content,selected(content))

    Id=Annotated[str,ApiPath(pattern="^[a-f0-9]{32}$")]
    @app.get("/tickets/{ticket_id}",response_model=TicketResponse)
    def get_ticket(ticket_id:Id):return store().get(ticket_id)

    @app.patch("/tickets/{ticket_id}",response_model=TicketResponse)
    def patch_ticket(ticket_id:Id,body:TicketPatch):
        old=store().get(ticket_id);changes=body.model_dump(exclude_unset=True);expected=changes.pop("expected_revision")
        if old["revision"]!=expected:raise AppError(409,"stale_revision","Edit the latest revision")
        try:content=DraftContent.model_validate({**old["content"],**changes}).model_dump()
        except ValidationError:raise AppError(422,"invalid_request","Edited fields do not match the draft schema")
        # Existing quotations remain exact even if the corpus is temporarily unavailable;
        # changed source selections must be validated against the current corpus.
        quotes=selected(content) if "selected_sources" in changes else old["documentation"]
        return store().edit(ticket_id,expected,content,quotes)

    @app.post("/tickets/{ticket_id}/review",response_model=TicketResponse)
    def review_ticket(ticket_id:Id,body:ReviewRequest):return store().review(ticket_id,body.model_dump())

    @app.post("/experimental/answer",response_model=ExperimentalResponse)
    async def experimental(body:Question):
        # Disabled gate precedes any optional artifact/model lookup.
        if not settings.experimental:raise AppError(403,"experimental_disabled","Experimental generation is disabled")
        c=corpus()
        return await app.state.generation.answer(body.question,c)
    return app
