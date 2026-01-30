"""Tests for MediaPool, Folder, MediaPoolItem."""

from kdenlive_api.media_pool import MediaPool, MediaPoolItem, Folder


def test_import_media(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/path/to/clip1.mp4", "/path/to/clip2.mp4"])
    assert len(clips) == 2
    assert all(isinstance(c, MediaPoolItem) for c in clips)


def test_create_folder(mock_dbus):
    pool = MediaPool(mock_dbus)
    folder = pool.AddSubFolder(None, "Test Folder")
    assert folder is not None
    assert folder.GetName() == "Test Folder"


def test_get_all_clips(mock_dbus):
    pool = MediaPool(mock_dbus)
    pool.ImportMedia(["/path/a.mp4", "/path/b.mp4"])
    clips = pool.GetAllClips()
    assert len(clips) == 2


def test_clip_properties(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/path/to/test.mp4"])
    clip = clips[0]
    assert clip.GetName() == "test.mp4"
    assert clip.GetDuration() == 125


def test_delete_clip(mock_dbus):
    pool = MediaPool(mock_dbus)
    clips = pool.ImportMedia(["/path/to/del.mp4"])
    assert clips[0].Delete()
    assert len(pool.GetAllClips()) == 0


def test_folder_clip_list(mock_dbus):
    pool = MediaPool(mock_dbus)
    folder = pool.AddSubFolder(None, "Scenes")
    clips = pool.ImportMedia(["/path/s01.mp4"], folder)
    folder_clips = folder.GetClipList()
    assert len(folder_clips) == 1


def test_get_root_folder(mock_dbus):
    pool = MediaPool(mock_dbus)
    root = pool.GetRootFolder()
    assert root.folder_id == "-1"
    assert root.GetName() == "Root"
