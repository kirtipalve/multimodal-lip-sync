"""
Wav2Lip LipSync Service - Main Entry Point
Unified Modal app combining GPU inference and FastAPI endpoints.

Author: Kirti Palve
Deploy with: modal deploy main.py
Run locally: modal serve main.py
"""

import modal
import os
import subprocess
import tempfile
import uuid
import io
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ============== Modal Setup ==============

# Define the GPU inference image with all Wav2Lip dependencies
wav2lip_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install(
        "git",
        "ffmpeg",
        "libsm6",
        "libxext6",
        "libxrender-dev",
        "libglib2.0-0",
        "wget",
    )
    .pip_install(
        "torch==2.0.1",
        "torchvision==0.15.2",
        "torchaudio==2.0.2",
        "numpy==1.24.3",
        "opencv-python-headless==4.8.0.74",
        "librosa==0.9.2",
        "scipy==1.11.1",
        "tqdm",
        "numba",
        "face-alignment",
        "facenet-pytorch",
        "batch-face",
        "fastapi",
        "python-multipart",
        "pydantic",
        "huggingface_hub",
    )
    .run_commands(
        # Clone Wav2Lip repository
        "git clone https://github.com/Rudrabha/Wav2Lip.git /app/Wav2Lip",
        "mkdir -p /app/Wav2Lip/checkpoints",
        "mkdir -p /app/Wav2Lip/face_detection/detection/sfd",
        # Download models using wget from Hugging Face
        "wget -O /app/Wav2Lip/checkpoints/wav2lip_gan.pth https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip_gan.pth",
        "wget -O /app/Wav2Lip/checkpoints/wav2lip.pth https://huggingface.co/Nekochu/Wav2Lip/resolve/main/wav2lip.pth",
        "wget -O /app/Wav2Lip/face_detection/detection/sfd/s3fd.pth https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth",
        # Verify downloads
        "ls -lh /app/Wav2Lip/checkpoints/ /app/Wav2Lip/face_detection/detection/sfd/",
    )
)

# Create Modal app
app = modal.App("wav2lip-lipsync-service")

# Create volumes for persistent storage
results_volume = modal.Volume.from_name("wav2lip-results", create_if_missing=True)

# Job status dictionary (persisted across function calls)
job_store = modal.Dict.from_name("wav2lip-jobs", create_if_missing=True)


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
    download_url: Optional[str] = None


# ============== GPU Inference Class ==============

