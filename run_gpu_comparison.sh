#!/bin/bash

# Automated GPU Comparison Script
# Author: Kirti Palve
#
# This script tests inference across different GPU types
# WARNING: This will modify main.py and redeploy multiple times (~22 minutes total)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
VIDEO="${1:-test_data/sample_video.mp4}"
AUDIO="${2:-test_data/sample_audio.wav}"
DURATION="${3:-10.0}"
RESULTS_DIR="gpu_comparison_results"

echo "=========================================="
echo "Automated GPU Comparison"
echo "Author: Kirti Palve"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Video: $VIDEO"
echo "  Audio: $AUDIO"
echo "  Duration: ${DURATION}s"
echo "  Results: $RESULTS_DIR"
echo ""

# Validate inputs
if [ ! -f "$VIDEO" ]; then
    echo "❌ Video file not found: $VIDEO"
    exit 1
fi

if [ ! -f "$AUDIO" ]; then
    echo "❌ Audio file not found: $AUDIO"
    exit 1
fi

# Create results directory
mkdir -p "$RESULTS_DIR"

# Backup main.py
cp main.py main.py.backup
echo "💾 Backed up main.py to main.py.backup"
echo ""

# Function to change GPU and deploy
deploy_gpu() {
    local gpu_type=$1
    echo "=========================================="
    echo "Testing GPU: $gpu_type"
    echo "=========================================="
    echo ""

    # Update main.py
    echo "📝 Updating main.py to use $gpu_type..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s/gpu=\"[^\"]*\"/gpu=\"$gpu_type\"/" main.py
    else
        # Linux
        sed -i "s/gpu=\"[^\"]*\"/gpu=\"$gpu_type\"/" main.py
    fi

    # Verify change
    if grep -q "gpu=\"$gpu_type\"" main.py; then
        echo "✅ Updated to $gpu_type"
    else
        echo "❌ Failed to update main.py"
        exit 1
    fi

    # Deploy
    echo ""
    echo "🚀 Deploying with $gpu_type..."
    modal deploy main.py

    echo ""
    echo "⏳ Waiting 20 seconds for deployment to stabilize..."
    sleep 20

    # Run test
    echo ""
    echo "🧪 Running test..."
    python test_gpu_comparison.py \
        --video "$VIDEO" \
        --audio "$AUDIO" \
        --duration "$DURATION" \
        --gpus "$gpu_type" \
        --output "$RESULTS_DIR/${gpu_type}_results.json"

    echo ""
    echo "✅ $gpu_type test complete"
    echo ""
}

# Ask user confirmation
echo "⚠️  WARNING: This will:"
echo "  1. Modify main.py (GPU setting)"
echo "  2. Deploy to Modal 3 times (~15 min deployment time)"
echo "  3. Run 3 inference tests (~5-10 min total inference)"
echo "  Total time: ~22-25 minutes"
echo ""
read -p "Continue? (y/n): " confirm

if [ "$confirm" != "y" ]; then
    echo "Cancelled"
    exit 0
fi

echo ""
echo "Starting GPU comparison..."
echo ""

# Test each GPU
deploy_gpu "T4"
sleep 5

deploy_gpu "A10G"
sleep 5

deploy_gpu "A100"

# Restore original GPU setting
echo ""
echo "=========================================="
echo "Restoring original configuration..."
echo "=========================================="
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' 's/gpu="[^"]*"/gpu="T4"/' main.py
else
    sed -i 's/gpu="[^"]*"/gpu="T4"/' main.py
fi

modal deploy main.py
echo "✅ Restored to T4"

# Generate combined report
echo ""
echo "=========================================="
echo "Generating Combined Report"
echo "=========================================="
echo ""

python3 << 'EOF'
import json
from pathlib import Path

results_dir = Path("gpu_comparison_results")
gpus = ["T4", "A10G", "A100"]

combined = {
    "comparison_results": [],
    "summary": {}
}

print("📊 Results Summary:\n")
print(f"{'GPU':<8} {'Inference (s)':<15} {'RT Factor':<12} {'Cost ($)':<10} {'Status'}")
print("-" * 70)

for gpu in gpus:
    result_file = results_dir / f"{gpu}_results.json"
    if result_file.exists():
        with open(result_file) as f:
            data = json.load(f)
            if data["results"]:
                result = data["results"][0]
                combined["comparison_results"].append(result)

                status = result["status"]
                if status == "completed":
                    inf_time = result["inference_time"]
                    rt_factor = result["realtime_factor"]
                    cost = result["cost_per_job"]
                    print(f"{gpu:<8} {inf_time:<15.2f} {rt_factor:<12.3f} ${cost:<9.4f} {status}")
                else:
                    print(f"{gpu:<8} {'N/A':<15} {'N/A':<12} {'N/A':<10} {status}")

# Save combined report
with open(results_dir / "combined_report.json", "w") as f:
    json.dump(combined, f, indent=2)

print("\n💾 Combined report saved: gpu_comparison_results/combined_report.json")
EOF

echo ""
echo "=========================================="
echo "GPU Comparison Complete!"
echo "=========================================="
echo ""
echo "Results available in: $RESULTS_DIR/"
echo "  - T4_results.json"
echo "  - A10G_results.json"
echo "  - A100_results.json"
echo "  - combined_report.json"
echo ""
echo "Next steps:"
echo "  1. Review results in $RESULTS_DIR/"
echo "  2. Update EVALUATION_TEMPLATE.md with findings"
echo "  3. Analyze cost-performance trade-offs"
echo ""
