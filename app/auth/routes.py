"""Authentication routes: sign-up, login, logout, recovery."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlmodel import Session

from app.auth import service as auth_svc
from app.config import get_settings
from app.csrf import csrf_token_for, get_or_create_session_id
from app.db import get_session
from app.deps import SESSION_COOKIE, check_csrf, get_current_user_optional
from app.i18n import t
from app.models.user import AccountStatus, User
from app.security import sign_session

router = APIRouter()


def _lang(request: Request) -> str:
    cookie = request.cookies.get("lang")
    return cookie if cookie in ("en", "bn") else "en"


def _common_ctx(request: Request) -> dict:
    return {
        "t": lambda key, **kw: t(key, lang=_lang(request), **kw),
        "lang": _lang(request),
        "csrf_token": csrf_token_for(request),
        "request": request,
    }


def _is_htmx(request: Request) -> bool:
    return request.headers.get("hx-request", "").lower() == "true"


def _set_session_cookie(response: Response, user: User) -> None:
    token = sign_session({"uid": user.id})
    is_prod = get_settings().is_production
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=is_prod,
        max_age=60 * 60 * 24 * 7,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


@router.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    return request.app.state.templates.TemplateResponse(
        "auth/signup.html", _common_ctx(request), status_code=200
    )


@router.post("/signup")
async def signup_submit(
    request: Request,
    full_name: str = Form(...),
    department: str = Form(...),
    batch_or_session: str = Form(...),
    mobile: str = Form(...),
    password: str = Form(...),
    is_member_confirmed: str = Form(""),
    is_adult_confirmed: str = Form(""),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    try:
        user = auth_svc.signup(
            session,
            full_name=full_name,
            department=department,
            batch_or_session=batch_or_session,
            mobile=mobile,
            password=password,
            is_member_confirmed=bool(is_member_confirmed),
            is_adult_confirmed=bool(is_adult_confirmed),
        )
    except ValueError as e:
        ctx = _common_ctx(request)
        ctx["error"] = str(e)
        ctx["form"] = {
            "full_name": full_name, "department": department,
            "batch_or_session": batch_or_session, "mobile": mobile,
        }
        return request.app.state.templates.TemplateResponse(
            "auth/signup.html", ctx, status_code=400
        )

    # Don't set a session cookie; user must wait for approval.
    return request.app.state.templates.TemplateResponse(
        "auth/pending.html",
        {**_common_ctx(request), "name": user.full_name},
        status_code=200,
    )


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return request.app.state.templates.TemplateResponse(
        "auth/login.html", _common_ctx(request), status_code=200
    )


@router.post("/login")
async def login_submit(
    request: Request,
    identifier: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
):
    await check_csrf(request)
    user, err = auth_svc.login(
        session, identifier, password, ip=request.client.host if request.client else None,
    )

    if err == "rate_limited":
        ctx = {**_common_ctx(request), "error": t("auth.error.rate_limited", lang=_lang(request))}
        return request.app.state.templates.TemplateResponse(
            "auth/login.html", ctx, status_code=429
        )
    if err != "ok":
        ctx = {**_common_ctx(request), "error": t("auth.error.invalid", lang=_lang(request))}
        return request.app.state.templates.TemplateResponse(
            "auth/login.html", ctx, status_code=401
        )

    # Success: set session cookie and redirect home
    redirect = RedirectResponse(url="/", status_code=302)
    _set_session_cookie(redirect, user)
    return redirect


@router.post("/logout")
async def logout(request: Request):
    await check_csrf(request)
    resp = RedirectResponse(url="/", status_code=302)
    _clear_session_cookie(resp)
    return resp


@router.get("/recovery", response_class=HTMLResponse)
def recovery_form(request: Request):
    return request.app.state.templates.TemplateResponse(
        "auth/recovery.html", _common_ctx(request), status_code=200
    )


@router.post("/recovery/generate")
async def recovery_generate(
    request: Request,
    identifier: str = Form(...),
    session: Session = Depends(get_session),
):
    """Generate recovery codes for the account with ``identifier``.

    To avoid leaking which identifiers exist, the response is the same
    generic page in both cases; if the account exists, the codes are
    shown once.
    """
    await check_csrf(request)
    from app.phone import normalize as _norm

    try:
        key = _norm(identifier.strip())
    except ValueError:
        key = identifier.strip()
    user = session.exec(
        select(User).where(User.mobile == key)
    ).one_or_none()

    if user is None:
        return request.app.state.templates.TemplateResponse(
            "auth/recovery_sent.html", _common_ctx(request), status_code=200
        )

    codes = auth_svc.generate_recovery_codes(session, user)
    return request.app.state.templates.TemplateResponse(
        "auth/recovery_codes.html",
        {**_common_ctx(request), "codes": codes},
        status_code=200,
    )


@router.post("/recovery/use")
async def recovery_use(
    request: Request,
    identifier: str = Form(...),
    code: str = Form(...),
    session: Session = Depends(get_session),
):
    """Use a recovery code to set a new password (sets a session cookie)."""
    await check_csrf(request)
    from app.phone import normalize as _norm

    try:
        key = _norm(identifier.strip())
    except ValueError:
        key = identifier.strip()
    user = session.exec(
        select(User).where(User.mobile == key)
    ).one_or_none()
    if user is None or not auth_svc.consume_recovery_code(session, user, code):
        ctx = {**_common_ctx(request), "error": t("auth.error.recovery_invalid", lang=_lang(request))}
        return request.app.state.templates.TemplateResponse(
            "auth/recovery.html", ctx, status_code=400
        )
    if user.status != AccountStatus.APPROVED:
        ctx = {**_common_ctx(request), "error": t("auth.error.account_inactive", lang=_lang(request))}
        return request.app.state.templates.TemplateResponse(
            "auth/recovery.html", ctx, status_code=403
        )
    resp = RedirectResponse(url="/", status_code=302)
    _set_session_cookie(resp, user)
    return resp
