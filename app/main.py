from pathlib import Path

from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import prisma, connect_db, disconnect_db
from api.routes import auth, events
from middleware.request_logging import RequestLoggingMiddleware
from api.deps import COOKIE_NAME, get_optional_user_id
from fastapi import HTTPException

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await disconnect_db()


app = FastAPI(title="Event Board", lifespan=lifespan)

# Middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(auth.router, prefix="/api")
app.include_router(events.router, prefix="/api/events")

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Homepage: list events and featured events."""
    from api.routes.events import list_events, list_featured, _event_to_response
    events_data = await list_events(skip=0, take=50, sort="date")
    featured_data = await list_featured(take=5)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "events": events_data, "featured": featured_data},
    )


@app.get("/events/{event_id}", response_class=HTMLResponse)
async def event_detail_page(request: Request, event_id: str):
    """Event detail view (with share button)."""
    from api.routes.events import get_event
    try:
        event = await get_event(event_id)
    except HTTPException:
        raise HTTPException(404, "Event not found")
    return templates.TemplateResponse(
        "events/detail.html",
        {"request": request, "event": event},
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Show login form."""
    return templates.TemplateResponse("auth/login.html", {"request": request})


@app.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    """Show signup form."""
    return templates.TemplateResponse("auth/signup.html", {"request": request})


from fastapi import Form


@app.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    """Process login form: validate and set JWT cookie, redirect to backend."""
    from database import prisma
    from core.security import verify_password, create_access_token
    from core.config import get_settings
    from datetime import timedelta

    user = await prisma.user.find_unique(where={"email": email})
    pwd_hash = getattr(user, "password_hash", None) or getattr(user, "passwordHash", None)
    if not user or not pwd_hash or not verify_password(password, pwd_hash):
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid email or password"},
        )
    settings = get_settings()
    token = create_access_token(
        subject=user.id,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    response = RedirectResponse(url="/backend", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
    )
    return response


@app.post("/signup")
async def signup_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(..., min_length=6),
):
    """Process signup form: create user and set JWT cookie, redirect to backend."""
    try:
        from database import prisma
        from core.security import hash_password, create_access_token
        from core.config import get_settings
        from datetime import timedelta

        existing = await prisma.user.find_unique(where={"email": email})
        if existing:
            return templates.TemplateResponse(
                "auth/signup.html",
                {"request": request, "error": "Email already registered"},
            )
        user = await prisma.user.create(
            data={"email": email, "passwordHash": hash_password(password)},
        )
        settings = get_settings()
        token = create_access_token(
            subject=user.id,
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        )
        response = RedirectResponse(url="/backend", status_code=303)
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            max_age=settings.access_token_expire_minutes * 60,
            samesite="lax",
        )
        return response
    except Exception as e:
        import traceback
        return PlainTextResponse(
            traceback.format_exc(),
            status_code=500,
            media_type="text/plain",
        )


@app.get("/logout")
async def logout():
    """Clear JWT cookie and redirect to home."""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/backend", response_class=HTMLResponse)
async def backend_dashboard(request: Request):
    """Backend: paginated event list (logged-in only)."""
    if await get_optional_user_id(request) is None:
        return RedirectResponse(url="/login", status_code=303)
    from api.routes.events import list_events
    try:
        page = int(request.query_params.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1
    per_page = 10
    skip = (page - 1) * per_page
    events_data = await list_events(skip=skip, take=per_page, sort="date")
    total = await prisma.event.count()
    total_pages = (total + per_page - 1) // per_page
    return templates.TemplateResponse(
        "backend/events_list.html",
        {
            "request": request,
            "events": events_data,
            "page": page,
            "total_pages": total_pages,
        },
    )


@app.get("/backend/events/new", response_class=HTMLResponse)
async def backend_new_event_page(request: Request):
    """Show create event form (logged-in only)."""
    if await get_optional_user_id(request) is None:
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "backend/event_form.html",
        {"request": request, "event": None, "is_edit": False},
    )


@app.get("/backend/events/{event_id}/edit", response_class=HTMLResponse)
async def backend_edit_event_page(request: Request, event_id: str):
    """Show edit event form (logged-in only)."""
    if await get_optional_user_id(request) is None:
        return RedirectResponse(url="/login", status_code=303)
    from api.routes.events import get_event
    try:
        event = await get_event(event_id)
    except HTTPException:
        raise HTTPException(404, "Event not found")
    return templates.TemplateResponse(
        "backend/event_form.html",
        {"request": request, "event": event, "is_edit": True},
    )


@app.post("/backend/events")
async def backend_create_event_submit(request: Request):
    """Create event from form (logged-in only)."""
    if await get_optional_user_id(request) is None:
        return RedirectResponse(url="/login", status_code=303)
    from fastapi import Form
    form = await request.form()
    title = form.get("title", "")
    description = form.get("description") or None
    location = form.get("location") or None
    image_url = form.get("image_url") or None
    featured = form.get("featured") == "on"
    dates_str = form.get("dates", "")
    date_list = [s.strip() for s in dates_str.replace(",", "\n").split() if s.strip()]
    from datetime import datetime
    date_times = []
    for s in date_list:
        try:
            date_times.append(datetime.fromisoformat(s.replace("Z", "+00:00")))
        except Exception:
            pass
    event = await prisma.event.create(
        data={
            "title": title,
            "description": description,
            "location": location,
            "imageUrl": image_url,
            "featured": featured,
            "dates": {"create": [{"dateTime": dt} for dt in date_times]},
        }
    )
    out = await prisma.event.find_unique(where={"id": event.id}, include={"dates": True})
    return RedirectResponse(url=f"/backend#event-{event.id}", status_code=303)


@app.post("/backend/events/{event_id}")
async def backend_update_event_submit(request: Request, event_id: str):
    """Update event from form (logged-in only)."""
    if await get_optional_user_id(request) is None:
        return RedirectResponse(url="/login", status_code=303)
    form = await request.form()
    title = form.get("title", "")
    description = form.get("description") or None
    location = form.get("location") or None
    image_url = form.get("image_url") or None
    featured = form.get("featured") == "on"
    dates_str = form.get("dates", "")
    date_list = [s.strip() for s in dates_str.replace(",", "\n").split() if s.strip()]
    from datetime import datetime
    date_times = []
    for s in date_list:
        try:
            date_times.append(datetime.fromisoformat(s.replace("Z", "+00:00")))
        except Exception:
            pass
    await prisma.eventdate.delete_many(where={"eventId": event_id})
    await prisma.event.update(
        where={"id": event_id},
        data={
            "title": title,
            "description": description,
            "location": location,
            "imageUrl": image_url,
            "featured": featured,
            "dates": {"create": [{"dateTime": dt} for dt in date_times]},
        },
    )
    return RedirectResponse(url="/backend", status_code=303)


@app.post("/backend/events/{event_id}/delete")
async def backend_delete_event(request: Request, event_id: str):
    """Delete event (logged-in only)."""
    if await get_optional_user_id(request) is None:
        return RedirectResponse(url="/login", status_code=303)
    existing = await prisma.event.find_unique(where={"id": event_id})
    if existing:
        await prisma.event.delete(where={"id": event_id})
    return RedirectResponse(url="/backend", status_code=303)


@app.get("/health")
async def health():
    try:
        await prisma.user.find_first()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            content={"status": "error", "database": "disconnected", "detail": str(e)},
            status_code=500,
        )
