"""
GPU Performance Comparison Script
Tests Wav2Lip inference across different GPU types with multiple test videos

Author: Kirti Palve

This script:
1. Tests inference on T4, A10G, and A100 GPUs
2. Measures processing time for each video
3. Calculates cost estimates
4. Performs qualitative evaluation
5. Generates comprehensive comparison report
"""

import requests
import time
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import argparse
from datetime import datetime

@dataclass
class TestVideo:
    """Test video configuration."""
    name: str
    category: str  # 'normal', 'synthetic', 'edge_case'
    video_path: str
    audio_path: str
    description: str
    expected_challenges: List[str]

@dataclass
class GPUConfig:
    """GPU configuration for testing."""
    name: str
    api_url: str
    cost_per_hour: float  # USD
    vram_gb: int

@dataclass
class InferenceResult:
    """Results from a single inference run."""
    video_name: str
    gpu_name: str
    status: str
    inference_time: float
    video_duration: float
    realtime_factor: float
    cost_estimate: float
    job_id: str
    error: Optional[str] = None
    error_type: Optional[str] = None

@dataclass
class QualitativeScore:
    """Qualitative evaluation scores."""
    lip_sync_accuracy: int  # 1-5
    visual_quality: int  # 1-5
    naturalness: int  # 1-5
    artifacts: int  # 1-5 (5 = no artifacts)
    overall: float
    notes: str

