"""
Wav2Lip LipSync Service - Test & Benchmark Script
Part 3: Test script and benchmark runtime

Author: Kirti Palve

This script:
1. Tests lip-sync quality with sample videos
2. Benchmarks inference time across different GPU options
3. Generates a performance report
"""

import requests
import time
import json
import os
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import argparse

# ============== Configuration ==============

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""
    api_base_url: str = "https://your-workspace--wav2lip-lipsync-service-fastapi-app.modal.run"
    test_video_path: str = "test_data/sample_video.mp4"
    test_audio_path: str = "test_data/sample_audio.wav"
    output_dir: str = "benchmark_results"
    timeout: int = 300  # 5 minutes


@dataclass 
class BenchmarkResult:
    """Results from a single benchmark run."""
    gpu_type: str
    video_duration_sec: float
    inference_time_sec: float
    status: str
    error: Optional[str] = None
    
    @property
    def realtime_factor(self) -> float:
        """How many times faster than realtime."""
        if self.inference_time_sec > 0:
            return self.video_duration_sec / self.inference_time_sec
        return 0.0


# ============== API Client ==============

class LipSyncClient:
    """Client for interacting with the LipSync API."""
    
    def __init__(self, base_url: str, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    
    def health_check(self) -> bool:
        """Check if API is running."""
        try:
            resp = requests.get(f"{self.base_url}/", timeout=10)
            return resp.status_code == 200
        except Exception as e:
            print(f"Health check failed: {e}")
            return False
    
    def submit_job(
        self,
        video_path: str,
        audio_path: str,
        use_gan: bool = True,
    ) -> str:
        """Submit async lip-sync job, returns job_id."""
        with open(video_path, "rb") as vf, open(audio_path, "rb") as af:
            files = {
                "video": ("video.mp4", vf, "video/mp4"),
                "audio": ("audio.wav", af, "audio/wav"),
            }
            params = {"use_gan": use_gan}
            resp = requests.post(
                f"{self.base_url}/api/v1/jobs",
                files=files,
                params=params,
                timeout=60,
            )
        
        if resp.status_code != 200:
            raise Exception(f"Submit failed: {resp.text}")
        
        return resp.json()["job_id"]
    
    def get_status(self, job_id: str) -> dict:
        """Get job status."""
        resp = requests.get(
            f"{self.base_url}/api/v1/jobs/{job_id}",
            timeout=30,
        )
        return resp.json()
    
    def wait_for_completion(
        self,
        job_id: str,
        poll_interval: float = 2.0,
    ) -> dict:
        """Poll until job completes or fails."""
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            status = self.get_status(job_id)
            
            if status["status"] == "completed":
                return status
            elif status["status"] == "failed":
                raise Exception(f"Job failed: {status.get('error')}")
            
            print(f"  Status: {status['status']} - {status.get('progress', '')}")
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Job {job_id} timed out after {self.timeout}s")
    
    def download_result(self, job_id: str, output_path: str) -> str:
        """Download result video."""
        resp = requests.get(
            f"{self.base_url}/api/v1/jobs/{job_id}/result",
            timeout=120,
            stream=True,
        )
        
        if resp.status_code != 200:
            raise Exception(f"Download failed: {resp.text}")
        
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return output_path
    
    def sync_inference(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        use_gan: bool = True,
    ) -> float:
        """Run synchronous inference, returns elapsed time."""
        start_time = time.time()
        
        with open(video_path, "rb") as vf, open(audio_path, "rb") as af:
            files = {
                "video": ("video.mp4", vf, "video/mp4"),
                "audio": ("audio.wav", af, "audio/wav"),
            }
            params = {"use_gan": use_gan}
            resp = requests.post(
                f"{self.base_url}/api/v1/sync",
                files=files,
                params=params,
                timeout=self.timeout,
                stream=True,
            )
        
        if resp.status_code != 200:
            raise Exception(f"Sync inference failed: {resp.text}")
        
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return time.time() - start_time


# ============== Benchmark Functions ==============

def get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    import subprocess
    
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())
    except Exception:
        return 10.0  # Default assumption


