"""
FastAPI REST API for Wav2Lip Service on Modal
Provides endpoints for triggering inference and checking job status.

Author: Kirti Palve
"""

import modal
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
import uuid
import io

# Import the inference module
from inference import app as inference_app, Wav2LipInference, get_job_status, results_volume, job_store

# Create the web app
web_app = FastAPI(
    title="Wav2Lip LipSync Service",
    description="API for generating lip-synced videos using Wav2Lip",
    version="1.0.0",
)

# Create Modal app for the API
app = modal.App("wav2lip-api")

# Define the image for API (lighter than inference)
api_image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "fastapi",
        "python-multipart",
        "pydantic",
    )
)


# ============== Pydantic Models ==============

class JobSubmitResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: Optional[str] = None
    elapsed_time: Optional[float] = None
    error: Optional[str] = None
    result_path: Optional[str] = None


class InferenceOptions(BaseModel):
    use_gan: bool = True
    resize_factor: int = 1
    pad_top: int = 0
    pad_bottom: int = 10
    pad_left: int = 0
    pad_right: int = 0


# ============== API Endpoints ==============

@web_app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Wav2Lip LipSync API",
        "status": "running",
        "version": "1.0.0",
    }


@web_app.get("/health")
async def health_check():
    """Health check for load balancers."""
    return {"status": "healthy"}


@web_app.post("/api/v1/submit", response_model=JobSubmitResponse)
async def submit_job(
    video: UploadFile = File(..., description="Input video file (mp4, avi, mov)"),
    audio: UploadFile = File(..., description="Input audio file (wav, mp3)"),
    use_gan: bool = True,
    resize_factor: int = 1,
    pad_top: int = 0,
    pad_bottom: int = 10,
    pad_left: int = 0,
    pad_right: int = 0,
):
    """
    Submit a new lip-sync job.
    
    This endpoint accepts a video and audio file, and starts an async
    inference job. Returns a job_id that can be used to check status.
    
    - **video**: Video file containing the face to animate
    - **audio**: Audio file to sync the lips to
    - **use_gan**: Use GAN model for better quality (default: True)
    - **resize_factor**: Resize factor for face detection (default: 1)
    - **pad_***: Padding around detected face region
    """
    # Validate file types
    video_extensions = [".mp4", ".avi", ".mov", ".mkv", ".webm"]
    audio_extensions = [".wav", ".mp3", ".m4a", ".flac", ".ogg"]
    
    video_ext = "." + video.filename.split(".")[-1].lower() if "." in video.filename else ""
    audio_ext = "." + audio.filename.split(".")[-1].lower() if "." in audio.filename else ""
    
    if video_ext not in video_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid video format. Supported: {video_extensions}"
        )
    
    if audio_ext not in audio_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid audio format. Supported: {audio_extensions}"
        )
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    # Read file bytes
    video_bytes = await video.read()
    audio_bytes = await audio.read()
    
    # Validate file sizes (max 100MB each)
    max_size = 100 * 1024 * 1024  # 100MB
    if len(video_bytes) > max_size:
        raise HTTPException(status_code=400, detail="Video file too large (max 100MB)")
    if len(audio_bytes) > max_size:
        raise HTTPException(status_code=400, detail="Audio file too large (max 100MB)")
    
    # Initialize job status
    job_store[job_id] = {
        "status": "queued",
        "progress": "Job submitted, waiting for GPU",
    }
    
    # Spawn the inference job asynchronously
    inference_cls = modal.Cls.lookup("wav2lip-inference", "Wav2LipInference")
    inference_cls().run_inference.spawn(
        video_bytes=video_bytes,
        audio_bytes=audio_bytes,
        job_id=job_id,
        use_gan=use_gan,
        resize_factor=resize_factor,
        pads=[pad_top, pad_bottom, pad_left, pad_right],
    )
    
    return JobSubmitResponse(
        job_id=job_id,
        status="queued",
        message="Job submitted successfully. Use /api/v1/status/{job_id} to check progress.",
    )


