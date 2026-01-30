"""FastAPI application main module."""
from fastapi import FastAPI

from peter_parser.api.routes.pipeline import router as pipeline_router

app = FastAPI(title="Peter Parser API", version="0.1.0")
app.include_router(pipeline_router)
