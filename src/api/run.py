import threading
import uvicorn
import sys
import os

from api.feedback_api import app


def run_api():
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)


def start_api_in_thread():
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    return api_thread
