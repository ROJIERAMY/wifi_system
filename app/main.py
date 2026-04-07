import csv
import io
import secrets
from typing import Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from starlette.middleware.sessions import SessionMiddleware

from app.config import ADMIN_PASSWORD, BASE_DIR, SESSION_SECRET
from app.db import PRESETS, get_session, init_db
from app.models import RouterSettings, Voucher, VoucherProfile
from app.services.mikrotik import remove_hotspot_user, sync_voucher, test_connection

app = FastAPI(title="WiFi Cards")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=86400 * 7)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def format_duration(seconds: int) -> str:
    if seconds >= 86400:
        return f"{seconds // 86400} day"
    if seconds >= 3600:
        return f"{seconds // 3600} h"
    if seconds >= 60:
        return f"{seconds // 60} min"
    return f"{seconds}s"


templates.env.filters["format_duration"] = format_duration


class AuthRedirect(Exception):
    pass


@app.exception_handler(AuthRedirect)
async def _auth_redirect_handler(_request: Request, _exc: AuthRedirect):
    return RedirectResponse("/login", status_code=302)


def require_login(request: Request) -> None:
    if not request.session.get("logged_in"):
        raise AuthRedirect()


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/login")
def login_page(request: Request):
    if request.session.get("logged_in"):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": None, "show_nav": False},
    )


@app.post("/login")
def login_post(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        request.session["logged_in"] = True
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Wrong password. Try again.", "show_nav": False},
        status_code=401,
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login")


def _random_username() -> str:
    return "WIFI-" + secrets.token_hex(3).upper()


def _random_password() -> str:
    return secrets.token_urlsafe(6).replace("-", "x")[:10]


@app.get("/")
def home(
    request: Request,
    session: Session = Depends(get_session),
    msg: str = Query(default=""),
    err: str = Query(default=""),
):
    require_login(request)
    allowed_names = {n for n, _ in PRESETS}
    profiles = session.exec(
        select(VoucherProfile)
        .where(VoucherProfile.name.in_(allowed_names))
        .order_by(VoucherProfile.duration_seconds)
    ).all()
    if not profiles:
        profiles = session.exec(select(VoucherProfile).order_by(VoucherProfile.duration_seconds)).all()
    vouchers = session.exec(select(Voucher).order_by(Voucher.id.desc())).limit(80).all()
    prof_map = {p.id: p for p in session.exec(select(VoucherProfile)).all()}
    pending_sync = session.exec(select(Voucher).where(Voucher.synced_to_router == False)).all()
    settings = session.get(RouterSettings, 1)
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "profiles": profiles,
            "presets_hint": PRESETS,
            "vouchers": vouchers,
            "prof_map": prof_map,
            "pending_count": len(pending_sync),
            "router_ready": bool(settings and settings.api_enabled and settings.host),
            "msg": msg,
            "err": err,
        },
    )


@app.post("/create")
def create_cards(
    request: Request,
    session: Session = Depends(get_session),
    profile_id: int = Form(...),
    count: int = Form(5),
):
    require_login(request)
    profile = session.get(VoucherProfile, profile_id)
    if not profile:
        return RedirectResponse("/?err=" + quote("Pick a time first"), status_code=302)
    count = max(1, min(count, 200))
    for _ in range(count):
        uname = _random_username()
        while session.exec(select(Voucher).where(Voucher.username == uname)).first():
            uname = _random_username()
        session.add(
            Voucher(
                username=uname,
                password=_random_password(),
                profile_id=profile_id,
                status="created",
                synced_to_router=False,
            )
        )
    session.commit()
    return RedirectResponse("/?msg=" + quote(f"Created {count} card(s)."), status_code=302)


