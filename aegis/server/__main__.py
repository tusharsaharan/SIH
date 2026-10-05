import os
from aegis.server import app
import uvicorn

uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")), log_level="info")
