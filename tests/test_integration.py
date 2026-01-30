"""Integration tests — require a running Kdenlive with D-Bus scripting patch.

Run with: pytest tests/test_integration.py -v --run-live

These tests are skipped by default. Pass --run-live to enable them.
"""

import os
import pytest

live = pytest.mark.skipif(
    "not config.getoption('--run-live', default=False)",
    reason="Requires running Kdenlive (pass --run-live)",
)


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="Run live D-Bus integration tests")


@live
def test_connect_to_kdenlive():
    from kdenlive_api import Resolve
    resolve = Resolve()
    pm = resolve.GetProjectManager()
    project = pm.GetCurrentProject()
    name = project.GetName()
    assert isinstance(name, str)
    print(f"Connected to: {name}")


@live
def test_project_info():
    from kdenlive_api import Resolve
    resolve = Resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    fps = project.GetFps()
    w, h = project.GetResolution()
    assert fps > 0
    assert w > 0 and h > 0
    print(f"Project: {fps}fps, {w}x{h}")


@live
def test_import_and_insert():
    from kdenlive_api import Resolve
    resolve = Resolve()
    project = resolve.GetProjectManager().GetCurrentProject()
    pool = project.GetMediaPool()
    timeline = project.GetCurrentTimeline()

    # This test requires at least one video file in output/video/
    video_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                             "output", "video")
    if not os.path.isdir(video_dir):
        pytest.skip("No output/video directory")

    import glob
    files = sorted(glob.glob(os.path.join(video_dir, "*.mp4")))[:3]
    if not files:
        pytest.skip("No MP4 files in output/video/")

    clips = pool.ImportMedia(files)
    assert len(clips) > 0

    tracks = timeline.GetAllTracksInfo()
    video_tracks = [t for t in tracks if not t.get("audio", True)]
    if not video_tracks:
        pytest.skip("No video tracks")

    track_id = video_tracks[0]["id"]
    item = timeline.InsertClip(clips[0].bin_id, track_id, 0)
    assert item is not None
    print(f"Inserted clip at frame 0, duration={item.GetDuration()}")
