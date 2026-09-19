from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import learning, workflows
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

APP_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=APP_DIR / "templates")
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")


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
        return RedirectResponse("/learn", status_code=303)
    return templates.TemplateResponse(
        request, "register.html", {"error": None, "credentials": None}
    )


@app.post("/register", response_class=HTMLResponse)
def register(request: Request, username: str = Form(...)):
    username = username.strip()
    if not username or len(username) > 32 or not all(
        c.isascii() and (c.isalnum() or c in "_-") for c in username
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
    user_id, password = result
    response = templates.TemplateResponse(
        request,
        "register.html",
        {
            "error": None,
            "credentials": {"username": username, "password": password},
        },
    )
    response.headers["Cache-Control"] = "no-store"
    set_session_cookie(response, issue_session(user_id, username))
    return response


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request, next: str = "/learn"):
    return templates.TemplateResponse(
        request, "login.html", {"error": None, "next": _login_destination(next)}
    )


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), next: str = Form("/learn")):
    user_id = authenticate(username.strip(), password.strip())
    if not user_id:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username or password.", "next": _login_destination(next)},
            status_code=401,
        )
    token = issue_session(user_id, username.strip())
    response = RedirectResponse(_login_destination(next), status_code=303)
    set_session_cookie(response, token)
    return response


def _login_destination(destination):
    allowed = {"/learn", "/learn/first-injection", *("/learn/" + slug for slug in workflows.LESSONS)}
    return destination if destination in allowed else "/learn"


@app.get("/learn", response_class=HTMLResponse)
def learn_home(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "learn.html", {
        "user": user, "progress": learning.progress_for(user["id"]),
        "workflows": workflows.LESSONS, "workflow_progress": workflows.progress_for(user["id"]),
    }, headers={"Cache-Control": "no-store"})


def _lesson_response(request, user, *, run_id=None, error=None, status_code=200, draft=""):
    state = learning.lesson_state(user["id"], run_id)
    context = {"request": request, "user": user, "lesson": state, "error": error, "draft": draft}
    headers = {"Cache-Control": "no-store"}
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({
            "html": templates.get_template("_lesson_content.html").render(context),
            "error": error,
        }, status_code=status_code, headers=headers)
    return templates.TemplateResponse(request, "lesson.html", context, status_code=status_code, headers=headers)


@app.get("/learn/first-injection", response_class=HTMLResponse)
def first_lesson(request: Request, attempt: str | None = None):
    user = get_current_user(request)
    if not user:
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"error": "Your session expired. Sign in to continue; your saved attempts will be here."}, status_code=401)
        return RedirectResponse("/login?next=/learn/first-injection", status_code=303)
    try:
        return _lesson_response(request, user, run_id=attempt)
    except learning.LessonError as e:
        raise HTTPException(e.status_code, str(e))


@app.post("/learn/first-injection/{action}")
async def lesson_action(request: Request, action: str, run_id: str = Form(...),
                        request_id: str = Form(""), message: str = Form("")):
    user = get_current_user(request)
    if not user:
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"error": "Your session expired. Sign in to continue; your draft is kept in this tab."}, status_code=401)
        return RedirectResponse("/login?next=/learn/first-injection", status_code=303)
    try:
        if action == "send":
            await learning.submit_turn(user["id"], run_id, request_id, message)
        elif action == "hint":
            learning.reveal_hint(user["id"], run_id)
        elif action == "reset":
            learning.reset_lesson(user["id"], run_id)
        else:
            raise HTTPException(404)
    except learning.LessonError as e:
        return _lesson_response(request, user, error=str(e), status_code=e.status_code,
                                draft=message if action == "send" else "")
    if "application/json" in request.headers.get("accept", ""):
        return _lesson_response(request, user)
    return RedirectResponse("/learn/first-injection", status_code=303)


def _workflow_response(request, user, slug, *, run_id=None, error=None, status_code=200, draft=""):
    state = workflows.state(user["id"], slug, run_id)
    context = {"request": request, "user": user, "lesson": state, "error": error, "draft": draft,
               "lesson_title": state["spec"]["title"], "lesson_url": state["url"],
               "lesson_partial": "_workflow_content.html"}
    headers = {"Cache-Control": "no-store"}
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"html": templates.get_template("_workflow_content.html").render(context), "error": error},
                            status_code=status_code, headers=headers)
    return templates.TemplateResponse(request, "lesson.html", context, status_code=status_code, headers=headers)


@app.get("/learn/{slug}", response_class=HTMLResponse)
def workflow_lesson(request: Request, slug: str, attempt: str | None = None):
    try:
        workflows.definition(slug)
        user = get_current_user(request)
        if not user:
            if "application/json" in request.headers.get("accept", ""):
                return JSONResponse({"error": "Your session expired. Sign in to resume this lesson."}, status_code=401)
            return RedirectResponse("/login?next=/learn/" + slug, status_code=303)
        return _workflow_response(request, user, slug, run_id=attempt)
    except learning.LessonError as e:
        raise HTTPException(e.status_code, str(e))


@app.post("/learn/{slug}/{action}")
async def workflow_action(request: Request, slug: str, action: str, run_id: str = Form(...),
                          request_id: str = Form(""), message: str = Form("")):
    if slug not in workflows.LESSONS or action not in ("send", "hint", "reset", "compare"):
        raise HTTPException(404)
    user = get_current_user(request)
    if not user:
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"error": "Your session expired. Sign in to continue; your draft is kept in this tab."}, status_code=401)
        return RedirectResponse("/login?next=/learn/" + slug, status_code=303)
    try:
        if action == "send":
            await workflows.submit(user["id"], slug, run_id, request_id, message)
        elif action == "hint":
            workflows.hint(user["id"], slug, run_id)
        elif action == "reset":
            workflows.reset(user["id"], slug, run_id)
        else:
            workflows.compare(user["id"], slug, run_id, request_id)
    except learning.LessonError as e:
        return _workflow_response(request, user, slug, error=str(e), status_code=e.status_code,
                                  draft=message if action == "send" else "")
    if "application/json" in request.headers.get("accept", ""):
        return _workflow_response(request, user, slug)
    return RedirectResponse("/learn/" + slug, status_code=303)


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
