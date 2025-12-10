"""Normalizers for UI consistency checking.

This module provides normalization utilities for styles, components, and tokens
to enable consistent comparison and duplicate detection.
"""

from .component import (
    ComponentNormalizer,
    NormalizedComponent,
)
from .hashing import (
    compute_content_hash,
    compute_minhash,
    compute_simhash,
    hamming_distance,
    jaccard_similarity,
    minhash_similarity,
    simhash_similarity,
)
from .style import (
    NormalizedStyle,
    StyleNormalizer,
)
from .token_resolver import (
    ResolutionStatus,
    TokenCategory,
    TokenResolution,
    TokenResolver,
)

__all__ = [
    # Token resolution
    "TokenCategory",
    "ResolutionStatus",
    "TokenResolution",
    "TokenResolver",
    # Style normalization
    "NormalizedStyle",
    "StyleNormalizer",
    # Component normalization
    "NormalizedComponent",
    "ComponentNormalizer",
    # Hashing utilities
    "compute_simhash",
    "simhash_similarity",
    "hamming_distance",
    "compute_minhash",
    "minhash_similarity",
    "jaccard_similarity",
    "compute_content_hash",
]
