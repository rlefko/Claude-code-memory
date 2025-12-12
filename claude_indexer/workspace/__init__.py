"""
Workspace support for Claude Code Memory.

This module enables support for VS Code multi-root workspaces and monorepos,
providing unified or isolated indexing based on workspace type.

Workspace Types:
    - VS Code Multi-Root: Uses .code-workspace files, creates separate collections
    - pnpm: Uses pnpm-workspace.yaml, single unified collection
    - npm/yarn: Uses package.json workspaces field, single unified collection
    - Lerna: Uses lerna.json, single unified collection
    - Nx: Uses nx.json/project.json, single unified collection
    - Turborepo: Uses turbo.json with npm workspaces, single unified collection

Key Components:
    - WorkspaceDetector: Detects workspace type from directory structure
    - WorkspaceManager: Manages workspace lifecycle and operations
    - WorkspaceContext: Tracks workspace session state
    - WorkspaceConfigLoader: Handles per-folder configuration

Example:
    from claude_indexer.workspace import WorkspaceManager, WorkspaceType

    manager = WorkspaceManager()

    if manager.is_workspace():
        context = manager.initialize()
        print(f"Workspace type: {context.workspace_config.workspace_type.value}")
        print(f"Members: {len(context.members)}")

        for member in context.members:
            collection = context.get_collection_for_path(member.path)
            print(f"  {member.name} -> {collection}")
    else:
        print("Not in a workspace (single project mode)")
"""

from .config import WorkspaceConfigLoader
from .context import WorkspaceContext
from .detector import WorkspaceDetector
from .manager import (
    WorkspaceManager,
    detect_workspace,
    get_workspace_context,
)
from .types import (
    CollectionStrategy,
    WorkspaceConfig,
    WorkspaceMember,
    WorkspaceType,
)

__all__ = [
    # Types
    "CollectionStrategy",
    "WorkspaceConfig",
    "WorkspaceMember",
    "WorkspaceType",
    # Classes
    "WorkspaceConfigLoader",
    "WorkspaceContext",
    "WorkspaceDetector",
    "WorkspaceManager",
    # Functions
    "detect_workspace",
    "get_workspace_context",
]
