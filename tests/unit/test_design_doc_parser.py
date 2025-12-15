"""Unit tests for design document parser (Milestone 8.1)."""

from claude_indexer.analysis.design_doc_parser import DesignDocParser
from claude_indexer.analysis.entities import EntityType

# Sample design documents for testing
PRD_CONTENT = """# Product Requirements Document

## Overview

This document describes the requirements for the new feature.

## Functional Requirements

### User Authentication

- The system MUST support email/password authentication
- The system SHOULD support OAuth2 providers
- Users MAY enable two-factor authentication

### Data Storage

[REQ-001] All user data must be encrypted at rest
[REQ-002] Data backups should occur daily

## Non-Functional Requirements

1. The system must handle 1000 concurrent users
2. Response time should be under 200ms

## Success Criteria

The feature will be considered complete when all MUST requirements are met.
"""

TDD_CONTENT = """# Technical Design Document

## System Design

This document outlines the technical architecture for the authentication system.

## Architecture Overview

The system uses a microservices architecture with the following components:

### API Gateway

Handles all incoming requests and routes them to appropriate services.

### Auth Service

- MUST validate JWT tokens
- SHALL support token refresh
- SHOULD cache validation results

## Data Model

The primary entities are:
- User
- Session
- Token

## Implementation Plan

Phase 1: Basic authentication
Phase 2: OAuth integration
"""

ADR_CONTENT = """# Architecture Decision Record: Database Selection

## Status

Status: Accepted

## Context

We need to select a database for the new service.

## Decision

We will use PostgreSQL for the following reasons:
- Strong ACID compliance
- Excellent performance
- Rich ecosystem

## Consequences

- The team MUST learn PostgreSQL
- We SHALL need to set up replication
"""

SPEC_CONTENT = """# API Specification

## Overview

This specification defines the REST API endpoints.

## Endpoints

### GET /users

Returns a list of users.

Requirements:
- MUST return paginated results
- SHOULD support filtering

### POST /users

Creates a new user.

## Error Handling

All errors MUST follow RFC 7807 format.
"""

REGULAR_MARKDOWN = """# README

This is a regular markdown file.

## Installation

Run npm install.

## Usage

Import the module.
"""


class TestDesignDocParser:
    """Test the DesignDocParser class."""

    def test_parser_initialization(self):
        """Test parser initializes correctly."""
        parser = DesignDocParser()
        assert parser.max_section_depth == 3
        assert parser.extract_requirements is True

    def test_parser_with_config(self):
        """Test parser with custom configuration."""
        config = {"max_section_depth": 2, "extract_requirements": False}
        parser = DesignDocParser(config)
        assert parser.max_section_depth == 2
        assert parser.extract_requirements is False

    def test_supported_extensions(self):
        """Test parser supports markdown files."""
        parser = DesignDocParser()
        assert ".md" in parser.get_supported_extensions()

    def test_can_parse_prd_filename(self, tmp_path):
        """Test parser recognizes PRD files by filename."""
        parser = DesignDocParser()

        # PRD filename patterns
        assert parser.can_parse(tmp_path / "PRD-feature.md")
        assert parser.can_parse(tmp_path / "prd_authentication.md")
        assert parser.can_parse(tmp_path / "prd.md")

    def test_can_parse_tdd_filename(self, tmp_path):
        """Test parser recognizes TDD files by filename."""
        parser = DesignDocParser()

        assert parser.can_parse(tmp_path / "TDD-api.md")
        assert parser.can_parse(tmp_path / "tdd_design.md")
        assert parser.can_parse(tmp_path / "tdd.md")

    def test_can_parse_adr_filename(self, tmp_path):
        """Test parser recognizes ADR files by filename."""
        parser = DesignDocParser()

        assert parser.can_parse(tmp_path / "adr-001-database.md")
        assert parser.can_parse(tmp_path / "ADR-002.md")
        assert parser.can_parse(tmp_path / "adr_decision.md")

    def test_can_parse_spec_filename(self, tmp_path):
        """Test parser recognizes spec files by filename."""
        parser = DesignDocParser()

        assert parser.can_parse(tmp_path / "spec-api.md")
        assert parser.can_parse(tmp_path / "SPEC_v1.md")
        assert parser.can_parse(tmp_path / "spec.md")


