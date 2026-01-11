"""
Video Preprocessing Script for Wav2Lip Testing
Prepares videos for optimal lip-sync performance

Author: Kirti Palve

This script:
1. Validates video files (face detection, format, quality)
2. Normalizes video properties (resolution, fps, codec)
3. Extracts and validates audio
4. Creates optimized versions for testing
5. Generates preview reports
"""

import cv2
import subprocess
import os
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Tuple
import numpy as np

@dataclass
class VideoMetadata:
    """Metadata for video file."""
    filename: str
    width: int
    height: int
    fps: float
    frame_count: int
    duration: float
    codec: str
    file_size_mb: float
    has_audio: bool
    face_detected: bool
    face_detection_confidence: float
    recommended_resize_factor: int
    preprocessing_needed: bool
    issues: list

class VideoPreprocessor:
    """Preprocesses videos for Wav2Lip inference."""

    def __init__(self, input_dir: str = "test_videos_raw", output_dir: str = "test_data"):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Optimal settings for Wav2Lip
        self.target_width = 1280  # 720p width
        self.target_height = 720
        self.target_fps = 25
        self.max_duration = 60  # seconds

    def analyze_video(self, video_path: Path) -> VideoMetadata:
        """Analyze video and return metadata."""
        print(f"\n🔍 Analyzing: {video_path.name}")

        # Get video properties
        cap = cv2.VideoCapture(str(video_path))

        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0

        # Get codec
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])

        # File size
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)

        # Face detection
        face_detected, confidence = self._detect_face_in_video(cap)

        cap.release()

        # Check for audio
        has_audio = self._check_audio(video_path)

        # Determine recommended resize factor
        resize_factor = self._calculate_resize_factor(width, height)

        # Check if preprocessing needed
        issues = []
        preprocessing_needed = False

        if width > 1920 or height > 1080:
            issues.append("High resolution (will downscale to 720p)")
            preprocessing_needed = True

        if fps > 30:
            issues.append(f"High FPS ({fps:.1f} will reduce to 25)")
            preprocessing_needed = True

        if duration > self.max_duration:
            issues.append(f"Long duration ({duration:.1f}s, recommend <60s)")

        if not has_audio:
            issues.append("No audio track detected")

        if not face_detected:
            issues.append("⚠️ No face detected - video may fail processing")
        elif confidence < 0.8:
            issues.append(f"Low face detection confidence ({confidence:.2f})")

        if codec not in ['avc1', 'h264', 'H264']:
            issues.append(f"Non-standard codec ({codec})")
            preprocessing_needed = True

        metadata = VideoMetadata(
            filename=video_path.name,
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
            duration=duration,
            codec=codec,
            file_size_mb=file_size_mb,
            has_audio=has_audio,
            face_detected=face_detected,
            face_detection_confidence=confidence,
            recommended_resize_factor=resize_factor,
            preprocessing_needed=preprocessing_needed,
            issues=issues
        )

        self._print_metadata(metadata)
        return metadata

    def _detect_face_in_video(self, cap: cv2.VideoCapture, sample_frames: int = 10) -> Tuple[bool, float]:
        """Detect face in video frames."""
        # Load face cascade
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_indices = np.linspace(0, total_frames - 1, min(sample_frames, total_frames), dtype=int)

        detections = []

        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.1, 4)
            detections.append(len(faces) > 0)

        if not detections:
            return False, 0.0

        confidence = sum(detections) / len(detections)
        face_detected = confidence > 0.5

        return face_detected, confidence

    def _check_audio(self, video_path: Path) -> bool:
        """Check if video has audio track."""
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'a:0',
                 '-count_packets', '-show_entries', 'stream=nb_read_packets',
                 '-of', 'csv=p=0', str(video_path)],
                capture_output=True,
                text=True
            )
            return result.stdout.strip() != '' and int(result.stdout.strip() or '0') > 0
        except:
            return False

    def _calculate_resize_factor(self, width: int, height: int) -> int:
        """Calculate recommended resize factor for face detection."""
        # Smaller videos need higher resize factor for better face detection
        max_dim = max(width, height)

        if max_dim < 480:
            return 4
        elif max_dim < 720:
            return 2
        else:
            return 1

    def preprocess_video(self, input_path: Path, output_name: str) -> Path:
        """Preprocess video to optimal format."""
        output_path = self.output_dir / f"{output_name}.mp4"

        print(f"\n🔧 Preprocessing: {input_path.name} -> {output_path.name}")

        # FFmpeg command for preprocessing
        cmd = [
            'ffmpeg', '-i', str(input_path),
            '-vf', f'scale={self.target_width}:{self.target_height}:force_original_aspect_ratio=decrease,pad={self.target_width}:{self.target_height}:(ow-iw)/2:(oh-ih)/2',
            '-r', str(self.target_fps),
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            '-y',
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Error preprocessing: {result.stderr}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr}")

        print(f"✅ Preprocessed: {output_path}")
        return output_path

    def extract_audio(self, video_path: Path, output_name: str) -> Path:
        """Extract audio from video."""
        audio_path = self.output_dir / f"{output_name}.wav"

        print(f"🎵 Extracting audio: {audio_path.name}")

        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vn', '-acodec', 'pcm_s16le',
            '-ar', '16000', '-ac', '1',
            '-y', str(audio_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"⚠️ Audio extraction failed: {result.stderr}")
            return None

        print(f"✅ Audio extracted: {audio_path}")
        return audio_path

    def _print_metadata(self, metadata: VideoMetadata):
        """Print metadata in readable format."""
        print(f"""
📊 Video Analysis Results:
   Resolution: {metadata.width}x{metadata.height}
   FPS: {metadata.fps:.1f}
   Duration: {metadata.duration:.1f}s ({metadata.frame_count} frames)
   Codec: {metadata.codec}
   Size: {metadata.file_size_mb:.2f} MB
   Audio: {'✓' if metadata.has_audio else '✗'}
   Face Detected: {'✓' if metadata.face_detected else '✗'} (confidence: {metadata.face_detection_confidence:.2%})
   Recommended resize_factor: {metadata.recommended_resize_factor}
   Preprocessing needed: {'Yes' if metadata.preprocessing_needed else 'No'}
""")

        if metadata.issues:
            print("   ⚠️ Issues:")
            for issue in metadata.issues:
                print(f"      - {issue}")

    def process_all(self, generate_report: bool = True) -> dict:
        """Process all videos in input directory."""
        if not self.input_dir.exists():
            print(f"❌ Input directory not found: {self.input_dir}")
            print(f"📁 Please create directory and add test videos: {self.input_dir}")
            return {}

        video_files = list(self.input_dir.glob("*.mp4")) + list(self.input_dir.glob("*.avi")) + list(self.input_dir.glob("*.mov"))

        if not video_files:
            print(f"❌ No video files found in {self.input_dir}")
            return {}

        print(f"📁 Found {len(video_files)} videos to process\n")

        results = {}

        for video_path in video_files:
            try:
                # Analyze
                metadata = self.analyze_video(video_path)

                # Generate output name
                output_name = video_path.stem

                # Preprocess if needed
                if metadata.preprocessing_needed or not metadata.face_detected:
                    processed_path = self.preprocess_video(video_path, output_name)
                else:
                    # Just copy
                    import shutil
                    processed_path = self.output_dir / f"{output_name}.mp4"
                    shutil.copy2(video_path, processed_path)
                    print(f"✅ Copied (no preprocessing needed): {processed_path}")

                # Extract audio
                audio_path = self.extract_audio(processed_path, output_name)

                results[output_name] = {
                    'metadata': asdict(metadata),
                    'processed_video': str(processed_path),
                    'audio': str(audio_path) if audio_path else None
                }

            except Exception as e:
                print(f"❌ Error processing {video_path.name}: {e}")
                continue

        # Generate report
        if generate_report and results:
            self._generate_report(results)

        return results

    def _generate_report(self, results: dict):
        """Generate preprocessing report."""
        report_path = self.output_dir / "preprocessing_report.json"

        with open(report_path, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\n📄 Report saved: {report_path}")

        # Print summary
        print("\n" + "="*60)
        print("PREPROCESSING SUMMARY")
        print("="*60)

        for name, data in results.items():
            meta = data['metadata']
            print(f"\n{name}:")
            print(f"  ✓ Processed: {data['processed_video']}")
            print(f"  ✓ Audio: {data['audio']}")
            print(f"  Face Detection: {'✓' if meta['face_detected'] else '✗'} ({meta['face_detection_confidence']:.1%})")
            print(f"  Recommended resize_factor: {meta['recommended_resize_factor']}")
            if meta['issues']:
                print(f"  Issues: {', '.join(meta['issues'])}")


def main():
    """Main preprocessing workflow."""
    import argparse

    parser = argparse.ArgumentParser(description='Preprocess videos for Wav2Lip testing')
    parser.add_argument('--input-dir', default='test_videos_raw', help='Input directory with raw videos')
    parser.add_argument('--output-dir', default='test_data', help='Output directory for processed videos')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze, do not process')

    args = parser.parse_args()

    preprocessor = VideoPreprocessor(args.input_dir, args.output_dir)

    if args.analyze_only:
        # Just analyze
        video_files = list(Path(args.input_dir).glob("*.mp4"))
        for video_path in video_files:
            preprocessor.analyze_video(video_path)
    else:
        # Full processing
        results = preprocessor.process_all()

        if results:
            print(f"\n✅ Successfully preprocessed {len(results)} videos")
            print(f"📁 Output directory: {preprocessor.output_dir}")
        else:
            print("\n⚠️ No videos were processed")


if __name__ == "__main__":
    main()
