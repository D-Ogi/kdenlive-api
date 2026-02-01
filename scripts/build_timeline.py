#!/usr/bin/env python3
"""Build a complete scene-based video timeline in Kdenlive.

Usage:
    python scripts/build_timeline.py --video-dir PATH [--audio PATH]
                                      [--variant A] [--transition-frames 13]
                                      [--num-scenes N] [--script PATH]
"""

from __future__ import annotations

import argparse
import os
import sys

# Add parent dir to path so kdenlive_api is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kdenlive_api import Resolve
from kdenlive_api.constants import (
    DEFAULT_MIX_DURATION,
    MARKER_BLUE,
    MARKER_GREEN,
    MARKER_PURPLE,
    SCENE_DURATION_FRAMES,
)
from kdenlive_api.utils import (
    collect_scene_videos,
    frames_to_timecode,
    parse_script_scenes,
)


def build_timeline(
    video_dir: str,
    audio_path: str | None = None,
    variant: str = "A",
    transition_frames: int = DEFAULT_MIX_DURATION,
    script_path: str | None = None,
    num_scenes: int | None = None,
):
    """Build a video timeline from numbered scene clips.

    Steps:
        1. Connect to running Kdenlive via D-Bus
        2. Import all scene videos into bin (with folder)
        3. Import audio track
        4. Insert clips sequentially on video track
        5. Add cross-dissolve transitions between scenes
        6. Add guide markers for each scene
        7. Print summary
    """
    # -- Connect ---------------------------------------------------------
    resolve = Resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    pool = project.GetMediaPool()
    timeline = project.GetCurrentTimeline()

    fps = project.GetFps()
    print(f"Connected to project: {project.GetName()} ({fps} fps)")

    # -- Parse script for scene metadata ---------------------------------
    scenes_meta = []
    if script_path and os.path.exists(script_path):
        scenes_meta = parse_script_scenes(script_path)

    # -- Determine scene count -------------------------------------------
    if num_scenes is None:
        # Auto-detect from script metadata or video directory
        if scenes_meta:
            num_scenes = max(s["number"] for s in scenes_meta)
        else:
            # Count scene files in directory
            import glob as globmod
            matches = globmod.glob(os.path.join(video_dir, f"scene*-{variant}*.mp4"))
            if matches:
                num_scenes = len(matches)
            else:
                print("ERROR: Cannot determine scene count. Use --num-scenes.")
                sys.exit(1)
        print(f"Auto-detected {num_scenes} scenes")

    # -- Collect scene video files ---------------------------------------
    video_files = collect_scene_videos(video_dir, num_scenes=num_scenes, variant=variant)
    available = [(i, f) for i, f in enumerate(video_files) if f is not None]
    print(f"Found {len(available)}/{num_scenes} scene videos (variant {variant})")

    if not available:
        print("ERROR: No scene videos found. Check --video-dir path.")
        sys.exit(1)

    # -- Create bin folder and import ------------------------------------
    folder = pool.AddSubFolder(None, f"Scenes ({variant})")
    paths = [f for _, f in available]
    clips = pool.ImportMedia(paths, folder)
    print(f"Imported {len(clips)} clips into bin")

    # Map scene index to MediaPoolItem
    scene_clips = {}
    for (idx, _path), clip in zip(available, clips):
        scene_clips[idx] = clip

    # -- Import audio track ----------------------------------------------
    if audio_path and os.path.exists(audio_path):
        audio_clips = pool.ImportMedia([os.path.abspath(audio_path)])
        if audio_clips:
            print(f"Imported audio: {audio_path}")
    else:
        audio_clips = []
        if audio_path:
            print(f"WARNING: Audio file not found: {audio_path}")

    # -- Get track info --------------------------------------------------
    tracks = timeline.GetAllTracksInfo()
    video_tracks = [t for t in tracks if not t.get("audio", True)]
    audio_tracks = [t for t in tracks if t.get("audio", False)]

    if not video_tracks:
        print("No video tracks found, adding one...")
        timeline.AddTrack("V1", audio=False)
        tracks = timeline.GetAllTracksInfo()
        video_tracks = [t for t in tracks if not t.get("audio", True)]

    video_track_id = video_tracks[0].get("id", 0)
    print(f"Using video track ID: {video_track_id}")

    # -- Insert clips sequentially ---------------------------------------
    position = 0
    timeline_items = []

    for idx in range(num_scenes):
        if idx not in scene_clips:
            print(f"  Scene {idx + 1:02d}: MISSING -- skipping")
            position += SCENE_DURATION_FRAMES
            continue

        clip = scene_clips[idx]
        item = timeline.InsertClip(clip.bin_id, video_track_id, position)
        if item:
            timeline_items.append((idx, item))
            duration = item.GetDuration()
            print(f"  Scene {idx + 1:02d}: inserted at {frames_to_timecode(position, fps)} "
                  f"({duration} frames)")
            position += duration
        else:
            print(f"  Scene {idx + 1:02d}: INSERT FAILED")
            position += SCENE_DURATION_FRAMES

    print(f"Total timeline duration: {frames_to_timecode(position, fps)}")

    # -- Insert audio on audio track -------------------------------------
    if audio_clips and audio_tracks:
        audio_track_id = audio_tracks[0].get("id", 0)
        audio_item = timeline.InsertClip(
            audio_clips[0].bin_id, audio_track_id, 0
        )
        if audio_item:
            print(f"Audio inserted on track {audio_track_id}")

    # -- Add transitions (same-track mixes) ------------------------------
    if transition_frames > 0 and len(timeline_items) >= 2:
        mix_count = 0
        for i in range(len(timeline_items) - 1):
            _, item_a = timeline_items[i]
            _, item_b = timeline_items[i + 1]
            if timeline.AddTransition(item_a, item_b, transition_frames):
                mix_count += 1
        print(f"Added {mix_count} transitions ({transition_frames} frames each)")

    # -- Add guide markers per scene -------------------------------------
    pos = 0
    marker_count = 0
    for idx in range(num_scenes):
        # Find scene metadata
        meta = next((s for s in scenes_meta if s["number"] == idx + 1), None)
        label = f"Scene {idx + 1:02d}"
        if meta:
            label += f" -- {meta['title']}"

        # Color by section
        category = MARKER_PURPLE
        if meta:
            section = meta.get("section", "").upper()
            if "INTRO" in section:
                category = MARKER_BLUE
            elif "VERSE" in section:
                category = MARKER_GREEN
            elif "DROP" in section or "CHORUS" in section:
                category = MARKER_PURPLE

        if timeline.AddMarker(pos, category, label):
            marker_count += 1

        # Advance position
        if idx in scene_clips:
            clip_info = next(
                (item for si, item in timeline_items if si == idx), None
            )
            if clip_info:
                pos += clip_info.GetDuration()
            else:
                pos += SCENE_DURATION_FRAMES
        else:
            pos += SCENE_DURATION_FRAMES

    print(f"Added {marker_count} guide markers")

    # -- Summary ---------------------------------------------------------
    print("\n-- Timeline Summary --")
    timeline.PrintSummary()
    print("Done!")


def main():
    parser = argparse.ArgumentParser(
        description="Build a scene-based video timeline in Kdenlive"
    )
    parser.add_argument(
        "--video-dir",
        required=True,
        help="Directory containing scene MP4 files (e.g. scene01-A.mp4)",
    )
    parser.add_argument(
        "--audio",
        default=None,
        help="Path to the audio file",
    )
    parser.add_argument(
        "--variant",
        default="A",
        help="Scene variant to use (default: A)",
    )
    parser.add_argument(
        "--transition-frames",
        type=int,
        default=DEFAULT_MIX_DURATION,
        help="Transition duration in frames (0 = no transitions)",
    )
    parser.add_argument(
        "--script",
        default=None,
        help="Path to script-scenes.md for scene metadata",
    )
    parser.add_argument(
        "--num-scenes",
        type=int,
        default=None,
        help="Number of scenes (auto-detected from script or directory if omitted)",
    )

    args = parser.parse_args()
    build_timeline(
        video_dir=args.video_dir,
        audio_path=args.audio,
        variant=args.variant,
        transition_frames=args.transition_frames,
        script_path=args.script,
        num_scenes=args.num_scenes,
    )


if __name__ == "__main__":
    main()
