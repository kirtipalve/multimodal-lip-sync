"""
GPU Performance Comparison Script
Tests inference time across different Modal GPU types

Author: Kirti Palve

This script:
1. Tests the same video/audio on different GPU configurations
2. Measures inference time for each GPU
3. Calculates cost per inference
4. Generates comparison report
"""

import requests
import time
import json
import sys
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

# Modal GPU pricing (as of Dec 2024)
GPU_PRICING = {
    "T4": 0.000166,      # $/second
    "A10G": 0.000300,    # $/second
    "A100": 0.001150,    # $/second
}

@dataclass
class GPUTestResult:
    """Results from a single GPU test."""
    gpu_type: str
    video_file: str
    audio_file: str
    video_duration: float
    use_gan: bool
    resize_factor: int

    # Results
    job_id: str
    status: str
    inference_time: Optional[float] = None  # seconds
    total_wait_time: Optional[float] = None  # includes queue time
    error: Optional[str] = None
    error_type: Optional[str] = None

    # Calculated metrics
    realtime_factor: Optional[float] = None  # inference_time / video_duration
    cost_per_job: Optional[float] = None     # estimated cost in USD
    fps_equivalent: Optional[float] = None    # video_duration / inference_time

    def calculate_metrics(self):
        """Calculate derived performance metrics."""
        if self.inference_time and self.video_duration:
            self.realtime_factor = self.inference_time / self.video_duration
            self.fps_equivalent = self.video_duration / self.inference_time

        if self.inference_time and self.gpu_type in GPU_PRICING:
            self.cost_per_job = self.inference_time * GPU_PRICING[self.gpu_type]