@app.cls(
    image=wav2lip_image,
    gpu="A10G",  # Options: "T4", "A10G", "A100"
    timeout=600,
    volumes={"/results": results_volume},
    scaledown_window=120,  # Keep warm for 2 minutes
)
class Wav2LipInference:
    """GPU-accelerated Wav2Lip inference."""

    @modal.enter()
    def setup(self):
        """Initialize on container startup."""
        import sys
        sys.path.insert(0, "/app/Wav2Lip")
        import torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Wav2Lip inference ready on {self.device}")

    @modal.method()
    def run_inference(
        self,
        video_bytes: bytes,
        audio_bytes: bytes,
        job_id: str,
        use_gan: bool = True,
        resize_factor: int = 1,
        pads: list = [0, 10, 0, 0],
    ) -> dict:
        """Run Wav2Lip lip-sync inference with comprehensive error handling."""
        import sys
        sys.path.insert(0, "/app/Wav2Lip")
        import time
        import cv2

        start_time = time.time()

        try:
            job_store[job_id] = {
                "status": "processing",
                "progress": "Validating input files",
                "started_at": start_time,
            }

            with tempfile.TemporaryDirectory() as temp_dir:
                video_path = os.path.join(temp_dir, "input.mp4")
                audio_path = os.path.join(temp_dir, "input.wav")
                output_path = os.path.join(temp_dir, "output.mp4")

                # Write input files
                with open(video_path, "wb") as f:
                    f.write(video_bytes)
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)

                # Validate video file
                video = cv2.VideoCapture(video_path)
                if not video.isOpened():
                    raise ValueError("Invalid video file: Unable to open video. Please ensure the file is a valid video format (mp4, avi, mov).")

                fps = video.get(cv2.CAP_PROP_FPS)
                frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
                video.release()

                if frame_count == 0:
                    raise ValueError("Invalid video file: Video has no frames.")
                if fps <= 0:
                    raise ValueError("Invalid video file: Video has invalid frame rate.")

                # Validate audio file
                import librosa
                try:
                    audio_data, sr = librosa.load(audio_path, sr=None)
                    if len(audio_data) == 0:
                        raise ValueError("Invalid audio file: Audio file is empty.")
                except Exception as audio_error:
                    raise ValueError(f"Invalid audio file: {str(audio_error)}")

                job_store[job_id] = {
                    "status": "processing",
                    "progress": "Running lip-sync inference",
                    "started_at": start_time,
                }

                checkpoint = "wav2lip_gan.pth" if use_gan else "wav2lip.pth"
                checkpoint_path = f"/app/Wav2Lip/checkpoints/{checkpoint}"

                cmd = [
                    "python", "/app/Wav2Lip/inference.py",
                    "--checkpoint_path", checkpoint_path,
                    "--face", video_path,
                    "--audio", audio_path,
                    "--outfile", output_path,
                    "--resize_factor", str(resize_factor),
                    "--pads", str(pads[0]), str(pads[1]), str(pads[2]), str(pads[3]),
                    "--nosmooth",
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd="/app/Wav2Lip",
                )

                if result.returncode != 0:
                    error_msg = result.stderr.lower()

                    # Parse common errors and provide helpful messages
                    if "no face" in error_msg or "face not detected" in error_msg:
                        # Check if it's partial face detection (face present in some frames only)
                        if "some frames" in error_msg or "intermittent" in error_msg or "lost track" in error_msg:
                            raise ValueError(
                                "Face detected only in some frames. Please ensure:\n"
                                "1. Face remains visible throughout the entire video\n"
                                "2. Avoid side angles, head turns, or occlusions\n"
                                "3. Keep consistent lighting throughout the video\n"
                                "4. Try increasing --resize_factor to 2 or 4 for better tracking\n"
                                "5. Consider trimming video to sections with continuous face visibility"
                            )
                        else:
                            raise ValueError(
                                "No face detected in video. Please ensure:\n"
                                "1. Video contains a clear, front-facing face\n"
                                "2. Face is well-lit and clearly visible\n"
                                "3. Try increasing --resize_factor parameter (e.g., 2 or 4)"
                            )
                    elif "multiple faces" in error_msg:
                        raise ValueError(
                            "Multiple faces detected in video. Wav2Lip works best with:\n"
                            "1. Single person videos\n"
                            "2. Clear, unobstructed face throughout the video\n"
                            "Consider cropping video to focus on one person."
                        )
                    elif "out of memory" in error_msg or "oom" in error_msg:
                        raise ValueError(
                            "Out of memory error. Try:\n"
                            "1. Using a shorter video\n"
                            "2. Reducing video resolution\n"
                            "3. Using --use_gan=false for lower memory usage"
                        )
                    elif "invalid" in error_msg or "corrupt" in error_msg:
                        raise ValueError(
                            "Invalid or corrupted input files. Please check:\n"
                            "1. Video file is not corrupted\n"
                            "2. Audio file is valid WAV or MP3\n"
                            "3. Files are not password-protected or encrypted"
                        )
                    else:
                        raise Exception(f"Inference failed: {result.stderr}")

                if os.path.exists(output_path):
                    # Verify output file is valid
                    output_size = os.path.getsize(output_path)
                    if output_size == 0:
                        raise Exception("Generated output file is empty")

                    result_filename = f"{job_id}.mp4"
                    result_path = f"/results/{result_filename}"

                    with open(output_path, "rb") as f:
                        with open(result_path, "wb") as out:
                            out.write(f.read())

                    results_volume.commit()
                    elapsed_time = time.time() - start_time

                    job_store[job_id] = {
                        "status": "completed",
                        "result_file": result_filename,
                        "elapsed_time": elapsed_time,
                        "completed_at": time.time(),
                    }

                    return {"status": "completed", "elapsed_time": elapsed_time}
                else:
                    raise Exception("Output file not generated")

        except ValueError as ve:
            # User input errors
            job_store[job_id] = {
                "status": "failed",
                "error": str(ve),
                "error_type": "validation_error",
                "failed_at": time.time(),
            }
            return {"status": "failed", "error": str(ve), "error_type": "validation_error"}
        except Exception as e:
            # System/unknown errors
            job_store[job_id] = {
                "status": "failed",
                "error": str(e),
                "error_type": "system_error",
                "failed_at": time.time(),
            }
            return {"status": "failed", "error": str(e), "error_type": "system_error"}

    @modal.method()
    def get_result_bytes(self, job_id: str) -> bytes:
        """Get result video bytes."""
        result_path = f"/results/{job_id}.mp4"
        if os.path.exists(result_path):
            with open(result_path, "rb") as f:
                return f.read()
        return None


# ============== FastAPI Web App ==============

web_app = FastAPI(
    title="Wav2Lip LipSync API",
    description="Generate lip-synced videos from face video and audio input",
    version="1.0.0",
)

