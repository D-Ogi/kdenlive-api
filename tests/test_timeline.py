"""Tests for Timeline and TimelineItem."""

from kdenlive_api.media_pool import MediaPool
from kdenlive_api.timeline import Timeline, TimelineItem
from kdenlive_api.constants import TRACK_VIDEO, TRACK_AUDIO


def test_track_count(mock_dbus):
    tl = Timeline(mock_dbus)
    assert tl.GetTrackCount(TRACK_VIDEO) == 2
    assert tl.GetTrackCount(TRACK_AUDIO) == 1


def test_add_track(mock_dbus):
    tl = Timeline(mock_dbus)
    tid = tl.AddTrack("V3", audio=False)
    assert tid >= 0
    assert tl.GetTrackCount(TRACK_VIDEO) == 3


def test_insert_clip(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/path/test.mp4"])
    tl = Timeline(mock_dbus)
    item = tl.InsertClip(clips[0].bin_id, 0, 0)
    assert item is not None
    assert isinstance(item, TimelineItem)


def test_insert_clips_sequentially(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/a.mp4", "/b.mp4", "/c.mp4"])
    tl = Timeline(mock_dbus)
    items = tl.InsertClipsSequentially(
        [c.bin_id for c in clips], 0, 0
    )
    assert len(items) == 3
    # Check positions are sequential
    positions = [item.GetStart() for item in items]
    assert positions[0] == 0
    assert positions[1] > positions[0]
    assert positions[2] > positions[1]


def test_clip_info(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/path/info.mp4"])
    tl = Timeline(mock_dbus)
    item = tl.InsertClip(clips[0].bin_id, 0, 50)
    assert item.GetStart() == 50
    assert item.GetDuration() == 125
    assert item.GetEnd() == 175


def test_move_clip(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/path/move.mp4"])
    tl = Timeline(mock_dbus)
    item = tl.InsertClip(clips[0].bin_id, 0, 0)
    assert item.Move(1, 100)
    assert item.GetStart() == 100


def test_resize_clip(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/path/resize.mp4"])
    tl = Timeline(mock_dbus)
    item = tl.InsertClip(clips[0].bin_id, 0, 0)
    new_dur = item.SetDuration(200)
    assert new_dur == 200


def test_delete_clip(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/path/del.mp4"])
    tl = Timeline(mock_dbus)
    item = tl.InsertClip(clips[0].bin_id, 0, 0)
    assert item.Delete()


def test_get_items_on_track(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/a.mp4", "/b.mp4"])
    tl = Timeline(mock_dbus)
    tl.InsertClip(clips[0].bin_id, 0, 0)
    tl.InsertClip(clips[1].bin_id, 0, 125)
    items = tl.GetItemListInTrack(TRACK_VIDEO, 0)
    assert len(items) == 2
