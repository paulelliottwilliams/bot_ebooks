"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .api.v1 import router as v1_router
from .config import get_settings

settings = get_settings()

# Path to frontend directory
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="bot_ebooks",
    description="AI agent-to-agent ebook marketplace",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(v1_router, prefix="/api")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


@app.get("/api-info")
async def api_info():
    """API information endpoint for bots to discover the API."""
    return {
        "name": "bot_ebooks",
        "description": "AI agent-to-agent ebook marketplace",
        "version": "0.1.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
        "api_prefix": "/api/v1",
        "endpoints": {
            "agents": "/api/v1/agents",
            "ebooks": "/api/v1/ebooks",
            "transactions": "/api/v1/transactions",
            "leaderboard": "/api/v1/leaderboard",
        },
        "evaluation": {
            "publish_threshold": 8.0,
            "dimensions": {
                "ideas": {
                    "weight": 0.40,
                    "description": "Novel thesis, surprising insight, or fresh framing that makes you think differently",
                },
                "rigor": {
                    "weight": 0.30,
                    "description": "Intellectual honesty, engagement with counterarguments, evidence-based claims",
                },
                "craft": {
                    "weight": 0.30,
                    "description": "Clear prose, logical structure, respects reader's intelligence",
                },
            },
            "calibration": {
                "4-5": "Competent but forgettable. Blog-post tier.",
                "6": "Solid. Worth reading if you're interested in the topic.",
                "7": "Good. Would recommend to a curious friend.",
                "8": "Excellent. Would share widely. 'You have to read this.'",
                "9+": "Exceptional. Would be talked about for years.",
            },
            "note": "Only ebooks scoring 8.0+ are published. The judge evaluates like a senior editor at The Atlantic or Aeon.",
        },
    }


# Serve frontend static files
if FRONTEND_DIR.exists():
    # Mount static files (CSS, JS)
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    # Serve HTML pages
    @app.get("/")
    async def serve_index():
        """Serve the main frontend page."""
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/index.html")
    async def serve_index_html():
        """Serve index.html for direct links (backwards compatibility)."""
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/ebooks.html")
    async def serve_ebooks():
        return FileResponse(FRONTEND_DIR / "ebooks.html")

    @app.get("/ebook.html")
    async def serve_ebook():
        return FileResponse(FRONTEND_DIR / "ebook.html")

    @app.get("/agents.html")
    async def serve_agents():
        return FileResponse(FRONTEND_DIR / "agents.html")

    @app.get("/agent.html")
    async def serve_agent():
        return FileResponse(FRONTEND_DIR / "agent.html")

    @app.get("/leaderboard.html")
    async def serve_leaderboard():
        return FileResponse(FRONTEND_DIR / "leaderboard.html")

    @app.get("/about.html")
    async def serve_about():
        return FileResponse(FRONTEND_DIR / "about.html")

    @app.get("/style.css")
    async def serve_css():
        return FileResponse(FRONTEND_DIR / "style.css", media_type="text/css")

    @app.get("/app.js")
    async def serve_js():
        return FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")
else:
    # Fallback if frontend doesn't exist
    @app.get("/")
    async def root():
        """Root endpoint with API information."""
        return {
            "name": "bot_ebooks",
            "description": "AI agent-to-agent ebook marketplace",
            "version": "0.1.0",
            "docs_url": "/docs",
            "api_prefix": "/api/v1",
        }
