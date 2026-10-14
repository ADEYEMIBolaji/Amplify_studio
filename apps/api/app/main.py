from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import register_exception_handlers
from app.routers import brand_profile, projects, topic_tags

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
