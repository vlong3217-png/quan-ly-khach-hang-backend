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
from app.routers.opportunity_tasks import router as opportunity_tasks_router
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

# Đảm bảo thư mục lưu trữ uploads tồn tại (an toàn cho serverless Vercel /tmp)
try:
    UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/uploads" if os.environ.get("VERCEL") else os.path.join(os.getcwd(), "uploads"))
    os.makedirs(os.path.join(UPLOAD_DIR, "avatars"), exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
except Exception as e:
    print(f"Warning: Could not initialize /uploads static directory: {e}")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.encoders import jsonable_encoder

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/auth/login":
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Tài khoản hoặc mật khẩu không chính xác"},
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
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



@app.on_event("startup")
def on_startup():
    try:
        Base.metadata.create_all(bind=engine)
        from app.models.user import User as UserModel
        from app.services.auth_service import hash_password, _DEFAULT_HASHED_PASSWORD
        from app.core.database import SessionLocal
        db = SessionLocal()
        admin = db.query(UserModel).filter(UserModel.email == "vlong3217@gmail.com").first()
        if not admin:
            admin = UserModel(
                id=1,
                email="vlong3217@gmail.com",
                username="admin",
                full_name="Admin",
                role="ADMIN",
                is_active=True,
                status="ACTIVE",
                hashed_password=_DEFAULT_HASHED_PASSWORD,
            )
            db.merge(admin)
            db.commit()
        db.close()
    except Exception:
        pass

app.include_router(auth_router)
app.include_router(customers_router)
app.include_router(users_router)
app.include_router(users_router, prefix="/admin")
from app.routers.opportunity_export import router as opportunity_export_router
app.include_router(opportunity_export_router)
from app.routers.opportunity_alerts import router as opportunity_alerts_router
app.include_router(opportunity_alerts_router)  # S5-07: phải đứng trước /opportunities/{id}
app.include_router(opportunity_tasks_router)
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

from app.routers.leads import router as leads_router
app.include_router(leads_router)
app.include_router(leads_router, prefix="/api/v1")

from app.routers.campaigns import router as campaigns_router
app.include_router(campaigns_router)

from app.routers.sales_forecast import router as sales_forecast_router
app.include_router(sales_forecast_router)

from app.routers.email_marketing import router as email_marketing_router
app.include_router(email_marketing_router)

from app.routers.notification_preferences import router as notification_preferences_router
app.include_router(notification_preferences_router)

from app.routers.sales_quotas import router as sales_quotas_router
app.include_router(sales_quotas_router)

from app.routers.sales_dashboard import router as sales_dashboard_router
app.include_router(sales_dashboard_router)

from app.routers.sales_funnel import router as sales_funnel_router
app.include_router(sales_funnel_router)

from app.routers.sales_forecast_report import router as sales_forecast_report_router
app.include_router(sales_forecast_report_router)

from app.routers.team_activity_sla import router as team_activity_sla_router
app.include_router(team_activity_sla_router)

from app.routers.team_leaderboard import router as team_leaderboard_router
app.include_router(team_leaderboard_router)

from app.routers.lead_source_report import router as lead_source_report_router
app.include_router(lead_source_report_router)

from app.routers.team_activity_audit import router as team_activity_audit_router
app.include_router(team_activity_audit_router)


from app.routers.contracts import router as contracts_router
app.include_router(contracts_router)

from app.routers.automation_rules import router as automation_rules_router
app.include_router(automation_rules_router)


@app.get("/system/db-info")
def get_system_db_info():
    import urllib.parse
    import re
    from app.core.database import engine, raw_db_url
    from sqlalchemy import text
    
    url_str = str(raw_db_url or "")
    if url_str:
        parsed = urllib.parse.urlsplit(url_str)
        masked_netloc = re.sub(r":([^@/]+)@", ":****@", parsed.netloc)
        masked_url = urllib.parse.urlunsplit((parsed.scheme, masked_netloc, parsed.path, parsed.query, parsed.fragment))
    else:
        masked_url = "NOT_CONFIGURED"
        
    res = {
        "raw_db_url_configured": bool(raw_db_url),
        "masked_url": masked_url,
        "engine_url": re.sub(r":([^@/]+)@", ":****@", str(engine.url)),
        "engine_host": engine.url.host,
        "engine_port": engine.url.port,
        "engine_database": engine.url.database,
        "is_aiven": "aiven" in str(engine.url.host or "").lower(),
        "connected": False,
        "error": None,
    }
    
    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT 1, DATABASE(), CURRENT_USER(), @@hostname, VERSION()")).fetchone()
            res["connected"] = True
            res["current_database"] = row[1]
            res["current_user"] = re.sub(r"@.*", "@****", str(row[2]))
            res["server_hostname"] = str(row[3])
            res["mysql_version"] = str(row[4])
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {str(e)}"
        
    return res
