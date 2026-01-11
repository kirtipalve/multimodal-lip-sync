"""
Wav2Lip GPU Inference on Modal
This module handles the GPU-bound lip-sync inference using Wav2Lip model.

Author: Kirti Palve
"""

import modal
import os
import subprocess
import tempfile
import uuid
from pathlib import Path

# Define the Modal image with all Wav2Lip dependencies
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
        "librosa==0.10.1",
        "scipy==1.11.1",
        "tqdm",
        "numba",
        "face-alignment",
        "facenet-pytorch",
        "batch-face",
    )
    .run_commands(
        # Clone Wav2Lip repository
        "git clone https://github.com/Rudrabha/Wav2Lip.git /app/Wav2Lip",
        # Download pre-trained models
        "mkdir -p /app/Wav2Lip/checkpoints",
        "wget -q 'https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/wav2lip_gan.pth' -O /app/Wav2Lip/checkpoints/wav2lip_gan.pth",
        "wget -q 'https://github.com/Rudrabha/Wav2Lip/releases/download/v1.0/wav2lip.pth' -O /app/Wav2Lip/checkpoints/wav2lip.pth",
        # Download face detection model
        "mkdir -p /app/Wav2Lip/face_detection/detection/sfd",
        "wget -q 'https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth' -O /app/Wav2Lip/face_detection/detection/sfd/s3fd.pth",
    )
)

# Create Modal app
app = modal.App("wav2lip-inference")

# Create a volume for storing results
results_volume = modal.Volume.from_name("wav2lip-results", create_if_missing=True)

# Dictionary to store job status (in production, use Redis or a database)
job_store = modal.Dict.from_name("wav2lip-jobs", create_if_missing=True)


@app.cls(
    image=wav2lip_image,
    gpu="T4",  # Can be changed to "A10G" or "A100" for better performance
    timeout=600,  # 10 minutes max
    volumes={"/results": results_volume},
)
class Wav2LipInference:
    """Wav2Lip inference class running on GPU."""
    
    @modal.enter()
    def setup(self):
        """Initialize model on container startup."""
        import sys
        sys.path.insert(0, "/app/Wav2Lip")
        
        # Pre-load the model to avoid cold start delays
        import torch
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")
        
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
        """
        Run Wav2Lip inference on video and audio.
        
        Args:
            video_bytes: Raw bytes of input video
            audio_bytes: Raw bytes of input audio
            job_id: Unique identifier for this job
            use_gan: Whether to use GAN model (better quality, slower)
            resize_factor: Resize factor for face detection
            pads: Padding for face detection [top, bottom, left, right]
            
        Returns:
            dict with status and result path
        """
        import sys
        sys.path.insert(0, "/app/Wav2Lip")
        
        import time
        start_time = time.time()
        
        try:
            # Update job status
            job_store[job_id] = {
                "status": "processing",
                "progress": "Setting up files",
                "started_at": start_time,
            }
            
            # Create temp directory for this job
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save input files
                video_path = os.path.join(temp_dir, "input_video.mp4")
                audio_path = os.path.join(temp_dir, "input_audio.wav")
                output_path = os.path.join(temp_dir, "output.mp4")
                
                with open(video_path, "wb") as f:
                    f.write(video_bytes)
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)
                
                # Select checkpoint
                checkpoint = "wav2lip_gan.pth" if use_gan else "wav2lip.pth"
                checkpoint_path = f"/app/Wav2Lip/checkpoints/{checkpoint}"
                
                job_store[job_id] = {
                    "status": "processing",
                    "progress": "Running inference",
                    "started_at": start_time,
                }
                
                # Run Wav2Lip inference
                cmd = [
                    "python", "/app/Wav2Lip/inference.py",
                    "--checkpoint_path", checkpoint_path,
                    "--face", video_path,
                    "--audio", audio_path,
                    "--outfile", output_path,
                    "--resize_factor", str(resize_factor),
                    "--pads", str(pads[0]), str(pads[1]), str(pads[2]), str(pads[3]),
                    "--nosmooth",  # Disable smoothing for faster inference
                ]
                
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd="/app/Wav2Lip",
                )
                
                if result.returncode != 0:
                    raise Exception(f"Wav2Lip failed: {result.stderr}")
                
                # Read output and save to volume
                if os.path.exists(output_path):
                    result_filename = f"{job_id}.mp4"
                    result_path = f"/results/{result_filename}"
                    
                    with open(output_path, "rb") as f:
                        output_bytes = f.read()
                    
                    with open(result_path, "wb") as f:
                        f.write(output_bytes)
                    
                    results_volume.commit()
                    
                    elapsed_time = time.time() - start_time
                    
                    job_store[job_id] = {
                        "status": "completed",
                        "result_path": result_filename,
                        "elapsed_time": elapsed_time,
                        "completed_at": time.time(),
                    }
                    
                    return {
                        "status": "completed",
                        "result_path": result_filename,
                        "elapsed_time": elapsed_time,
                    }
                else:
                    raise Exception("Output file not generated")
                    
        except Exception as e:
            job_store[job_id] = {
                "status": "failed",
                "error": str(e),
                "failed_at": time.time(),
            }
            return {
                "status": "failed",
                "error": str(e),
            }
    
    @modal.method()
    def get_result(self, job_id: str) -> bytes:
        """Retrieve the result video bytes for a completed job."""
        result_path = f"/results/{job_id}.mp4"
        if os.path.exists(result_path):
            with open(result_path, "rb") as f:
                return f.read()
        return None


@app.function(image=wav2lip_image)
def get_job_status(job_id: str) -> dict:
    """Get the status of a job."""
    if job_id in job_store:
        return job_store[job_id]
    return {"status": "not_found"}


@app.function(image=wav2lip_image)
def list_available_gpus() -> list:
    """List available GPU options on Modal."""
    return ["T4", "A10G", "A100-40GB", "A100-80GB", "H100"]


# For local testing
if __name__ == "__main__":
    print("Wav2Lip Inference Module")
    print("Deploy with: modal deploy inference.py")
