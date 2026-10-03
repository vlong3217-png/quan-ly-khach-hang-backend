import os
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.portal import get_portal_html
from app.routers.auth import router as auth_router
from app.routers.customers import router as customers_router
from app.routers.users import router as users_router
from app.routers.opportunities import router as opportunities_router
from app.routers.activities import router as activities_router
from app.routers.quotes import router as quotes_router
from app.routers.menu import router as menu_router

app = FastAPI(
    title="Customer Management API",
    description="Backend API for Customer Management System",
    version="1.0.0",
)

# Đảm bảo thư mục lưu trữ uploads tồn tại
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(os.path.join(UPLOAD_DIR, "avatars"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/auth/login":
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Tài khoản hoặc mật khẩu không chính xác"},
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.get("/")
def root(request: Request):
    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header:
        return HTMLResponse(content=get_portal_html())
    return {
        "message": "Customer Management API is running"
    }


@app.get("/portal", response_class=HTMLResponse)
def portal():
    return HTMLResponse(content=get_portal_html())


app.include_router(auth_router)
app.include_router(customers_router)
app.include_router(users_router)
app.include_router(users_router, prefix="/admin")
app.include_router(opportunities_router)
app.include_router(activities_router)
app.include_router(quotes_router)
app.include_router(menu_router)
app.include_router(menu_router, prefix="/auth")

from app.routers.audit_logs import router as audit_logs_router
app.include_router(audit_logs_router)


