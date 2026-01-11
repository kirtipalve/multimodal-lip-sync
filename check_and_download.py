#!/usr/bin/env python3
"""
Quick script to check job status and download result when ready.
"""
import requests
import time
import sys

job_id = "aadd644d-69ef-4d20-883b-5be4c3fe0929"
api_url = "https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run"
output_file = "results/french_lipsync/kirti_french_lipsync.mp4"

print(f"Monitoring job {job_id}...")

max_attempts = 60  # 5 minutes
for i in range(max_attempts):
    try:
        response = requests.get(f"{api_url}/api/v1/jobs/{job_id}")
        data = response.json()

        status = data.get("status")
        print(f"[{i+1}/{max_attempts}] Status: {status}")

        if status == "completed":
            download_url = data.get("download_url")
            if download_url:
                print(f"\n✓ Job completed! Downloading result...")
                print(f"Download URL: {download_url}")

                # Download the video
                video_response = requests.get(download_url)
                with open(output_file, 'wb') as f:
                    f.write(video_response.content)

                print(f"✓ Video saved to: {output_file}")
                sys.exit(0)

        elif status == "failed":
            error = data.get("error", "Unknown error")
            print(f"\n✗ Job failed: {error}")
            sys.exit(1)

        time.sleep(5)

    except Exception as e:
        print(f"Error checking status: {e}")
        time.sleep(5)

print("\n✗ Timeout waiting for job to complete")
sys.exit(1)
