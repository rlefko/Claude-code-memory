"""Framework-specific source adapters.

This module provides adapters for different UI frameworks
to extract components and styles from source files.
"""

from .css import CSSAdapter
from .generic import GenericAdapter
from .react import ReactAdapter
from .svelte import SvelteAdapter
from .vue import VueAdapter

__all__ = [
    "ReactAdapter",
    "VueAdapter",
    "SvelteAdapter",
    "CSSAdapter",
    "GenericAdapter",
]
