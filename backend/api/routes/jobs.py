from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_container
from ...core.container import AppContainer

router = APIRouter()


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str, container: AppContainer = Depends(get_container)):
    job = container.job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str, container: AppContainer = Depends(get_container)):
    job = container.job_manager.cancel(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job