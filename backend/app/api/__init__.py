from fastapi import APIRouter

from . import projects, settings_api

api_router = APIRouter()
api_router.include_router(projects.router)
api_router.include_router(settings_api.router)
