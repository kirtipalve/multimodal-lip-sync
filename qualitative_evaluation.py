"""
Qualitative Evaluation Framework for Lip-Sync Quality
Interactive tool for evaluating generated videos

Author: Kirti Palve

This script provides:
1. Side-by-side video comparison
2. Structured evaluation criteria
3. Scoring system (1-5 scale)
4. JSON export of evaluations
5. Summary statistics
"""

import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
import subprocess

@dataclass
class EvaluationCriteria:
    """Evaluation criteria for lip-sync quality."""
    lip_sync_accuracy: int  # 1-5: How well lips match audio
    visual_quality: int  # 1-5: Overall video quality, no artifacts
    naturalness: int  # 1-5: How natural the result looks
    temporal_consistency: int  # 1-5: Frame-to-frame smoothness
    audio_preservation: int  # 1-5: Audio quality maintained
    face_quality: int  # 1-5: Face details preserved

    def overall_score(self) -> float:
        """Calculate overall weighted score."""
        weights = {
            'lip_sync_accuracy': 0.35,
            'visual_quality': 0.20,
            'naturalness': 0.20,
            'temporal_consistency': 0.10,
            'audio_preservation': 0.10,
            'face_quality': 0.05
        }

        total = (
            self.lip_sync_accuracy * weights['lip_sync_accuracy'] +
            self.visual_quality * weights['visual_quality'] +
            self.naturalness * weights['naturalness'] +
            self.temporal_consistency * weights['temporal_consistency'] +
            self.audio_preservation * weights['audio_preservation'] +
            self.face_quality * weights['face_quality']
        )

        return round(total, 2)

@dataclass
class VideoEvaluation:
    """Complete evaluation for a video."""
    video_name: str
    gpu_name: str
    category: str
    scores: EvaluationCriteria
    observations: str
    artifacts_noted: List[str]
    success: bool
    timestamp: str