@web_app.get("/api/v1/status/{job_id}", response_model=JobStatusResponse)
async def get_status(job_id: str):
    """
    Get the status of a submitted job.
    
    - **job_id**: The unique job identifier returned from /submit
    
    Status values:
    - `queued`: Job is waiting for GPU resources
    - `processing`: Job is currently running
    - `completed`: Job finished successfully
    - `failed`: Job encountered an error
    - `not_found`: Job ID doesn't exist
    """
    status_fn = modal.Function.lookup("wav2lip-inference", "get_job_status")
    status = status_fn.remote(job_id)
    
    return JobStatusResponse(
        job_id=job_id,
        status=status.get("status", "not_found"),
        progress=status.get("progress"),
        elapsed_time=status.get("elapsed_time"),
        error=status.get("error"),
        result_path=status.get("result_path"),
    )


@web_app.get("/api/v1/result/{job_id}")
async def get_result(job_id: str):
    """
    Download the result video for a completed job.
    
    - **job_id**: The unique job identifier
    
    Returns the video file as a streaming response.
    """
    # Check job status first
    status_fn = modal.Function.lookup("wav2lip-inference", "get_job_status")
    status = status_fn.remote(job_id)
    
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    
    if status.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not ready. Current status: {status.get('status')}"
        )
    
    # Get the result video
    inference_cls = modal.Cls.lookup("wav2lip-inference", "Wav2LipInference")
    video_bytes = inference_cls().get_result.remote(job_id)
    
    if video_bytes is None:
        raise HTTPException(status_code=404, detail="Result file not found")
    
    return StreamingResponse(
        io.BytesIO(video_bytes),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f"attachment; filename=lipsync_{job_id}.mp4"
        }
    )


@web_app.post("/api/v1/sync")
async def sync_inference(
    video: UploadFile = File(...),
    audio: UploadFile = File(...),
    use_gan: bool = True,
    resize_factor: int = 1,
    pad_top: int = 0,
    pad_bottom: int = 10,
    pad_left: int = 0,
    pad_right: int = 0,
):
    """
    Synchronous lip-sync inference (blocking).
    
    This endpoint waits for the inference to complete and returns
    the result directly. Use for shorter videos or when you need
    immediate results.
    
    **Warning**: This can timeout for long videos. Use /submit for
    videos longer than 30 seconds.
    """
    # Read file bytes
    video_bytes = await video.read()
    audio_bytes = await audio.read()
    
    job_id = str(uuid.uuid4())
    
    # Run inference synchronously
    inference_cls = modal.Cls.lookup("wav2lip-inference", "Wav2LipInference")
    result = inference_cls().run_inference.remote(
        video_bytes=video_bytes,
        audio_bytes=audio_bytes,
        job_id=job_id,
        use_gan=use_gan,
        resize_factor=resize_factor,
        pads=[pad_top, pad_bottom, pad_left, pad_right],
    )
    
    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result.get("error", "Inference failed"))
    
    # Get and return the result
    video_bytes = inference_cls().get_result.remote(job_id)
    
    return StreamingResponse(
        io.BytesIO(video_bytes),
        media_type="video/mp4",
        headers={
            "Content-Disposition": f"attachment; filename=lipsync_{job_id}.mp4"
        }
    )


@web_app.get("/api/v1/gpus")
async def list_gpus():
    """List available GPU options for inference."""
    return {
        "available_gpus": [
            {"name": "T4", "vram": "16GB", "cost": "Low", "speed": "Good"},
            {"name": "A10G", "vram": "24GB", "cost": "Medium", "speed": "Better"},
            {"name": "A100-40GB", "vram": "40GB", "cost": "High", "speed": "Best"},
            {"name": "A100-80GB", "vram": "80GB", "cost": "Highest", "speed": "Best"},
        ],
        "current": "T4",
    }


# ============== Modal Web Endpoint ==============

@app.function(image=api_image)
@modal.asgi_app()
def fastapi_app():
    """Deploy FastAPI app as Modal web endpoint."""
    return web_app


# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(web_app, host="0.0.0.0", port=8000)
