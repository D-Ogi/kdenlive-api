"""ProjectManager — create, load, save projects."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kdenlive_api.dbus_client import KdenliveDBus

from kdenlive_api.project import Project


class ProjectManager:
    """Manages Kdenlive projects (open, save, create).

    Kdenlive does not have a project database like Resolve. The folder
    navigation methods (GetProjectListInCurrentFolder, OpenFolder, etc.)
    are stubs that report the current project only.
    """

    def __init__(self, dbus: KdenliveDBus):
        self._dbus = dbus

    def CreateProject(self, name: str) -> Project | None:
        """Create a new project with default settings."""
        result = self._dbus.new_project(name)
        if result:
            return Project(self._dbus)
        return None

    def LoadProject(self, file_path: str) -> Project | None:
        """Open an existing .kdenlive project file."""
        if self._dbus.open_project(file_path):
            return Project(self._dbus)
        return None

    def SaveProject(self) -> bool:
        """Save the current project."""
        return self._dbus.save_project()

    def GetCurrentProject(self) -> Project:
        """Return a Project handle for the currently open project."""
        return Project(self._dbus)

    # ── Resolve project-database compatibility stubs ───────────────────

    def GetProjectListInCurrentFolder(self) -> list[str]:
        """Return project names in the current folder.

        Kdenlive has no project database — returns the currently open
        project name in a list.
        """
        name = self._dbus.get_project_name()
        return [name] if name else []

    def GetFolderListInCurrentFolder(self) -> list[str]:
        """Return subfolder names in the current project folder.

        Always returns an empty list (no project database).
        """
        return []

    def OpenFolder(self, folder_name: str) -> bool:
        """Open a folder in the project database. No-op."""
        return False

    def GotoParentFolder(self) -> bool:
        """Navigate to the parent folder. No-op stub."""
        return True

    def GotoRootFolder(self) -> bool:
        """Navigate to the root folder. No-op stub."""
        return True

    def CloseProject(self, project: Project) -> bool:
        """Close a project. Stub — Kdenlive always has one project."""
        return True
