from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings
from .repositories import build_repository
from .repositories.base import Repository
from .routes import router


def create_app(settings: Settings | None = None, repo: Repository | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.repo = repo or build_repository(settings)
        yield

    app = FastAPI(title="LogAD API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_list, allow_methods=["GET"], allow_headers=["*"],
    )
    app.include_router(router)

    def problem(status: int, title: str, detail: str | None = None) -> JSONResponse:
        return JSONResponse({"status": status, "title": title, "detail": detail}, status_code=status)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        titles = {404: "Không tìm thấy", 405: "Phương thức không được hỗ trợ"}
        return problem(exc.status_code, titles.get(exc.status_code, "Lỗi"), str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        return problem(422, "Tham số không hợp lệ", detail)

    return app


app = create_app()
