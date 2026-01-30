#!/usr/bin/env python3
"""Add or re-apply transitions between all clips on the video track.

Usage:
    python scripts/add_transitions.py [--duration 13] [--track 0]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from kdenlive_api import Resolve
from kdenlive_api.constants import DEFAULT_MIX_DURATION, TRACK_VIDEO


def add_transitions(duration_frames: int = DEFAULT_MIX_DURATION,
                    track_idx: int = 0):
    """Add same-track mix transitions between all adjacent clips."""
    resolve = Resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    timeline = project.GetCurrentTimeline()

    items = timeline.GetItemListInTrack(TRACK_VIDEO, track_idx)
    print(f"Found {len(items)} clips on video track {track_idx}")

    if len(items) < 2:
        print("Need at least 2 clips for transitions")
        return

    success = 0
    failed = 0
    for i in range(len(items) - 1):
        a = items[i]
        b = items[i + 1]
        if timeline.AddTransition(a, b, duration_frames):
            success += 1
        else:
            failed += 1
            print(f"  FAILED: transition between clip {i + 1} and {i + 2}")

    print(f"Added {success} transitions, {failed} failed "
          f"({duration_frames} frames each)")


def main():
    parser = argparse.ArgumentParser(description="Add transitions in Kdenlive")
    parser.add_argument("--duration", type=int, default=DEFAULT_MIX_DURATION,
                        help="Transition duration in frames")
    parser.add_argument("--track", type=int, default=0,
                        help="Video track index (0-based)")
    args = parser.parse_args()
    add_transitions(args.duration, args.track)


if __name__ == "__main__":
    main()
