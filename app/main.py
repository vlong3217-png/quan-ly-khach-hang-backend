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
from app.routers.contacts import router as contacts_router
from app.routers.tickets import router as tickets_router
from app.models import Base
from app.core.database import engine

# Tự động tạo các bảng SQL nếu kết nối cơ sở dữ liệu khả dụng
try:
    Base.metadata.create_all(bind=engine)
except Exception:
    pass

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
app.include_router(contacts_router)
app.include_router(tickets_router)

from app.routers.audit_logs import router as audit_logs_router
app.include_router(audit_logs_router)

from app.routers.products import router as products_router
app.include_router(products_router)

from app.routers.organizations import router as organizations_router
app.include_router(organizations_router)

from app.routers.master_data import router as master_data_router
app.include_router(master_data_router)

from app.routers.custom_fields import router as custom_fields_router
app.include_router(custom_fields_router)

from app.routers.pipeline import router as pipeline_stages_router
app.include_router(pipeline_stages_router)

from app.routers.win_loss import router as win_loss_router
app.include_router(win_loss_router)


