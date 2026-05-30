"""FastAPI application entry point"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from app.db import SessionLocal, init_db
from app.routers import pages, api_auth, api_chat, api_generation
from app.config import DEBUG, STATIC_DIR, VACANCY_POOL_AUTO_SYNC, VACANCY_POOL_MIN_SIZE, VACANCY_POOL_SYNC_LIMIT
from app.services.vacancy_recommendations import start_getmatch_pool_sync_if_needed

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Resume Career Consultant MVP",
    description="Adaptive resume generation powered by multi-agent AI",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized")
    start_getmatch_pool_sync_if_needed(
        SessionLocal,
        enabled=VACANCY_POOL_AUTO_SYNC,
        min_size=VACANCY_POOL_MIN_SIZE,
        limit=VACANCY_POOL_SYNC_LIMIT,
    )

# Include routers
app.include_router(pages.router)
app.include_router(api_auth.router)
app.include_router(api_chat.router)
app.include_router(api_generation.router)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Health check
@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=DEBUG
    )
