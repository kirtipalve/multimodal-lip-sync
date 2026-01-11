"""
Multi-GPU Deployment Configuration for Benchmarking
Deploy separate endpoints with different GPU types to compare performance.

Author: Kirti Palve

Usage:
    modal deploy gpu_variants.py

This creates separate endpoints for each GPU type for fair comparison.
"""

import modal
import subprocess
import tempfile
import os
import time
import uuid

# Shared image definition
wav2lip_image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsm6", "libxext6", "libxrender-dev", "libglib2.0-0", "wget")
    .pip_install(
        "torch==2.0.1", "torchvision==0.15.2", "torchaudio==2.0.2",
        "numpy==1.24.3", "opencv-python-headless==4.8.0.74",
        "librosa==0.10.1", "scipy==1.11.1", "tqdm", "numba",
        "face-alignment", "facenet-pytorch", "batch-face",
        "fastapi", "python-multipart", "pydantic",
    )
    .run_commands(
        "git clone https://github.com/Rudrabha/Wav2Lip.git /app/Wav2Lip",
        "mkdir -p /app/Wav2Lip/checkpoints",
        "wget -q 'https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/wav2lip_gan.pth' -O /app/Wav2Lip/checkpoints/wav2lip_gan.pth || true",
        "mkdir -p /app/Wav2Lip/face_detection/detection/sfd",
        "wget -q 'https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth' -O /app/Wav2Lip/face_detection/detection/sfd/s3fd.pth || true",
    )
)

app = modal.App("wav2lip-gpu-benchmark")
results_volume = modal.Volume.from_name("wav2lip-benchmark-results", create_if_missing=True)


def run_wav2lip_inference(video_bytes: bytes, audio_bytes: bytes, job_id: str, gpu_type: str) -> dict:
    """Common inference logic."""
    import sys
    sys.path.insert(0, "/app/Wav2Lip")
    
    start_time = time.time()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        video_path = os.path.join(temp_dir, "input.mp4")
        audio_path = os.path.join(temp_dir, "input.wav")
        output_path = os.path.join(temp_dir, "output.mp4")
        
        with open(video_path, "wb") as f:
            f.write(video_bytes)
        with open(audio_path, "wb") as f:
            f.write(audio_bytes)
        
        cmd = [
            "python", "/app/Wav2Lip/inference.py",
            "--checkpoint_path", "/app/Wav2Lip/checkpoints/wav2lip_gan.pth",
            "--face", video_path,
            "--audio", audio_path,
            "--outfile", output_path,
            "--resize_factor", "1",
            "--pads", "0", "10", "0", "0",
            "--nosmooth",
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd="/app/Wav2Lip")
        
        inference_time = time.time() - start_time
        
        if result.returncode != 0 or not os.path.exists(output_path):
            return {
                "status": "failed",
                "error": result.stderr,
                "gpu_type": gpu_type,
                "inference_time": inference_time,
            }
        
        result_path = f"/results/{job_id}_{gpu_type}.mp4"
        with open(output_path, "rb") as f:
            with open(result_path, "wb") as out:
                out.write(f.read())
        
        results_volume.commit()
        
        return {
            "status": "completed",
            "gpu_type": gpu_type,
            "inference_time": inference_time,
            "result_file": f"{job_id}_{gpu_type}.mp4",
        }


# ============== T4 GPU Variant ==============

@app.cls(image=wav2lip_image, gpu="T4", timeout=600, volumes={"/results": results_volume})
class Wav2LipT4:
    @modal.method()
    def inference(self, video_bytes: bytes, audio_bytes: bytes, job_id: str) -> dict:
        return run_wav2lip_inference(video_bytes, audio_bytes, job_id, "T4")


# ============== A10G GPU Variant ==============

@app.cls(image=wav2lip_image, gpu="A10G", timeout=600, volumes={"/results": results_volume})
class Wav2LipA10G:
    @modal.method()
    def inference(self, video_bytes: bytes, audio_bytes: bytes, job_id: str) -> dict:
        return run_wav2lip_inference(video_bytes, audio_bytes, job_id, "A10G")