def run_benchmark(
    client: LipSyncClient,
    video_path: str,
    audio_path: str,
    output_dir: str,
    use_gan: bool = True,
    gpu_type: str = "T4",
) -> BenchmarkResult:
    """Run a single benchmark test."""
    
    video_duration = get_video_duration(video_path)
    print(f"\nBenchmarking with {gpu_type} GPU")
    print(f"  Video duration: {video_duration:.2f}s")
    print(f"  Model: {'Wav2Lip-GAN' if use_gan else 'Wav2Lip'}")
    
    try:
        start_time = time.time()
        
        # Submit job
        print("  Submitting job...")
        job_id = client.submit_job(video_path, audio_path, use_gan)
        print(f"  Job ID: {job_id}")
        
        # Wait for completion
        print("  Waiting for completion...")
        status = client.wait_for_completion(job_id)
        
        inference_time = time.time() - start_time
        
        # Download result
        output_path = os.path.join(output_dir, f"result_{gpu_type}_{job_id[:8]}.mp4")
        print(f"  Downloading result to {output_path}...")
        client.download_result(job_id, output_path)
        
        result = BenchmarkResult(
            gpu_type=gpu_type,
            video_duration_sec=video_duration,
            inference_time_sec=inference_time,
            status="success",
        )
        
        print(f"  ✓ Completed in {inference_time:.2f}s")
        print(f"  ✓ Realtime factor: {result.realtime_factor:.2f}x")
        
        return result
        
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return BenchmarkResult(
            gpu_type=gpu_type,
            video_duration_sec=video_duration,
            inference_time_sec=0,
            status="failed",
            error=str(e),
        )


def run_full_benchmark(config: BenchmarkConfig) -> list[BenchmarkResult]:
    """Run benchmarks across all GPU types."""
    
    # Ensure output directory exists
    os.makedirs(config.output_dir, exist_ok=True)
    
    # Initialize client
    client = LipSyncClient(config.api_base_url, config.timeout)
    
    # Check health
    print("Checking API health...")
    if not client.health_check():
        print("ERROR: API is not responding")
        return []
    print("API is healthy!\n")
    
    results = []
    
    # Note: To benchmark different GPUs, you'd need to deploy
    # separate Modal apps with different GPU configurations
    # For this script, we benchmark the default deployment
    
    # Test with GAN model
    result = run_benchmark(
        client=client,
        video_path=config.test_video_path,
        audio_path=config.test_audio_path,
        output_dir=config.output_dir,
        use_gan=True,
        gpu_type="T4-GAN",
    )
    results.append(result)
    
    # Test without GAN model (faster, lower quality)
    result = run_benchmark(
        client=client,
        video_path=config.test_video_path,
        audio_path=config.test_audio_path,
        output_dir=config.output_dir,
        use_gan=False,
        gpu_type="T4-Base",
    )
    results.append(result)
    
    return results


def generate_report(results: list[BenchmarkResult], output_path: str):
    """Generate benchmark report."""
    
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_tests": len(results),
            "successful": sum(1 for r in results if r.status == "success"),
            "failed": sum(1 for r in results if r.status == "failed"),
        },
        "results": [
            {
                "gpu_type": r.gpu_type,
                "video_duration_sec": r.video_duration_sec,
                "inference_time_sec": r.inference_time_sec,
                "realtime_factor": r.realtime_factor,
                "status": r.status,
                "error": r.error,
            }
            for r in results
        ],
        "recommendations": [],
    }
    
    # Add recommendations based on results
    successful = [r for r in results if r.status == "success"]
    if successful:
        fastest = min(successful, key=lambda r: r.inference_time_sec)
        report["recommendations"].append(
            f"Fastest configuration: {fastest.gpu_type} "
            f"({fastest.inference_time_sec:.2f}s, {fastest.realtime_factor:.2f}x realtime)"
        )
    
    # Save report
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to {output_path}")
    
    # Print summary
    print("\n" + "="*50)
    print("BENCHMARK SUMMARY")
    print("="*50)
    
    for r in results:
        status_icon = "✓" if r.status == "success" else "✗"
        print(f"{status_icon} {r.gpu_type}: {r.inference_time_sec:.2f}s ({r.realtime_factor:.2f}x realtime)")
    
    return report


