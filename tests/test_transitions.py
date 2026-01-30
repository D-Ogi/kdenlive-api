"""Tests for transitions/mixes."""

from kdenlive_api.media_pool import MediaPool
from kdenlive_api.timeline import Timeline


def test_add_mix(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/a.mp4", "/b.mp4"])
    tl = Timeline(mock_dbus)
    item_a = tl.InsertClip(clips[0].bin_id, 0, 0)
    item_b = tl.InsertClip(clips[1].bin_id, 0, 125)
    assert tl.AddTransition(item_a, item_b, 13)


def test_remove_mix(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/a.mp4"])
    tl = Timeline(mock_dbus)
    item = tl.InsertClip(clips[0].bin_id, 0, 0)
    assert tl.RemoveMix(item)


def test_add_composition(mock_dbus):
    tl = Timeline(mock_dbus)
    comp_id = tl.AddComposition("wipe", 0, 100, 25)
    assert comp_id >= 0
