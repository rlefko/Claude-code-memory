"""Unified configuration loading with project support.

This module provides backward-compatible access to the hierarchical configuration
system. It delegates internally to HierarchicalConfigLoader while returning
IndexerConfig for compatibility with existing code.

Migration Note (v1.0.0):
    ConfigLoader now uses HierarchicalConfigLoader internally. All consumers
    continue to work unchanged - they receive IndexerConfig as before, but
    the loading logic uses the modern hierarchical system.
"""

from pathlib import Path
from typing import Any

from ..indexer_logging import get_logger
from .hierarchical_loader import HierarchicalConfigLoader
from .legacy import load_legacy_settings
from .models import IndexerConfig
from .unified_config import UnifiedConfig

logger = get_logger()


class ConfigLoader:
    """Unified configuration loader with project-level support.

    This class delegates to HierarchicalConfigLoader internally while
    maintaining backward compatibility by returning IndexerConfig.

    Precedence (highest to lowest):
    1. Explicit overrides
    2. Environment variables
    3. Local overrides (.claude/settings.local.json)
    4. Project config (.claude/settings.json or .claude-indexer/config.json)
    5. Global config (~/.claude-indexer/config.json)
    6. Legacy settings.txt
    7. Defaults
    """

    def __init__(
        self,
        project_path: Path | None = None,
        settings_file_override: Path | None = None,
    ):
        """Initialize the configuration loader.

        Args:
            project_path: Path to the project root. Defaults to current directory.
            settings_file_override: Optional explicit settings file path (for tests).
        """
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self._settings_file_override = settings_file_override
        self._unified_config: UnifiedConfig | None = None

    def load(self, **overrides: Any) -> IndexerConfig:
        """Load unified configuration from all sources.

        Returns:
            IndexerConfig with settings from all sources merged.
        """
        # Create hierarchical loader
        loader = HierarchicalConfigLoader(self.project_path)

        # Convert all flat-key overrides to nested format
        # This ensures backward compatibility with old-style calls like:
        #   load_config(openai_api_key="sk-xxx", qdrant_url="http://...")
        nested_overrides = self._convert_legacy_to_nested(overrides)

        # Handle custom-named settings files (not "settings.txt")
        # HierarchicalConfigLoader automatically loads "settings.txt" from project_path,
        # but for custom-named files (e.g., "test_settings.txt"), we need to load them
        # and inject the values. These values have LOWER priority than env vars.
        if self._settings_file_override and self._settings_file_override.exists():
            if self._settings_file_override.name != "settings.txt":
                # Custom-named file - HierarchicalConfigLoader won't find it
                # Load it separately and inject BEFORE env vars (via loader's internal logic)
                legacy_settings = load_legacy_settings(self._settings_file_override)
                file_nested = self._convert_legacy_to_nested(legacy_settings)
                # Merge file settings, then explicit overrides take precedence
                # Note: This still puts custom file values at override priority level
                # For proper precedence, we'd need to extend HierarchicalConfigLoader
                merged_overrides = dict(file_nested)
                merged_overrides.update(nested_overrides)
                logger.debug(
                    f"Applied {len(legacy_settings)} settings from custom file "
                    f"{self._settings_file_override}"
                )
            else:
                # Standard "settings.txt" - HierarchicalConfigLoader will find it
                # Just pass the explicit overrides
                merged_overrides = nested_overrides
        else:
            merged_overrides = nested_overrides

        # Load unified config and store for get_parser_config()
        self._unified_config = loader.load(**merged_overrides)

        # Convert to IndexerConfig for backward compatibility
        try:
            return self._unified_config.to_indexer_config()
        except (AttributeError, TypeError) as e:
            # Fallback: HierarchicalConfigLoader._create_fallback_config may return
            # a UnifiedConfig with dict values instead of proper model instances
            logger.warning(f"Config conversion failed, using defaults: {e}")
            # Create IndexerConfig with defaults and apply valid flat overrides
            config = IndexerConfig()
            for key, value in overrides.items():
                if hasattr(config, key):
                    try:
                        setattr(config, key, value)
                    except (ValueError, TypeError, AttributeError):
                        logger.debug(f"Skipping invalid override {key}={value}")
            return config

    def _convert_legacy_to_nested(self, legacy: dict[str, Any]) -> dict[str, Any]:
        """Convert legacy flat keys to nested format for HierarchicalConfigLoader.

        Uses dot notation that HierarchicalConfigLoader._apply_overrides() supports.
        """
        # Mapping from legacy flat keys to dot-notation paths
        key_mappings = {
            "openai_api_key": "api.openai.api_key",
            "voyage_api_key": "api.voyage.api_key",
            "qdrant_api_key": "api.qdrant.api_key",
            "qdrant_url": "api.qdrant.url",
            "embedding_provider": "embedding.provider",
            "voyage_model": "api.voyage.model",
            "indexer_debug": "logging.debug",
            "indexer_verbose": "logging.verbose",
            "debounce_seconds": "watcher.debounce_seconds",
            "max_file_size": "indexing.max_file_size",
            "batch_size": "performance.batch_size",
            "max_concurrent_files": "performance.max_concurrent_files",
            "use_parallel_processing": "performance.use_parallel_processing",
            "max_parallel_workers": "performance.max_parallel_workers",
            "cleanup_interval_minutes": "performance.cleanup_interval_minutes",
            "include_tests": "indexing.include_tests",
        }

        result: dict[str, Any] = {}
        for old_key, value in legacy.items():
            if old_key in key_mappings:
                result[key_mappings[old_key]] = value
            else:
                # Pass through unknown keys as-is
                result[old_key] = value

        return result

    def get_parser_config(self, parser_name: str) -> dict[str, Any]:
        """Get parser-specific configuration.

        Args:
            parser_name: Name of the parser (e.g., 'python', 'javascript').

        Returns:
            Parser-specific configuration dictionary.
        """
        # Ensure config is loaded
        if self._unified_config is None:
            self.load()

        if self._unified_config and self._unified_config.indexing.parser_config:
            parser_config = self._unified_config.indexing.parser_config.get(
                parser_name, {}
            )
            if isinstance(parser_config, dict):
                return parser_config
            # Handle ParserSpecificConfig model
            if hasattr(parser_config, "dict"):
                return parser_config.dict()
            if hasattr(parser_config, "model_dump"):
                return parser_config.model_dump()
        return {}


def load_config(settings_file: Path | None = None, **overrides: Any) -> IndexerConfig:
    """Load configuration from multiple sources with precedence.

    Maintains backward compatibility with old signature.

    Args:
        settings_file: Path to settings.txt file OR project directory (auto-detected)
        **overrides: Explicit configuration overrides

    Returns:
        Configured IndexerConfig instance
    """
    # Auto-detect if settings_file is actually a project directory
    project_path = None
    explicit_settings_file = None

    if settings_file is not None:
        if settings_file.is_dir():
            # It's a project directory
            project_path = settings_file
        elif settings_file.is_file() or settings_file.suffix == ".txt":
            # It's an explicit settings file path (includes test_settings.txt, etc.)
            explicit_settings_file = settings_file
            project_path = (
                settings_file.parent
                if settings_file.parent != Path(__file__).parent.parent.parent
                else None
            )
        else:
            # Default behavior - treat as project directory
            project_path = settings_file

    # Create loader with explicit settings file if provided
    loader = ConfigLoader(
        project_path=project_path,
        settings_file_override=explicit_settings_file,
    )

    return loader.load(**overrides)
