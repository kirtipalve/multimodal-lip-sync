"""Quick test of the deployed Wav2Lip API"""
import requests
import time
import sys

API_URL = "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run"

print("=" * 60)
print("QUICK TEST: Wav2Lip API")
print("=" * 60)

# Health check
print("\n1. Health Check...")
resp = requests.get(f"{API_URL}/")
if resp.status_code == 200:
    print("   ✓ API is healthy!")
    print(f"   Response: {resp.json()}")
else:
    print(f"   ✗ Health check failed: {resp.status_code}")
    sys.exit(1)

# Submit job
print("\n2. Submitting lip-sync job...")
with open("test_data/sample_video.mp4", "rb") as vf:
    with open("test_data/sample_audio.wav", "rb") as af:
        files = {
            "video": ("video.mp4", vf, "video/mp4"),
            "audio": ("audio.wav", af, "audio/wav"),
        }
        params = {"use_gan": True}

        start_time = time.time()
        resp = requests.post(
            f"{API_URL}/api/v1/jobs",
            files=files,
            params=params,
            timeout=60,
        )

if resp.status_code != 200:
    print(f"   ✗ Job submission failed: {resp.status_code}")
    print(f"   Response: {resp.text}")
    sys.exit(1)

job_data = resp.json()
job_id = job_data["job_id"]
print(f"   ✓ Job submitted: {job_id}")
print(f"   Status: {job_data['status']}")

# Poll for completion
print("\n3. Waiting for completion...")
poll_count = 0
while True:
    time.sleep(3)
    poll_count += 1

    resp = requests.get(f"{API_URL}/api/v1/jobs/{job_id}", timeout=30)
    status_data = resp.json()

    status = status_data["status"]
    progress = status_data.get("progress", "")

    print(f"   [{poll_count}] Status: {status} - {progress}")

    if status == "completed":
        elapsed = status_data.get("elapsed_time", 0)
        print(f"\n   ✓ COMPLETED in {elapsed:.2f}s")
        print(f"   Total wait time: {time.time() - start_time:.2f}s")
        break
    elif status == "failed":
        error = status_data.get("error", "Unknown error")
        print(f"\n   ✗ FAILED: {error}")
        sys.exit(1)

    if poll_count > 120:  # 6 minutes timeout
        print("\n   ✗ Timeout after 6 minutes")
        sys.exit(1)

# Download result
print("\n4. Downloading result...")
resp = requests.get(
    f"{API_URL}/api/v1/jobs/{job_id}/result",
    timeout=120,
    stream=True,
)

if resp.status_code == 200:
    output_path = f"benchmark_results/test_output_{job_id[:8]}.mp4"
    import os
    os.makedirs("benchmark_results", exist_ok=True)

    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"   ✓ Downloaded: {output_path}")
    print(f"   Size: {size_mb:.2f} MB")
else:
    print(f"   ✗ Download failed: {resp.status_code}")
    sys.exit(1)

print("\n" + "=" * 60)
print("TEST COMPLETE!")
print("=" * 60)
print(f"\nOutput video: {output_path}")
print("Open this file to check lip-sync quality!")
