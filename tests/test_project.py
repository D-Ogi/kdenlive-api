"""Tests for Project and ProjectManager."""

from kdenlive_api.project_manager import ProjectManager
from kdenlive_api.project import Project


def test_get_current_project(mock_dbus):
    pm = ProjectManager(mock_dbus)
    project = pm.GetCurrentProject()
    assert isinstance(project, Project)


def test_project_name(mock_dbus):
    project = Project(mock_dbus)
    assert project.GetName() == "Test Project"


def test_project_fps(mock_dbus):
    project = Project(mock_dbus)
    assert project.GetFps() == 25.0


def test_project_resolution(mock_dbus):
    project = Project(mock_dbus)
    w, h = project.GetResolution()
    assert w == 1536
    assert h == 864


def test_project_settings(mock_dbus):
    project = Project(mock_dbus)
    project.SetSetting("test_key", "test_value")
    assert project.GetSetting("test_key") == "test_value"


def test_save_project(mock_dbus):
    project = Project(mock_dbus)
    assert project.Save()


def test_save_project_as(mock_dbus):
    project = Project(mock_dbus)
    assert project.SaveAs("/tmp/new_project.kdenlive")
    assert project.GetProjectPath() == "/tmp/new_project.kdenlive"


def test_create_project(mock_dbus):
    pm = ProjectManager(mock_dbus)
    project = pm.CreateProject("New Project")
    assert project is not None
    assert project.GetName() == "New Project"


def test_load_project(mock_dbus):
    pm = ProjectManager(mock_dbus)
    project = pm.LoadProject("/tmp/existing.kdenlive")
    assert project is not None
