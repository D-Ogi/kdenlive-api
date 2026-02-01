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

    @staticmethod
    def _result_to_dict(result) -> dict:
        """Convert a D-Bus result to a Python dict.

        Handles both native dicts (pydbus) and list-of-tuples
        (subprocess parser).
        """
        if isinstance(result, dict):
            return dict(result)
        if isinstance(result, list):
            d = {}
            for item in result:
                if isinstance(item, tuple) and len(item) == 2:
                    d[item[0]] = item[1]
                elif isinstance(item, dict):
                    d.update(item)
            return d
        return {}

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
                # dbus-send array syntax: array:<type>:v1,v2,v3
                if len(a) == 0:
                    cmd_dbus_send.append("array:string:")
                elif all(isinstance(item, int) and not isinstance(item, bool) for item in a):
                    items = ",".join(str(item) for item in a)
                    cmd_dbus_send.append(f"array:int32:{items}")
                else:
                    items = ",".join(str(item) for item in a)
                    cmd_dbus_send.append(f"array:string:{items}")
            else:
                cmd_dbus_send.append(f"string:{a}")
        try:
            result = subprocess.run(cmd_dbus_send, capture_output=True,
                                    text=True, encoding="utf-8",
                                    timeout=30, check=True)
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
                                    encoding="utf-8", timeout=30, check=True)
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
                                encoding="utf-8", timeout=30, check=True)
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

    # ── Undo / Redo ──────────────────────────────────────────────────

    def undo(self, steps: int = 1) -> bool:
        """Undo the last N operations. Returns True if at least one was undone."""
        result = self._call("scriptUndo", steps)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def redo(self, steps: int = 1) -> bool:
        """Redo the last N undone operations. Returns True if at least one was redone."""
        result = self._call("scriptRedo", steps)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def undo_status(self) -> dict:
        """Get undo/redo status: can_undo, can_redo, undo_text, redo_text, index, count."""
        result = self._call("scriptUndoStatus")
        if not isinstance(result, str) or not result:
            return {}
        d = {}
        for pair in result.split(";"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                d[k] = v
        return d

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
        """Get clip properties from the bin (name, duration, type, url)."""
        try:
            result = self._call("scriptGetClipProperties", bin_id)
            if isinstance(result, dict):
                return result
            if isinstance(result, list):
                d = {}
                for item in result:
                    if isinstance(item, tuple) and len(item) == 2:
                        d[item[0]] = item[1]
                    elif isinstance(item, dict):
                        d.update(item)
                return d if d else {"id": bin_id}
            return {"id": bin_id}
        except Exception:
            return {"id": bin_id}

    def delete_bin_clip(self, bin_id: str) -> bool:
        return bool(self._call("scriptDeleteBinClip", bin_id))

    def relink_bin_clip(self, bin_id: str, new_file_path: str) -> bool:
        """Relink a bin clip to a new file. Preserves all timeline instances."""
        result = self._call("scriptRelinkBinClip", bin_id, new_file_path)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def create_title_clip(self, title_xml: str, duration_frames: int,
                          clip_name: str = "Title clip",
                          folder_id: str = "-1") -> str:
        """Create a title clip in the bin. Returns bin ID or '-1'."""
        result = self._call("scriptCreateTitleClip",
                            title_xml, duration_frames, clip_name, folder_id)
        return str(result) if result else "-1"

    def get_title_xml(self, bin_id: str) -> str:
        """Get the XML content of a title clip. Returns empty string if not found."""
        result = self._call("scriptGetTitleXml", bin_id)
        return str(result) if result else ""

    def set_title_xml(self, bin_id: str, new_xml: str) -> bool:
        """Set the XML content of a title clip and reload. Returns True on success."""
        result = self._call("scriptSetTitleXml", bin_id, new_xml)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

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
            raise ValueError(f"Invalid track_id {track_id}. Valid: {sorted(valid)}")
        result = self._call("scriptInsertClipsSequentially",
                            bin_clip_ids, track_id, start_position)
        if isinstance(result, list):
            return [int(x) for x in result if x is not None]
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
        return self._result_to_dict(result)

    def cut_clip(self, clip_id: int, position: int) -> bool:
        return bool(self._call("scriptCutClip", clip_id, position))

    def slip_clip(self, clip_id: int, offset: int) -> bool:
        """Slip a clip's source in/out points by offset frames.

        Positive offset moves the source window forward (later in source).
        Negative offset moves it backward (earlier in source).
        Timeline position and duration remain unchanged.

        Args:
            clip_id: Timeline clip ID.
            offset: Number of frames to slip.
        """
        result = self._call("scriptSlipClip", clip_id, offset)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

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

    # ── Compositions ──────────────────────────────────────────────────

    def get_compositions(self) -> list[dict]:
        result = self._call("scriptGetCompositions")
        if isinstance(result, list):
            return [dict(c) for c in result] if result else []
        return []

    def get_composition_info(self, compo_id: int) -> dict:
        result = self._call("scriptGetCompositionInfo", compo_id)
        return self._result_to_dict(result)

    def move_composition(self, compo_id: int, track_id: int, position: int) -> bool:
        return bool(self._call("scriptMoveComposition", compo_id, track_id, position))

    def resize_composition(self, compo_id: int, new_duration: int, from_right: bool = True) -> int:
        result = self._call("scriptResizeComposition", compo_id, new_duration, from_right)
        return int(result) if isinstance(result, str) else result

    def delete_composition(self, compo_id: int) -> bool:
        return bool(self._call("scriptDeleteComposition", compo_id))

    def get_composition_types(self) -> list[dict]:
        result = self._call("scriptGetCompositionTypes")
        if isinstance(result, list):
            return [dict(t) for t in result] if result else []
        return []

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

    # ── Effect Keyframes ──────────────────────────────────────────────

    def get_effect_keyframes(self, clip_id: int,
                             effect_index: int) -> list[dict]:
        """Get all keyframes for an effect on a timeline clip.

        Args:
            clip_id: Timeline clip ID.
            effect_index: 0-based index of the effect in the clip's effect stack.

        Returns list of dicts with keys: frame, type, value.
        """
        result = self._call("scriptGetEffectKeyframes", clip_id, effect_index)
        if isinstance(result, list):
            out = []
            for item in result:
                if isinstance(item, dict):
                    out.append(item)
                elif isinstance(item, list):
                    d = {}
                    for pair in item:
                        if isinstance(pair, tuple) and len(pair) == 2:
                            d[pair[0]] = pair[1]
                    if d:
                        out.append(d)
            return out
        return []

    def add_effect_keyframe(self, clip_id: int, effect_index: int,
                            frame: int, value: float = 0.0,
                            keyframe_type: int = -1) -> bool:
        """Add a keyframe to an effect.

        Args:
            clip_id: Timeline clip ID.
            effect_index: 0-based effect index in the stack.
            frame: Frame position (relative to clip start).
            value: Normalized value 0.0–1.0.
            keyframe_type: KeyframeType enum (-1 = use value-based add,
                0=linear, 1=discrete, 2=smooth, 3=smooth_natural, ...).
        """
        result = self._call("scriptAddEffectKeyframe", clip_id, effect_index,
                            frame, value, keyframe_type)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def remove_effect_keyframe(self, clip_id: int, effect_index: int,
                               frame: int) -> bool:
        """Remove a keyframe from an effect.

        Args:
            clip_id: Timeline clip ID.
            effect_index: 0-based effect index in the stack.
            frame: Frame position of the keyframe to remove.
        """
        result = self._call("scriptRemoveEffectKeyframe", clip_id,
                            effect_index, frame)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def update_effect_keyframe(self, clip_id: int, effect_index: int,
                               old_frame: int, new_frame: int,
                               value: float = -1.0) -> bool:
        """Move and/or update a keyframe value.

        Args:
            clip_id: Timeline clip ID.
            effect_index: 0-based effect index in the stack.
            old_frame: Current frame position of the keyframe.
            new_frame: New frame position (same as old_frame to only change value).
            value: New normalized value 0.0–1.0 (-1 to keep existing value).
        """
        result = self._call("scriptUpdateEffectKeyframe", clip_id,
                            effect_index, old_frame, new_frame, value)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    # ── Speed ─────────────────────────────────────────────────────────

    def set_clip_speed(self, clip_id: int, speed: float,
                       pitch_compensate: bool = False) -> bool:
        """Set clip speed. speed is percentage: 100=normal, 50=half, 200=double."""
        return bool(self._call("scriptSetClipSpeed", clip_id, speed, pitch_compensate))

    # ── Audio ─────────────────────────────────────────────────────────

    def set_clip_volume(self, clip_id: int, dB: float) -> bool:
        """Set audio volume (gain) on a timeline clip in dB."""
        return bool(self._call("scriptSetClipVolume", clip_id, dB))

    def get_clip_volume(self, clip_id: int) -> float:
        """Get the current audio volume of a timeline clip in dB."""
        result = self._call("scriptGetClipVolume", clip_id)
        return float(result) if isinstance(result, str) else result

    def set_audio_fade(self, clip_id: int, fade_in_frames: int, fade_out_frames: int) -> bool:
        """Set audio fade in/out. Pass -1 to skip a fade."""
        return bool(self._call("scriptSetAudioFade", clip_id, fade_in_frames, fade_out_frames))

    def set_track_mute(self, track_id: int, mute: bool) -> bool:
        """Mute or unmute a track."""
        return bool(self._call("scriptSetTrackMute", track_id, mute))

    def get_track_mute(self, track_id: int) -> bool:
        """Check if a track is muted."""
        result = self._call("scriptGetTrackMute", track_id)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def get_audio_levels(self, bin_id: str, stream: int = 0, downsample: int = 1,
                         mode: int = 0) -> list[float]:
        """Get normalized audio levels (0.0-1.0) from a media pool clip.

        mode: 0=peak (default), 1=RMS.
        """
        result = self._call("scriptGetAudioLevels", bin_id, stream, downsample, mode)
        if isinstance(result, list):
            return [float(v) for v in result]
        return []

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

    # ── Clip Markers ──────────────────────────────────────────────────

    def add_clip_marker(self, bin_id: str, frame: int, comment: str, category: int) -> bool:
        return bool(self._call("scriptAddClipMarker", bin_id, frame, comment, category))

    def get_clip_markers(self, bin_id: str) -> list[dict]:
        result = self._call("scriptGetClipMarkers", bin_id)
        if isinstance(result, str):
            return []
        if isinstance(result, list):
            out = []
            for m in result:
                if isinstance(m, dict):
                    out.append(m)
                elif isinstance(m, list):
                    d = {}
                    for item in m:
                        if isinstance(item, tuple) and len(item) == 2:
                            d[item[0]] = item[1]
                    if d:
                        out.append(d)
            return out
        return []

    def delete_clip_marker(self, bin_id: str, frame: int) -> bool:
        return bool(self._call("scriptDeleteClipMarker", bin_id, frame))

    def delete_clip_markers_by_category(self, bin_id: str, category: int) -> bool:
        return bool(self._call("scriptDeleteClipMarkersByCategory", bin_id, category))

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

    # ── Fill Frame ─────────────────────────────────────────────────────

    def fill_frame(self, clip_id: int) -> bool:
        """Scale-to-fill a timeline clip (remove black bars, center crop).

        Reads source resolution via MLT, calculates qtblend rect, applies effect.
        Returns True on success.
        """
        result = self._call("scriptFillFrame", clip_id)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    # ── Preview / Frame Rendering ─────────────────────────────────────

    def render_bin_frame(self, bin_id: str, frame: int, width: int,
                         height: int, output_path: str) -> str:
        """Render a single frame from a bin clip to a JPEG file.

        Returns the output path on success, empty string on failure.
        """
        result = self._call("scriptRenderBinFrame",
                            bin_id, frame, width, height, output_path)
        return result if isinstance(result, str) else ""

    def render_timeline_frame(self, frame: int, width: int,
                              height: int, output_path: str) -> str:
        """Render a composited timeline frame to a JPEG file.

        Returns the output path on success, empty string on failure.
        """
        result = self._call("scriptRenderTimelineFrame",
                            frame, width, height, output_path)
        return result if isinstance(result, str) else ""

    # ── Subtitles ──────────────────────────────────────────────────────

    def get_subtitles(self) -> list[dict]:
        """Get all subtitles as a list of dicts with id, layer, startFrame, endFrame, text."""
        result = self._call("scriptGetSubtitles")
        if isinstance(result, list):
            out = []
            for item in result:
                if isinstance(item, dict):
                    out.append(item)
                elif isinstance(item, list):
                    d = {}
                    for pair in item:
                        if isinstance(pair, tuple) and len(pair) == 2:
                            d[pair[0]] = pair[1]
                    if d:
                        out.append(d)
            return out
        return []

    def add_subtitle(self, start_frame: int, end_frame: int, text: str,
                     layer: int = 0) -> int:
        """Add a subtitle. Returns its ID or -1 on error."""
        result = self._call("scriptAddSubtitle", start_frame, end_frame, text, layer)
        return int(result) if isinstance(result, str) else result

    def edit_subtitle(self, subtitle_id: int, new_text: str) -> bool:
        """Edit subtitle text by ID."""
        result = self._call("scriptEditSubtitle", subtitle_id, new_text)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def delete_subtitle(self, subtitle_id: int) -> bool:
        """Delete a subtitle by ID."""
        result = self._call("scriptDeleteSubtitle", subtitle_id)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def export_subtitles(self, file_path: str) -> bool:
        """Export subtitles to an .ass file. Returns True on success."""
        result = self._call("scriptExportSubtitles", file_path)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    # ── Subtitle Styles ───────────────────────────────────────────────

    def get_subtitle_styles(self, global_styles: bool = False) -> list[dict]:
        """Get all subtitle styles as a list of dicts.

        Args:
            global_styles: If True, return global styles; otherwise local (project) styles.
        """
        result = self._call("scriptGetSubtitleStyles", global_styles)
        if isinstance(result, list):
            out = []
            for item in result:
                if isinstance(item, dict):
                    out.append(item)
                elif isinstance(item, list):
                    d = {}
                    for pair in item:
                        if isinstance(pair, tuple) and len(pair) == 2:
                            d[pair[0]] = pair[1]
                    if d:
                        out.append(d)
            return out
        return []

    def set_subtitle_style(self, name: str, params: dict,
                           global_style: bool = False) -> bool:
        """Create or update a subtitle style.

        Args:
            name: Style name (e.g. "Default", "Accent").
            params: Dict of style properties (camelCase keys matching C++ property names).
            global_style: If True, modify global styles; otherwise local.
        """
        keys = list(params.keys())
        values = [str(v) for v in params.values()]
        result = self._call("scriptSetSubtitleStyle", name, keys, values, global_style)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def delete_subtitle_style(self, name: str,
                              global_style: bool = False) -> bool:
        """Delete a subtitle style. Cannot delete 'Default'."""
        result = self._call("scriptDeleteSubtitleStyle", name, global_style)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def set_subtitle_style_name(self, subtitle_id: int,
                                style_name: str) -> bool:
        """Assign a named style to a subtitle event."""
        result = self._call("scriptSetSubtitleStyleName", subtitle_id, style_name)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    # ── Groups ─────────────────────────────────────────────────────────

    def group_clips(self, item_ids: list[int]) -> int:
        """Group timeline items (clips/compositions).

        Args:
            item_ids: List of timeline item IDs to group (minimum 2).

        Returns:
            Group ID on success, -1 on failure.
        """
        result = self._call("scriptGroupClips", item_ids)
        return int(result) if isinstance(result, str) else result

    def ungroup_clips(self, item_id: int) -> bool:
        """Ungroup the topmost group containing the given item.

        All members are released from the group.
        """
        result = self._call("scriptUngroupClips", item_id)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def get_group_info(self, item_id: int) -> dict:
        """Get group information for a timeline item.

        Returns dict with keys: isInGroup, isGroup, rootId, groupType,
        members (list of {id, type, trackId, position}).
        """
        result = self._call("scriptGetGroupInfo", item_id)
        return self._result_to_dict(result)

    def remove_from_group(self, item_id: int) -> bool:
        """Remove a single item from its group, keeping the rest grouped."""
        result = self._call("scriptRemoveFromGroup", item_id)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    # ── Zones (timeline in/out points) ────────────────────────────────

    def get_zone(self) -> dict:
        """Get the current timeline zone (in/out points).

        Returns dict with keys: zoneIn, zoneOut (frame numbers).
        """
        result = self._call("scriptGetZone")
        return self._result_to_dict(result)

    def set_zone(self, in_frame: int, out_frame: int) -> bool:
        """Set the timeline zone (in/out points)."""
        result = self._call("scriptSetZone", in_frame, out_frame)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def set_zone_in(self, in_frame: int) -> bool:
        """Set the timeline zone in-point only."""
        result = self._call("scriptSetZoneIn", in_frame)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def set_zone_out(self, out_frame: int) -> bool:
        """Set the timeline zone out-point only."""
        result = self._call("scriptSetZoneOut", out_frame)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def extract_zone(self, in_frame: int, out_frame: int,
                     lift_only: bool = False) -> bool:
        """Extract (remove) content in the given zone.

        Args:
            in_frame: Zone start frame.
            out_frame: Zone end frame.
            lift_only: If True, lifts without ripple (leaves gap).
                       If False, ripple deletes (closes gap).
        """
        result = self._call("scriptExtractZone", in_frame, out_frame, lift_only)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    # ── Sequences (multi-timeline) ────────────────────────────────────

    def get_sequences(self) -> list[dict]:
        """Get all sequences in the project.

        Returns list of dicts with keys: uuid, name, duration, tracks, active.
        """
        result = self._call("scriptGetSequences")
        if isinstance(result, list):
            out = []
            for item in result:
                if isinstance(item, dict):
                    out.append(item)
                elif isinstance(item, list):
                    d = {}
                    for pair in item:
                        if isinstance(pair, tuple) and len(pair) == 2:
                            d[pair[0]] = pair[1]
                    if d:
                        out.append(d)
            return out
        return []

    def get_active_sequence(self) -> dict:
        """Get info about the currently active sequence.

        Returns dict with keys: uuid, name, duration, tracks.
        """
        result = self._call("scriptGetActiveSequence")
        if isinstance(result, dict):
            return result
        if isinstance(result, list):
            d = {}
            for pair in result:
                if isinstance(pair, tuple) and len(pair) == 2:
                    d[pair[0]] = pair[1]
            return d
        return {}

    def set_active_sequence(self, uuid: str) -> bool:
        """Switch to a sequence by its UUID.

        Args:
            uuid: Sequence UUID string (without braces).
        """
        result = self._call("scriptSetActiveSequence", uuid)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    # ── Proxy Clips ────────────────────────────────────────────────────

    def get_clip_proxy_status(self, bin_id: str) -> dict:
        """Get proxy status for a bin clip.

        Returns dict with keys: supportsProxy, hasProxy, proxyPath,
        originalUrl, isGenerating.
        """
        result = self._call("scriptGetClipProxyStatus", bin_id)
        return self._result_to_dict(result)

    def set_clip_proxy(self, bin_id: str, enabled: bool) -> bool:
        """Enable or disable proxy for a bin clip."""
        result = self._call("scriptSetClipProxy", bin_id, enabled)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def delete_clip_proxy(self, bin_id: str) -> bool:
        """Delete proxy file and disable proxy for a bin clip."""
        result = self._call("scriptDeleteClipProxy", bin_id)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def rebuild_clip_proxy(self, bin_id: str) -> bool:
        """Force regenerate proxy for a bin clip."""
        result = self._call("scriptRebuildClipProxy", bin_id)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    # ── Render ─────────────────────────────────────────────────────────

    def render(self, url: str) -> None:
        self._call("scriptRender", url)

    # ── Selection ─────────────────────────────────────────────────────

    def get_selection(self) -> list[int]:
        """Get currently selected timeline item IDs."""
        result = self._call("scriptGetSelection")
        if not result:
            return []
        # Result is a list of ID values (as strings from D-Bus)
        if isinstance(result, list):
            return [int(x) for x in result if isinstance(x, (int, str)) and str(x).lstrip('-').isdigit()]
        return []

    def set_selection(self, ids: list[int]) -> bool:
        """Set selection to the given timeline item IDs."""
        if not ids:
            return self.clear_selection()
        result = self._call("scriptSetSelection", ids)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def add_to_selection(self, item_id: int, clear: bool = False) -> bool:
        """Add an item to the selection. If clear=True, replaces current selection."""
        result = self._call("scriptAddToSelection", item_id, clear)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def clear_selection(self) -> bool:
        """Clear the current selection."""
        result = self._call("scriptClearSelection")
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def select_all(self) -> bool:
        """Select all clips, compositions, and subtitles on the timeline."""
        result = self._call("scriptSelectAll")
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def select_current_track(self) -> bool:
        """Select all items on the currently active track."""
        result = self._call("scriptSelectCurrentTrack")
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)

    def select_items_in_range(self, track_ids: list[int], start_frame: int, end_frame: int) -> bool:
        """Select items within a frame range on specified tracks."""
        result = self._call("scriptSelectItems", track_ids, start_frame, end_frame)
        if isinstance(result, str):
            return result.lower() == "true"
        return bool(result)