@app.post("/sync")
def sync_router(request: Request, session: Session = Depends(get_session)):
    require_login(request)
    settings = session.get(RouterSettings, 1)
    if not settings or not settings.api_enabled:
        return RedirectResponse(
            "/?err=" + quote("Turn on “Send to router” in Settings and save."),
            status_code=302,
        )
    pending = session.exec(select(Voucher).where(Voucher.synced_to_router == False)).all()
    if not pending:
        return RedirectResponse("/?msg=" + quote("Nothing new to send."), status_code=302)
    profiles = {p.id: p for p in session.exec(select(VoucherProfile)).all()}
    errors = []
    for v in pending:
        prof = profiles.get(v.profile_id)
        if not prof:
            errors.append(f"{v.username}: missing time profile")
            continue
        r = sync_voucher(settings, v, prof)
        if r.ok:
            v.synced_to_router = True
            v.status = "on_router"
            session.add(v)
        else:
            errors.append(f"{v.username}: {r.message}")
    session.commit()
    if errors:
        return RedirectResponse("/?err=" + quote(errors[0][:300]), status_code=302)
    return RedirectResponse(
        "/?msg=" + quote(f"Sent {len(pending)} card(s) to the router."),
        status_code=302,
    )


@app.post("/revoke/{vid}")
def revoke_card(request: Request, vid: int, session: Session = Depends(get_session)):
    require_login(request)
    v = session.get(Voucher, vid)
    settings = session.get(RouterSettings, 1)
    if v and settings and settings.api_enabled:
        remove_hotspot_user(settings, v.username)
    if v:
        v.status = "revoked"
        v.synced_to_router = False
        session.add(v)
        session.commit()
    return RedirectResponse("/?msg=" + quote("Card turned off."), status_code=302)


@app.get("/export.csv")
def export_csv(request: Request, session: Session = Depends(get_session)):
    require_login(request)
    vouchers = session.exec(select(Voucher).order_by(Voucher.id)).all()
    profiles = {p.id: p for p in session.exec(select(VoucherProfile)).all()}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["username", "password", "time", "note"])
    for v in vouchers:
        p = profiles.get(v.profile_id)
        w.writerow(
            [
                v.username,
                v.password,
                format_duration(p.duration_seconds) if p else "",
                v.status,
            ]
        )
    data = buf.getvalue().encode("utf-8")
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="wifi-cards.csv"'},
    )


@app.get("/settings")
def settings_page(request: Request, session: Session = Depends(get_session), msg: str = ""):
    require_login(request)
    s = session.get(RouterSettings, 1)
    if s is None:
        s = RouterSettings(id=1)
        session.add(s)
        session.commit()
        session.refresh(s)
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "settings": s, "msg": msg},
    )


@app.post("/settings")
def settings_save(
    request: Request,
    session: Session = Depends(get_session),
    host: str = Form(...),
    port: int = Form(8728),
    username: str = Form(...),
    password: str = Form(""),
    use_plaintext_login: Optional[str] = Form(None),
    api_enabled: Optional[str] = Form(None),
):
    require_login(request)
    s = session.get(RouterSettings, 1)
    if s is None:
        s = RouterSettings(id=1)
    s.host = host.strip()
    s.port = port
    s.username = username.strip()
    s.password = password
    s.use_plaintext_login = use_plaintext_login == "on"
    s.api_enabled = api_enabled == "on"
    session.add(s)
    session.commit()
    return RedirectResponse("/settings?msg=" + quote("Saved."), status_code=302)


@app.post("/settings/test")
def settings_test(request: Request, session: Session = Depends(get_session)):
    require_login(request)
    s = session.get(RouterSettings, 1)
    if not s:
        return RedirectResponse("/settings?msg=" + quote("Nothing to test."), status_code=302)
    r = test_connection(s)
    msg = "Router OK — " + r.message if r.ok else "Cannot reach router: " + r.message
    return RedirectResponse("/settings?msg=" + quote(msg[:400]), status_code=302)


# Old URLs → one simple app
@app.get("/profiles")
@app.get("/vouchers")
@app.get("/portal-preview")
def _redirect_old():
    return RedirectResponse("/", status_code=302)
