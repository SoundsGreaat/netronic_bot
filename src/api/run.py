import threading
import uvicorn


def run_api():
    uvicorn.run("src.api.feedback_api:app", host="0.0.0.0", port=8000, reload=False)


def start_api_in_thread():
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    return api_thread
