"""Pytest fixtures for kdenlive_api tests."""

from __future__ import annotations

import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class MockDBus:
    """Mock D-Bus client for testing without a running Kdenlive instance."""

    def __init__(self):
        self._project_name = "Test Project"
        self._project_path = "/tmp/test.kdenlive"
        self._fps = 25.0
        self._width = 1536
        self._height = 864
        self._clips = {}
        self._folders = {}
        self._timeline_clips = {}
        self._tracks = [
            {"id": 0, "name": "V1", "audio": False},
            {"id": 1, "name": "V2", "audio": False},
            {"id": 2, "name": "A1", "audio": True},
        ]
        self._guides = []
        self._position = 0
        self._next_bin_id = 1
        self._next_clip_id = 100
        self._next_folder_id = 10
        self._properties = {}

    # Project
    def new_project(self, name):
        self._project_name = name
        return name

    def open_project(self, path):
        self._project_path = path
        return True

    def save_project(self):
        return True

    def save_project_as(self, path):
        self._project_path = path
        return True

    def get_project_name(self):
        return self._project_name

    def get_project_path(self):
        return self._project_path

    def get_project_fps(self):
        return self._fps

    def get_project_resolution_width(self):
        return self._width

    def get_project_resolution_height(self):
        return self._height

    def get_project_property(self, key):
        return self._properties.get(key, "")

    def set_project_property(self, key, value):
        self._properties[key] = value
        return True

    # Media Pool
    def import_media(self, file_paths, folder_id="-1"):
        ids = []
        for p in file_paths:
            bid = str(self._next_bin_id)
            self._next_bin_id += 1
            self._clips[bid] = {
                "name": os.path.basename(p),
                "path": p,
                "duration": 125,
                "folder": folder_id,
            }
            ids.append(bid)
        return ids

    def create_folder(self, name, parent_id="-1"):
        fid = str(self._next_folder_id)
        self._next_folder_id += 1
        self._folders[fid] = {"name": name, "parent": parent_id}
        return fid

    def get_all_clip_ids(self):
        return list(self._clips.keys())

    def get_folder_clip_ids(self, folder_id):
        return [cid for cid, c in self._clips.items()
                if c.get("folder") == folder_id]

    def get_clip_properties(self, bin_id):
        return dict(self._clips.get(bin_id, {}))

    def delete_bin_clip(self, bin_id):
        return self._clips.pop(bin_id, None) is not None

    # Timeline
    def get_track_count(self, track_type):
        is_audio = track_type == "audio"
        return sum(1 for t in self._tracks if t["audio"] == is_audio)

    def get_track_info(self, track_index):
        if 0 <= track_index < len(self._tracks):
            return dict(self._tracks[track_index])
        return {}

    def get_all_tracks_info(self):
        return [dict(t) for t in self._tracks]

    def add_track(self, name, audio):
        tid = len(self._tracks)
        self._tracks.append({"id": tid, "name": name, "audio": audio})
        return tid

    def insert_clip(self, bin_clip_id, track_id, position):
        cid = self._next_clip_id
        self._next_clip_id += 1
        clip_data = self._clips.get(bin_clip_id, {})
        self._timeline_clips[cid] = {
            "id": cid,
            "binId": bin_clip_id,
            "trackId": track_id,
            "position": position,
            "duration": clip_data.get("duration", 125),
            "name": clip_data.get("name", f"clip_{cid}"),
        }
        return cid

    def insert_clips_sequentially(self, bin_clip_ids, track_id, start_position):
        ids = []
        pos = start_position
        for bid in bin_clip_ids:
            cid = self.insert_clip(bid, track_id, pos)
            ids.append(cid)
            pos += self._timeline_clips[cid]["duration"]
        return ids

    def move_clip(self, clip_id, track_id, position):
        if clip_id in self._timeline_clips:
            self._timeline_clips[clip_id]["trackId"] = track_id
            self._timeline_clips[clip_id]["position"] = position
            return True
        return False

    def resize_clip(self, clip_id, new_duration, from_right):
        if clip_id in self._timeline_clips:
            self._timeline_clips[clip_id]["duration"] = new_duration
            return new_duration
        return -1

    def delete_timeline_clip(self, clip_id):
        return self._timeline_clips.pop(clip_id, None) is not None

    def get_clips_on_track(self, track_id):
        return [dict(c) for c in self._timeline_clips.values()
                if c["trackId"] == track_id]

    def get_timeline_clip_info(self, clip_id):
        return dict(self._timeline_clips.get(clip_id, {}))

    def cut_clip(self, clip_id, position):
        return clip_id in self._timeline_clips

    # Transitions
    def add_mix(self, clip_id_a, clip_id_b, duration_frames):
        return (clip_id_a in self._timeline_clips and
                clip_id_b in self._timeline_clips)

    def add_composition(self, transition_id, track_id, position, duration):
        return self._next_clip_id

    def remove_mix(self, clip_id):
        return clip_id in self._timeline_clips

    # Guides
    def add_guide(self, frame, comment, category):
        self._guides.append({
            "frame": frame, "comment": comment, "category": category
        })
        return True

    def get_guides(self):
        return list(self._guides)

    def delete_guide(self, frame):
        before = len(self._guides)
        self._guides = [g for g in self._guides if g["frame"] != frame]
        return len(self._guides) < before

    def delete_guides_by_category(self, category):
        before = len(self._guides)
        self._guides = [g for g in self._guides if g["category"] != category]
        return len(self._guides) < before

    # Playback
    def seek(self, frame):
        self._position = frame

    def get_position(self):
        return self._position

    def play(self):
        pass

    def pause(self):
        pass

    def render(self, url):
        pass


@pytest.fixture
def mock_dbus():
    """Return a MockDBus instance for testing."""
    return MockDBus()


@pytest.fixture
def resolve(mock_dbus):
    """Return a Resolve instance with mocked D-Bus."""
    from kdenlive_api.resolve import Resolve
    r = Resolve.__new__(Resolve)
    r._dbus = mock_dbus
    return r
