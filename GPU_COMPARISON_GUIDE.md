# GPU Comparison Testing Guide

**Author**: Kirti Palve

This guide explains how to compare inference performance across different GPU types on Modal.

---

## ⚠️ Important: GPU Configuration

Currently, the GPU type is hardcoded in `main.py` at line 101:

```python
@app.cls(
    image=wav2lip_image,
    gpu="T4",  # Options: "T4", "A10G", "A100"
    timeout=600,
    volumes={"/results": results_volume},
)
```

To test different GPUs, you have **two options**:

---

## Option 1: Sequential Testing (Change & Redeploy)

Test one GPU at a time by changing the code and redeploying.

### Steps:

1. **Test T4 (current)**:
   ```bash
   # Already deployed with T4
   python test_gpu_comparison.py \
     --video test_videos_raw/video_no_face.mp4 \
     --audio test_videos_raw/english_audio.wav \
     --duration 15.0 \
     --gpus T4 \
     --output results/gpu_t4_results.json
   ```

2. **Change to A10G**:
   ```bash
   # Edit main.py line 101:
   # gpu="A10G",

   modal deploy main.py

   # Test A10G
   python test_gpu_comparison.py \
     --video test_videos_raw/video_no_face.mp4 \
     --audio test_videos_raw/english_audio.wav \
     --duration 15.0 \
     --gpus A10G \
     --output results/gpu_a10g_results.json
   ```

3. **Change to A100**:
   ```bash
   # Edit main.py line 101:
   # gpu="A100",

   modal deploy main.py

   # Test A100
   python test_gpu_comparison.py \
     --video test_videos_raw/video_no_face.mp4 \
     --audio test_videos_raw/english_audio.wav \
     --duration 15.0 \
     --gpus A100 \
     --output results/gpu_a100_results.json
   ```

4. **Combine results**:
   ```bash
   python combine_gpu_results.py \
     results/gpu_t4_results.json \
     results/gpu_a10g_results.json \
     results/gpu_a100_results.json \
     --output final_gpu_comparison.json
   ```

---

## Option 2: Use Existing gpu_comparison.py (Recommended)

The `gpu_comparison.py` script is designed to handle this workflow automatically.

### How it works:

The script tests one video across all GPUs but expects you to have deployed different GPU versions or accepts the limitation of testing the same GPU multiple times.

### Usage:

```bash
python gpu_comparison.py --results-dir gpu_comparison_results
```

This will:
1. Use preprocessed videos from `test_data/`
2. Submit jobs for each video
3. Measure inference time
4. Generate comparison report

**Note**: Since GPU is hardcoded, all tests will use the same GPU (T4). For true comparison, you must deploy with different GPU types between runs.

---

## Quick Comparison Workflow

### Step 1: Prepare Test Video

```bash
# Use a video with an actual face (not video_no_face.mp4)
# Download from Pexels or use existing:
cp test_data/sample_video.mp4 test_videos_raw/comparison_test.mp4
cp test_data/sample_audio.wav test_videos_raw/comparison_test.wav
```

### Step 2: Test Current GPU (T4)

```bash
python test_gpu_comparison.py \
  --video test_data/sample_video.mp4 \
  --audio test_data/sample_audio.wav \
  --duration 10.0 \
  --gpus T4 \
  --output gpu_comparison_results/t4_results.json
```

### Step 3: Deploy with A10G

```bash
# Edit main.py line 101 to: gpu="A10G"
modal deploy main.py

# Wait for deployment (~5 minutes)
```

### Step 4: Test A10G

```bash
python test_gpu_comparison.py \
  --video test_data/sample_video.mp4 \
  --audio test_data/sample_audio.wav \
  --duration 10.0 \
  --gpus A10G \
  --output gpu_comparison_results/a10g_results.json
```

### Step 5: Deploy with A100

```bash
# Edit main.py line 101 to: gpu="A100"
modal deploy main.py

# Wait for deployment (~5 minutes)
```