class TestDocTypeDetection:
    """Test document type detection from content."""

    def test_detect_prd_from_content(self, tmp_path):
        """Test PRD detection from content patterns."""
        parser = DesignDocParser()

        # Create PRD file with generic filename
        prd_file = tmp_path / "requirements.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        assert result.success
        assert len(result.entities) > 0

        # Check document entity type
        doc_entity = result.entities[0]
        assert doc_entity.entity_type == EntityType.PRD
        assert "PRD" in doc_entity.name

    def test_detect_tdd_from_content(self, tmp_path):
        """Test TDD detection from content patterns."""
        parser = DesignDocParser()

        tdd_file = tmp_path / "design.md"
        tdd_file.write_text(TDD_CONTENT)

        result = parser.parse(tdd_file)

        assert result.success
        assert len(result.entities) > 0

        doc_entity = result.entities[0]
        assert doc_entity.entity_type == EntityType.TDD
        assert "TDD" in doc_entity.name

    def test_detect_adr_from_content(self, tmp_path):
        """Test ADR detection from content patterns."""
        parser = DesignDocParser()

        adr_file = tmp_path / "decision.md"
        adr_file.write_text(ADR_CONTENT)

        result = parser.parse(adr_file)

        assert result.success
        assert len(result.entities) > 0

        doc_entity = result.entities[0]
        assert doc_entity.entity_type == EntityType.ADR
        assert "ADR" in doc_entity.name

    def test_detect_spec_from_content(self, tmp_path):
        """Test SPEC detection from content patterns."""
        parser = DesignDocParser()

        spec_file = tmp_path / "api.md"
        spec_file.write_text(SPEC_CONTENT)

        result = parser.parse(spec_file)

        assert result.success
        assert len(result.entities) > 0

        doc_entity = result.entities[0]
        assert doc_entity.entity_type == EntityType.SPEC
        assert "SPEC" in doc_entity.name

    def test_regular_markdown_fallback(self, tmp_path):
        """Test that regular markdown files get minimal handling."""
        parser = DesignDocParser()

        md_file = tmp_path / "readme.md"
        md_file.write_text(REGULAR_MARKDOWN)

        result = parser.parse(md_file)

        # Should still succeed but with minimal entities
        assert result.success
        # Only file entity should be created for non-design docs
        assert len(result.entities) == 1
        assert result.entities[0].entity_type == EntityType.FILE


class TestSectionExtraction:
    """Test markdown section extraction."""

    def test_extract_sections_from_prd(self, tmp_path):
        """Test section extraction from PRD document."""
        parser = DesignDocParser()

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        # Should have document entity + section entities
        assert len(result.entities) > 1

        # Check for expected sections
        section_names = [e.name for e in result.entities if "Section:" in e.name]
        assert len(section_names) > 0

        # Check section observations
        for entity in result.entities:
            if "Section:" in entity.name:
                assert entity.entity_type == EntityType.DOCUMENTATION
                assert len(entity.observations) > 0

    def test_section_depth_limit(self, tmp_path):
        """Test that section extraction respects max depth."""
        parser = DesignDocParser({"max_section_depth": 2})

        content = """# Level 1
## Level 2
### Level 3 (should not be extracted as separate)
#### Level 4 (should not be extracted)
"""
        md_file = tmp_path / "TDD.md"
        md_file.write_text(content)

        result = parser.parse(md_file)

        # Count section entities
        section_entities = [e for e in result.entities if "Section:" in e.name]
        # Should only have level 1 and 2 sections
        assert len(section_entities) == 2


class TestRequirementExtraction:
    """Test requirement extraction from documents."""

    def test_extract_must_requirements(self, tmp_path):
        """Test extraction of MUST requirements."""
        parser = DesignDocParser()

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        # Find requirement entities
        req_entities = [
            e for e in result.entities if e.entity_type == EntityType.REQUIREMENT
        ]

        assert len(req_entities) > 0

        # Check requirement properties
        for req in req_entities:
            assert "REQ-" in req.name
            assert req.metadata.get("type") == "requirement"

    def test_extract_bracketed_requirements(self, tmp_path):
        """Test extraction of [REQ-XXX] style requirements."""
        parser = DesignDocParser()

        content = """# Specification

[REQ-001] The system must authenticate users
[REQ-002] Data must be encrypted
"""
        spec_file = tmp_path / "SPEC.md"
        spec_file.write_text(content)

        result = parser.parse(spec_file)

        req_entities = [
            e for e in result.entities if e.entity_type == EntityType.REQUIREMENT
        ]

        assert len(req_entities) >= 2

    def test_requirement_type_classification(self, tmp_path):
        """Test that requirements are classified by type."""
        parser = DesignDocParser()

        content = """# Requirements

- The system MUST do X
- The system SHOULD do Y
- The system MAY do Z
"""
        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(content)

        result = parser.parse(prd_file)

        req_entities = [
            e for e in result.entities if e.entity_type == EntityType.REQUIREMENT
        ]

        # Check requirement types in metadata
        req_types = [e.metadata.get("requirement_type") for e in req_entities]
        assert "mandatory" in req_types  # MUST
        assert "recommended" in req_types  # SHOULD
        assert "optional" in req_types  # MAY

    def test_disable_requirement_extraction(self, tmp_path):
        """Test that requirement extraction can be disabled."""
        parser = DesignDocParser({"extract_requirements": False})

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        # Should have no requirement entities
        req_entities = [
            e for e in result.entities if e.entity_type == EntityType.REQUIREMENT
        ]
        assert len(req_entities) == 0


