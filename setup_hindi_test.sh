#!/bin/bash

# Quick Hindi Test Setup Script
# Author: Kirti Palve
#
# This script helps you quickly set up a Hindi lip-sync test

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="$SCRIPT_DIR/test_videos_raw"

cd "$SCRIPT_DIR"

echo "=========================================="
echo "Hindi Lip-Sync Test Setup"
echo "Author: Kirti Palve"
echo "=========================================="
echo ""

# Check if Hindi audio exists
if [ -f "$TEST_DIR/hindi_audio.wav" ]; then
    echo "✅ Hindi audio already exists: $(du -h $TEST_DIR/hindi_audio.wav | cut -f1)"
else
    echo "🎵 Generating Hindi audio..."

    # Check if gtts is installed
    if ! python3 -c "import gtts" 2>/dev/null; then
        echo "📦 Installing gtts..."
        pip3 install gtts
    fi

    # Generate Hindi audio
    python3 << 'EOF'
from gtts import gTTS
text = '''नमस्ते, मेरा नाम किर्ति है। यह एक लिप सिंक परीक्षण है।
आज हम देखेंगे कि यह तकनीक कैसे काम करती है।'''
tts = gTTS(text=text, lang='hi', slow=False)
tts.save('test_videos_raw/hindi_audio.mp3')
print('✅ Generated: hindi_audio.mp3')
EOF

    # Convert to WAV
    ffmpeg -i "$TEST_DIR/hindi_audio.mp3" -ar 16000 -ac 1 \
           -acodec pcm_s16le "$TEST_DIR/hindi_audio.wav" -y \
           2>&1 | grep -E "(Duration|Output)" || true

    echo "✅ Converted to WAV: hindi_audio.wav"
fi

echo ""
echo "=========================================="
echo "Download Video of Man Speaking"
echo "=========================================="
echo ""

if [ -f "$TEST_DIR/man_speaking.mp4" ]; then
    echo "✅ Video already exists: $(du -h $TEST_DIR/man_speaking.mp4 | cut -f1)"
else
    echo "📹 You need to download a video of a man speaking."
    echo ""
    echo "Option 1: Download from Pexels (FREE, no login required)"
    echo ""
    echo "Recommended videos:"
    echo "  1. https://www.pexels.com/video/a-man-in-suit-talking-4752630/"
    echo "     (14s, professional setting, good quality)"
    echo ""
    echo "  2. https://www.pexels.com/video/a-man-speaking-while-sitting-5473739/"
    echo "     (17s, office setting)"
    echo ""
    echo "Steps:"
    echo "  1. Visit one of the URLs above in your browser"
    echo "  2. Click 'Free Download' button"
    echo "  3. Select 'HD 1280x720' quality"
    echo "  4. Save as 'man_speaking.mp4' in: $TEST_DIR"
    echo ""
    echo "Option 2: Use existing video"
    echo "  If you have a video of a man speaking, place it in:"
    echo "  $TEST_DIR/man_speaking.mp4"
    echo ""

    read -p "Press Enter when you've downloaded the video..."

    if [ ! -f "$TEST_DIR/man_speaking.mp4" ]; then
        echo "⚠️  man_speaking.mp4 not found in $TEST_DIR"
        echo "Please download and try again."
        exit 1
    fi
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""

echo "📁 Files ready:"
ls -lh "$TEST_DIR/man_speaking.mp4" "$TEST_DIR/hindi_audio.wav" 2>/dev/null || true

echo ""
echo "🎬 Next steps:"
echo ""
echo "Test locally first:"
echo "  python quick_test.py \\"
echo "    --video test_videos_raw/man_speaking.mp4 \\"
echo "    --audio test_videos_raw/hindi_audio.wav"
echo ""
echo "Or run full pipeline:"
echo "  python preprocess_videos.py --input-dir test_videos_raw"
echo "  python gpu_comparison.py"
echo ""
echo "✅ Ready to test Hindi lip-sync!"
