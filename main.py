from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import resume

app = FastAPI(title="Resume Builder API")

# Allow React frontend to talk to FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resume.router, prefix="/api/resume")

@app.get("/")
def root():
    return {"status": "Resume Builder API running"}