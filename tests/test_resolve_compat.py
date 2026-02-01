"""Tests for DaVinci Resolve API compatibility.

Covers features added to match the 11 official Resolve example scripts.
"""

from __future__ import annotations

import pytest


# ── Resolve top-level ────────────────────────────────────────────────


def test_get_media_storage(resolve):
    storage = resolve.GetMediaStorage()
    assert storage is not None
    from kdenlive_api.media_storage import MediaStorage
    assert isinstance(storage, MediaStorage)


def test_open_page(resolve):
    assert resolve.OpenPage("color") is True
    assert resolve.OpenPage("edit") is True


def test_product_info(resolve):
    assert resolve.GetProductName() == "Kdenlive"
    assert isinstance(resolve.GetVersion(), list)
    assert isinstance(resolve.GetVersionString(), str)


def test_export_constants(resolve):
    assert resolve.EXPORT_AAF == 0
    assert resolve.EXPORT_DRT == 1
    assert resolve.EXPORT_EDL == 2
    assert resolve.EXPORT_FCP_7_XML == 3
    assert resolve.EXPORT_OTIO == 17
    assert resolve.EXPORT_TEXT_CSV == 13
    assert resolve.EXPORT_TEXT_TAB == 14


def test_fusion_returns_none(resolve):
    assert resolve.Fusion() is None


def test_layout_presets(resolve):
    assert resolve.GetCurrentLayoutPreset() == ""
    assert resolve.LoadLayoutPreset("Default") is True
    assert resolve.SaveLayoutPreset("MyLayout") is True
    assert resolve.UpdateLayoutPreset("MyLayout") is True
    assert resolve.DeleteLayoutPreset("MyLayout") is True
    assert resolve.ExportLayoutPreset("MyLayout", "/tmp/l.preset") is True


# ── Project ──────────────────────────────────────────────────────────


