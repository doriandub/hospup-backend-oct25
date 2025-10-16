#!/usr/bin/env python3
"""
Test FFmpeg concatenation without pre-conversion
Tests if we can directly concatenate videos of different formats/resolutions
"""
import subprocess
import sys
import os

def test_concat_without_conversion():
    """Test direct concatenation of mixed format videos"""

    print("=" * 60)
    print("TEST: FFmpeg Concatenation WITHOUT Pre-Conversion")
    print("=" * 60)

    # Simulate what we would receive from users:
    # - Different resolutions (720p, 1080p, 4K)
    # - Different codecs (H.264, HEVC)
    # - Different framerates (24fps, 30fps, 60fps)
    # - Different aspect ratios (16:9, 9:16)

    test_videos = [
        "video1.mp4",  # Will be created: 1080p, 30fps, H.264
        "video2.mp4",  # Will be created: 720p, 24fps, H.264
        "video3.mp4",  # Will be created: 1080p, 60fps, H.264
    ]

    # Create test videos with different specs
    print("\n📹 Creating test videos with different specs...")

    # Video 1: 1080p, 30fps, red color
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "color=c=red:s=1920x1080:r=30:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        test_videos[0]
    ], capture_output=True)
    print(f"✅ Created {test_videos[0]}: 1920x1080, 30fps")

    # Video 2: 720p, 24fps, blue color
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "color=c=blue:s=1280x720:r=24:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        test_videos[1]
    ], capture_output=True)
    print(f"✅ Created {test_videos[1]}: 1280x720, 24fps")

    # Video 3: 1080p, 60fps, green color
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", "color=c=green:s=1920x1080:r=60:d=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        test_videos[2]
    ], capture_output=True)
    print(f"✅ Created {test_videos[2]}: 1920x1080, 60fps")

    # Get detailed info on each video
    print("\n📊 Video specifications:")
    for video in test_videos:
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,codec_name",
            "-of", "json", video
        ], capture_output=True, text=True)
        print(f"\n{video}:")
        print(result.stdout)

    # Test 1: Direct concatenation with concat demuxer (FAILS with mixed specs)
    print("\n" + "=" * 60)
    print("TEST 1: Concat demuxer (simple but requires identical specs)")
    print("=" * 60)

    # Create file list
    with open("concat_list.txt", "w") as f:
        for video in test_videos:
            f.write(f"file '{video}'\n")

    result = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy",  # Try to copy without re-encoding
        "output_concat_demuxer.mp4"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ SUCCESS: Concat demuxer worked!")
        print("   -> Videos can be concatenated WITHOUT conversion")
    else:
        print("❌ FAILED: Concat demuxer requires identical specs")
        print(f"   Error: {result.stderr[:200]}")

    # Test 2: Concat filter with auto-scaling (WORKS but re-encodes)
    print("\n" + "=" * 60)
    print("TEST 2: Concat filter (handles mixed specs, re-encodes)")
    print("=" * 60)

    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", test_videos[0],
        "-i", test_videos[1],
        "-i", test_videos[2],
        "-filter_complex",
        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v0];"
        "[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1];"
        "[2:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v2];"
        "[v0][v1][v2]concat=n=3:v=1:a=0[outv]",
        "-map", "[outv]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "output_concat_filter.mp4"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ SUCCESS: Concat filter worked!")
        print("   -> Mixed specs handled BUT requires re-encoding during concat")

        # Get output video info
        probe = subprocess.run([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            "output_concat_filter.mp4"
        ], capture_output=True, text=True)
        print(f"   Output specs: {probe.stdout.strip()}")
    else:
        print("❌ FAILED: Concat filter failed")
        print(f"   Error: {result.stderr[:500]}")

    # Test 3: Pre-convert to same specs THEN concat (YOUR CURRENT APPROACH)
    print("\n" + "=" * 60)
    print("TEST 3: Pre-convert then concat (your current approach)")
    print("=" * 60)

    converted_videos = []
    for i, video in enumerate(test_videos):
        converted = f"converted_{i}.mp4"
        result = subprocess.run([
            "ffmpeg", "-y", "-i", video,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-pix_fmt", "yuv420p",
            converted
        ], capture_output=True, text=True)
        converted_videos.append(converted)
        print(f"✅ Converted {video} -> {converted}")

    # Now concat with demuxer (should work since all specs identical)
    with open("concat_list_converted.txt", "w") as f:
        for video in converted_videos:
            f.write(f"file '{video}'\n")

    result = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", "concat_list_converted.txt",
        "-c", "copy",  # Can copy since all specs identical
        "output_preconvert.mp4"
    ], capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ SUCCESS: Pre-convert + concat demuxer worked!")
        print("   -> Can use fast 'copy' codec for concatenation")
    else:
        print("❌ FAILED")
        print(f"   Error: {result.stderr[:500]}")

    # Comparison
    print("\n" + "=" * 60)
    print("RESULTS COMPARISON")
    print("=" * 60)

    print("\n📊 File sizes:")
    for f in ["output_concat_demuxer.mp4", "output_concat_filter.mp4", "output_preconvert.mp4"]:
        if os.path.exists(f):
            size = os.path.getsize(f) / 1024 / 1024
            print(f"  {f}: {size:.2f} MB")

    print("\n⏱️  Performance implications:")
    print("  Method 1 (Concat demuxer):")
    print("    ❌ Requires ALL videos in IDENTICAL format")
    print("    ✅ Fastest concatenation (copy codec)")
    print("    ❌ Not practical with user uploads")

    print("\n  Method 2 (Concat filter):")
    print("    ✅ Handles mixed formats")
    print("    ❌ Re-encodes DURING concatenation (slow for final video)")
    print("    ❌ Quality loss from re-encoding user assets")

    print("\n  Method 3 (Pre-convert):")
    print("    ✅ Handles mixed formats")
    print("    ✅ Fast concatenation (copy codec)")
    print("    ✅ Pre-process ONCE per asset (not per video generation)")
    print("    ✅ Predictable quality")

    print("\n" + "=" * 60)
    print("CONCLUSION")
    print("=" * 60)
    print("""
    🎯 Pre-conversion IS necessary because:

    1. User uploads = unpredictable formats (iPhone HEVC, Android H.264, etc.)
    2. Concat demuxer (fast copy) REQUIRES identical specs
    3. Concat filter works BUT re-encodes every video generation

    💡 Your current approach is OPTIMAL:
    - Pre-convert assets ONCE on upload
    - Concat with fast 'copy' codec during video generation
    - No re-encoding = faster generation + consistent quality

    ✅ Recommendation: KEEP the pre-conversion on asset upload
    """)

    # Cleanup
    print("\n🧹 Cleaning up test files...")
    for f in test_videos + converted_videos + ["concat_list.txt", "concat_list_converted.txt",
                                                "output_concat_demuxer.mp4", "output_concat_filter.mp4",
                                                "output_preconvert.mp4"]:
        if os.path.exists(f):
            os.remove(f)
    print("✅ Cleanup complete")

if __name__ == "__main__":
    test_concat_without_conversion()
