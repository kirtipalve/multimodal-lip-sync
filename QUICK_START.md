# Quick Start Guide

Author: Kirti Palve

## Deployed Service

Your Wav2Lip LipSync Service is live at:
**https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run**

## Test the Service (30 seconds)

### 1. Quick Health Check
```bash
curl https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run
```

### 2. Submit a Test Job
```bash
curl -X POST "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/api/v1/jobs" \
  -F "video=@test_data/sample_video.mp4" \
  -F "audio=@test_data/sample_audio.wav" \
  -F "use_gan=true"
```

Save the `job_id` from the response.

### 3. Check Job Status
```bash
curl "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/api/v1/jobs/{job_id}"
```

### 4. Download Result
```bash
curl "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/api/v1/jobs/{job_id}/result" -o output.mp4
```

## Run Benchmarks

```bash
python benchmark.py \
  --api-url "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run" \
  --video test_data/sample_video.mp4 \
  --audio test_data/sample_audio.wav \
  --output-dir benchmark_results
```

## View Interactive API Docs

Visit: https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/docs

## Common Use Cases

### Use Case 1: Short Video (< 30s)
Use synchronous endpoint for immediate results:
```python
import requests

with open("video.mp4", "rb") as v, open("audio.wav", "rb") as a:
    response = requests.post(
        "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/api/v1/sync",
        files={"video": v, "audio": a},
        params={"use_gan": True}
    )

with open("result.mp4", "wb") as f:
    f.write(response.content)
```

### Use Case 2: Long Video (> 30s)
Use async endpoint with polling:
```python
import requests
import time

# Submit job
with open("video.mp4", "rb") as v, open("audio.wav", "rb") as a:
    response = requests.post(
        "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/api/v1/jobs",
        files={"video": v, "audio": a},
        params={"use_gan": True}
    )
    job_id = response.json()["job_id"]

# Poll for completion
while True:
    status = requests.get(
        f"https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/api/v1/jobs/{job_id}"
    ).json()

    if status["status"] == "completed":
        break
    elif status["status"] == "failed":
        print(f"Error: {status['error']}")
        exit(1)

    print(f"Progress: {status.get('progress', 'Processing...')}")
    time.sleep(2)

# Download result
result = requests.get(
    f"https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run/api/v1/jobs/{job_id}/result"
)

with open("result.mp4", "wb") as f:
    f.write(result.content)
```

## Troubleshooting

### "No face detected"
- Ensure video has clear, front-facing face
- Try `resize_factor=2` or `resize_factor=4`

### "Multiple faces detected"
- Crop video to show only one person
- Ensure background has no faces

### Timeout errors
- Use async endpoint (`/api/v1/jobs`) for videos > 30 seconds
- Consider splitting very long videos

## Files Overview

- `main.py` - Main deployment file
- `benchmark.py` - Test and benchmark script
- `test_data/` - Sample test files
- `README.md` - Full documentation
- `ERROR_HANDLING.md` - Error handling guide

## Need Help?

- Check `ERROR_HANDLING.md` for detailed error solutions
- See `README.md` for complete documentation
- Visit `/docs` endpoint for interactive API testing

---

**Estimated Processing Time**: ~24 seconds per 1 second of video (T4 GPU)
**Recommended Video**: 10-60 seconds, 720p, single person, front-facing
