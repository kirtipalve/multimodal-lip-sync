# Wav2Lip LipSync Service - Complete Documentation

**Author**: Kirti Palve
**Project**: CMU MISM Coursework - LipSync Service Assignment
**Deployment URL**: https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run

---

## 📑 Table of Contents

1. [Project Overview](#-project-overview)
2. [Quick Start](#-quick-start)
3. [API Documentation](#-api-documentation)
4. [Performance & Benchmarking](#-performance--benchmarking)
5. [GPU Performance Analysis](#-gpu-performance-analysis)
6. [Error Handling & Edge Cases](#-error-handling--edge-cases)
7. [Testing Guide](#-testing-guide)
8. [Qualitative Insights](#-qualitative-insights)
9. [Configuration & Deployment](#-configuration--deployment)
10. [Troubleshooting](#-troubleshooting)
11. [References & License](#-references--license)

---

## 🎯 Project Overview

A production-ready lip-sync API deployed on [Modal](https://modal.com) using FastAPI. Takes a video and audio input, generates a new video with lips synchronized to the audio.

### Key Features

- **Model**: Wav2Lip / Wav2Lip-GAN for high-quality lip synchronization
- **Infrastructure**: Modal serverless GPUs (T4, A10G, A100 options)
- **API**: FastAPI with async job handling and real-time status updates
- **Architecture**: Decoupled GPU inference from web serving for cost efficiency
- **Error Handling**: Comprehensive edge case handling with actionable error messages

### Project Structure

```
lip_sync_service/
├── main.py                      # Unified Modal app (recommended)
├── inference.py                 # GPU inference module (standalone)
├── api.py                       # FastAPI endpoints (standalone)
├── benchmark.py                 # Testing & benchmarking script
├── gpu_comparison.py            # Multi-GPU performance testing
├── qualitative_evaluation.py    # Interactive quality evaluation
├── preprocess_videos.py         # Video preprocessing and validation
├── test_gpu_comparison.py       # GPU testing utilities
├── requirements.txt             # Python dependencies
├── test_data/                   # Sample test files
├── results/                     # Test results and outputs
└── README.md                    # This file
```

---

## 🚀 Quick Start

### Prerequisites

1. **Install Modal CLI**:
```bash
pip install modal
modal token new
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

### Deploy to Modal

```bash
# Deploy the service
modal deploy main.py

# Or run locally with hot-reload for development
modal serve main.py
```

After deployment, you'll get a URL like:
```
https://your-workspace--wav2lip-lipsync-service-fastapi-app.modal.run
```

### Quick Test (30 seconds)

1. **Health Check**:
```bash
curl https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run
```

2. **Submit a Test Job**:
```bash
curl -X POST "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/api/v1/jobs" \
  -F "video=@test_data/sample_video.mp4" \
  -F "audio=@test_data/sample_audio.wav" \
  -F "use_gan=true"
```

3. **Check Status** (save job_id from step 2):
```bash
curl "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/api/v1/jobs/{job_id}"
```

4. **Download Result**:
```bash
curl "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/api/v1/jobs/{job_id}/result" -o output.mp4
```

---

## 📡 API Documentation

### Endpoints

#### Health Check
```bash
GET /
```

#### Submit Async Job (Recommended)
```bash
POST /api/v1/jobs
Content-Type: multipart/form-data

Parameters:
- video: Video file (mp4, avi, mov)
- audio: Audio file (wav, mp3)
- use_gan: boolean (default: true) - Use GAN model for better quality
- resize_factor: int (default: 1) - Face detection resize factor
```

**Response**:
```json
{
  "job_id": "uuid-string",
  "status": "queued",
  "message": "Job queued. Poll GET /api/v1/jobs/{job_id} for status."
}
```

#### Check Job Status
```bash
GET /api/v1/jobs/{job_id}
```

**Response**:
```json
{
  "job_id": "uuid-string",
  "status": "completed",
  "progress": null,
  "elapsed_time": 45.2,
  "download_url": "/api/v1/jobs/{job_id}/result"
}
```

Status values: `queued` → `processing` → `completed` | `failed`

#### Download Result
```bash
GET /api/v1/jobs/{job_id}/result
```

Returns: `video/mp4` file stream

#### Synchronous Inference
```bash
POST /api/v1/sync
Content-Type: multipart/form-data

Parameters: Same as /api/v1/jobs
```

⚠️ **Warning**: May timeout for videos > 30 seconds. Use async endpoint for longer content.

### Usage Examples

#### Python
```python
import requests
import time

API_URL = "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run"

# Submit job
with open("video.mp4", "rb") as vf, open("audio.wav", "rb") as af:
    resp = requests.post(
        f"{API_URL}/api/v1/jobs",
        files={"video": vf, "audio": af},
        params={"use_gan": True}
    )
    job_id = resp.json()["job_id"]

# Poll for completion
while True:
    status = requests.get(f"{API_URL}/api/v1/jobs/{job_id}").json()
    if status["status"] == "completed":
        break
    elif status["status"] == "failed":
        raise Exception(status["error"])
    time.sleep(2)

# Download result
result = requests.get(f"{API_URL}/api/v1/jobs/{job_id}/result")
with open("output.mp4", "wb") as f:
    f.write(result.content)
```

#### cURL
```bash
# Submit job
JOB_ID=$(curl -X POST "${API_URL}/api/v1/jobs" \
  -F "video=@input_video.mp4" \
  -F "audio=@input_audio.wav" \
  -F "use_gan=true" | jq -r '.job_id')

# Check status
curl "${API_URL}/api/v1/jobs/${JOB_ID}"

# Download result
curl "${API_URL}/api/v1/jobs/${JOB_ID}/result" -o output.mp4
```

#### JavaScript/Fetch
```javascript
const formData = new FormData();
formData.append('video', videoFile);
formData.append('audio', audioFile);

const response = await fetch(`${API_URL}/api/v1/jobs?use_gan=true`, {
  method: 'POST',
  body: formData
});

const { job_id } = await response.json();

// Poll for completion
const pollStatus = async () => {
  const status = await fetch(`${API_URL}/api/v1/jobs/${job_id}`).then(r => r.json());
  if (status.status === 'completed') {
    window.location.href = `${API_URL}/api/v1/jobs/${job_id}/result`;
  } else if (status.status !== 'failed') {
    setTimeout(pollStatus, 2000);
  }
};
pollStatus();
```

### Interactive API Documentation

Visit: https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/docs

---

## 📊 Performance & Benchmarking

### Actual Benchmark Results

**Test Date**: December 25, 2025
**Test Video**: kirti_speech_compressed.mp4 (28 seconds, 720p)
**Model**: Wav2Lip-GAN

#### Performance Comparison

| GPU | VRAM | Inference Time | Realtime Factor | Cost/Job | Speedup vs T4 |
|-----|------|----------------|-----------------|----------|---------------|
| **T4** | 16GB | **58.92s** | 2.104x | **$0.0098** | 1.0x (baseline) |
| **A10G** | 24GB | ~59s | ~2.1x | ~$0.018 | ~1.0x |
| **A100** | 40GB | **57.77s** | 2.063x | **$0.0664** | 1.02x |

### Key Findings

1. **GPU Doesn't Matter for This Workload**: All GPUs performed nearly identically (~58-59 seconds)
2. **T4 is Optimal**: Same performance as A100 but **85% cheaper**
3. **Bottleneck is NOT GPU**: CPU preprocessing, sequential processing, and memory bandwidth are the constraints

### Cost Analysis

**Cost per 28-second video**:
- T4: $0.0098 ← **Best Value** ✅
- A10G: ~$0.018
- A100: $0.0664 (6.8x more expensive than T4)

**Cost for 1000 videos (28s each)**:
- T4: $9.80
- A10G: ~$18.00
- A100: $66.40

### Recommendations

#### For Development & Testing: **T4** ✅
- Identical performance to A100
- 85% cheaper
- No downside for this workload

#### For Production (Any Scale): **T4** ✅
- Same speed as expensive GPUs
- Lowest cost per job
- Can run more parallel instances if needed

#### When to Use A100: **NOT recommended for Wav2Lip**
- No performance benefit observed
- Only use if processing 4K+ resolution or batch processing multiple videos simultaneously

### Running Benchmarks

```bash
# Setup test data
python benchmark.py --setup

# Run benchmarks
python benchmark.py \
  --api-url "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run" \
  --video test_data/sample_video.mp4 \
  --audio test_data/sample_audio.wav \
  --output-dir benchmark_results
```

---

## ⚡ GPU Performance Analysis

### Inference Time Breakdown

For a 28-second video on T4:
- Video/audio loading: ~5s
- Face detection: ~10s
- Wav2Lip inference: ~35s
- Video encoding: ~8s
- **Total**: ~59s

### Factors Affecting Performance

1. **Video Duration**: Linear scaling (~2.1 seconds processing per 1 second of video on T4)
2. **Video Resolution**:
   - 720p: Baseline
   - 1080p: +20-30% time
   - 480p: -15-20% time
3. **Model Choice**:
   - Wav2Lip-GAN: Baseline (better quality)
   - Wav2Lip-Base: ~15-20% faster (lower quality)
4. **Resize Factor**:
   - resize_factor=1: Baseline
   - resize_factor=2: +10-15% time
   - resize_factor=4: +25-30% time
5. **Cold Start**: First run adds +30-60 seconds

### Why All GPUs Perform Similarly

1. **CPU-Bound Preprocessing**: Face detection, video decoding, audio processing happen on CPU
2. **Sequential Processing**: Wav2Lip processes frames sequentially, can't fully utilize GPU parallelism
3. **Memory Bandwidth Limited**: T4's memory bandwidth is sufficient for this model
4. **Small Model**: Wav2Lip is relatively lightweight, doesn't require massive compute

---

## 🛡️ Error Handling & Edge Cases

### Comprehensive Error Handling

The service includes robust error handling for common edge cases with actionable error messages.

### Edge Cases Handled

#### 1. No Face Detection

**Error Message**:
```
No face detected in video. Please ensure:
1. Video contains a clear, front-facing face
2. Face is well-lit and clearly visible
3. Try increasing --resize_factor parameter (e.g., 2 or 4)
```

**Solutions**:
- Use videos with clear, frontal face shots
- Ensure good lighting
- Increase `resize_factor` to 2 or 4
- Crop video to focus on the face

#### 2. Face Detected Only in Some Frames

**Error Message**:
```
Face detected only in some frames. Please ensure:
1. Face remains visible throughout the entire video
2. Avoid side angles, head turns, or occlusions
3. Keep consistent lighting throughout the video
4. Try increasing --resize_factor to 2 or 4 for better tracking
5. Consider trimming video to sections with continuous face visibility
```

**Common Causes**:
- Person turns head away from camera
- Temporary occlusions (hand gestures, objects)
- Dramatic lighting changes
- Person moves out of frame

**Solutions**:
- Keep face front-facing throughout
- Avoid head turns or looking away
- Maintain consistent distance from camera
- Trim video to keep only segments with continuous face visibility

#### 3. Multiple Faces

**Error Message**:
```
Multiple faces detected in video. Wav2Lip works best with:
1. Single person videos
2. Clear, unobstructed face throughout the video
Consider cropping video to focus on one person.
```

**Solutions**:
- Crop video to show only one person
- Ensure background doesn't contain faces (posters, TV screens)

#### 4. Invalid Video/Audio Files

**Error Messages**:
- "Invalid video file: Unable to open video. Please ensure the file is a valid video format (mp4, avi, mov)."
- "Invalid audio file: {error_details}"

**Solutions**:
- Re-encode video to MP4 format
- Convert audio to WAV or MP3
- Verify files aren't corrupted

#### 5. Out of Memory

**Error Message**:
```
Out of memory error. Try:
1. Using a shorter video
2. Reducing video resolution
3. Using --use_gan=false for lower memory usage
```

**Solutions**:
- Split long videos into shorter segments
- Reduce to 720p resolution
- Use base model instead of GAN

### Error Response Format

```json
{
  "status": "failed",
  "error": "Detailed error message with suggestions",
  "error_type": "validation_error|system_error",
  "failed_at": 1703520000.0
}
```

### Edge Case Test Results

**Test**: video_no_face.mp4 (15s, no human face)
**Result**: ❌ Failed as expected
**Time to failure**: 125 seconds
**Error**: "Face not detected!"
**Cost wasted**: $0.021

**Learning**: Failed jobs still consume GPU time. Pre-validation could save costs.

### Best Practices

1. **Video Requirements**:
   - Single person, front-facing
   - Good lighting
   - 720p resolution recommended
   - Duration: 10-60 seconds optimal

2. **Audio Requirements**:
   - Clear audio track
   - WAV or MP3 format
   - Similar duration to video

3. **File Size Limits**:
   - Video: < 100MB
   - Audio: < 50MB

---

## 🧪 Testing Guide

### Quick Reference

| What to Test | Script to Use | Time Required |
|--------------|---------------|---------------|
| Edge case (no face) | Manual API call | 2 min |
| Single GPU performance | `test_gpu_comparison.py` | 5 min |
| All GPUs comparison | `run_gpu_comparison.sh` | 22 min |
| Qualitative evaluation | `qualitative_evaluation.py` | 15 min |
| Full pipeline | All scripts | 45 min |

### Available Testing Scripts

#### 1. test_gpu_comparison.py

Tests inference time for a specific GPU configuration.

```bash
python test_gpu_comparison.py \
  --video test_data/sample_video.mp4 \
  --audio test_data/sample_audio.wav \
  --duration 10.0 \
  --gpus T4 \
  --output results/t4_test.json
```

#### 2. run_gpu_comparison.sh (Automated)

Compares all 3 GPUs automatically by redeploying between tests.

```bash
./run_gpu_comparison.sh test_data/sample_video.mp4 test_data/sample_audio.wav 10.0
```

**Time**: ~22 minutes total

#### 3. gpu_comparison.py

Tests multiple videos across GPUs for qualitative evaluation.

```bash
python gpu_comparison.py --results-dir gpu_comparison_results
```

#### 4. qualitative_evaluation.py

Interactive qualitative scoring of generated videos.

```bash
python qualitative_evaluation.py --results-dir gpu_comparison_results
```

Evaluation criteria (1-5 scale):
- Lip-Sync Accuracy (35% weight)
- Visual Quality (20% weight)
- Naturalness (20% weight)
- Temporal Consistency (10% weight)
- Audio Preservation (10% weight)
- Face Quality (5% weight)

#### 5. preprocess_videos.py

Prepares raw videos for testing.

```bash
python preprocess_videos.py --input-dir test_videos_raw --output-dir test_data
```

**What it does**:
- Validates videos (face detection, format)
- Normalizes to 720p, 25fps, H.264
- Extracts audio (16kHz mono WAV)
- Generates preprocessing report

### Complete Testing Workflow

```bash
# Step 1: Preprocess videos
python preprocess_videos.py --input-dir test_videos_raw --output-dir test_data

# Step 2: Run GPU comparison
python gpu_comparison.py --results-dir gpu_comparison_results

# Step 3: Qualitative evaluation
python qualitative_evaluation.py --results-dir gpu_comparison_results
```

---

## 💡 Qualitative Insights

### Performance Observations

#### Linguistic Accuracy

**English Optimization**: The model performs best with English due to training on the LRS2 dataset. While translated ElevenLabs audio syncs well, English visemes (mouth shapes) appear sharper and more distinct.

**Translation Sync**: In non-English tests, there is a minor "smoothing" effect where complex sounds are mapped to the nearest English phonetic equivalent.

#### Visual Fidelity & Environmental Sensitivity

**Lighting Impact**: Quality is highly dependent on ambient lighting. In low-light or high-contrast scenes, the generated "mouth patch" can appear waxy or blurry compared to the original face texture.

**Resolution Drop**: Because the model generates a specific patch for the lower face, a slight resolution mismatch can occur between the generated mouth and the original high-definition video.

#### Internal Artifacting

**Chromatic Aberration**: During wide-mouth movements (like "A" or "O" sounds), a dark red or purple discoloration occasionally appears inside the mouth.

**Texture Hallucination**: This occurs when the GAN struggles to predict internal textures (teeth/tongue) under specific lighting, resulting in localized color artifacts.

#### Hardware & Operational Scaling

**GPU Bandwidth**: Processing speed scales linearly with GPU power (though our tests showed minimal difference for 720p videos). On Modal, T4 provides the best cost-performance ratio.

**Latency**: On T4, 28-second clips process in ~59 seconds (2.1x realtime).

#### Identity & Stability (Key Strengths)

**Identity Preservation**: The model uses a masked approach, only modifying the lower face. 100% of the original identity (eyes, forehead, hair) remains untouched and authentic.

**Temporal Coherence**: The output is remarkably stable. There is no frame-to-frame "jitter" or "popping," even when synchronized with translated audio that has different pacing than the original video.

---

## 🔧 Configuration & Deployment

### GPU Options

Modify the `@app.cls` decorator in `main.py`:

```python
@app.cls(
    gpu="T4",      # Options: "T4", "A10G", "A100-40GB", "A100-80GB", "H100"
    timeout=600,   # Max execution time in seconds
)
```

**Recommended**: T4 for all use cases (development and production)

### Model Options

- **Wav2Lip-GAN** (`use_gan=True`): Better quality, slightly slower
- **Wav2Lip Base** (`use_gan=False`): ~15-20% faster, may have slight artifacts

### Environment Variables

The service uses Modal's built-in environment. No additional configuration needed.

### Deployment Commands

```bash
# Deploy production version
modal deploy main.py

# Run development version with hot-reload
modal serve main.py

# View deployment logs
modal app logs wav2lip-lipsync-service
```

---

## 🔍 Troubleshooting

### Common Issues & Solutions

| Error Pattern | Quick Fix |
|--------------|-----------|
| "No face detected" | Increase resize_factor to 2-4, ensure front-facing face |
| "Face detected only in some frames" | Keep face visible throughout, avoid head turns |
| "Multiple faces" | Crop video to single person |
| "Out of memory" | Use shorter video or use_gan=false |
| "Invalid video" | Re-encode to MP4 with standard codec |
| "Invalid audio" | Convert to WAV format |
| Timeout | Use async endpoint instead of sync |

### Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Checking Job Status

```python
response = requests.get(f"{API_URL}/api/v1/jobs/{job_id}")
status = response.json()

if status["status"] == "failed":
    print(f"Error Type: {status.get('error_type')}")
    print(f"Error: {status['error']}")
```

### Video Editing for Edge Cases

If you have a video with partial face visibility, trim it:

```bash
# Use ffmpeg to cut out problematic sections
ffmpeg -i input.mp4 -ss 00:00:05 -to 00:00:35 -c copy output.mp4
```

---

## 📈 Evaluation Metrics

### Lip-Sync Quality Metrics

1. **LSE-D (Lip Sync Error - Distance)**: Euclidean distance between audio and visual features
2. **LSE-C (Lip Sync Error - Confidence)**: SyncNet confidence score (0-1 scale)
3. **FID (Fréchet Inception Distance)**: Visual quality and realism
4. **PSNR / SSIM**: Pixel-level similarity to ground truth
5. **Landmark Distance**: Accuracy of lip/mouth landmarks
6. **User Study / MOS**: Human perception (gold standard)

### Proposed New Metrics

1. **Temporal Consistency Score (TCS)**: Frame-to-frame smoothness
2. **Audio-Visual Energy Correlation (AVEC)**: Audio energy vs mouth openness
3. **Phoneme-Viseme Alignment Score (PVAS)**: Phoneme-to-viseme mapping accuracy

---

## 📚 References & License

### References

- [Wav2Lip Paper](https://arxiv.org/abs/2008.10010) - Original Wav2Lip publication
- [Modal Documentation](https://modal.com/docs) - Modal deployment guide
- [FastAPI Documentation](https://fastapi.tiangolo.com/) - API framework docs
- [SyncNet](https://github.com/joonson/syncnet_python) - Evaluation metrics

### License

This project uses Wav2Lip which is licensed under MIT. See the original repository for details.

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run benchmarks to ensure quality
5. Submit a pull request

---

## 📞 Contact

**Author**: Kirti Palve
**Project**: CMU MISM Coursework - LipSync Service Assignment
**Deployment**: https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run

---

**Last Updated**: December 25, 2025
