"""Base adapter re-export for convenience.

This module re-exports the base adapter class for easier imports
within the adapters package.
"""

from ..base import (
    BaseSourceAdapter,
    ExtractedComponent,
    ExtractedStyle,
    ExtractionResult,
)

__all__ = [
    "BaseSourceAdapter",
    "ExtractedComponent",
    "ExtractedStyle",
    "ExtractionResult",
]
