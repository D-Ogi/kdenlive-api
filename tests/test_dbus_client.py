"""Tests for D-Bus client module (unit tests, no live Kdenlive needed)."""

import pytest
from kdenlive_api.dbus_client import _get_dbus_backend, KdenliveDBus
from kdenlive_api.constants import DBUS_SERVICE, DBUS_PATH, DBUS_IFACE_SCRIPTING


def test_constants():
    assert DBUS_SERVICE == "org.kde.kdenlive"
    assert DBUS_PATH == "/MainWindow"
    assert DBUS_IFACE_SCRIPTING == "org.kde.kdenlive.scripting"


def test_backend_detection():
    """Backend detection should return a string or None."""
    result = _get_dbus_backend()
    assert result is None or isinstance(result, str)
