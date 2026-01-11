# Error Handling Documentation

Author: Kirti Palve

This document describes the comprehensive error handling implemented in the Wav2Lip LipSync Service.

## Overview

The service includes robust error handling for common edge cases and failure scenarios to provide clear, actionable error messages to users.

## Edge Cases Handled

### 1. No Face Detection

**Scenario**: Video doesn't contain a detectable human face

**Error Message**:
```
No face detected in video. Please ensure:
1. Video contains a clear, front-facing face
2. Face is well-lit and clearly visible
3. Try increasing --resize_factor parameter (e.g., 2 or 4)
```

**Possible Causes**:
- Video contains only objects/scenery
- Face is too small in frame
- Poor lighting conditions
- Extreme side profile
- Face is occluded or partially visible

**Solutions**:
- Use videos with clear, frontal face shots
- Ensure good lighting
- Increase `resize_factor` parameter to 2 or 4
- Crop video to focus on the face

### 1a. Partial Face Detection (Face Present Only in Some Frames)

**Scenario**: Face is detected in some frames but lost in others

**Error Message**:
```
Face detected only in some frames. Please ensure:
1. Face remains visible throughout the entire video
2. Avoid side angles, head turns, or occlusions
3. Keep consistent lighting throughout the video
4. Try increasing --resize_factor to 2 or 4 for better tracking
5. Consider trimming video to sections with continuous face visibility
```

**Possible Causes**:
- Person turns their head away from camera mid-video
- Temporary occlusions (hand gestures, objects passing by)
- Dramatic lighting changes during video
- Person moves out of frame temporarily
- Extreme facial expressions causing tracking loss

**Solutions**:
- Keep face front-facing throughout entire video
- Avoid head turns or looking away
- Remove frames where face is occluded
- Maintain consistent distance from camera
- Use stable, continuous lighting
- Trim video to keep only segments with continuous face visibility
- Increase `resize_factor` for more robust tracking

### 2. Multiple Faces

**Scenario**: Video contains multiple people

**Error Message**:
```
Multiple faces detected in video. Wav2Lip works best with:
1. Single person videos
2. Clear, unobstructed face throughout the video
Consider cropping video to focus on one person.
```

**Solutions**:
- Crop video to show only one person
- Use single-person footage
- Ensure background doesn't contain faces (posters, TV screens, etc.)

### 3. Invalid Video File

**Scenario**: Corrupted or unsupported video format

**Error Message**:
```
Invalid video file: Unable to open video. Please ensure the file is a valid video format (mp4, avi, mov).
```

**Validation Checks**:
- File can be opened by OpenCV
- Video has valid frame rate (fps > 0)
- Video contains frames (frame_count > 0)

**Solutions**:
- Re-encode video to MP4 format
- Verify file isn't corrupted
- Ensure file size > 0

### 4. Invalid Audio File

**Scenario**: Corrupted or unsupported audio format

**Error Message**:
```
Invalid audio file: {error_details}
```

**Validation Checks**:
- Audio file can be loaded by librosa
- Audio data is not empty

**Solutions**:
- Convert audio to WAV or MP3
- Verify file isn't corrupted
- Check audio has actual content (not silence)

### 5. Out of Memory

**Scenario**: Video too large for GPU memory

**Error Message**:
```
Out of memory error. Try:
1. Using a shorter video
2. Reducing video resolution
3. Using --use_gan=false for lower memory usage
```

**Solutions**:
- Split long videos into shorter segments
- Reduce video resolution (720p recommended)
- Use base model instead of GAN model
- Upgrade to larger GPU (A10G or A100)

### 6. Empty Output

**Scenario**: Processing completes but output file is empty or missing

**Error**: `Generated output file is empty` or `Output file not generated`

**Possible Causes**:
- Insufficient disk space
- Processing interrupted
- Invalid input causing silent failure

**Solutions**:
- Check logs for processing errors
- Verify input files are valid
- Retry with different parameters

## Error Types

The service categorizes errors into two types for better debugging:

### Validation Errors
- User input issues (bad files, missing faces, etc.)
- Can be fixed by user
- `error_type`: `validation_error`

### System Errors
- Internal processing failures
- May require developer investigation
- `error_type`: `system_error`

## API Error Response Format