# ============== A100 GPU Variant ==============

@app.cls(image=wav2lip_image, gpu="A100", timeout=600, volumes={"/results": results_volume})
class Wav2LipA100:
    @modal.method()
    def inference(self, video_bytes: bytes, audio_bytes: bytes, job_id: str) -> dict:
        return run_wav2lip_inference(video_bytes, audio_bytes, job_id, "A100")


# ============== Benchmark Orchestrator ==============

@app.function(image=wav2lip_image, timeout=1800)
def run_gpu_comparison(video_bytes: bytes, audio_bytes: bytes) -> dict:
    """
    Run the same inference across all GPU types and compare.
    Returns timing comparison.
    """
    job_id = str(uuid.uuid4())[:8]
    
    results = {}
    
    # Run on each GPU type
    print("Running on T4...")
    results["T4"] = Wav2LipT4().inference.remote(video_bytes, audio_bytes, job_id)
    
    print("Running on A10G...")
    results["A10G"] = Wav2LipA10G().inference.remote(video_bytes, audio_bytes, job_id)
    
    print("Running on A100...")
    results["A100"] = Wav2LipA100().inference.remote(video_bytes, audio_bytes, job_id)
    
    # Compile comparison
    comparison = {
        "job_id": job_id,
        "results": results,
        "fastest": min(
            [(k, v["inference_time"]) for k, v in results.items() if v["status"] == "completed"],
            key=lambda x: x[1],
            default=("none", 0)
        )[0],
        "timing_comparison": {
            k: v["inference_time"] for k, v in results.items() if v["status"] == "completed"
        }
    }
    
    return comparison


# ============== FastAPI for Benchmark ==============

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

benchmark_app = FastAPI(title="GPU Benchmark API")


@benchmark_app.post("/benchmark")
async def benchmark_all_gpus(
    video: UploadFile = File(...),
    audio: UploadFile = File(...),
):
    """Run inference on all GPU types and return comparison."""
    video_bytes = await video.read()
    audio_bytes = await audio.read()
    
    comparison = run_gpu_comparison.remote(video_bytes, audio_bytes)
    
    return JSONResponse(content=comparison)


@benchmark_app.post("/benchmark/{gpu_type}")
async def benchmark_single_gpu(
    gpu_type: str,
    video: UploadFile = File(...),
    audio: UploadFile = File(...),
):
    """Run inference on specific GPU type."""
    video_bytes = await video.read()
    audio_bytes = await audio.read()
    job_id = str(uuid.uuid4())[:8]
    
    if gpu_type.upper() == "T4":
        result = Wav2LipT4().inference.remote(video_bytes, audio_bytes, job_id)
    elif gpu_type.upper() == "A10G":
        result = Wav2LipA10G().inference.remote(video_bytes, audio_bytes, job_id)
    elif gpu_type.upper() == "A100":
        result = Wav2LipA100().inference.remote(video_bytes, audio_bytes, job_id)
    else:
        return JSONResponse(
            status_code=400,
            content={"error": f"Unknown GPU type: {gpu_type}. Use T4, A10G, or A100"}
        )
    
    return JSONResponse(content=result)


@app.function(image=wav2lip_image)
@modal.asgi_app()
def benchmark_api():
    return benchmark_app


if __name__ == "__main__":
    print("""
    GPU Benchmark Deployment
    ========================
    
    Deploy: modal deploy gpu_variants.py
    
    This creates endpoints for testing different GPUs:
    - POST /benchmark - Compare all GPUs
    - POST /benchmark/t4 - Test T4 only
    - POST /benchmark/a10g - Test A10G only  
    - POST /benchmark/a100 - Test A100 only
    
    Note: A100 costs significantly more than T4/A10G.
    Monitor your Modal usage carefully.
    """)