# ============== Test Functions ==============

def qualitative_test(
    client: LipSyncClient,
    test_cases: list[dict],
    output_dir: str,
):
    """
    Run qualitative tests on various video types.
    
    Test cases should be a list of dicts with:
    - name: Test case name
    - video_path: Path to test video
    - audio_path: Path to test audio
    - description: What we're testing
    """
    
    print("\n" + "="*50)
    print("QUALITATIVE TESTING")
    print("="*50)
    
    results = []
    
    for i, tc in enumerate(test_cases):
        print(f"\nTest {i+1}: {tc['name']}")
        print(f"  Description: {tc['description']}")
        
        try:
            job_id = client.submit_job(tc["video_path"], tc["audio_path"])
            status = client.wait_for_completion(job_id)
            
            output_path = os.path.join(output_dir, f"test_{i+1}_{tc['name']}.mp4")
            client.download_result(job_id, output_path)
            
            results.append({
                "name": tc["name"],
                "status": "success",
                "output": output_path,
                "notes": "Review manually for lip-sync quality",
            })
            
            print(f"  ✓ Output saved to {output_path}")
            
        except Exception as e:
            results.append({
                "name": tc["name"],
                "status": "failed",
                "error": str(e),
            })
            print(f"  ✗ Failed: {e}")
    
    return results


# ============== Main ==============

def create_sample_test_data():
    """Instructions for creating test data."""
    print("""
    ============================================
    TEST DATA SETUP
    ============================================
    
    Create a 'test_data' directory with:
    
    1. sample_video.mp4 - A video with a clear face
       - Can be from YouTube (download with yt-dlp)
       - Self-recorded video works great
       - 5-15 seconds is ideal for testing
    
    2. sample_audio.wav - Audio to lip-sync to
       - Speech works best
       - Match approximate length to video
       - Can use text-to-speech for consistent testing
    
    Example commands:
    
    # Download a YouTube clip (requires yt-dlp)
    yt-dlp -f 'best[height<=720]' -o 'test_data/sample_video.mp4' 'YOUTUBE_URL'
    
    # Extract audio from a video
    ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 test_data/sample_audio.wav
    
    # Generate TTS audio (requires edge-tts)
    edge-tts --text "Hello, this is a test of the lip sync system." -o test_data/sample_audio.wav
    """)


def main():
    parser = argparse.ArgumentParser(description="Wav2Lip Benchmark & Test Script")
    parser.add_argument("--api-url", required=True, help="Base URL of deployed API")
    parser.add_argument("--video", default="test_data/sample_video.mp4", help="Test video path")
    parser.add_argument("--audio", default="test_data/sample_audio.wav", help="Test audio path")
    parser.add_argument("--output-dir", default="benchmark_results", help="Output directory")
    parser.add_argument("--setup", action="store_true", help="Show test data setup instructions")
    
    args = parser.parse_args()
    
    if args.setup:
        create_sample_test_data()
        return
    
    # Validate inputs
    if not os.path.exists(args.video):
        print(f"ERROR: Video file not found: {args.video}")
        print("Run with --setup for instructions on creating test data")
        return
    
    if not os.path.exists(args.audio):
        print(f"ERROR: Audio file not found: {args.audio}")
        print("Run with --setup for instructions on creating test data")
        return
    
    # Run benchmarks
    config = BenchmarkConfig(
        api_base_url=args.api_url,
        test_video_path=args.video,
        test_audio_path=args.audio,
        output_dir=args.output_dir,
    )
    
    results = run_full_benchmark(config)
    
    if results:
        report_path = os.path.join(args.output_dir, "benchmark_report.json")
        generate_report(results, report_path)


if __name__ == "__main__":
    main()
