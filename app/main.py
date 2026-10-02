from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router

app = FastAPI(
    title="Customer Management API",
    description="Backend API for Customer Management System",
    version="1.0.0",
)

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
            content={"detail": "T??i kho???n ho???c m???t kh???u kh??ng ch??nh x??c"},
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


@app.get("/")
def root():
    return {
        "message": "Customer Management API is running"
    }


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(users_router, prefix="/admin")
