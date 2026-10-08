from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.blades import router

app = FastAPI(title="BladeGen API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")
