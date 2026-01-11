#!/bin/bash
# Quick setup script for test data

set -e

echo "Setting up test data for Wav2Lip benchmarking..."

# Create directory
mkdir -p test_data

echo "Downloading sample video..."
curl -L -o test_data/sample_video.mp4 "https://assets.sync.so/docs/example-video.mp4"

echo "Downloading sample audio..."
curl -L -o test_data/sample_audio.wav "https://assets.sync.so/docs/example-audio.wav"

echo ""
echo "✓ Test data ready!"
echo ""
ls -lh test_data/

echo ""
echo "Next step: Run benchmark with:"
echo "python benchmark.py --api-url https://kirtipalve--wav2lip-lipsync-service-fastapi-app.modal.run"