class TestRelationCreation:
    """Test relation creation between entities."""

    def test_doc_contains_sections(self, tmp_path):
        """Test CONTAINS relations from doc to sections."""
        parser = DesignDocParser()

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        # Check for CONTAINS relations
        contains_relations = [
            r for r in result.relations if r.relation_type.value == "contains"
        ]

        assert len(contains_relations) > 0

        # Document should be the parent of sections
        doc_name = result.entities[0].name
        for relation in contains_relations:
            if "Section:" in relation.to_entity:
                assert relation.from_entity == doc_name

    def test_section_contains_requirements(self, tmp_path):
        """Test CONTAINS relations from sections to requirements."""
        parser = DesignDocParser()

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        # Find relations to requirements
        req_relations = [r for r in result.relations if "REQ-" in r.to_entity]

        # Requirements should have parent relations
        assert len(req_relations) > 0


class TestImplementationChunks:
    """Test implementation chunk creation."""

    def test_document_chunk_created(self, tmp_path):
        """Test that document implementation chunk is created."""
        parser = DesignDocParser()

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        assert result.implementation_chunks is not None
        assert len(result.implementation_chunks) > 0

        # Find document chunk
        doc_chunks = [
            c
            for c in result.implementation_chunks
            if c.metadata.get("doc_type") == "prd"
        ]
        assert len(doc_chunks) == 1

    def test_section_chunks_created(self, tmp_path):
        """Test that section implementation chunks are created."""
        parser = DesignDocParser()

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        # Find section chunks
        section_chunks = [
            c
            for c in result.implementation_chunks
            if c.metadata.get("entity_type") == "section"
        ]
        assert len(section_chunks) > 0

    def test_chunk_metadata(self, tmp_path):
        """Test that chunks have correct metadata."""
        parser = DesignDocParser()

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        for chunk in result.implementation_chunks:
            assert chunk.chunk_type == "implementation"
            assert "file_path" in chunk.metadata
            assert chunk.entity_name


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_file(self, tmp_path):
        """Test parsing empty file."""
        parser = DesignDocParser()

        empty_file = tmp_path / "PRD.md"
        empty_file.write_text("")

        result = parser.parse(empty_file)

        # Should not crash, may have minimal entities
        assert result is not None

    def test_file_with_only_title(self, tmp_path):
        """Test parsing file with only a title."""
        parser = DesignDocParser()

        content = "# Product Requirements Document"
        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(content)

        result = parser.parse(prd_file)

        assert result.success
        assert len(result.entities) >= 1

    def test_nonexistent_file(self, tmp_path):
        """Test parsing non-existent file."""
        parser = DesignDocParser()

        result = parser.parse(tmp_path / "nonexistent.md")

        # Should have error
        assert result.errors is not None
        assert len(result.errors) > 0

    def test_file_hash_calculation(self, tmp_path):
        """Test file hash is calculated."""
        parser = DesignDocParser()

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        assert result.file_hash
        assert len(result.file_hash) == 64  # SHA256 hex length

    def test_parsing_time_tracked(self, tmp_path):
        """Test that parsing time is tracked."""
        parser = DesignDocParser()

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        assert result.parsing_time >= 0


class TestEntityTypeIntegration:
    """Test integration with new entity types."""

    def test_all_design_doc_types_used(self, tmp_path):
        """Test that all design doc entity types can be created."""
        parser = DesignDocParser()

        # Create files for each type
        docs = {
            "PRD.md": PRD_CONTENT,
            "TDD.md": TDD_CONTENT,
            "ADR-001.md": ADR_CONTENT,
            "SPEC.md": SPEC_CONTENT,
        }

        expected_types = {
            EntityType.PRD,
            EntityType.TDD,
            EntityType.ADR,
            EntityType.SPEC,
        }

        found_types = set()

        for filename, content in docs.items():
            doc_file = tmp_path / filename
            doc_file.write_text(content)
            result = parser.parse(doc_file)

            if result.entities:
                found_types.add(result.entities[0].entity_type)

        assert expected_types == found_types

    def test_requirement_entity_type(self, tmp_path):
        """Test REQUIREMENT entity type is used."""
        parser = DesignDocParser()

        prd_file = tmp_path / "PRD.md"
        prd_file.write_text(PRD_CONTENT)

        result = parser.parse(prd_file)

        req_entities = [
            e for e in result.entities if e.entity_type == EntityType.REQUIREMENT
        ]

        assert len(req_entities) > 0
        for req in req_entities:
            assert req.entity_type == EntityType.REQUIREMENT
