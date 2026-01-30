#!/usr/bin/env python3
"""Replace a single scene in the timeline with a new video file.

Usage:
    python scripts/replace_scene.py --scene 5 --file output/video/scene05-B-seed3.mp4
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kdenlive_api import Resolve
from kdenlive_api.constants import TRACK_VIDEO


def replace_scene(scene_number: int, new_file: str, track_idx: int = 0):
    """Replace a scene clip on the timeline.

    Finds the clip at the scene's position, removes it, imports the
    new file, and inserts it at the same position with the same duration.
    """
    resolve = Resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    pool = project.GetMediaPool()
    timeline = project.GetCurrentTimeline()

    # Get all clips on the target video track
    items = timeline.GetItemListInTrack(TRACK_VIDEO, track_idx)
    if scene_number < 1 or scene_number > len(items):
        print(f"ERROR: Scene {scene_number} not found (track has {len(items)} clips)")
        sys.exit(1)

    target = items[scene_number - 1]
    old_position = target.GetStart()
    old_duration = target.GetDuration()
    old_track = target.GetTrackId()

    print(f"Replacing scene {scene_number}: "
          f"pos={old_position}, dur={old_duration}, track={old_track}")

    # Import new clip
    new_clips = pool.ImportMedia([os.path.abspath(new_file)])
    if not new_clips:
        print("ERROR: Failed to import new file")
        sys.exit(1)

    new_clip = new_clips[0]
    print(f"Imported: {new_clip.GetName()} (bin_id={new_clip.bin_id})")

    # Delete old clip
    target.Delete()
    print("Deleted old clip")

    # Insert new clip at same position
    new_item = timeline.InsertClip(new_clip.bin_id, old_track, old_position)
    if new_item:
        # Match duration if needed
        new_dur = new_item.GetDuration()
        if new_dur != old_duration:
            actual = new_item.SetDuration(old_duration)
            print(f"Resized: {new_dur} -> {actual} frames")
        print(f"Inserted new clip at position {old_position}")
    else:
        print("ERROR: Failed to insert new clip")
        sys.exit(1)

    print("Done!")


def main():
    parser = argparse.ArgumentParser(description="Replace a scene in Kdenlive timeline")
    parser.add_argument("--scene", type=int, required=True, help="Scene number (1-38)")
    parser.add_argument("--file", required=True, help="Path to new video file")
    parser.add_argument("--track", type=int, default=0, help="Video track index (0-based)")
    args = parser.parse_args()
    replace_scene(args.scene, args.file, args.track)


if __name__ == "__main__":
    main()