class QualitativeEvaluator:
    """Interactive qualitative evaluation tool."""

    def __init__(self, results_dir: str = "gpu_comparison_results"):
        self.results_dir = Path(results_dir)
        self.evaluations = []

    def play_video(self, video_path: Path):
        """Play video using system default player."""
        try:
            if os.name == 'darwin':  # macOS
                subprocess.run(['open', str(video_path)])
            elif os.name == 'nt':  # Windows
                os.startfile(str(video_path))
            else:  # Linux
                subprocess.run(['xdg-open', str(video_path)])
        except:
            print(f"⚠️ Could not auto-play video. Please manually open: {video_path}")

    def evaluate_video(self, video_path: Path, original_video: Optional[Path] = None) -> VideoEvaluation:
        """Interactive evaluation of a single video."""
        print(f"\n{'='*70}")
        print(f"Evaluating: {video_path.name}")
        print(f"{'='*70}\n")

        # Extract metadata from filename
        # Format: {video_name}_{gpu_name}_result.mp4
        parts = video_path.stem.split('_')
        video_name = parts[0]
        gpu_name = parts[1] if len(parts) > 1 else 'unknown'

        # Play videos
        print("🎥 Playing generated video...")
        self.play_video(video_path)

        if original_video and original_video.exists():
            input("\nPress Enter to play original video for comparison...")
            self.play_video(original_video)

        input("\nPress Enter when ready to evaluate...")

        # Get scores
        print("\n📊 Evaluation Criteria (Rate 1-5, where 5 is best):\n")

        print("1. Lip-Sync Accuracy")
        print("   5: Perfect sync, no visible mismatch")
        print("   4: Very good sync, minor occasional mismatch")
        print("   3: Good sync, some noticeable mismatch")
        print("   2: Poor sync, frequent mismatch")
        print("   1: Very poor sync, constant mismatch")
        lip_sync = self._get_score("Lip-Sync Accuracy")

        print("\n2. Visual Quality")
        print("   5: Excellent quality, no visible artifacts")
        print("   4: Good quality, very minor artifacts")
        print("   3: Acceptable quality, some artifacts")
        print("   2: Poor quality, many artifacts")
        print("   1: Very poor quality, severe artifacts")
        visual = self._get_score("Visual Quality")

        print("\n3. Naturalness")
        print("   5: Completely natural, indistinguishable from real")
        print("   4: Very natural, minor uncanny valley")
        print("   3: Somewhat natural, noticeable synthetic look")
        print("   2: Unnatural, clearly synthetic")
        print("   1: Very unnatural, jarring")
        naturalness = self._get_score("Naturalness")

        print("\n4. Temporal Consistency")
        print("   5: Perfectly smooth, no flickering")
        print("   4: Very smooth, rare minor flicker")
        print("   3: Mostly smooth, occasional flicker")
        print("   2: Noticeable flickering/jitter")
        print("   1: Severe flickering/jitter")
        temporal = self._get_score("Temporal Consistency")

        print("\n5. Audio Preservation")
        print("   5: Perfect audio quality")
        print("   4: Very good audio quality")
        print("   3: Acceptable audio quality")
        print("   2: Degraded audio quality")
        print("   1: Poor audio quality")
        audio = self._get_score("Audio Preservation")

        print("\n6. Face Quality")
        print("   5: All facial details preserved")
        print("   4: Most details preserved")
        print("   3: Some details lost")
        print("   2: Many details lost")
        print("   1: Severe detail loss")
        face = self._get_score("Face Quality")

        # Get observations
        print("\n📝 Additional observations:")
        observations = input("Enter any notes about this video: ").strip()

        # Artifacts
        print("\n⚠️ Artifacts noted (enter comma-separated, or press Enter if none):")
        print("   Examples: blurring, color shift, edge artifacts, flickering, etc.")
        artifacts_str = input("Artifacts: ").strip()
        artifacts = [a.strip() for a in artifacts_str.split(',') if a.strip()]

        # Success
        success_str = input("\n✅ Overall success? (y/n): ").strip().lower()
        success = success_str == 'y'

        # Create evaluation
        scores = EvaluationCriteria(
            lip_sync_accuracy=lip_sync,
            visual_quality=visual,
            naturalness=naturalness,
            temporal_consistency=temporal,
            audio_preservation=audio,
            face_quality=face
        )

        from datetime import datetime
        evaluation = VideoEvaluation(
            video_name=video_name,
            gpu_name=gpu_name,
            category='',  # Will be filled later
            scores=scores,
            observations=observations,
            artifacts_noted=artifacts,
            success=success,
            timestamp=datetime.now().isoformat()
        )

        print(f"\n✅ Overall Score: {scores.overall_score()}/5.0")

        return evaluation

    def _get_score(self, criterion: str) -> int:
        """Get a score from user with validation."""
        while True:
            try:
                score = int(input(f"Score for {criterion} (1-5): "))
                if 1 <= score <= 5:
                    return score
                else:
                    print("Please enter a number between 1 and 5")
            except ValueError:
                print("Please enter a valid number")

    def evaluate_all(self):
        """Evaluate all videos in results directory."""
        video_files = list(self.results_dir.glob("*_result.mp4"))

        if not video_files:
            print(f"❌ No result videos found in {self.results_dir}")
            return

        print(f"📁 Found {len(video_files)} videos to evaluate\n")

        for video_path in sorted(video_files):
            evaluation = self.evaluate_video(video_path)
            self.evaluations.append(evaluation)

            # Save after each evaluation
            self.save_evaluations()

        # Generate summary
        self.print_summary()

    def save_evaluations(self):
        """Save evaluations to JSON."""
        output_file = self.results_dir / "qualitative_evaluations.json"

        data = {
            'evaluations': [
                {
                    'video_name': e.video_name,
                    'gpu_name': e.gpu_name,
                    'category': e.category,
                    'scores': asdict(e.scores),
                    'overall_score': e.scores.overall_score(),
                    'observations': e.observations,
                    'artifacts_noted': e.artifacts_noted,
                    'success': e.success,
                    'timestamp': e.timestamp
                }
                for e in self.evaluations
            ]
        }

        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"💾 Saved evaluations to: {output_file}")

    def print_summary(self):
        """Print summary statistics."""
        if not self.evaluations:
            print("No evaluations to summarize")
            return

        print("\n" + "="*70)
        print("EVALUATION SUMMARY")
        print("="*70 + "\n")

        # Overall statistics
        total = len(self.evaluations)
        successful = sum(1 for e in self.evaluations if e.success)

        print(f"Total Videos Evaluated: {total}")
        print(f"Successful: {successful} ({successful/total*100:.1f}%)")
        print(f"Failed: {total - successful} ({(total-successful)/total*100:.1f}%)\n")

        # Average scores
        avg_scores = {
            'lip_sync_accuracy': sum(e.scores.lip_sync_accuracy for e in self.evaluations) / total,
            'visual_quality': sum(e.scores.visual_quality for e in self.evaluations) / total,
            'naturalness': sum(e.scores.naturalness for e in self.evaluations) / total,
            'temporal_consistency': sum(e.scores.temporal_consistency for e in self.evaluations) / total,
            'audio_preservation': sum(e.scores.audio_preservation for e in self.evaluations) / total,
            'face_quality': sum(e.scores.face_quality for e in self.evaluations) / total,
        }

        print("Average Scores (out of 5):")
        for criterion, score in avg_scores.items():
            print(f"  {criterion.replace('_', ' ').title()}: {score:.2f}")

        avg_overall = sum(e.scores.overall_score() for e in self.evaluations) / total
        print(f"\n  Overall Average: {avg_overall:.2f}/5.0")

        # By GPU
        gpus = set(e.gpu_name for e in self.evaluations)
        if len(gpus) > 1:
            print("\n\nBy GPU:")
            for gpu in sorted(gpus):
                gpu_evals = [e for e in self.evaluations if e.gpu_name == gpu]
                gpu_avg = sum(e.scores.overall_score() for e in gpu_evals) / len(gpu_evals)
                print(f"  {gpu}: {gpu_avg:.2f}/5.0 ({len(gpu_evals)} videos)")

        # Common artifacts
        all_artifacts = []
        for e in self.evaluations:
            all_artifacts.extend(e.artifacts_noted)

        if all_artifacts:
            from collections import Counter
            artifact_counts = Counter(all_artifacts)
            print("\n\nMost Common Artifacts:")
            for artifact, count in artifact_counts.most_common(5):
                print(f"  {artifact}: {count} occurrences")


def main():
    """Main evaluation workflow."""
    import argparse

    parser = argparse.ArgumentParser(description='Qualitative evaluation of lip-sync videos')
    parser.add_argument('--results-dir', default='gpu_comparison_results', help='Directory with result videos')
    parser.add_argument('--video', help='Evaluate specific video file')

    args = parser.parse_args()

    evaluator = QualitativeEvaluator(args.results_dir)

    if args.video:
        # Evaluate single video
        video_path = Path(args.video)
        if not video_path.exists():
            print(f"❌ Video not found: {video_path}")
            return

        evaluation = evaluator.evaluate_video(video_path)
        evaluator.evaluations.append(evaluation)
        evaluator.save_evaluations()
    else:
        # Evaluate all videos
        evaluator.evaluate_all()


if __name__ == "__main__":
    main()
