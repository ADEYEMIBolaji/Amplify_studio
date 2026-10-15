from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_exception_handlers
from app.routers import (
    brand_profile,
    dashboard,
    hooks,
    media,
    metrics,
    platform_limits,
    posts,
    projects,
    references,
    scripts,
    topic_tags,
    transcripts,
    vocabulary,
)

settings = get_settings()

app = FastAPI(title="Amplify Studio API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(projects.router)
app.include_router(topic_tags.router)
app.include_router(brand_profile.router)
app.include_router(scripts.router)
app.include_router(hooks.router)
app.include_router(references.router)
app.include_router(media.router)
app.include_router(transcripts.router)
app.include_router(vocabulary.router)
app.include_router(posts.router)
app.include_router(platform_limits.router)
app.include_router(metrics.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
