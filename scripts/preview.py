#!/usr/bin/env python3
"""Preview the timeline — seek to a scene and play.

Usage:
    python scripts/preview.py --scene 12
    python scripts/preview.py --frame 500
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kdenlive_api import Resolve
from kdenlive_api.constants import TRACK_VIDEO
from kdenlive_api.utils import frames_to_timecode


def preview_scene(scene_number: int | None = None,
                  frame: int | None = None,
                  track_idx: int = 0,
                  auto_play: bool = True):
    """Seek to a scene or frame and optionally start playback."""
    resolve = Resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    timeline = project.GetCurrentTimeline()
    fps = project.GetFps()

    if scene_number is not None:
        items = timeline.GetItemListInTrack(TRACK_VIDEO, track_idx)
        if scene_number < 1 or scene_number > len(items):
            print(f"ERROR: Scene {scene_number} not found")
            sys.exit(1)
        target = items[scene_number - 1]
        frame = target.GetStart()
        print(f"Scene {scene_number}: {target.GetName()} "
              f"at {frames_to_timecode(frame, fps)}")

    if frame is not None:
        timeline.Seek(frame)
        print(f"Seeked to frame {frame} ({frames_to_timecode(frame, fps)})")

        if auto_play:
            timeline.Play()
            print("Playing...")
    else:
        pos = timeline.GetPosition()
        print(f"Current position: frame {pos} ({frames_to_timecode(pos, fps)})")


def main():
    parser = argparse.ArgumentParser(description="Preview timeline in Kdenlive")
    parser.add_argument("--scene", type=int, default=None, help="Scene number (1-38)")
    parser.add_argument("--frame", type=int, default=None, help="Frame number")
    parser.add_argument("--track", type=int, default=0, help="Video track index")
    parser.add_argument("--no-play", action="store_true", help="Don't auto-play")
    args = parser.parse_args()

    if args.scene is None and args.frame is None:
        # Just show current position
        preview_scene(auto_play=False)
    else:
        preview_scene(args.scene, args.frame, args.track, not args.no_play)


if __name__ == "__main__":
    main()
