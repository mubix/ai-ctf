from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .auth import (
    COOKIE_NAME,
    authenticate,
    create_user,
    get_current_user,
    issue_session,
    set_session_cookie,
)
from .chat import get_history, send_message
from .config import (
    FLAG_RECON_AUDIT_HEADER,
    FLAG_RECON_ROBOTS_TOKEN,
    POWERED_BY,
)
from .db import init_db
from .personas import get_persona, visible_personas


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Anvil Industries AI Console", lifespan=lifespan)

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def add_audit_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Powered-By"] = POWERED_BY
    response.headers["X-Audit-Token"] = FLAG_RECON_AUDIT_HEADER
    return response


# ---------------------------------------------------------------------------
# Recon endpoints — robots.txt and sitemap.xml host flag #19 and a clue for #13
# ---------------------------------------------------------------------------

@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return (
        "User-agent: *\n"
        "Disallow: /chat/internal_admin\n"
        "Disallow: /admin\n"
        "Disallow: /api/v1/internal\n"
        "Sitemap: /sitemap.xml\n"
        "\n"
        f"# Internal: do not index. Audit canary: {FLAG_RECON_ROBOTS_TOKEN}\n"
    )


@app.get("/sitemap.xml")
def sitemap():
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>/</loc></url>\n'
        '  <url><loc>/login</loc></url>\n'
        '</urlset>\n'
    )
    return Response(content=xml, media_type="application/xml")


# ---------------------------------------------------------------------------
# Registration / login / logout
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    if get_current_user(request):
        return RedirectResponse("/chat/customer_service", status_code=303)
    return templates.TemplateResponse(
        request, "register.html", {"error": None, "credentials": None}
    )


@app.post("/register", response_class=HTMLResponse)
def register(request: Request, username: str = Form(...)):
    username = username.strip()
    if not username or len(username) > 32 or not all(
        c.isalnum() or c in "_-" for c in username
    ):
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "error": "Username must be 1-32 chars, letters/digits/_/- only.",
                "credentials": None,
            },
            status_code=400,
        )
    result = create_user(username)
    if result is None:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "error": f"Username '{username}' is already taken. Pick another.",
                "credentials": None,
            },
            status_code=409,
        )
    _, password = result
    return templates.TemplateResponse(
        request,
        "register.html",
        {
            "error": None,
            "credentials": {"username": username, "password": password},
        },
    )


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(
        request, "login.html", {"error": None}
    )


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user_id = authenticate(username.strip(), password.strip())
    if not user_id:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username or password."},
            status_code=401,
        )
    token = issue_session(user_id, username.strip())
    response = RedirectResponse("/chat/customer_service", status_code=303)
    set_session_cookie(response, token)
    return response


@app.post("/logout")
def logout():
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

@app.get("/chat", response_class=HTMLResponse)
def chat_default():
    return RedirectResponse("/chat/customer_service", status_code=303)


@app.get("/chat/{persona_slug}", response_class=HTMLResponse)
def chat_view(request: Request, persona_slug: str):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/", status_code=303)
    persona = get_persona(persona_slug)
    if not persona:
        raise HTTPException(404, "No such bot.")
    history = get_history(user["id"], persona_slug)
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "user": user,
            "persona": persona,
            "personas": visible_personas(),
            "history": history,
        },
    )


@app.post("/chat/{persona_slug}/send", response_class=HTMLResponse)
async def chat_send(
    request: Request, persona_slug: str, message: str = Form(...)
):
    user = get_current_user(request)
    if not user:
        raise HTTPException(401)
    persona = get_persona(persona_slug)
    if not persona:
        raise HTTPException(404)
    bot_message = await send_message(user["id"], persona_slug, message.strip())
    return templates.TemplateResponse(
        request, "_message.html", {"bot_message": bot_message}
    )