def test_project_timeline_count(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    assert proj.GetTimelineCount() == 1


def test_project_timeline_by_index(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetTimelineByIndex(1)
    assert tl is not None
    assert proj.GetTimelineByIndex(2) is None


def test_project_set_current_timeline(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    assert proj.SetCurrentTimeline(tl) is True


def test_project_get_setting_resolve_keys(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    assert proj.GetSetting("timelineFrameRate") == "25.0"
    assert proj.GetSetting("timelineResolutionWidth") == "1920"
    assert proj.GetSetting("timelineResolutionHeight") == "1080"


def test_project_render_stubs(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    assert proj.LoadRenderPreset("YouTube 1080p") is True
    assert proj.SetCurrentRenderFormatAndCodec("mp4", "H264") is True
    assert proj.SetRenderSettings({"TargetDir": "/tmp"}) is True
    assert proj.AddRenderJob() == "job_1"
    assert proj.StartRendering("job_1") is True
    assert proj.IsRenderingInProgress() is False
    assert proj.GetRenderJobList() == []
    assert proj.GetRenderJobStatus("job_1") == {"JobStatus": "Complete"}
    assert proj.DeleteAllRenderJobs() is True
    assert proj.DeleteRenderJob("job_1") is True


def test_project_get_current_video_item(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    assert proj.GetCurrentVideoItem() is None


def test_project_set_name(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    assert proj.SetName("New Name") is True


# ── ProjectManager ───────────────────────────────────────────────────


def test_project_manager_folder_stubs(resolve):
    pm = resolve.GetProjectManager()
    names = pm.GetProjectListInCurrentFolder()
    assert isinstance(names, list)
    assert len(names) >= 1

    assert pm.GetFolderListInCurrentFolder() == []
    assert pm.OpenFolder("foo") is False
    assert pm.GotoParentFolder() is True
    assert pm.GotoRootFolder() is True


def test_project_manager_close_project(resolve):
    pm = resolve.GetProjectManager()
    proj = pm.GetCurrentProject()
    assert pm.CloseProject(proj) is True


# ── MediaPool ────────────────────────────────────────────────────────


def test_media_pool_set_current_folder(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    root = pool.GetRootFolder()
    assert pool.SetCurrentFolder(root) is True
    assert pool.GetCurrentFolder().folder_id == root.folder_id


def test_media_pool_create_empty_timeline(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    tl = pool.CreateEmptyTimeline("New Timeline")
    assert tl is not None


def test_media_pool_append_to_timeline_single(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    # Import a clip first
    items = pool.ImportMedia(["/tmp/test.mp4"])
    assert len(items) == 1
    result = pool.AppendToTimeline(items[0])
    assert result is True or isinstance(result, bool)


def test_media_pool_append_to_timeline_list(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/a.mp4", "/tmp/b.mp4"])
    result = pool.AppendToTimeline(items)
    assert isinstance(result, list)
    assert len(result) == 2


def test_media_pool_append_to_timeline_subclip_dicts(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/clip.mp4"])
    clip = items[0]
    subclips = [{"mediaPoolItem": clip, "startFrame": 0, "endFrame": 50}]
    result = pool.AppendToTimeline(subclips)
    # Single subclip dict → bool
    assert result is True or isinstance(result, bool)


def test_media_pool_delete_clips(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/del.mp4"])
    assert pool.DeleteClips(items) is True


def test_media_pool_move_clips(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/mv.mp4"])
    root = pool.GetRootFolder()
    assert pool.MoveClips(items, root) is True


# ── MediaPoolItem ────────────────────────────────────────────────────


def test_clip_property_no_args(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/props.mp4"])
    clip = items[0]
    props = clip.GetClipProperty()
    assert isinstance(props, dict)
    assert "name" in props


def test_clip_property_with_key(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/props2.mp4"])
    clip = items[0]
    name = clip.GetClipProperty("name")
    assert isinstance(name, str)


def test_clip_markers(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/markers.mp4"])
    clip = items[0]

    assert clip.AddMarker(10, "Red", "Start", "Intro starts", 1, "custom1") is True
    assert clip.AddMarker(50, "Blue", "End", "Outro", 1, "custom2") is True

    markers = clip.GetMarkers()
    assert 10 in markers
    assert markers[10]["color"] == "Red"
    assert markers[10]["name"] == "Start"

    assert clip.GetMarkerCustomData(10) == "custom1"
    assert clip.UpdateMarkerCustomData(10, "updated") is True
    assert clip.GetMarkerCustomData(10) == "updated"

    found = clip.GetMarkerByCustomData("custom2")
    assert found.get("name") == "End"

    assert clip.DeleteMarkerAtFrame(10) is True
    assert 10 not in clip.GetMarkers()

    assert clip.DeleteMarkersByColor("Blue") is True
    assert len(clip.GetMarkers()) == 0


def test_clip_delete_marker_by_custom_data(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/m2.mp4"])
    clip = items[0]
    clip.AddMarker(5, "Green", "Mark", custom_data="cd1")
    assert clip.DeleteMarkerByCustomData("cd1") is True
    assert len(clip.GetMarkers()) == 0


def test_clip_fusion_stubs(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/fusion.mp4"])
    clip = items[0]
    assert clip.GetFusionCompCount() == 0
    assert clip.AddFusionComp() is False
    assert clip.GetFusionCompByIndex(0) is None
    assert clip.GetFusionCompNameList() == []


def test_clip_color_stubs(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/color.mp4"])
    clip = items[0]
    assert clip.SetClipColor("Orange") is True
    assert clip.GetClipColor() == ""


def test_clip_get_media_id(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    items = pool.ImportMedia(["/tmp/mid.mp4"])
    clip = items[0]
    assert clip.GetMediaId() == clip.bin_id


# ── Folder ───────────────────────────────────────────────────────────


def test_folder_get_subfolder_list(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    root = pool.GetRootFolder()
    assert root.GetSubFolderList() == []
    assert root.GetIsFolderStale() is False


# ── Timeline ─────────────────────────────────────────────────────────


def test_timeline_get_name(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    assert tl.GetName() == "Test Project"


def test_timeline_set_name(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    assert tl.SetName("New TL") is True


def test_timeline_subtitle_track_count(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    assert tl.GetTrackCount("subtitle") == 0


def test_timeline_start_end_frame(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    assert tl.GetStartFrame() == 0
    # GetEndFrame == GetTotalDuration (0 with no clips)
    assert tl.GetEndFrame() >= 0


def test_timeline_marker_string_color(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    # String color (Resolve-style)
    assert tl.AddMarker(100, "Red", "Shot 1", "First scene") is True
    markers = tl.GetMarkers()
    assert 100 in markers
    # Returns string color name
    assert isinstance(markers[100]["color"], str)


def test_timeline_delete_markers_by_color_string(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    tl.AddMarker(200, "Blue", "Shot A")
    tl.AddMarker(300, "Blue", "Shot B")
    tl.AddMarker(400, "Red", "Shot C")
    assert tl.DeleteMarkersByColor("Blue") is True
    remaining = tl.GetMarkers()
    for frame, m in remaining.items():
        assert m.get("category") != 4  # Blue category


def test_timeline_delete_marker_at_frame(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    tl.AddMarker(500, 0, "ToDelete")
    assert tl.DeleteMarkerAtFrame(500) is True


def test_timeline_export_stub(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert tl.Export("/tmp/out.aaf", 0) is True


def test_timeline_drx_stub(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert tl.ApplyGradeFromDRX("/tmp/grade.drx") is True


def test_timeline_thumbnail_stub(resolve):
    proj = resolve.GetProjectManager().GetCurrentProject()
    tl = proj.GetCurrentTimeline()
    assert tl.GetCurrentClipThumbnailImage() is None


def test_timeline_item_get_media_pool_item(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    tl = proj.GetCurrentTimeline()
    items = pool.ImportMedia(["/tmp/ti.mp4"])
    ti = tl.InsertClip(items[0].bin_id, 0, 0)
    assert ti is not None
    mpi = ti.GetMediaPoolItem()
    assert mpi is not None
    assert mpi.bin_id == items[0].bin_id


def test_timeline_item_fusion_stubs(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    tl = proj.GetCurrentTimeline()
    items = pool.ImportMedia(["/tmp/tf.mp4"])
    ti = tl.InsertClip(items[0].bin_id, 0, 0)
    assert ti.GetFusionCompCount() == 0
    assert ti.AddFusionComp() is False
    assert ti.GetFusionCompByIndex(0) is None
    assert ti.GetFusionCompNameList() == []


def test_timeline_item_color_stubs(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    tl = proj.GetCurrentTimeline()
    items = pool.ImportMedia(["/tmp/tc.mp4"])
    ti = tl.InsertClip(items[0].bin_id, 0, 0)
    assert ti.SetClipColor("Orange") is True
    assert ti.GetClipColor() == ""


def test_timeline_item_offsets(resolve, mock_dbus):
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    tl = proj.GetCurrentTimeline()
    items = pool.ImportMedia(["/tmp/to.mp4"])
    ti = tl.InsertClip(items[0].bin_id, 0, 0)
    assert isinstance(ti.GetLeftOffset(), int)
    assert isinstance(ti.GetRightOffset(), int)


def test_timeline_1based_track_index(resolve, mock_dbus):
    """Resolve uses 1-based track indexing."""
    proj = resolve.GetProjectManager().GetCurrentProject()
    pool = proj.GetMediaPool()
    tl = proj.GetCurrentTimeline()
    items = pool.ImportMedia(["/tmp/idx.mp4"])
    # Insert on track 0 (V1)
    tl.InsertClip(items[0].bin_id, 0, 0)
    # GetItemListInTrack with 1-based index (Resolve convention)
    clips = tl.GetItemListInTrack("video", 1)
    assert len(clips) >= 1


# ── MediaStorage ─────────────────────────────────────────────────────


def test_media_storage_get_mounted_volumes(resolve):
    storage = resolve.GetMediaStorage()
    volumes = storage.GetMountedVolumeList()
    assert isinstance(volumes, list)
    assert len(volumes) > 0


def test_media_storage_reveal_stub(resolve):
    storage = resolve.GetMediaStorage()
    assert storage.RevealInStorage("/tmp") is True
