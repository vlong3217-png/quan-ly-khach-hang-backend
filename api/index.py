import os
import sys

# Ensure current working directory is on python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from app.main import app
except Exception as e:
    import traceback
    err_trace = traceback.format_exc()
    from fastapi import FastAPI
    from fastapi.responses import PlainTextResponse

    app = FastAPI(title="Diagnosis API")

    @app.get("/{rest_of_path:path}")
    def fallback_error(rest_of_path: str = ""):
        return PlainTextResponse(f"Backend Startup Exception:\n\n{err_trace}", status_code=500)
