"""Collectors for UI consistency checking.

This module provides collectors that gather UI-related information from
source code and git diff for analysis.
"""

from .base import (
    BaseSourceAdapter,
    ExtractedComponent,
    ExtractedStyle,
    ExtractionResult,
)
from .git_diff import (
    DiffResult,
    FileChange,
    GitDiffCollector,
)
from .source import (
    SourceCollector,
)

__all__ = [
    # Git diff collection
    "FileChange",
    "DiffResult",
    "GitDiffCollector",
    # Source extraction
    "ExtractedComponent",
    "ExtractedStyle",
    "ExtractionResult",
    "BaseSourceAdapter",
    "SourceCollector",
]