# Add CORS for frontend integration
web_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@web_app.get("/")
async def root():
    """API root - health check."""
    return {
        "service": "Wav2Lip LipSync API",
        "status": "running",
        "endpoints": {
            "submit_async": "POST /api/v1/jobs",
            "get_status": "GET /api/v1/jobs/{job_id}",
            "get_result": "GET /api/v1/jobs/{job_id}/result",
            "sync_inference": "POST /api/v1/sync",
        }
    }


@web_app.post("/api/v1/jobs", response_model=JobSubmitResponse)
async def submit_job(
    video: UploadFile = File(..., description="Face video (mp4, avi, mov)"),
    audio: UploadFile = File(..., description="Audio file (wav, mp3)"),
    use_gan: bool = True,
    resize_factor: int = 1,
):
    """
    Submit async lip-sync job.

    Returns job_id for status polling. Best for videos > 30 seconds.
    """
    video_bytes = await video.read()
    audio_bytes = await audio.read()

    # Validate sizes
    if len(video_bytes) > 100 * 1024 * 1024:
        raise HTTPException(400, "Video too large (max 100MB)")
    if len(audio_bytes) > 50 * 1024 * 1024:
        raise HTTPException(400, "Audio too large (max 50MB)")

    job_id = str(uuid.uuid4())

    job_store[job_id] = {
        "status": "queued",
        "progress": "Waiting for GPU",
    }

    # Spawn async inference
    Wav2LipInference().run_inference.spawn(
        video_bytes=video_bytes,
        audio_bytes=audio_bytes,
        job_id=job_id,
        use_gan=use_gan,
        resize_factor=resize_factor,
        pads=[0, 10, 0, 0],
    )

    return JobSubmitResponse(
        job_id=job_id,
        status="queued",
        message=f"Job queued. Poll GET /api/v1/jobs/{job_id} for status.",
    )


@web_app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Get job status and progress."""
    if job_id not in job_store:
        raise HTTPException(404, "Job not found")

    status = job_store[job_id]
    download_url = None

    if status.get("status") == "completed":
        download_url = f"/api/v1/jobs/{job_id}/result"

    return JobStatusResponse(
        job_id=job_id,
        status=status.get("status", "unknown"),
        progress=status.get("progress"),
        elapsed_time=status.get("elapsed_time"),
        error=status.get("error"),
        download_url=download_url,
    )


@web_app.get("/api/v1/jobs/{job_id}/result")
async def download_result(job_id: str):
    """Download completed result video."""
    if job_id not in job_store:
        raise HTTPException(404, "Job not found")

    status = job_store[job_id]
    if status.get("status") != "completed":
        raise HTTPException(400, f"Job not ready: {status.get('status')}")

    video_bytes = Wav2LipInference().get_result_bytes.remote(job_id)

    if not video_bytes:
        raise HTTPException(404, "Result file not found")

    return StreamingResponse(
        io.BytesIO(video_bytes),
        media_type="video/mp4",
        headers={"Content-Disposition": f"attachment; filename=lipsync_{job_id}.mp4"}
    )


@web_app.post("/api/v1/sync")
async def sync_inference(
    video: UploadFile = File(...),
    audio: UploadFile = File(...),
    use_gan: bool = True,
):
    """
    Synchronous inference - waits for completion.

    Best for short videos (< 30 seconds). May timeout for longer content.
    """
    video_bytes = await video.read()
    audio_bytes = await audio.read()

    job_id = str(uuid.uuid4())

    result = Wav2LipInference().run_inference.remote(
        video_bytes=video_bytes,
        audio_bytes=audio_bytes,
        job_id=job_id,
        use_gan=use_gan,
        resize_factor=1,
        pads=[0, 10, 0, 0],
    )

    if result["status"] == "failed":
        raise HTTPException(500, result.get("error", "Inference failed"))

    video_bytes = Wav2LipInference().get_result_bytes.remote(job_id)

    return StreamingResponse(
        io.BytesIO(video_bytes),
        media_type="video/mp4",
        headers={"Content-Disposition": f"attachment; filename=lipsync_{job_id}.mp4"}
    )


# ============== Modal ASGI Entrypoint ==============

@app.function(image=wav2lip_image)
@modal.asgi_app()
def fastapi_app():
    """Deploy FastAPI as Modal web endpoint."""
    return web_app


# ============== CLI Entry ==============

if __name__ == "__main__":
    print("""
    Wav2Lip LipSync Service
    =======================

    Commands:
      modal serve main.py    # Run locally with hot-reload
      modal deploy main.py   # Deploy to Modal cloud

    After deployment, you'll get a URL like:
      https://your-workspace--wav2lip-lipsync-service-fastapi-app.modal.run

    API Endpoints:
      POST /api/v1/jobs      - Submit async job
      GET  /api/v1/jobs/{id} - Check job status
      GET  /api/v1/jobs/{id}/result - Download result
      POST /api/v1/sync      - Synchronous inference
    """)