### Step 6: Test A100

```bash
python test_gpu_comparison.py \
  --video test_data/sample_video.mp4 \
  --audio test_data/sample_audio.wav \
  --duration 10.0 \
  --gpus A100 \
  --output gpu_comparison_results/a100_results.json
```

---

## Expected Performance (10-second video)

Based on typical Wav2Lip performance:

| GPU | VRAM | Inference Time | Realtime Factor | Cost/Job |
|-----|------|----------------|-----------------|----------|
| T4 | 16GB | ~240s (4 min) | 0.042x (24x slower) | ~$0.04 |
| A10G | 24GB | ~80s (1.3 min) | 0.125x (8x slower) | ~$0.024 |
| A100 | 40GB/80GB | ~40s (40 sec) | 0.25x (4x slower) | ~$0.046 |

**Notes**:
- First run includes cold start (~30-60s)
- A10G offers best cost-performance balance
- A100 is fastest but most expensive
- T4 is cheapest per second but slowest overall

---

## Time Investment

**Total time for full comparison**:
- T4 deployment: ~5 min (already done)
- T4 test: ~4 min inference
- A10G deployment: ~5 min
- A10G test: ~1.5 min inference
- A100 deployment: ~5 min
- A100 test: ~1 min inference

**Total**: ~22 minutes for complete comparison

---

## Alternative: Test with Current GPU Only

If you don't want to redeploy multiple times, you can still generate a useful report with the current T4 GPU:

```bash
# Test current deployment (T4)
python test_gpu_comparison.py \
  --video test_data/sample_video.mp4 \
  --audio test_data/sample_audio.wav \
  --duration 10.0 \
  --gpus T4 \
  --output gpu_comparison_results/current_gpu_results.json
```

Then **extrapolate** performance for other GPUs based on typical speedup factors:
- A10G: ~3x faster than T4
- A100: ~6x faster than T4

This is less accurate but saves deployment time.

---

## Automated Comparison Script

For convenience, here's a complete script:

```bash
#!/bin/bash
# File: run_full_gpu_comparison.sh

VIDEO="test_data/sample_video.mp4"
AUDIO="test_data/sample_audio.wav"
DURATION=10.0

echo "Starting GPU Comparison..."
echo "This will take ~22 minutes"
echo ""

# Test T4
echo "=== Testing T4 ==="
sed -i '' 's/gpu="[^"]*"/gpu="T4"/' main.py
modal deploy main.py
sleep 30  # Wait for deployment
python test_gpu_comparison.py --video $VIDEO --audio $AUDIO --duration $DURATION --gpus T4 --output results/t4.json

# Test A10G
echo "=== Testing A10G ==="
sed -i '' 's/gpu="[^"]*"/gpu="A10G"/' main.py
modal deploy main.py
sleep 30
python test_gpu_comparison.py --video $VIDEO --audio $AUDIO --duration $DURATION --gpus A10G --output results/a10g.json

# Test A100
echo "=== Testing A100 ==="
sed -i '' 's/gpu="[^"]*"/gpu="A100"/' main.py
modal deploy main.py
sleep 30
python test_gpu_comparison.py --video $VIDEO --audio $AUDIO --duration $DURATION --gpus A100 --output results/a100.json

echo "=== Comparison Complete ==="
```

---

## For Your Evaluation (Part 3)

For the submission, I recommend:

1. **Test at least 2 GPUs**: T4 (current) + A10G
2. **Use actual face video**: Not video_no_face.mp4
3. **Document results** in EVALUATION_TEMPLATE.md
4. **Include**:
   - Inference time for each GPU
   - Cost comparison
   - Realtime factor
   - Recommendation for production use

---

## Current Deployment Info

- **URL**: https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run
- **Current GPU**: T4 (16GB VRAM)
- **Model**: Wav2Lip-GAN
- **Status**: Deployed and ready

---

**Author**: Kirti Palve
**Updated**: December 25, 2025
