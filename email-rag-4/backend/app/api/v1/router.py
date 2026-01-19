"""
API v1 Router

Aggregates all API v1 endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, emails, forensic, rag, search, stats, upload, users

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(upload.router)
api_router.include_router(rag.router)
api_router.include_router(search.router)
api_router.include_router(emails.router)
api_router.include_router(stats.router)
api_router.include_router(forensic.router)
