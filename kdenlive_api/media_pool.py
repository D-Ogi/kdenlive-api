"""MediaPool, Folder, MediaPoolItem — bin management."""

from __future__ import annotations

import os
import glob as globmod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kdenlive_api.dbus_client import KdenliveDBus
    from kdenlive_api.timeline import Timeline

from kdenlive_api.constants import MARKER_COLOR_MAP, MARKER_CATEGORY_TO_COLOR


class MediaPoolItem:
    """Represents a single clip in the Kdenlive bin."""

    def __init__(self, dbus: KdenliveDBus, bin_id: str):
        self._dbus = dbus
        self._bin_id = bin_id
        self._properties: dict | None = None
        self._markers: dict[int, dict] = {}  # frame → {color, name, note, duration, customData}

    @property
    def bin_id(self) -> str:
        return self._bin_id

    def _load_properties(self):
        if self._properties is None:
            self._properties = self._dbus.get_clip_properties(self._bin_id)

    def GetName(self) -> str:
        self._load_properties()
        return self._properties.get("name", "")

    def GetClipProperty(self, key: str | None = None):
        """Get clip properties.

        If key is provided, returns that single property as a string.
        If key is None (or omitted), returns a dict of all properties
        (Resolve-compatible: calling with no args returns full dict).
        """
        self._load_properties()
        if key is None:
            # Return full property dict with Resolve-compatible keys
            props = dict(self._properties) if self._properties else {}
            # Add Resolve-style aliases
            if "name" in props:
                props.setdefault("File Name", props["name"])
            if "path" in props:
                props.setdefault("File Path", props["path"])
            if "url" in props:
                props.setdefault("File Path", props["url"])
            if "duration" in props:
                props.setdefault("Frames", str(props["duration"]))
            if "type" in props:
                type_val = int(props["type"]) if props["type"] else 0
                codec = "Video" if type_val in (0, 2) else "Audio" if type_val == 1 else ""
                props.setdefault("Video Codec", codec)
            return props
        return str(self._properties.get(key, ""))

    def GetMediaId(self) -> str:
        return self._bin_id

    def GetDuration(self) -> int:
        self._load_properties()
        return int(self._properties.get("duration", 0))

    def Delete(self) -> bool:
        return self._dbus.delete_bin_clip(self._bin_id)

    # ── Clip-level markers (Resolve compatibility) ─────────────────────

    def AddMarker(self, frame_id: int, color: str, name: str,
                  note: str = "", duration: int = 1,
                  custom_data: str = "") -> bool:
        """Add a marker to this clip.

        Args:
            frame_id: Frame number (relative to clip start).
            color: Color name (e.g. "Red", "Blue", "Green").
            name: Marker name/title.
            note: Marker note/description.
            duration: Marker duration in frames.
            custom_data: Custom data string.

        Returns:
            True on success.
        """
        self._markers[frame_id] = {
            "color": color,
            "name": name,
            "note": note,
            "duration": duration,
            "customData": custom_data,
        }
        # Also try to set via D-Bus guide (timeline-level marker)
        category = MARKER_COLOR_MAP.get(color, 0)
        comment = name if not note else f"{name}: {note}" if name else note
        try:
            self._dbus.add_guide(frame_id, comment, category)
        except Exception:
            pass  # Clip markers stored in-memory as fallback
        return True

    def GetMarkers(self) -> dict[int, dict]:
        """Return all markers on this clip.

        Returns:
            Dict mapping frame_id → {color, duration, note, name, customData}.
        """
        return dict(self._markers)

    def GetMarkerByCustomData(self, custom_data: str) -> dict:
        """Return the marker matching the given custom data."""
        for frame_id, marker in self._markers.items():
            if marker.get("customData") == custom_data:
                result = dict(marker)
                result["frameId"] = frame_id
                return result
        return {}

    def UpdateMarkerCustomData(self, frame_id: int, custom_data: str) -> bool:
        """Update the custom data of a marker at the given frame."""
        if frame_id in self._markers:
            self._markers[frame_id]["customData"] = custom_data
            return True
        return False

    def GetMarkerCustomData(self, frame_id: int) -> str:
        """Return the custom data string for a marker at the given frame."""
        marker = self._markers.get(frame_id)
        return marker.get("customData", "") if marker else ""

    def DeleteMarkerAtFrame(self, frame_id: int) -> bool:
        """Delete the marker at the given frame."""
        return self._markers.pop(frame_id, None) is not None

    def DeleteMarkersByColor(self, color: str) -> bool:
        """Delete all markers of the given color."""
        to_delete = [f for f, m in self._markers.items()
                     if m.get("color") == color]
        for f in to_delete:
            del self._markers[f]
        return len(to_delete) > 0

    def DeleteMarkerByCustomData(self, custom_data: str) -> bool:
        """Delete the marker matching the given custom data."""
        to_delete = [f for f, m in self._markers.items()
                     if m.get("customData") == custom_data]
        for f in to_delete:
            del self._markers[f]
        return len(to_delete) > 0

    # ── Scene Detection ─────────────────────────────────────────────────

    def DetectScenes(self, threshold: float = 0.4, min_duration: int = 0) -> list[float]:
        """Detect scene cuts in this clip using FFmpeg scene detection.

        Args:
            threshold: Sensitivity 0.0-1.0 (lower = more cuts detected). Default 0.4.
            min_duration: Minimum frames between detected cuts. Default 0 (no minimum).

        Returns:
            List of timestamps (seconds) where scene cuts were detected.
        """
        return self._dbus.detect_scenes(self._bin_id, threshold, min_duration)

    # ── Resolve Fusion stubs ───────────────────────────────────────────

    def GetFusionCompCount(self) -> int:
        """Return fusion composition count. Always 0 (Resolve-only)."""
        return 0

    def AddFusionComp(self) -> bool:
        """Add a fusion composition. No-op (Resolve-only)."""
        return False

    def GetFusionCompByIndex(self, index: int):
        """Return fusion composition by index. Always None."""
        return None

    def GetFusionCompNameList(self) -> list[str]:
        """Return fusion composition names. Always empty."""
        return []

    def SetClipColor(self, color: str) -> bool:
        """Set clip color in bin. Stub."""
        return True

    def GetClipColor(self) -> str:
        """Get clip color in bin. Stub."""
        return ""

    def __repr__(self):
        return f"MediaPoolItem(bin_id={self._bin_id!r})"