class GPUComparison:
    """Compare Wav2Lip performance across different GPUs."""

    def __init__(self, output_dir: str = "gpu_comparison_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # GPU configurations
        self.gpus = {
            't4': GPUConfig(
                name='T4',
                api_url='https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run',
                cost_per_hour=0.60,
                vram_gb=16
            ),
            # Add more GPU configs when you deploy variants
            # 'a10g': GPUConfig(
            #     name='A10G',
            #     api_url='https://kirtipalve--wav2lip-a10g.modal.run',
            #     cost_per_hour=1.28,
            #     vram_gb=24
            # ),
        }

        # Test videos
        self.test_videos = []

    def add_test_video(self, video: TestVideo):
        """Add a test video to the comparison."""
        self.test_videos.append(video)

    def submit_job(self, api_url: str, video_path: str, audio_path: str, use_gan: bool = True) -> Dict:
        """Submit inference job to API."""
        with open(video_path, 'rb') as vf, open(audio_path, 'rb') as af:
            response = requests.post(
                f"{api_url}/api/v1/jobs",
                files={
                    'video': vf,
                    'audio': af
                },
                params={'use_gan': use_gan}
            )

        if response.status_code != 200:
            raise RuntimeError(f"Job submission failed: {response.text}")

        return response.json()

    def poll_job_status(self, api_url: str, job_id: str, timeout: int = 600) -> Dict:
        """Poll job status until completion."""
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Job {job_id} timed out after {timeout}s")

            response = requests.get(f"{api_url}/api/v1/jobs/{job_id}")

            if response.status_code != 200:
                raise RuntimeError(f"Status check failed: {response.text}")

            status_data = response.json()

            if status_data['status'] == 'completed':
                return status_data
            elif status_data['status'] == 'failed':
                return status_data

            print(f"  Status: {status_data.get('status')} - {status_data.get('progress', '')}")
            time.sleep(3)

    def download_result(self, api_url: str, job_id: str, output_path: Path):
        """Download result video."""
        response = requests.get(f"{api_url}/api/v1/jobs/{job_id}/result")

        if response.status_code != 200:
            raise RuntimeError(f"Download failed: {response.text}")

        with open(output_path, 'wb') as f:
            f.write(response.content)

        print(f"  ✅ Downloaded: {output_path}")

    def run_inference(self, gpu_config: GPUConfig, test_video: TestVideo) -> InferenceResult:
        """Run inference on specific GPU."""
        print(f"\n{'='*60}")
        print(f"Testing: {test_video.name} on {gpu_config.name}")
        print(f"{'='*60}")

        try:
            # Get video duration
            import cv2
            cap = cv2.VideoCapture(test_video.video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_duration = frame_count / fps if fps > 0 else 0
            cap.release()

            # Submit job
            print("  📤 Submitting job...")
            job_data = self.submit_job(
                gpu_config.api_url,
                test_video.video_path,
                test_video.audio_path
            )
            job_id = job_data['job_id']
            print(f"  Job ID: {job_id}")

            # Poll for completion
            start_time = time.time()
            print("  ⏳ Processing...")

            status_data = self.poll_job_status(gpu_config.api_url, job_id)

            inference_time = status_data.get('elapsed_time', time.time() - start_time)

            if status_data['status'] == 'failed':
                return InferenceResult(
                    video_name=test_video.name,
                    gpu_name=gpu_config.name,
                    status='failed',
                    inference_time=inference_time,
                    video_duration=video_duration,
                    realtime_factor=0,
                    cost_estimate=0,
                    job_id=job_id,
                    error=status_data.get('error'),
                    error_type=status_data.get('error_type')
                )

            # Calculate metrics
            realtime_factor = video_duration / inference_time if inference_time > 0 else 0
            cost_estimate = (inference_time / 3600) * gpu_config.cost_per_hour

            # Download result
            output_path = self.output_dir / f"{test_video.name}_{gpu_config.name}_result.mp4"
            self.download_result(gpu_config.api_url, job_id, output_path)

            print(f"\n  📊 Results:")
            print(f"     Processing Time: {inference_time:.2f}s")
            print(f"     Video Duration: {video_duration:.2f}s")
            print(f"     Realtime Factor: {realtime_factor:.3f}x")
            print(f"     Cost Estimate: ${cost_estimate:.4f}")

            return InferenceResult(
                video_name=test_video.name,
                gpu_name=gpu_config.name,
                status='completed',
                inference_time=inference_time,
                video_duration=video_duration,
                realtime_factor=realtime_factor,
                cost_estimate=cost_estimate,
                job_id=job_id
            )

        except Exception as e:
            print(f"  ❌ Error: {e}")
            return InferenceResult(
                video_name=test_video.name,
                gpu_name=gpu_config.name,
                status='error',
                inference_time=0,
                video_duration=0,
                realtime_factor=0,
                cost_estimate=0,
                job_id='',
                error=str(e)
            )

    def run_all_comparisons(self) -> List[InferenceResult]:
        """Run all GPU comparisons for all test videos."""
        all_results = []

        print(f"\n🚀 Starting GPU Comparison")
        print(f"   GPUs to test: {', '.join([g.name for g in self.gpus.values()])}")
        print(f"   Test videos: {len(self.test_videos)}")
        print(f"   Total tests: {len(self.gpus) * len(self.test_videos)}\n")

        for test_video in self.test_videos:
            print(f"\n{'#'*70}")
            print(f"Test Video: {test_video.name} ({test_video.category})")
            print(f"Description: {test_video.description}")
            if test_video.expected_challenges:
                print(f"Expected Challenges: {', '.join(test_video.expected_challenges)}")
            print(f"{'#'*70}")

            for gpu_key, gpu_config in self.gpus.items():
                result = self.run_inference(gpu_config, test_video)
                all_results.append(result)

                # Wait a bit between tests
                time.sleep(2)

        return all_results

    def generate_report(self, results: List[InferenceResult], qualitative_scores: Optional[Dict] = None):
        """Generate comprehensive comparison report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save raw results
        results_file = self.output_dir / f"results_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2)

        # Generate markdown report
        report_file = self.output_dir / f"GPU_COMPARISON_REPORT_{timestamp}.md"

        with open(report_file, 'w') as f:
            f.write(f"""# GPU Comparison Report - Wav2Lip Inference

**Author**: Kirti Palve
**Date**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Test Videos**: {len(self.test_videos)}
**GPUs Tested**: {', '.join(set(r.gpu_name for r in results))}

---

## Executive Summary

This report compares Wav2Lip inference performance across different GPU types using three distinct test videos representing different real-world scenarios.

### Test Videos

""")

            for video in self.test_videos:
                f.write(f"""
#### {video.name} ({video.category})
- **Description**: {video.description}
- **Expected Challenges**: {', '.join(video.expected_challenges) if video.expected_challenges else 'None'}
""")

            f.write("\n---\n\n## Performance Results\n\n")

            # Performance table
            f.write("### Inference Time Comparison\n\n")
            f.write("| Video | GPU | Duration (s) | Processing Time (s) | Realtime Factor | Cost/Video | Status |\n")
            f.write("|-------|-----|--------------|---------------------|-----------------|------------|--------|\n")

            for result in results:
                status_icon = "✅" if result.status == "completed" else "❌"
                f.write(f"| {result.video_name} | {result.gpu_name} | {result.video_duration:.1f} | "
                       f"{result.inference_time:.1f} | {result.realtime_factor:.3f}x | "
                       f"${result.cost_estimate:.4f} | {status_icon} {result.status} |\n")

            # GPU Summary
            f.write("\n### GPU Performance Summary\n\n")

            gpu_summaries = {}
            for result in results:
                if result.status == 'completed':
                    if result.gpu_name not in gpu_summaries:
                        gpu_summaries[result.gpu_name] = {
                            'times': [],
                            'costs': [],
                            'factors': []
                        }
                    gpu_summaries[result.gpu_name]['times'].append(result.inference_time)
                    gpu_summaries[result.gpu_name]['costs'].append(result.cost_estimate)
                    gpu_summaries[result.gpu_name]['factors'].append(result.realtime_factor)

            for gpu_name, data in gpu_summaries.items():
                avg_time = sum(data['times']) / len(data['times'])
                avg_cost = sum(data['costs']) / len(data['costs'])
                avg_factor = sum(data['factors']) / len(data['factors'])

                f.write(f"""
**{gpu_name}**
- Average Processing Time: {avg_time:.1f}s
- Average Cost per Video: ${avg_cost:.4f}
- Average Realtime Factor: {avg_factor:.3f}x
- Completed: {len(data['times'])}/{len(self.test_videos)} videos
""")

            # Error Analysis
            failed_results = [r for r in results if r.status != 'completed']
            if failed_results:
                f.write("\n### Error Analysis\n\n")
                for result in failed_results:
                    f.write(f"""
**{result.video_name} on {result.gpu_name}**
- Status: {result.status}
- Error Type: {result.error_type or 'N/A'}
- Error: {result.error or 'N/A'}
""")

            # Qualitative Evaluation
            if qualitative_scores:
                f.write("\n---\n\n## Qualitative Evaluation\n\n")
                f.write("*(Manual evaluation after viewing generated videos)*\n\n")
                f.write("| Video | GPU | Lip Sync | Visual Quality | Naturalness | Artifacts | Overall | Notes |\n")
                f.write("|-------|-----|----------|----------------|-------------|-----------|---------|-------|\n")

                for key, score in qualitative_scores.items():
                    f.write(f"| {score.get('video')} | {score.get('gpu')} | "
                           f"{score.get('lip_sync', 0)}/5 | {score.get('visual_quality', 0)}/5 | "
                           f"{score.get('naturalness', 0)}/5 | {score.get('artifacts', 0)}/5 | "
                           f"{score.get('overall', 0):.1f}/5 | {score.get('notes', '')} |\n")

            # Recommendations
            f.write("\n---\n\n## Recommendations\n\n")

            best_gpu = max(gpu_summaries.items(),
                          key=lambda x: sum(x[1]['factors']) / len(x[1]['factors']) if x[1]['factors'] else 0)

            f.write(f"""
### For Production Use

**Recommended GPU**: {best_gpu[0]}
- Best realtime factor among tested GPUs
- Consistent performance across test scenarios

### Cost-Benefit Analysis

""")

            for gpu_name, data in sorted(gpu_summaries.items(), key=lambda x: sum(x[1]['costs'])/len(x[1]['costs']) if x[1]['costs'] else float('inf')):
                avg_cost = sum(data['costs']) / len(data['costs'])
                avg_time = sum(data['times']) / len(data['times'])
                f.write(f"""
**{gpu_name}**
- Cost: ${avg_cost:.4f} per video
- Time: {avg_time:.1f}s average
- Use case: {'Development/Testing' if avg_time > 60 else 'Production'}
""")

            f.write("\n---\n\n## Conclusion\n\n")
            f.write("*[Add your conclusions about GPU performance, edge cases, and quality observations]*\n")

        print(f"\n📄 Report generated: {report_file}")
        print(f"📊 Raw data saved: {results_file}")

        return report_file


def setup_test_videos() -> List[TestVideo]:
    """Setup test video configurations."""
    test_videos = [
        TestVideo(
            name="news_anchor",
            category="normal",
            video_path="test_data/news_anchor_video.mp4",
            audio_path="test_data/news_anchor_audio.wav",
            description="Professional news anchor speaking clearly in controlled environment",
            expected_challenges=["Professional quality baseline", "Clear face visibility"]
        ),
        TestVideo(
            name="synthetic_elevenlabs",
            category="synthetic",
            video_path="test_data/synthetic_video.mp4",
            audio_path="test_data/synthetic_audio.wav",
            description="Self-recorded video with ElevenLabs generated audio/translation",
            expected_challenges=["Audio-video mismatch", "Synthetic speech patterns", "Potential accent changes"]
        ),
        TestVideo(
            name="edge_case",
            category="edge_case",
            video_path="test_data/edge_case_video.mp4",
            audio_path="test_data/edge_case_audio.wav",
            description="Video with challenging conditions (lighting, angles, occlusions)",
            expected_challenges=["Poor lighting", "Head turns", "Temporary occlusions", "Multiple faces or movement"]
        )
    ]

    return test_videos


def main():
    """Main GPU comparison workflow."""
    parser = argparse.ArgumentParser(description='Compare Wav2Lip performance across GPUs')
    parser.add_argument('--output-dir', default='gpu_comparison_results', help='Output directory')
    parser.add_argument('--timeout', type=int, default=600, help='Timeout per job in seconds')

    args = parser.parse_args()

    # Initialize comparison
    comparison = GPUComparison(args.output_dir)

    # Setup test videos
    test_videos = setup_test_videos()

    # Check if videos exist
    print("🔍 Checking test videos...")
    missing_videos = []
    for video in test_videos:
        if not Path(video.video_path).exists():
            missing_videos.append(video.video_path)
            print(f"  ❌ Missing: {video.video_path}")
        elif not Path(video.audio_path).exists():
            missing_videos.append(video.audio_path)
            print(f"  ❌ Missing: {video.audio_path}")
        else:
            print(f"  ✅ Found: {video.name}")
            comparison.add_test_video(video)

    if missing_videos:
        print(f"\n⚠️ Missing {len(missing_videos)} files. Please prepare test videos first:")
        print(f"   1. Create test_videos_raw/ directory")
        print(f"   2. Add your 3 test videos")
        print(f"   3. Run: python preprocess_videos.py")
        return

    # Run comparisons
    print(f"\n🚀 Starting comparison with {len(comparison.test_videos)} videos")

    results = comparison.run_all_comparisons()

    # Generate report
    report_file = comparison.generate_report(results)

    print(f"\n✅ Comparison complete!")
    print(f"📄 Review the report: {report_file}")
    print(f"\n📝 Next steps:")
    print(f"   1. Review generated videos in {args.output_dir}/")
    print(f"   2. Fill in qualitative evaluation scores")
    print(f"   3. Update report with observations and conclusions")


if __name__ == "__main__":
    main()
