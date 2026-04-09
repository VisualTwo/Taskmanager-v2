#!/usr/bin/env python3
"""
Minimal test server to identify the issue
"""

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Test Server")

@app.get("/")
async def root():
    return {"message": "Test server is running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    print("🧪 Starting minimal test server...")
    uvicorn.run(
        "test_minimal_server:app",
        host="127.0.0.1", 
        port=8001,
        reload=False,
        log_level="info"
    )