class GPUComparison:
    """Compares inference performance across different GPUs."""

    def __init__(self, api_url: str):
        self.api_url = api_url
        self.results: List[GPUTestResult] = []

    def test_gpu(
        self,
        gpu_type: str,
        video_path: Path,
        audio_path: Path,
        video_duration: float,
        use_gan: bool = True,
        resize_factor: int = 1,
    ) -> GPUTestResult:
        """Test a specific GPU configuration."""

        print(f"\n{'='*70}")
        print(f"Testing: {gpu_type} GPU")
        print(f"{'='*70}")
        print(f"Video: {video_path.name}")
        print(f"Audio: {audio_path.name}")
        print(f"Model: {'Wav2Lip-GAN' if use_gan else 'Wav2Lip-Base'}")
        print(f"Resize Factor: {resize_factor}")
        print("")

        result = GPUTestResult(
            gpu_type=gpu_type,
            video_file=str(video_path),
            audio_file=str(audio_path),
            video_duration=video_duration,
            use_gan=use_gan,
            resize_factor=resize_factor,
            job_id="",
            status="pending",
        )

        # Submit job
        print("📤 Submitting job...")
        start_time = time.time()

        try:
            with open(video_path, "rb") as vf:
                with open(audio_path, "rb") as af:
                    files = {
                        "video": (video_path.name, vf, "video/mp4"),
                        "audio": (audio_path.name, af, "audio/wav"),
                    }
                    params = {
                        "use_gan": use_gan,
                        "resize_factor": resize_factor,
                    }

                    resp = requests.post(
                        f"{self.api_url}/api/v1/jobs",
                        files=files,
                        params=params,
                        timeout=60,
                    )

            if resp.status_code != 200:
                result.status = "failed"
                result.error = f"Job submission failed: {resp.status_code} - {resp.text}"
                return result

            job_data = resp.json()
            result.job_id = job_data["job_id"]
            print(f"✅ Job submitted: {result.job_id}")
            print("")

            # Poll for completion
            print("⏳ Waiting for completion...")
            poll_count = 0

            while True:
                time.sleep(3)
                poll_count += 1

                resp = requests.get(
                    f"{self.api_url}/api/v1/jobs/{result.job_id}",
                    timeout=30
                )
                status_data = resp.json()

                status = status_data["status"]
                progress = status_data.get("progress", "")

                # Show progress every 5 polls
                if poll_count % 5 == 0 or status in ["completed", "failed"]:
                    print(f"   [{poll_count}] {status} - {progress}")

                if status == "completed":
                    result.status = "completed"
                    result.inference_time = status_data.get("elapsed_time", 0)
                    result.total_wait_time = time.time() - start_time
                    result.calculate_metrics()

                    print(f"\n✅ COMPLETED")
                    print(f"   Inference time: {result.inference_time:.2f}s")
                    print(f"   Total wait time: {result.total_wait_time:.2f}s")
                    print(f"   Realtime factor: {result.realtime_factor:.3f}x")
                    print(f"   Cost: ${result.cost_per_job:.4f}")
                    break

                elif status == "failed":
                    result.status = "failed"
                    result.error = status_data.get("error", "Unknown error")
                    result.error_type = status_data.get("error_type", "unknown")
                    result.total_wait_time = time.time() - start_time

                    print(f"\n❌ FAILED after {result.total_wait_time:.2f}s")
                    print(f"   Error type: {result.error_type}")
                    print(f"   Error: {result.error}")
                    break

                if poll_count > 240:  # 12 minutes timeout
                    result.status = "timeout"
                    result.error = "Timeout after 12 minutes"
                    result.total_wait_time = time.time() - start_time
                    print(f"\n⏱️  TIMEOUT after {result.total_wait_time:.2f}s")
                    break

        except Exception as e:
            result.status = "error"
            result.error = str(e)
            print(f"\n❌ ERROR: {e}")

        return result

    def run_comparison(
        self,
        video_path: Path,
        audio_path: Path,
        video_duration: float,
        gpu_types: List[str] = None,
        use_gan: bool = True,
        resize_factor: int = 1,
    ):
        """Run comparison across multiple GPUs."""

        if gpu_types is None:
            gpu_types = ["T4", "A10G", "A100"]

        print(f"\n{'='*70}")
        print("GPU PERFORMANCE COMPARISON")
        print(f"{'='*70}")
        print(f"\nTest Configuration:")
        print(f"  Video: {video_path.name} ({video_duration:.1f}s)")
        print(f"  Audio: {audio_path.name}")
        print(f"  Model: {'Wav2Lip-GAN' if use_gan else 'Wav2Lip-Base'}")
        print(f"  GPUs to test: {', '.join(gpu_types)}")
        print("")

        for gpu_type in gpu_types:
            result = self.test_gpu(
                gpu_type=gpu_type,
                video_path=video_path,
                audio_path=audio_path,
                video_duration=video_duration,
                use_gan=use_gan,
                resize_factor=resize_factor,
            )
            self.results.append(result)

            # Brief pause between tests
            if gpu_type != gpu_types[-1]:
                print("\n⏸️  Waiting 10 seconds before next test...\n")
                time.sleep(10)

    def print_summary(self):
        """Print comparison summary table."""

        print(f"\n{'='*70}")
        print("PERFORMANCE SUMMARY")
        print(f"{'='*70}\n")

        # Filter successful results
        successful = [r for r in self.results if r.status == "completed"]
        failed = [r for r in self.results if r.status != "completed"]

        if successful:
            print("✅ Successful Runs:\n")
            print(f"{'GPU':<8} {'Inference (s)':<15} {'RT Factor':<12} {'Cost ($)':<10} {'Status':<10}")
            print("-" * 70)

            for r in successful:
                print(f"{r.gpu_type:<8} {r.inference_time:<15.2f} "
                      f"{r.realtime_factor:<12.3f} ${r.cost_per_job:<9.4f} "
                      f"{r.status:<10}")

            # Speed comparison
            if len(successful) > 1:
                baseline = successful[0]
                print(f"\n📊 Speed Comparison (vs {baseline.gpu_type}):\n")

                for r in successful[1:]:
                    speedup = baseline.inference_time / r.inference_time
                    cost_ratio = r.cost_per_job / baseline.cost_per_job

                    print(f"  {r.gpu_type} vs {baseline.gpu_type}:")
                    print(f"    Speed: {speedup:.2f}x faster")
                    print(f"    Cost: {cost_ratio:.2f}x more expensive")
                    print(f"    Cost per second of video: "
                          f"${r.cost_per_job / r.video_duration:.4f} "
                          f"({baseline.gpu_type}: ${baseline.cost_per_job / baseline.video_duration:.4f})")
                    print("")

        if failed:
            print("\n❌ Failed Runs:\n")
            print(f"{'GPU':<8} {'Status':<12} {'Error':<50}")
            print("-" * 70)

            for r in failed:
                error_preview = r.error[:47] + "..." if r.error and len(r.error) > 50 else r.error
                print(f"{r.gpu_type:<8} {r.status:<12} {error_preview:<50}")

        # Recommendations
        print(f"\n{'='*70}")
        print("RECOMMENDATIONS")
        print(f"{'='*70}\n")

        if successful:
            # Find best cost-performance
            best_perf = min(successful, key=lambda r: r.inference_time)
            best_cost = min(successful, key=lambda r: r.cost_per_job)

            print(f"⚡ Fastest: {best_perf.gpu_type} ({best_perf.inference_time:.2f}s)")
            print(f"💰 Cheapest: {best_cost.gpu_type} (${best_cost.cost_per_job:.4f})")

            # Calculate cost-efficiency score (lower is better)
            for r in successful:
                r.cost_efficiency = r.cost_per_job / (1 / r.realtime_factor)

            best_efficiency = min(successful, key=lambda r: r.cost_efficiency)
            print(f"⭐ Best Value: {best_efficiency.gpu_type}")

            print(f"\n📝 Use Case Recommendations:")
            print(f"  • Development/Testing: {best_cost.gpu_type}")
            print(f"  • Production (speed): {best_perf.gpu_type}")
            print(f"  • Production (cost): {best_efficiency.gpu_type}")

    def save_report(self, output_path: Path):
        """Save detailed JSON report."""

        report = {
            "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "api_url": self.api_url,
            "results": [asdict(r) for r in self.results],
            "gpu_pricing": GPU_PRICING,
        }

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n💾 Detailed report saved: {output_path}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Compare GPU performance for Wav2Lip inference"
    )
    parser.add_argument(
        "--api-url",
        default="https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run",
        help="Modal API URL"
    )
    parser.add_argument(
        "--video",
        required=True,
        help="Path to test video"
    )
    parser.add_argument(
        "--audio",
        required=True,
        help="Path to test audio"
    )
    parser.add_argument(
        "--duration",
        type=float,
        required=True,
        help="Video duration in seconds"
    )
    parser.add_argument(
        "--gpus",
        nargs="+",
        default=["T4", "A10G", "A100"],
        help="GPU types to test (default: T4 A10G A100)"
    )
    parser.add_argument(
        "--use-gan",
        action="store_true",
        default=True,
        help="Use GAN model (default: True)"
    )
    parser.add_argument(
        "--resize-factor",
        type=int,
        default=1,
        help="Face detection resize factor (default: 1)"
    )
    parser.add_argument(
        "--output",
        default="gpu_comparison_results/gpu_comparison_report.json",
        help="Output JSON report path"
    )

    args = parser.parse_args()

    # Validate files
    video_path = Path(args.video)
    audio_path = Path(args.audio)

    if not video_path.exists():
        print(f"❌ Video file not found: {video_path}")
        sys.exit(1)

    if not audio_path.exists():
        print(f"❌ Audio file not found: {audio_path}")
        sys.exit(1)

    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Run comparison
    comparison = GPUComparison(args.api_url)

    comparison.run_comparison(
        video_path=video_path,
        audio_path=audio_path,
        video_duration=args.duration,
        gpu_types=args.gpus,
        use_gan=args.use_gan,
        resize_factor=args.resize_factor,
    )

    # Print summary
    comparison.print_summary()

    # Save report
    comparison.save_report(output_path)

    print(f"\n{'='*70}")
    print("GPU COMPARISON COMPLETE!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
