"""Source collector for UI component and style extraction.

This module provides the main SourceCollector class that uses
framework-specific adapters to extract components and styles
from source files.
"""

from pathlib import Path
from typing import Any

from .base import BaseSourceAdapter, ExtractionResult


class SourceCollector:
    """Collects UI components and styles using framework adapters.

    The SourceCollector manages a set of framework adapters and
    routes files to the appropriate adapter based on file extension
    and adapter capabilities.
    """

    def __init__(self, project_path: Path | str | None = None):
        """Initialize the source collector.

        Args:
            project_path: Optional project root path.
        """
        self.project_path = Path(project_path) if project_path else None
        self._adapters: list[BaseSourceAdapter] = []
        self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        """Register built-in framework adapters.

        Imports and registers all default adapters. The generic
        fallback adapter is registered last.
        """
        # Import adapters lazily to avoid circular imports
        from .adapters.css import CSSAdapter
        from .adapters.generic import GenericAdapter
        from .adapters.react import ReactAdapter
        from .adapters.svelte import SvelteAdapter
        from .adapters.vue import VueAdapter

        self._adapters = [
            ReactAdapter(),
            VueAdapter(),
            SvelteAdapter(),
            CSSAdapter(),
            GenericAdapter(),  # Fallback - always last
        ]

    def register(self, adapter: BaseSourceAdapter) -> None:
        """Register a custom adapter.

        Custom adapters are inserted before the generic fallback
        adapter to ensure they take priority.

        Args:
            adapter: The adapter to register.
        """
        # Insert before the last adapter (generic fallback)
        if len(self._adapters) > 0:
            self._adapters.insert(-1, adapter)
        else:
            self._adapters.append(adapter)

    def unregister(self, adapter_name: str) -> bool:
        """Unregister an adapter by name.

        Args:
            adapter_name: Name of the adapter to remove.

        Returns:
            True if an adapter was removed.
        """
        for i, adapter in enumerate(self._adapters):
            if adapter.name == adapter_name:
                self._adapters.pop(i)
                return True
        return False

    def get_adapter(self, file_path: Path) -> BaseSourceAdapter | None:
        """Get appropriate adapter for file.

        Returns the first adapter that reports it can handle
        the given file.

        Args:
            file_path: Path to the file.

        Returns:
            Adapter that can handle the file, or None.
        """
        for adapter in self._adapters:
            if adapter.can_handle(file_path):
                return adapter
        return None

    def get_adapter_for_extension(self, extension: str) -> BaseSourceAdapter | None:
        """Get adapter by file extension.

        Args:
            extension: File extension (with or without dot).

        Returns:
            Adapter that handles this extension, or None.
        """
        if not extension.startswith("."):
            extension = f".{extension}"

        for adapter in self._adapters:
            if extension.lower() in [e.lower() for e in adapter.supported_extensions]:
                return adapter
        return None

    def list_adapters(self) -> list[dict[str, Any]]:
        """List all registered adapters.

        Returns:
            List of adapter info dicts with name and extensions.
        """
        return [
            {
                "name": adapter.name,
                "extensions": adapter.supported_extensions,
            }
            for adapter in self._adapters
        ]

    def extract(
        self, file_path: Path | str, content: str | None = None
    ) -> ExtractionResult:
        """Extract components and styles from file.

        Args:
            file_path: Path to the source file.
            content: Optional file content.

        Returns:
            ExtractionResult with extracted data.
        """
        file_path = Path(file_path)

        adapter = self.get_adapter(file_path)
        if adapter is None:
            return ExtractionResult(
                file_path=file_path,
                errors=[f"No adapter found for {file_path.suffix}"],
            )

        return adapter.extract(file_path, content)

    def extract_batch(
        self,
        file_paths: list[Path | str],
        continue_on_error: bool = True,
    ) -> list[ExtractionResult]:
        """Extract from multiple files.

        Args:
            file_paths: List of file paths.
            continue_on_error: If True, continue extracting on errors.

        Returns:
            List of ExtractionResult objects.
        """
        results = []

        for file_path in file_paths:
            try:
                result = self.extract(file_path)
                results.append(result)
            except Exception as e:
                if continue_on_error:
                    results.append(
                        ExtractionResult(
                            file_path=Path(file_path),
                            errors=[f"Extraction failed: {e}"],
                        )
                    )
                else:
                    raise

        return results

    def extract_directory(
        self,
        directory: Path | str,
        extensions: list[str] | None = None,
        recursive: bool = True,
    ) -> list[ExtractionResult]:
        """Extract from all supported files in a directory.

        Args:
            directory: Directory to scan.
            extensions: Optional list of extensions to include.
            recursive: If True, scan subdirectories.

        Returns:
            List of ExtractionResult objects.
        """
        directory = Path(directory)

        # Default to all supported extensions
        if extensions is None:
            extensions = []
            for adapter in self._adapters:
                extensions.extend(adapter.supported_extensions)
            extensions = list(set(extensions))

        # Find files
        file_paths = []
        if recursive:
            for ext in extensions:
                file_paths.extend(directory.rglob(f"*{ext}"))
        else:
            for ext in extensions:
                file_paths.extend(directory.glob(f"*{ext}"))

        return self.extract_batch(file_paths)

    def get_supported_extensions(self) -> list[str]:
        """Get all supported file extensions.

        Returns:
            Deduplicated list of all extensions from all adapters.
        """
        extensions = []
        for adapter in self._adapters:
            extensions.extend(adapter.supported_extensions)
        return list(set(extensions))
