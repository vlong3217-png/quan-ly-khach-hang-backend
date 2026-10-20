import os
import sys

# Ensure backend root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

# Top-level handler aliases for Vercel Serverless Function detection
handler = app
application = app