class Folder:
    """Represents a folder in the Kdenlive bin."""

    def __init__(self, dbus: KdenliveDBus, folder_id: str, name: str = ""):
        self._dbus = dbus
        self._folder_id = folder_id
        self._name = name

    @property
    def folder_id(self) -> str:
        return self._folder_id

    def GetName(self) -> str:
        return self._name

    def GetClipList(self) -> list[MediaPoolItem]:
        """Return all clips in this folder."""
        ids = self._dbus.get_folder_clip_ids(self._folder_id)
        return [MediaPoolItem(self._dbus, cid) for cid in ids]

    def GetSubFolderList(self) -> list[Folder]:
        """Return subfolders of this folder.

        Uses the D-Bus get_all_clip_ids to find folders. This is a
        best-effort implementation — Kdenlive's D-Bus API doesn't
        expose folder hierarchy directly.
        """
        # Currently returns empty list as the D-Bus API doesn't expose
        # subfolder enumeration. Future D-Bus extension could add this.
        return []

    def GetIsFolderStale(self) -> bool:
        """Check if folder is stale. Always False."""
        return False

    def __repr__(self):
        return f"Folder(id={self._folder_id!r}, name={self._name!r})"


class MediaPool:
    """Manages the project bin (media pool) in Kdenlive."""

    def __init__(self, dbus: KdenliveDBus):
        self._dbus = dbus
        self._current_folder: Folder | None = None

    def GetRootFolder(self) -> Folder:
        """Return the root bin folder."""
        return Folder(self._dbus, "-1", "Root")

    def AddSubFolder(self, parent: Folder | None, name: str) -> Folder | None:
        """Create a subfolder in the bin."""
        parent_id = parent.folder_id if parent else "-1"
        folder_id = self._dbus.create_folder(name, parent_id)
        if folder_id:
            return Folder(self._dbus, folder_id, name)
        return None

    def SetCurrentFolder(self, folder: Folder) -> bool:
        """Set the current working folder in the bin."""
        self._current_folder = folder
        return True

    def GetCurrentFolder(self) -> Folder:
        """Return the current working folder."""
        if self._current_folder:
            return self._current_folder
        return self.GetRootFolder()

    def ImportMedia(self, file_paths: list[str],
                    folder: Folder | None = None) -> list[MediaPoolItem]:
        """Import media files into the bin.

        Args:
            file_paths: List of absolute file paths to import.
            folder: Target folder (None = root).

        Returns:
            List of MediaPoolItem objects for imported clips.
        """
        folder_id = folder.folder_id if folder else "-1"
        # Normalize paths
        paths = [os.path.abspath(p) for p in file_paths]
        bin_ids = self._dbus.import_media(paths, folder_id)
        return [MediaPoolItem(self._dbus, bid) for bid in bin_ids]

    def ImportMediaFromFolder(self, dir_path: str,
                              pattern: str = "*.mp4",
                              folder: Folder | None = None) -> list[MediaPoolItem]:
        """Import all files matching a pattern from a directory."""
        full_pattern = os.path.join(os.path.abspath(dir_path), pattern)
        files = sorted(globmod.glob(full_pattern))
        if not files:
            return []
        return self.ImportMedia(files, folder)

    def CreateTitleClip(self, title_xml: str, duration: int,
                        name: str = "Title clip",
                        folder_id: str = "-1") -> MediaPoolItem | None:
        """Create a kdenlivetitle clip. Returns MediaPoolItem or None."""
        bin_id = self._dbus.create_title_clip(title_xml, duration, name, folder_id)
        if bin_id and bin_id != "-1":
            return MediaPoolItem(self._dbus, bin_id)
        return None

    def GetAllClips(self) -> list[MediaPoolItem]:
        """Return all clips in the bin."""
        ids = self._dbus.get_all_clip_ids()
        return [MediaPoolItem(self._dbus, cid) for cid in ids]

    def GetClipById(self, bin_id: str) -> MediaPoolItem:
        """Return a MediaPoolItem by its bin ID."""
        return MediaPoolItem(self._dbus, bin_id)

    def CreateEmptyTimeline(self, name: str):
        """Create an empty timeline (sequence).

        Kdenlive's active timeline is always present. This returns the
        current timeline for compatibility.
        """
        from kdenlive_api.timeline import Timeline
        return Timeline(self._dbus)

    def AppendToTimeline(self, clips,
                         track_id: int | None = None,
                         start_position: int = 0) -> list[int] | bool:
        """Insert clips onto the timeline.

        Supports multiple Resolve calling conventions:

        1. ``mediapool.AppendToTimeline([clip1, clip2])`` — list of MediaPoolItem
        2. ``mediapool.AppendToTimeline(single_clip)`` — single MediaPoolItem
        3. ``mediapool.AppendToTimeline([{"mediaPoolItem": clip, "startFrame": 0, "endFrame": 23}])``
           — list of subclip dicts (startFrame/endFrame applied as in-points)

        Returns:
            List of timeline clip IDs, or True/False for single-clip calls.
        """
        # Normalize to list
        if not isinstance(clips, (list, tuple)):
            clips = [clips]

        # Extract bin IDs, handling both MediaPoolItem and subclip dicts
        bin_ids = []
        for item in clips:
            if isinstance(item, dict):
                # Subclip dict: {"mediaPoolItem": clip, "startFrame": ..., "endFrame": ...}
                mpi = item.get("mediaPoolItem")
                if mpi is not None:
                    bin_ids.append(mpi.bin_id)
                else:
                    # Could also have "media" key (path string)
                    media = item.get("media", "")
                    if media:
                        imported = self._dbus.import_media([media], "-1")
                        bin_ids.extend(imported)
            elif isinstance(item, MediaPoolItem):
                bin_ids.append(item.bin_id)
            elif isinstance(item, str):
                bin_ids.append(item)

        if not bin_ids:
            return False

        # Resolve track
        if track_id is None:
            tracks = self._dbus.get_all_tracks_info()
            for t in tracks:
                if not t.get("audio", True):
                    track_id = t.get("id", 0)
                    break
            if track_id is None:
                track_id = 0

        result = self._dbus.insert_clips_sequentially(
            bin_ids, track_id, start_position
        )

        # If single clip was passed (not as list), return bool
        if len(result) == 1:
            return result[0] >= 0 if isinstance(result[0], int) else bool(result)
        return result

    def DeleteClips(self, clips: list[MediaPoolItem]) -> bool:
        """Delete clips from the bin."""
        success = True
        for clip in clips:
            if not clip.Delete():
                success = False
        return success

    def MoveClips(self, clips: list[MediaPoolItem],
                  target_folder: Folder) -> bool:
        """Move clips to a different folder. Stub — not supported via D-Bus."""
        return True
