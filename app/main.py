"""FastAPI app factory.

The factory keeps global state out of import time so tests can build
fresh, isolated apps with their own settings.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.i18n import DEFAULT_LANG, languages, t
from app.security_headers import SecurityHeadersMiddleware

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR.parent / "static"


def _select_lang(request: Request) -> str:
    """Pick a language: cookie > header > default."""
    cookie = request.cookies.get("lang")
    if cookie in languages():
        return cookie
    accept = request.headers.get("accept-language", "").lower()
    if accept.startswith("bn"):
        return "bn"
    return DEFAULT_LANG


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CampusFound",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings

    # Templates
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    def render(
        request: Request,
        template: str,
        context: Optional[dict] = None,
        status_code: int = 200,
    ) -> HTMLResponse:
        from app.csrf import csrf_token_for
        from app.notifications import service as notif_svc

        ctx = {
            "t": lambda key, **kw: t(key, lang=_select_lang(request), **kw),
            "lang": _select_lang(request),
            "languages": languages(),
            "demo_mode": settings.is_demo,
            "request": request,
            "current_user": None,
            "unread_count": 0,
            "csrf_token": csrf_token_for(request),
            "flash_error": None,
            "flash_ok": None,
        }
        if context:
            ctx.update(context)
        # If a route provided a current_user, compute unread_count for the
        # base.html nav badge. We open a short-lived session to do this so
        # callers do not have to remember to pass it in.
        cu = ctx.get("current_user")
        if cu is not None and getattr(cu, "id", None) is not None:
            from app.db import session_scope

            try:
                with session_scope() as s:
                    ctx["unread_count"] = notif_svc.unread_count(s, cu.id)
            except Exception:
                ctx["unread_count"] = 0
        return templates.TemplateResponse(template, ctx, status_code=status_code)

    app.state.render = render
    app.state.templates = templates

    # Static (vendored HTMX)
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Security headers on every response
    app.add_middleware(SecurityHeadersMiddleware)

    # Trusted hosts (host header validation). In development the default
    # is "*" which disables this; in production deployments should set
    # TRUSTED_HOSTS to the actual host(s).
    from fastapi.middleware.trustedhost import TrustedHostMiddleware

    if settings.trusted_host_list != ["*"]:
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=settings.trusted_host_list
        )

    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    @app.get("/health", include_in_schema=False)
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok"})

    @app.get("/", include_in_schema=False)
    def landing(request: Request) -> HTMLResponse:
        return render(request, "landing.html")

    @app.exception_handler(404)
    async def not_found(request: Request, exc) -> HTMLResponse:
        return render(request, "errors/404.html", status_code=404)

    @app.exception_handler(500)
    async def server_error(request: Request, exc) -> HTMLResponse:
        return render(request, "errors/500.html", status_code=500)

    # Language toggle
    @app.post("/lang/{lang}", include_in_schema=False)
    async def set_lang(lang: str):
        from fastapi import Response

        if lang not in languages():
            return Response(status_code=400)
        resp = Response(status_code=204)
        resp.set_cookie(
            "lang",
            lang,
            httponly=True,
            samesite="lax",
            secure=settings.is_production,
        )
        return resp

    # Routers
    from app.auth.routes import router as auth_router  # noqa: E402
    from app.categories.routes import router as categories_router  # noqa: E402
    from app.claims.routes import router as claims_router  # noqa: E402
    from app.items.routes import router as items_router  # noqa: E402
    from app.lost.routes import router as lost_router  # noqa: E402
    from app.moderation.routes import router as moderation_router  # noqa: E402
    from app.notifications.routes import router as notifications_router  # noqa: E402
    from app.notifications.telegram import router as telegram_router  # noqa: E402
    from app.photos.routes import router as photos_router  # noqa: E402
    from app.places.routes import router as places_router  # noqa: E402

    app.include_router(auth_router)
    app.include_router(items_router)
    app.include_router(claims_router)
    app.include_router(lost_router)
    app.include_router(places_router)
    app.include_router(categories_router)
    app.include_router(moderation_router)
    app.include_router(notifications_router)
    app.include_router(photos_router)
    app.include_router(telegram_router)

    return app


# uvicorn target: ``app.main:app``
app = create_app()
