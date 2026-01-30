"""Low-level D-Bus client for Kdenlive scripting interface."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from kdenlive_api.constants import (
    DBUS_IFACE_SCRIPTING,
    DBUS_PATH,
    DBUS_SERVICE,
)


def _get_dbus_backend():
    """Select the best available D-Bus backend."""
    # Try pydbus first (Linux, synchronous, simple)
    try:
        import pydbus
        return "pydbus"
    except ImportError:
        pass
    # Try dbus-next (async, cross-platform)
    try:
        import dbus_next
        return "dbus_next"
    except ImportError:
        pass
    # Try jeepney (pure-python, Linux)
    try:
        import jeepney
        return "jeepney"
    except ImportError:
        pass
    return None


class KdenliveDBus:
    """Low-level D-Bus proxy for Kdenlive scripting methods.

    Wraps the org.kde.kdenlive.scripting interface exposed by our
    patched Kdenlive build. On Linux uses pydbus; falls back to
    subprocess calls to qdbus/gdbus on other platforms.
    """

    def __init__(self):
        self._backend = _get_dbus_backend()
        self._proxy = None
        self._connect()

    def _connect(self):
        if self._backend == "pydbus":
            import pydbus
            bus = pydbus.SessionBus()
            self._proxy = bus.get(DBUS_SERVICE, DBUS_PATH)[DBUS_IFACE_SCRIPTING]
        elif self._backend == "dbus_next":
            # dbus_next requires async — we use sync wrapper
            self._proxy = None  # Will use _call_subprocess fallback
            self._backend = "subprocess"
        elif self._backend == "jeepney":
            self._proxy = None
            self._backend = "subprocess"
        else:
            self._backend = "subprocess"

    def _call(self, method: str, *args) -> Any:
        """Call a D-Bus method on the scripting interface."""
        if self._proxy is not None:
            func = getattr(self._proxy, method)
            return func(*args)
        return self._call_subprocess(method, *args)

    def _call_subprocess(self, method: str, *args) -> str:
        """Fallback: call via qdbus/gdbus CLI."""
        # Try qdbus first
        cmd = ["qdbus", DBUS_SERVICE, DBUS_PATH,
               f"{DBUS_IFACE_SCRIPTING}.{method}"]
        for a in args:
            if isinstance(a, (list, tuple)):
                for item in a:
                    cmd.append(str(item))
            else:
                cmd.append(str(a))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    timeout=30, check=True)
            return result.stdout.strip()
        except FileNotFoundError:
            pass
        # Try gdbus
        call_args = ", ".join(repr(a) for a in args) if args else ""
        cmd_gdbus = [
            "gdbus", "call", "--session",
            "--dest", DBUS_SERVICE,
            "--object-path", DBUS_PATH,
            "--method", f"{DBUS_IFACE_SCRIPTING}.{method}",
        ]
        for a in args:
            cmd_gdbus.append(str(a))
        result = subprocess.run(cmd_gdbus, capture_output=True, text=True,
                                timeout=30, check=True)
        return result.stdout.strip()

    # ── Project Management ─────────────────────────────────────────────

    def new_project(self, name: str) -> str:
        return self._call("scriptNewProject", name)

    def open_project(self, file_path: str) -> bool:
        return bool(self._call("scriptOpenProject", file_path))

    def save_project(self) -> bool:
        return bool(self._call("scriptSaveProject"))

    def save_project_as(self, file_path: str) -> bool:
        return bool(self._call("scriptSaveProjectAs", file_path))

    def get_project_name(self) -> str:
        return self._call("scriptGetProjectName")

    def get_project_path(self) -> str:
        return self._call("scriptGetProjectPath")

    def get_project_fps(self) -> float:
        result = self._call("scriptGetProjectFps")
        return float(result) if isinstance(result, str) else result

    def get_project_resolution_width(self) -> int:
        result = self._call("scriptGetProjectResolutionWidth")
        return int(result) if isinstance(result, str) else result

    def get_project_resolution_height(self) -> int:
        result = self._call("scriptGetProjectResolutionHeight")
        return int(result) if isinstance(result, str) else result

    def get_project_property(self, key: str) -> str:
        return self._call("scriptGetProjectProperty", key)

    def set_project_property(self, key: str, value: str) -> bool:
        return bool(self._call("scriptSetProjectProperty", key, value))

    # ── Media Pool (Bin) ───────────────────────────────────────────────

    def import_media(self, file_paths: list[str], folder_id: str = "-1") -> list[str]:
        result = self._call("scriptImportMedia", file_paths, folder_id)
        if isinstance(result, str):
            return [r for r in result.split("\n") if r] if result else []
        return list(result) if result else []

    def create_folder(self, name: str, parent_id: str = "-1") -> str:
        return self._call("scriptCreateFolder", name, parent_id)

    def get_all_clip_ids(self) -> list[str]:
        result = self._call("scriptGetAllClipIds")
        if isinstance(result, str):
            return [r for r in result.split("\n") if r] if result else []
        return list(result) if result else []

    def get_folder_clip_ids(self, folder_id: str) -> list[str]:
        result = self._call("scriptGetFolderClipIds", folder_id)
        if isinstance(result, str):
            return [r for r in result.split("\n") if r] if result else []
        return list(result) if result else []

    def get_clip_properties(self, bin_id: str) -> dict:
        result = self._call("scriptGetClipProperties", bin_id)
        if isinstance(result, str):
            return {}  # subprocess fallback returns string
        return dict(result) if result else {}

    def delete_bin_clip(self, bin_id: str) -> bool:
        return bool(self._call("scriptDeleteBinClip", bin_id))

    # ── Timeline ───────────────────────────────────────────────────────

    def get_track_count(self, track_type: str) -> int:
        result = self._call("scriptGetTrackCount", track_type)
        return int(result) if isinstance(result, str) else result

    def get_track_info(self, track_index: int) -> dict:
        result = self._call("scriptGetTrackInfo", track_index)
        return dict(result) if result and not isinstance(result, str) else {}

    def get_all_tracks_info(self) -> list[dict]:
        result = self._call("scriptGetAllTracksInfo")
        if isinstance(result, str):
            return []
        return [dict(t) for t in result] if result else []

    def add_track(self, name: str, audio_track: bool) -> int:
        result = self._call("scriptAddTrack", name, audio_track)
        return int(result) if isinstance(result, str) else result

    def insert_clip(self, bin_clip_id: str, track_id: int, position: int) -> int:
        result = self._call("scriptInsertClip", bin_clip_id, track_id, position)
        return int(result) if isinstance(result, str) else result

    def insert_clips_sequentially(self, bin_clip_ids: list[str], track_id: int,
                                   start_position: int) -> list[int]:
        result = self._call("scriptInsertClipsSequentially",
                            bin_clip_ids, track_id, start_position)
        if isinstance(result, str):
            return [int(x) for x in result.split("\n") if x]
        return list(result) if result else []

    def move_clip(self, clip_id: int, track_id: int, position: int) -> bool:
        return bool(self._call("scriptMoveClip", clip_id, track_id, position))

    def resize_clip(self, clip_id: int, new_duration: int, from_right: bool) -> int:
        result = self._call("scriptResizeClip", clip_id, new_duration, from_right)
        return int(result) if isinstance(result, str) else result

    def delete_timeline_clip(self, clip_id: int) -> bool:
        return bool(self._call("scriptDeleteTimelineClip", clip_id))

    def get_clips_on_track(self, track_id: int) -> list[dict]:
        result = self._call("scriptGetClipsOnTrack", track_id)
        if isinstance(result, str):
            return []
        return [dict(c) for c in result] if result else []

    def get_timeline_clip_info(self, clip_id: int) -> dict:
        result = self._call("scriptGetTimelineClipInfo", clip_id)
        return dict(result) if result and not isinstance(result, str) else {}

    def cut_clip(self, clip_id: int, position: int) -> bool:
        return bool(self._call("scriptCutClip", clip_id, position))

    # ── Transitions & Mixes ────────────────────────────────────────────

    def add_mix(self, clip_id_a: int, clip_id_b: int, duration_frames: int) -> bool:
        return bool(self._call("scriptAddMix", clip_id_a, clip_id_b, duration_frames))

    def add_composition(self, transition_id: str, track_id: int,
                        position: int, duration: int) -> int:
        result = self._call("scriptAddComposition",
                            transition_id, track_id, position, duration)
        return int(result) if isinstance(result, str) else result

    def remove_mix(self, clip_id: int) -> bool:
        return bool(self._call("scriptRemoveMix", clip_id))

    # ── Markers & Guides ───────────────────────────────────────────────

    def add_guide(self, frame: int, comment: str, category: int) -> bool:
        return bool(self._call("scriptAddGuide", frame, comment, category))

    def get_guides(self) -> list[dict]:
        result = self._call("scriptGetGuides")
        if isinstance(result, str):
            return []
        return [dict(g) for g in result] if result else []

    def delete_guide(self, frame: int) -> bool:
        return bool(self._call("scriptDeleteGuide", frame))

    def delete_guides_by_category(self, category: int) -> bool:
        return bool(self._call("scriptDeleteGuidesByCategory", category))

    # ── Playback & Monitor ─────────────────────────────────────────────

    def seek(self, frame: int) -> None:
        self._call("scriptSeek", frame)

    def get_position(self) -> int:
        result = self._call("scriptGetPosition")
        return int(result) if isinstance(result, str) else result

    def play(self) -> None:
        self._call("scriptPlay")

    def pause(self) -> None:
        self._call("scriptPause")

    # ── Render ─────────────────────────────────────────────────────────

    def render(self, url: str) -> None:
        self._call("scriptRender", url)
