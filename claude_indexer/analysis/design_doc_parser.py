"""Parser for design documents (PRD, TDD, ADR, specifications).

Milestone 8.1: Design Document Indexing

This parser extracts structured information from design documents including:
- Document type detection (PRD, TDD, ADR, SPEC)
- Section extraction from markdown headers
- Requirement extraction (MUST, SHALL, numbered items)
- Relations between document sections
"""

import hashlib
import re
import time
from pathlib import Path
from typing import Any

from .entities import (
    Entity,
    EntityChunk,
    EntityFactory,
    EntityType,
    Relation,
    RelationFactory,
)
from .parser import CodeParser, ParserResult


class DesignDocParser(CodeParser):
    """Parse design documents (PRD, TDD, ADR, specifications).

    Detects document type from filename and content patterns,
    extracts sections and requirements as separate entities.
    """

    # File extensions this parser handles
    # Note: This parser is selective - it only processes markdown files
    # that match design document patterns
    SUPPORTED_EXTENSIONS = [".md"]

    # Document type detection patterns
    # Each pattern is a tuple of (regex, match_type) where match_type is
    # "filename" or "content"
    DOC_TYPE_PATTERNS: dict[str, list[tuple[str, str]]] = {
        "prd": [
            (r"product\s+requirements?\s+document", "content"),
            (r"^prd[_-]", "filename"),
            (r"(?:^|/)prd\.", "filename"),
            (r"requirements\s+specification", "content"),
            (r"product\s+specification", "content"),
        ],
        "tdd": [
            (r"technical\s+design\s+document", "content"),
            (r"^tdd[_-]", "filename"),
            (r"(?:^|/)tdd\.", "filename"),
            (r"system\s+design", "content"),
            (r"technical\s+specification", "content"),
        ],
        "adr": [
            (r"architecture\s+decision\s+record", "content"),
            (r"^adr[_-]\d+", "filename"),
            (r"(?:^|/)adr[_-]", "filename"),
            (r"decision:\s*\w+", "content"),
            (r"status:\s*(?:accepted|proposed|deprecated|superseded)", "content"),
        ],
        "spec": [
            (r"specification", "content"),
            (r"^spec[_-]", "filename"),
            (r"(?:^|/)spec\.", "filename"),
            (r"functional\s+requirements", "content"),
        ],
    }

    # Requirement extraction patterns
    REQUIREMENT_PATTERNS = [
        # RFC 2119 style requirements
        r"(?:^|\n)\s*[-*]\s*(?:The\s+system\s+)?(?:MUST|SHALL|SHOULD|MAY)\s+(.+?)(?:\n|$)",
        # Bracketed requirement IDs
        r"\[REQ-\d+\]\s*(.+?)(?:\n|$)",
        # Numbered requirements
        r"(?:^|\n)\s*\d+\.\s*(?:The\s+system\s+)?(?:must|shall|should|may)\s+(.+?)(?:\n|$)",
    ]

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the design document parser.

        Args:
            config: Optional parser configuration
        """
        self.config = config or {}
        self.max_section_depth = self.config.get("max_section_depth", 3)
        self.extract_requirements = self.config.get("extract_requirements", True)

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file.

        This parser is selective - it only handles markdown files that
        match design document patterns in filename or content.
        """
        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return False

        # Check filename patterns - only claim files that match design doc patterns
        filename = file_path.name.lower()
        for _doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            for pattern, match_type in patterns:
                if match_type == "filename":
                    if re.search(pattern, filename, re.IGNORECASE):
                        return True

        # For .md files that don't match filename patterns, let MarkdownParser
        # handle them. Content-based detection still works during parsing for
        # files that DO match filename patterns.
        return False

    def get_supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""
        return self.SUPPORTED_EXTENSIONS

    def parse(self, file_path: Path) -> ParserResult:
        """Parse a design document and extract entities.

        Args:
            file_path: Path to the design document

        Returns:
            ParserResult with entities, relations, and chunks
        """
        start_time = time.time()
        result = ParserResult(file_path=file_path, entities=[], relations=[])

        try:
            # Read file content
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()

            result.file_hash = self._get_file_hash(file_path)

            # Detect document type
            doc_type = self._detect_doc_type(file_path, content)

            # If no design doc type detected, return minimal result
            # (let other parsers handle it)
            if doc_type is None:
                # Still create file entity for indexing
                file_entity = EntityFactory.create_file_entity(
                    file_path,
                    content_type="markdown",
                    parsing_method="design-doc-fallback",
                )
                result.entities = [file_entity]
                result.parsing_time = time.time() - start_time
                return result

            entities: list[Entity] = []
            relations: list[Relation] = []
            chunks: list[EntityChunk] = []

            # Create document entity based on type
            doc_entity = self._create_doc_entity(file_path, content, doc_type)
            entities.append(doc_entity)

            # Extract sections
            sections = self._extract_sections(content, file_path, doc_type)
            for section_entity, section_content, start_line in sections:
                entities.append(section_entity)

                # Create CONTAINS relation from doc to section
                relations.append(
                    RelationFactory.create_contains_relation(
                        doc_entity.name, section_entity.name
                    )
                )

                # Create implementation chunk for section
                chunk = self._create_section_chunk(
                    file_path, section_entity, section_content, start_line
                )
                chunks.append(chunk)

            # Extract requirements if enabled
            if self.extract_requirements:
                requirements = self._extract_requirements(content, file_path, doc_type)
                for req_entity, parent_section in requirements:
                    entities.append(req_entity)

                    # Create relation to parent section or document
                    parent_name = parent_section or doc_entity.name
                    relations.append(
                        RelationFactory.create_contains_relation(
                            parent_name, req_entity.name
                        )
                    )

            # Create document implementation chunk
            doc_chunk = EntityChunk(
                id=self._create_chunk_id(
                    file_path, doc_entity.name, "implementation", doc_type
                ),
                entity_name=doc_entity.name,
                chunk_type="implementation",
                content=content[:10000],  # Limit size
                metadata={
                    "entity_type": doc_type,
                    "file_path": str(file_path),
                    "doc_type": doc_type,
                    "section_count": len(sections),
                    "requirement_count": (
                        len(requirements) if self.extract_requirements else 0
                    ),
                },
            )
            chunks.append(doc_chunk)

            result.entities = entities
            result.relations = relations
            result.implementation_chunks = chunks

        except Exception as e:
            result.errors = [f"Design doc parsing failed: {e}"]

        result.parsing_time = time.time() - start_time
        return result

    def _detect_doc_type(self, file_path: Path, content: str) -> str | None:
        """Detect document type from filename and content patterns.

        Args:
            file_path: Path to the document
            content: Document content

        Returns:
            Document type string or None if not a design doc
        """
        filename = file_path.name.lower()
        content_lower = content.lower()

        # Check each document type
        for doc_type, patterns in self.DOC_TYPE_PATTERNS.items():
            for pattern, match_type in patterns:
                if match_type == "filename":
                    if re.search(pattern, filename, re.IGNORECASE):
                        return doc_type
                elif match_type == "content":
                    if re.search(pattern, content_lower, re.IGNORECASE):
                        return doc_type

        return None

    def _create_doc_entity(
        self, file_path: Path, content: str, doc_type: str
    ) -> Entity:
        """Create the main document entity.

        Args:
            file_path: Path to the document
            content: Document content
            doc_type: Detected document type

        Returns:
            Entity representing the document
        """
        # Map doc type to EntityType
        type_mapping = {
            "prd": EntityType.PRD,
            "tdd": EntityType.TDD,
            "adr": EntityType.ADR,
            "spec": EntityType.SPEC,
        }
        entity_type = type_mapping.get(doc_type, EntityType.DOCUMENTATION)

        # Extract title from first heading
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else file_path.stem

        # Count sections and requirements for observations
        section_count = len(re.findall(r"^#{1,3}\s+", content, re.MULTILINE))
        req_matches = []
        for pattern in self.REQUIREMENT_PATTERNS:
            req_matches.extend(re.findall(pattern, content, re.IGNORECASE))

        observations = [
            f"{doc_type.upper()}: {title}",
            f"Design document type: {doc_type}",
            f"Sections: {section_count}",
            f"Requirements detected: {len(req_matches)}",
            f"File: {file_path.name}",
        ]

        return Entity(
            name=f"{doc_type.upper()}: {title}",
            entity_type=entity_type,
            observations=observations,
            file_path=file_path,
            line_number=1,
            metadata={
                "type": doc_type,
                "title": title,
                "section_count": section_count,
                "requirement_count": len(req_matches),
            },
        )

    def _extract_sections(
        self, content: str, file_path: Path, doc_type: str
    ) -> list[tuple[Entity, str, int]]:
        """Extract sections from markdown content.

        Args:
            content: Document content
            file_path: Path to the document
            doc_type: Document type

        Returns:
            List of (Entity, section_content, start_line) tuples
        """
        sections: list[tuple[Entity, str, int]] = []
        lines = content.split("\n")

        current_section: dict[str, Any] | None = None
        section_content_lines: list[str] = []

        for i, line in enumerate(lines):
            # Check for heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)

            if heading_match:
                # Save previous section if exists
                if current_section is not None:
                    section_content = "\n".join(section_content_lines).strip()
                    if section_content:
                        entity = self._create_section_entity(
                            current_section, section_content, file_path, doc_type
                        )
                        sections.append(
                            (entity, section_content, current_section["start_line"])
                        )

                # Start new section
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # Only extract up to max_section_depth
                if level <= self.max_section_depth:
                    current_section = {
                        "level": level,
                        "title": title,
                        "start_line": i + 1,
                    }
                    section_content_lines = []
                else:
                    # Include deeper headings in current section content
                    if current_section is not None:
                        section_content_lines.append(line)
            elif current_section is not None:
                section_content_lines.append(line)

        # Save last section
        if current_section is not None:
            section_content = "\n".join(section_content_lines).strip()
            if section_content:
                entity = self._create_section_entity(
                    current_section, section_content, file_path, doc_type
                )
                sections.append(
                    (entity, section_content, current_section["start_line"])
                )

        return sections

    def _create_section_entity(
        self,
        section_info: dict[str, Any],
        content: str,
        file_path: Path,
        doc_type: str,
    ) -> Entity:
        """Create an entity for a document section.

        Args:
            section_info: Section metadata (title, level, start_line)
            content: Section content
            file_path: Path to the document
            doc_type: Document type

        Returns:
            Entity representing the section
        """
        title = section_info["title"]
        level = section_info["level"]
        start_line = section_info["start_line"]

        # Create unique name
        name = f"Section: {title}"

        # Count requirements in this section
        req_count = 0
        for pattern in self.REQUIREMENT_PATTERNS:
            req_count += len(re.findall(pattern, content, re.IGNORECASE))

        observations = [
            f"Section: {title}",
            f"Heading level: {level}",
            f"From {doc_type.upper()} document",
            f"Content preview: {content[:150]}..." if len(content) > 150 else content,
        ]
        if req_count > 0:
            observations.append(f"Contains {req_count} requirements")

        return Entity(
            name=name,
            entity_type=EntityType.DOCUMENTATION,
            observations=observations,
            file_path=file_path,
            line_number=start_line,
            metadata={
                "type": "section",
                "doc_type": doc_type,
                "heading_level": level,
                "requirement_count": req_count,
            },
        )

    def _extract_requirements(
        self, content: str, file_path: Path, doc_type: str
    ) -> list[tuple[Entity, str | None]]:
        """Extract requirements from document content.

        Args:
            content: Document content
            file_path: Path to the document
            doc_type: Document type

        Returns:
            List of (Entity, parent_section_name) tuples
        """
        requirements: list[tuple[Entity, str | None]] = []
        lines = content.split("\n")

        current_section: str | None = None
        req_counter = 0

        for i, line in enumerate(lines):
            # Track current section
            heading_match = re.match(r"^#{1,3}\s+(.+)$", line)
            if heading_match:
                current_section = f"Section: {heading_match.group(1).strip()}"
                continue

            # Check for requirements
            for pattern in self.REQUIREMENT_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    req_counter += 1
                    req_text = match.group(1) if match.groups() else match.group(0)
                    req_text = req_text.strip()

                    # Determine requirement type
                    req_type = "general"
                    if re.search(r"\bMUST\b", line, re.IGNORECASE):
                        req_type = "mandatory"
                    elif re.search(r"\bSHOULD\b", line, re.IGNORECASE):
                        req_type = "recommended"
                    elif re.search(r"\bMAY\b", line, re.IGNORECASE):
                        req_type = "optional"

                    entity = Entity(
                        name=f"REQ-{req_counter:03d}: {req_text[:50]}",
                        entity_type=EntityType.REQUIREMENT,
                        observations=[
                            f"Requirement: {req_text}",
                            f"Type: {req_type}",
                            f"From {doc_type.upper()} document",
                            f"Source section: {current_section or 'Document root'}",
                        ],
                        file_path=file_path,
                        line_number=i + 1,
                        metadata={
                            "type": "requirement",
                            "requirement_type": req_type,
                            "doc_type": doc_type,
                            "full_text": req_text,
                            "parent_section": current_section,
                        },
                    )
                    requirements.append((entity, current_section))

        return requirements

    def _create_section_chunk(
        self, file_path: Path, entity: Entity, content: str, start_line: int
    ) -> EntityChunk:
        """Create an implementation chunk for a section.

        Args:
            file_path: Path to the document
            entity: Section entity
            content: Section content
            start_line: Starting line number

        Returns:
            EntityChunk for the section
        """
        return EntityChunk(
            id=self._create_chunk_id(
                file_path, entity.name, "implementation", "section"
            ),
            entity_name=entity.name,
            chunk_type="implementation",
            content=content,
            metadata={
                "entity_type": "section",
                "file_path": str(file_path),
                "start_line": start_line,
                "content_length": len(content),
            },
        )

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file contents."""
        try:
            with open(file_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""

    def _create_chunk_id(
        self, file_path: Path, entity_name: str, chunk_type: str, entity_type: str
    ) -> str:
        """Create a deterministic chunk ID.

        Args:
            file_path: Path to the file
            entity_name: Name of the entity
            chunk_type: Type of chunk (metadata/implementation)
            entity_type: Type of entity

        Returns:
            Unique chunk ID
        """
        # Create hash for collision resistance
        hash_input = f"{file_path}::{entity_name}::{chunk_type}"
        hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        return f"{file_path}::{entity_type}::{entity_name}::{chunk_type}::{hash_suffix}"
