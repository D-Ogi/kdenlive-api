"""Low-level D-Bus client for Kdenlive scripting interface."""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from kdenlive_api.constants import (
    DBUS_IFACE_SCRIPTING,
    DBUS_PATH,
    DBUS_SERVICE,
    DBUS_SERVICE_PREFIX,
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


def _find_dbus_tool(name: str) -> str | None:
    """Find a D-Bus CLI tool (dbus-send, gdbus, qdbus) in CraftRoot or PATH."""
    import os
    import shutil
    craft_root = os.environ.get("CRAFT_ROOT", r"C:\CraftRoot")
    craft_path = os.path.join(craft_root, "bin", f"{name}.exe")
    if os.path.isfile(craft_path):
        return craft_path
    craft_path2 = os.path.join(craft_root, "bin", name)
    if os.path.isfile(craft_path2):
        return craft_path2
    return shutil.which(name)


class KdenliveDBus:
    """Low-level D-Bus proxy for Kdenlive scripting methods.

    Wraps the org.kde.kdenlive.scripting interface exposed by our
    patched Kdenlive build. On Linux uses pydbus; falls back to
    subprocess calls to qdbus/gdbus on other platforms.
    """

    def __init__(self):
        self._backend = _get_dbus_backend()
        self._proxy = None
        self._service = self._discover_service()
        self._connect()

    def _discover_service(self) -> str:
        """Find the actual D-Bus service name (org.kde.kdenlive-{PID})."""
        dbus_send = _find_dbus_tool("dbus-send")
        if not dbus_send:
            return DBUS_SERVICE

        try:
            result = subprocess.run(
                [dbus_send, "--session",
                 "--dest=org.freedesktop.DBus",
                 "--print-reply", "/org/freedesktop/DBus",
                 "org.freedesktop.DBus.ListNames"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                # Lines look like: string "org.kde.kdenlive-12345"
                if line.startswith('string "'):
                    value = line[8:].rstrip('"')
                    if value.startswith(DBUS_SERVICE_PREFIX + "-"):
                        return value
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass
        return DBUS_SERVICE

    def _connect(self):
        if self._backend == "pydbus":
            import pydbus
            bus = pydbus.SessionBus()
            self._proxy = bus.get(self._service, DBUS_PATH)[DBUS_IFACE_SCRIPTING]
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
        try:
            return self._call_subprocess(method, *args)
        except (subprocess.CalledProcessError, Exception) as e:
            # Service may have restarted — try re-discovering
            old_svc = self._service
            self._service = self._discover_service()
            if self._service != old_svc:
                return self._call_subprocess(method, *args)
            raise

    def _call_subprocess(self, method: str, *args) -> str:
        """Fallback: call via dbus-send/qdbus/gdbus CLI."""
        service = self._service

        # Try dbus-send first (available on Windows via KDE Craft)
        dbus_send = _find_dbus_tool("dbus-send")
        if not dbus_send:
            dbus_send = "dbus-send"
        cmd_dbus_send = [
            dbus_send, "--session", "--print-reply",
            f"--dest={service}",
            DBUS_PATH,
            f"{DBUS_IFACE_SCRIPTING}.{method}",
        ]
        for a in args:
            if isinstance(a, bool):
                cmd_dbus_send.append(f"boolean:{str(a).lower()}")
            elif isinstance(a, int):
                cmd_dbus_send.append(f"int32:{a}")
            elif isinstance(a, float):
                cmd_dbus_send.append(f"double:{a}")
            elif isinstance(a, (list, tuple)):
                # dbus-send array syntax: array:string:"v1","v2","v3"
                if len(a) == 0:
                    cmd_dbus_send.append("array:string:")
                else:
                    items = ",".join(f'"{item}"' for item in a)
                    cmd_dbus_send.append(f"array:string:{items}")
            else:
                cmd_dbus_send.append(f"string:{a}")
        try:
            result = subprocess.run(cmd_dbus_send, capture_output=True,
                                    text=True, timeout=30, check=True)
            return self._parse_dbus_send_output(result.stdout.strip())
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

        # Try qdbus
        qdbus = _find_dbus_tool("qdbus") or "qdbus"
        cmd = [qdbus, service, DBUS_PATH,
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
        gdbus = _find_dbus_tool("gdbus") or "gdbus"
        cmd_gdbus = [
            gdbus, "call", "--session",
            "--dest", service,
            "--object-path", DBUS_PATH,
            "--method", f"{DBUS_IFACE_SCRIPTING}.{method}",
        ]
        for a in args:
            cmd_gdbus.append(str(a))
        result = subprocess.run(cmd_gdbus, capture_output=True, text=True,
                                timeout=30, check=True)
        return result.stdout.strip()

    @staticmethod
    def _parse_dbus_send_output(output: str):
        """Parse dbus-send --print-reply output to extract the value.

        Returns:
            str for simple values
            list[str] for string arrays (as)
            list[dict] for variant arrays (av) containing dicts
            dict for dict entries (a{sv})
            "" for void returns
        """
        lines = output.strip().splitlines()
        payload = []
        for line in lines:
            if line.strip().startswith("method return "):
                continue
            payload.append(line)

        if not payload:
            return ""

        result, _ = KdenliveDBus._parse_dbus_value(payload, 0)
        return result

    @staticmethod
    def _parse_scalar(line: str):
        """Try to parse a scalar value from a stripped line. Returns (value, True) or (None, False)."""
        if line.startswith('string "'):
            return line[8:-1] if line.endswith('"') else line[7:], True
        for prefix, start in [("int32 ", 6), ("int64 ", 6), ("uint32 ", 7),
                               ("uint64 ", 7), ("double ", 7), ("boolean ", 8)]:
            if line.startswith(prefix):
                return line[start:], True
        return None, False

    @staticmethod
    def _parse_dbus_value(lines: list[str], idx: int):
        """Recursive parser for dbus-send --print-reply output.

        Returns (parsed_value, next_index).
        """
        while idx < len(lines):
            line = lines[idx].strip()
            if not line or line == ")":
                idx += 1
                continue

            # Scalar
            val, ok = KdenliveDBus._parse_scalar(line)
            if ok:
                return val, idx + 1

            # Variant — unwrap; value may be inline or on next lines
            if line.startswith("variant"):
                rest = line[len("variant"):].strip()
                if rest:
                    # Inline scalar: "variant    int32 5"
                    scalar, ok = KdenliveDBus._parse_scalar(rest)
                    if ok:
                        return scalar, idx + 1
                    # Inline array start: "variant    array ["
                    if rest == "array [":
                        # Parse the array from subsequent lines
                        return KdenliveDBus._parse_array(lines, idx + 1)
                # Next line holds the value
                return KdenliveDBus._parse_dbus_value(lines, idx + 1)

            # Array
            if line == "array [":
                return KdenliveDBus._parse_array(lines, idx + 1)

            # Empty array
            if line == "array [" or line == "]":
                idx += 1
                continue

            # Dict entry
            if line == "dict entry(":
                idx += 1
                key, idx = KdenliveDBus._parse_dbus_value(lines, idx)
                val, idx = KdenliveDBus._parse_dbus_value(lines, idx)
                # Skip closing ")"
                if idx < len(lines) and lines[idx].strip() == ")":
                    idx += 1
                return (key, val), idx

            # Skip unknown lines
            idx += 1

        return "", idx

    @staticmethod
    def _parse_array(lines: list[str], idx: int):
        """Parse array contents starting after 'array ['. Returns (value, next_idx).

        Detects content type:
        - dict entry → returns dict
        - variant → returns list (of whatever the variants contain)
        - scalars → returns list[str]
        """
        items = []
        has_dict_entries = False

        while idx < len(lines):
            inner = lines[idx].strip()
            if inner == "]":
                idx += 1
                break
            if inner == "dict entry(":
                has_dict_entries = True
            val, idx = KdenliveDBus._parse_dbus_value(lines, idx)
            if val is not None and val != "":
                items.append(val)

        # If all items are (key, val) tuples → dict
        if has_dict_entries and items and all(isinstance(i, tuple) and len(i) == 2 for i in items):
            return dict(items), idx

        return items, idx

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
        """Import media files into the bin via addProjectClip (native Kdenlive).

        Adds files one by one, tracking new IDs per file to preserve order.
        """
        import time
        result_ids = []
        for path in file_paths:
            ids_before = set(self.get_all_clip_ids())
            if folder_id and folder_id != "-1":
                self._call("addProjectClip", path, folder_id)
            else:
                self._call("addProjectClip", path)
            time.sleep(0.3)  # Let Kdenlive register the clip
            ids_after = set(self.get_all_clip_ids())
            new = ids_after - ids_before
            if new:
                result_ids.append(sorted(new, key=int)[0])
        return result_ids

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
        """Get clip properties.

        WARNING: scriptGetClipProperties causes a deadlock in Kdenlive
        if the clip is still loading (thumbnails/metadata). Returns
        minimal info without calling D-Bus when possible.
        """
        # UNSAFE — causes permanent freeze / deadlock in Kdenlive.
        # Return empty dict; callers should use get_all_clip_ids() and
        # track filenames externally.
        return {"id": bin_id}

    def delete_bin_clip(self, bin_id: str) -> bool:
        return bool(self._call("scriptDeleteBinClip", bin_id))

    def create_title_clip(self, title_xml: str, duration_frames: int,
                          clip_name: str = "Title clip",
                          folder_id: str = "-1") -> str:
        """Create a title clip in the bin. Returns bin ID or '-1'."""
        result = self._call("scriptCreateTitleClip",
                            title_xml, duration_frames, clip_name, folder_id)
        return str(result) if result else "-1"

    # ── Timeline ───────────────────────────────────────────────────────

    def get_track_count(self, track_type: str) -> int:
        result = self._call("scriptGetTrackCount", track_type)
        return int(result) if isinstance(result, str) else result

    def get_track_info(self, track_index: int) -> dict:
        result = self._call("scriptGetTrackInfo", track_index)
        return dict(result) if result and not isinstance(result, str) else {}

    def get_all_tracks_info(self) -> list[dict]:
        result = self._call("scriptGetAllTracksInfo")
        if isinstance(result, list):
            out = []
            for t in result:
                if isinstance(t, dict):
                    out.append(t)
                elif isinstance(t, list):
                    # list of (key, val) tuples
                    d = {}
                    for item in t:
                        if isinstance(item, tuple) and len(item) == 2:
                            d[item[0]] = item[1]
                    if d:
                        out.append(d)
            return out
        return []

    def add_track(self, name: str, audio_track: bool) -> int:
        result = self._call("scriptAddTrack", name, audio_track)
        return int(result) if isinstance(result, str) else result

    def insert_clip(self, bin_clip_id: str, track_id: int, position: int) -> int:
        valid = self._get_valid_track_ids()
        if valid and track_id not in valid:
            return -1  # Non-existent track
        result = self._call("scriptInsertClip", bin_clip_id, track_id, position)
        return int(result) if isinstance(result, str) else result

    def insert_clips_sequentially(self, bin_clip_ids: list[str], track_id: int,
                                   start_position: int) -> list[int]:
        valid = self._get_valid_track_ids()
        if valid and track_id not in valid:
            return []  # Non-existent track
        result = self._call("scriptInsertClipsSequentially",
                            bin_clip_ids, track_id, start_position)
        if isinstance(result, list):
            return [int(x) for x in result if x]
        if isinstance(result, str) and result:
            return [int(x) for x in result.split("\n") if x]
        return []

    def move_clip(self, clip_id: int, track_id: int, position: int) -> bool:
        valid = self._get_valid_track_ids()
        if valid and track_id not in valid:
            return False  # Non-existent track
        return bool(self._call("scriptMoveClip", clip_id, track_id, position))

    def resize_clip(self, clip_id: int, new_duration: int, from_right: bool) -> int:
        result = self._call("scriptResizeClip", clip_id, new_duration, from_right)
        return int(result) if isinstance(result, str) else result

    def delete_timeline_clip(self, clip_id: int) -> bool:
        return bool(self._call("scriptDeleteTimelineClip", clip_id))

    def _get_valid_track_ids(self) -> set[int]:
        """Return set of valid track IDs from current project."""
        tracks = self.get_all_tracks_info()
        ids = set()
        for t in tracks:
            tid = t.get("id")
            if tid is not None:
                ids.add(int(tid))
        return ids

    def get_clips_on_track(self, track_id: int) -> list[dict]:
        """Get all clips on a track. Validates track_id to prevent crash."""
        valid = self._get_valid_track_ids()
        if valid and track_id not in valid:
            return []  # Non-existent track — would crash Kdenlive
        result = self._call("scriptGetClipsOnTrack", track_id)
        if isinstance(result, list):
            out = []
            for c in result:
                if isinstance(c, dict):
                    out.append(c)
                elif isinstance(c, list):
                    d = {}
                    for item in c:
                        if isinstance(item, tuple) and len(item) == 2:
                            d[item[0]] = item[1]
                    if d:
                        out.append(d)
            return out
        return []

    def get_timeline_clip_info(self, clip_id: int) -> dict:
        result = self._call("scriptGetTimelineClipInfo", clip_id)
        if isinstance(result, dict):
            return result
        if isinstance(result, list):
            d = {}
            for item in result:
                if isinstance(item, tuple) and len(item) == 2:
                    d[item[0]] = item[1]
                elif isinstance(item, dict):
                    d.update(item)
            return d
        return {}

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

    # ── Effects ────────────────────────────────────────────────────────

    def add_clip_effect(self, clip_id: int, effect_id: str,
                        params: dict[str, str] | None = None) -> bool:
        """Add an effect to a timeline clip with optional parameters."""
        keys = list(params.keys()) if params else []
        values = list(params.values()) if params else []
        return bool(self._call("scriptAddClipEffect", clip_id, effect_id,
                               keys, values))

    def remove_clip_effect(self, clip_id: int, effect_id: str) -> bool:
        """Remove an effect from a timeline clip by effect ID."""
        return bool(self._call("scriptRemoveClipEffect", clip_id, effect_id))

    def get_clip_effects(self, clip_id: int) -> str:
        """Get comma-separated list of effect names on a timeline clip."""
        result = self._call("scriptGetClipEffects", clip_id)
        return result if isinstance(result, str) else ""

    # ── Speed ─────────────────────────────────────────────────────────

    def set_clip_speed(self, clip_id: int, speed: float,
                       pitch_compensate: bool = False) -> bool:
        """Set clip speed. speed is percentage: 100=normal, 50=half, 200=double."""
        return bool(self._call("scriptSetClipSpeed", clip_id, speed, pitch_compensate))

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

    # ── Scene Detection ───────────────────────────────────────────────

    def detect_scenes(self, bin_clip_id: str, threshold: float = 0.4,
                      min_duration: int = 0) -> list[float]:
        """Detect scene cuts in a clip using FFmpeg scene detection.

        Args:
            bin_clip_id: Clip ID in the bin/media pool.
            threshold: Sensitivity 0.0-1.0 (lower = more cuts). Default 0.4.
            min_duration: Minimum frames between cuts. Default 0 (no minimum).

        Returns:
            List of timestamps (seconds) where scene cuts were detected.
        """
        result = self._call("scriptDetectScenes", bin_clip_id, threshold, min_duration)
        if isinstance(result, list):
            return [float(t) for t in result]
        if isinstance(result, str) and result:
            return [float(t) for t in result.split("\n") if t]
        return []

    # ── Render ─────────────────────────────────────────────────────────

    def render(self, url: str) -> None:
        self._call("scriptRender", url)
