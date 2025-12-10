"""Generic fallback adapter for extracting styles from any file.

This module provides a regex-based fallback adapter that can extract
basic style usage from HTML, JS, and other files.
"""

import re
from pathlib import Path

from ...models import SymbolKind, Visibility
from ..base import BaseSourceAdapter, ExtractedComponent, ExtractedStyle


class GenericAdapter(BaseSourceAdapter):
    """Fallback regex-based adapter for unknown file types.

    Provides basic extraction of class attributes and inline styles
    using regex patterns. Used as a last resort when no specific
    framework adapter is available.
    """

    SUPPORTED_EXTENSIONS = [".html", ".htm", ".js", ".mjs", ".cjs"]

    @property
    def supported_extensions(self) -> list[str]:
        """File extensions this adapter explicitly supports."""
        return self.SUPPORTED_EXTENSIONS

    def can_handle(self, file_path: Path) -> bool:
        """Check if this adapter can handle the given file.

        As a fallback, this returns True for any file, but prefers
        explicitly supported extensions.

        Args:
            file_path: Path to the file.

        Returns:
            Always True (fallback adapter).
        """
        # Accept any file as fallback
        return True

    def extract_components(
        self, file_path: Path, content: str | None = None
    ) -> list[ExtractedComponent]:
        """Extract component-like patterns.

        Uses heuristics to find component definitions in generic files.

        Args:
            file_path: Path to the file.
            content: Optional file content.

        Returns:
            List of extracted components (may be empty).
        """
        content = self._read_file(file_path, content)
        components = []

        # Look for class-based components (generic pattern)
        for match in re.finditer(
            r"class\s+([A-Z][a-zA-Z0-9_]*)\s+extends\s+\w+",
            content,
        ):
            name = match.group(1)
            start_line = content[: match.start()].count("\n") + 1

            components.append(
                ExtractedComponent(
                    name=name,
                    source_ref=self._create_symbol_ref(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=start_line,
                        name=name,
                        kind=SymbolKind.COMPONENT,
                        visibility=Visibility.LOCAL,
                    ),
                    tag_name=name,
                    props={},
                    children_structure="",
                    style_refs=[],
                    framework="generic",
                )
            )

        return components

    def extract_style_usage(
        self, file_path: Path, content: str | None = None
    ) -> list[ExtractedStyle]:
        """Extract style usage using regex patterns.

        Finds class attributes, style attributes, and className usage.

        Args:
            file_path: Path to the file.
            content: Optional file content.

        Returns:
            List of extracted styles.
        """
        content = self._read_file(file_path, content)
        styles = []

        # Find class="..." or class='...'
        for match in re.finditer(r'class\s*=\s*["\']([^"\']+)["\']', content):
            class_names = match.group(1).split()
            if not class_names:
                continue

            line_number = content[: match.start()].count("\n") + 1

            styles.append(
                ExtractedStyle(
                    source_ref=self._create_symbol_ref(
                        file_path=file_path,
                        start_line=line_number,
                        end_line=line_number,
                        kind=SymbolKind.STYLE_OBJECT,
                    ),
                    selector=None,
                    declarations={},
                    is_inline=False,
                    class_names=class_names,
                )
            )

        # Find className="..." (JSX-style)
        for match in re.finditer(r'className\s*=\s*["\']([^"\']+)["\']', content):
            class_names = match.group(1).split()
            if not class_names:
                continue

            line_number = content[: match.start()].count("\n") + 1

            styles.append(
                ExtractedStyle(
                    source_ref=self._create_symbol_ref(
                        file_path=file_path,
                        start_line=line_number,
                        end_line=line_number,
                        kind=SymbolKind.STYLE_OBJECT,
                    ),
                    selector=None,
                    declarations={},
                    is_inline=False,
                    class_names=class_names,
                )
            )

        # Find style="..." inline styles
        for match in re.finditer(r'style\s*=\s*["\']([^"\']+)["\']', content):
            style_content = match.group(1)
            line_number = content[: match.start()].count("\n") + 1
            declarations = self._parse_inline_style(style_content)

            if declarations:
                styles.append(
                    ExtractedStyle(
                        source_ref=self._create_symbol_ref(
                            file_path=file_path,
                            start_line=line_number,
                            end_line=line_number,
                            kind=SymbolKind.STYLE_OBJECT,
                        ),
                        selector=None,
                        declarations=declarations,
                        is_inline=True,
                        class_names=[],
                    )
                )

        return styles

    def _parse_inline_style(self, style_content: str) -> dict[str, str]:
        """Parse inline style string to declarations.

        Args:
            style_content: CSS inline style string.

        Returns:
            Dictionary of property -> value pairs.
        """
        declarations = {}

        for decl in style_content.split(";"):
            decl = decl.strip()
            if ":" in decl:
                parts = decl.split(":", 1)
                prop = parts[0].strip()
                value = parts[1].strip()
                if prop and value:
                    declarations[prop] = value

        return declarations
