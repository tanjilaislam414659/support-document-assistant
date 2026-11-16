"""Lazy single-flight manager. Client cancellation does not release the active slot."""
import asyncio
from .errors import AppError

class GenerationManager:
    def __init__(self,enabled,factory):
        self.enabled,self.factory=enabled,factory
        self.engine=None;self.active=None;self.closing=False;self.failed=False
        self.initialization_error=None
        if enabled:
            try:self.engine=factory()  # configuration/stat checks only; never weights/loading
            except (OSError,ValueError) as exc:self.initialization_error=type(exc).__name__

    def availability(self):
        if not self.enabled:return {"enabled":False,"available":False,"state":"disabled","reason":"Explicit --experimental opt-in required"}
        if self.closing or self.failed:return {"enabled":True,"available":False,"state":"unavailable_until_restart","reason":"Shutdown or prior native failure"}
        if self.active and not self.active.done():return {"enabled":True,"available":False,"state":"busy","reason":"One generation already active"}
        if self.engine is None:return {"enabled":True,"available":False,"state":"artifacts_unavailable","reason":self.initialization_error}
        return self.engine.availability()

    def _done(self,task):
        # Retrieve exceptions even when the requesting client disconnected.
        if not task.cancelled():
            exc=task.exception()
            if exc is not None:self.failed=True
        if self.active is task:self.active=None

    async def answer(self,question,corpus):
        if not self.enabled:raise AppError(403,"experimental_disabled","Experimental generation is disabled")
        if self.active and not self.active.done():raise AppError(409,"generation_busy","One generation is already active; no queue")
        state=self.availability()
        if not state["available"]:raise AppError(503,"generation_unavailable",state["reason"] or "Generation unavailable")
        self.active=asyncio.create_task(asyncio.to_thread(self.engine.answer,question,corpus))
        task=self.active;task.add_done_callback(self._done)
        return await asyncio.shield(task)

    async def close(self):
        self.closing=True
        if self.engine is not None:self.engine.close()
        if self.active is not None:
            try:await asyncio.wait_for(asyncio.shield(self.active),timeout=210)
            except (AppError,asyncio.TimeoutError):pass
