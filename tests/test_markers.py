"""Tests for markers/guides."""

from kdenlive_api.timeline import Timeline
from kdenlive_api.constants import MARKER_BLUE, MARKER_RED


def test_add_guide(mock_dbus):
    tl = Timeline(mock_dbus)
    assert tl.AddMarker(0, MARKER_BLUE, "Scene 1")
    assert tl.AddMarker(125, MARKER_BLUE, "Scene 2")


def test_get_guides(mock_dbus):
    tl = Timeline(mock_dbus)
    tl.AddMarker(0, MARKER_BLUE, "Start")
    tl.AddMarker(250, MARKER_RED, "End")
    markers = tl.GetMarkers()
    assert 0 in markers
    assert 250 in markers
    assert markers[0]["comment"] == "Start"


def test_delete_guide(mock_dbus):
    tl = Timeline(mock_dbus)
    tl.AddMarker(100, MARKER_BLUE, "Delete me")
    assert tl.DeleteMarker(100)
    markers = tl.GetMarkers()
    assert 100 not in markers


def test_delete_guides_by_category(mock_dbus):
    tl = Timeline(mock_dbus)
    tl.AddMarker(0, MARKER_BLUE, "Blue 1")
    tl.AddMarker(100, MARKER_BLUE, "Blue 2")
    tl.AddMarker(200, MARKER_RED, "Red 1")
    assert tl.DeleteMarkersByColor(MARKER_BLUE)
    markers = tl.GetMarkers()
    assert len(markers) == 1
    assert 200 in markers
