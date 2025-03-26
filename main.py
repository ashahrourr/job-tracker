# main.py 
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.workflow_pipeline.database import SessionLocal, JobApplication, init_models
from fastapi.middleware.cors import CORSMiddleware
from backend.workflow_pipeline.auth import router as auth_router
from backend.workflow_pipeline.emails import router as gmail_router
from backend.workflow_pipeline.scheduler import router as scheduler_router
from backend.workflow_pipeline.session import get_current_user
import uvicorn
from sqlalchemy import select


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database on startup
    await init_models()
    yield

app = FastAPI(lifespan=lifespan)

# Include the auth, Gmail, and scheduler routes
app.include_router(auth_router)
app.include_router(gmail_router)
app.include_router(scheduler_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://job-tracker-frontend-045g.onrender.com",  # Production Frontend
        "http://localhost:5173",  # Local Frontend (React, Next.js, etc.)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Async database dependency
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session

# Updated endpoints
@app.get("/jobs/")
async def get_user_jobs(
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(JobApplication).where(JobApplication.user_email == current_user)
    )
    jobs = result.scalars().all()
    return jobs

@app.delete("/jobs/{job_id}")
async def delete_job(
    job_id: int,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(JobApplication)
        .where(JobApplication.id == job_id)
        .where(JobApplication.user_email == current_user)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    await db.delete(job)
    await db.commit()
    return {"message": "Job deleted successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
