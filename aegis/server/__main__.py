from aegis.server import app
import uvicorn

uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