```json
{
  "status": "failed",
  "error": "Detailed error message with suggestions",
  "error_type": "validation_error|system_error",
  "failed_at": 1703520000.0
}
```

## Best Practices for Users

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

4. **Testing Workflow**:
   - Test with sample data first
   - Start with short videos
   - Gradually increase complexity

## Troubleshooting Guide

| Error Pattern | Quick Fix |
|--------------|-----------|
| "No face detected" | Increase resize_factor to 2-4, ensure front-facing face |
| "Face detected only in some frames" | Keep face visible throughout, avoid head turns, trim problematic sections |
| "Multiple faces" | Crop video to single person |
| "Out of memory" | Use shorter video or use_gan=false |
| "Invalid video" | Re-encode to MP4 with standard codec |
| "Invalid audio" | Convert to WAV format |
| Timeout | Use async endpoint instead of sync |

## Monitoring and Debugging

### Checking Job Status

```python
response = requests.get(f"{API_URL}/api/v1/jobs/{job_id}")
status = response.json()

if status["status"] == "failed":
    print(f"Error Type: {status.get('error_type')}")
    print(f"Error: {status['error']}")
```

### Common Debug Steps

1. Verify input files locally first
2. Check file sizes and formats
3. Test with provided sample data
4. Review error_type to determine if user or system issue
5. Check API logs for detailed stack traces

## Future Enhancements

Planned improvements:
- Pre-processing face detection preview
- Automatic video optimization suggestions
- Multi-face support with face selection
- Progressive upload with validation
- Real-time progress updates during processing

---

## Advanced Edge Case: Partial Face Visibility

### The Challenge

Wav2Lip requires the face to be visible in **every frame** of the video. If the face disappears even temporarily, processing will fail. This is a common issue that many users encounter.

### Common Scenarios Where This Happens

1. **Head Turns**
   - Person looks to the side
   - Person looks up or down
   - 3/4 profile views

2. **Temporary Occlusions**
   - Hand gestures covering face
   - Hair moving across face
   - Objects passing between camera and subject

3. **Movement**
   - Person walks out of frame
   - Person leans back out of camera view
   - Extreme close-ups where face goes out of frame

4. **Camera/Lighting Changes**
   - Scene transitions
   - Dramatic lighting shifts
   - Camera cuts or pans

### How the System Handles It

The enhanced error handling detects this specific scenario and provides targeted advice:

```python
# In main.py lines 210-218
if "some frames" in error_msg or "intermittent" in error_msg or "lost track" in error_msg:
    raise ValueError(
        "Face detected only in some frames. Please ensure:\n"
        "1. Face remains visible throughout the entire video\n"
        "2. Avoid side angles, head turns, or occlusions\n"
        "3. Keep consistent lighting throughout the video\n"
        "4. Try increasing --resize_factor to 2 or 4 for better tracking\n"
        "5. Consider trimming video to sections with continuous face visibility"
    )
```

### Best Practices for Video Recording

To avoid partial face detection issues:

1. ✅ **Keep face centered and front-facing**
   - Maintain eye contact with camera
   - Avoid turning head more than 15-20 degrees

2. ✅ **Avoid hand gestures near face**
   - Keep hands below chin level
   - No face touching or hair adjusting

3. ✅ **Maintain consistent framing**
   - Stay within frame boundaries
   - Don't lean too far forward/backward

4. ✅ **Use consistent lighting**
   - Avoid moving between light/shadow
   - No sudden brightness changes

5. ✅ **Review before processing**
   - Play through entire video
   - Identify and trim problematic sections
   - Consider splitting into multiple clips

### Video Editing Solutions

If you have a video with partial face visibility:

**Option 1: Trim the Video**
```bash
# Use ffmpeg to cut out problematic sections
ffmpeg -i input.mp4 -ss 00:00:05 -to 00:00:35 -c copy output.mp4
```

**Option 2: Split into Multiple Clips**
Process only the sections with continuous face visibility separately, then combine results.

**Option 3: Increase Tracking Robustness**
Use higher `resize_factor` parameter (2 or 4) which can help maintain face tracking through minor occlusions.

### Technical Implementation Notes

The partial face detection is identified by parsing Wav2Lip's stderr output for keywords:
- "some frames"
- "intermittent"
- "lost track"

This provides more specific guidance than the generic "no face detected" error, helping users understand exactly what went wrong and how to fix it.
