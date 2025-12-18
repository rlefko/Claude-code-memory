"""Unit tests for watcher handler, specifically ignore functionality."""

import tempfile
from pathlib import Path

import pytest


class TestIndexingEventHandlerIgnore:
    """Test that IndexingEventHandler properly ignores files."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_watcher_ignores_index_cache_via_hierarchical_manager(self, temp_project):
        """Test that watcher ignores .index_cache/ via HierarchicalIgnoreManager."""
        from claude_indexer.watcher.handler import IndexingEventHandler

        handler = IndexingEventHandler(
            project_path=str(temp_project),
            collection_name="test",
        )

        # Create the cache directory and file
        cache_dir = temp_project / ".index_cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "state.json"
        cache_file.write_text("{}")

        # Should be ignored via HierarchicalIgnoreManager
        assert handler._should_process_file(cache_file) is False

    def test_watcher_ignores_embedding_cache_via_hierarchical_manager(
        self, temp_project
    ):
        """Test that watcher ignores .embedding_cache/ via HierarchicalIgnoreManager."""
        from claude_indexer.watcher.handler import IndexingEventHandler

        handler = IndexingEventHandler(
            project_path=str(temp_project),
            collection_name="test",
        )

        # Create the cache directory and file
        cache_dir = temp_project / ".embedding_cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "vectors.txt"
        cache_file.write_text("test")

        # Should be ignored via HierarchicalIgnoreManager
        assert handler._should_process_file(cache_file) is False

    def test_watcher_ignores_nested_cache_paths(self, temp_project):
        """Test watcher ignores deeply nested .index_cache paths."""
        from claude_indexer.watcher.handler import IndexingEventHandler

        handler = IndexingEventHandler(
            project_path=str(temp_project),
            collection_name="test",
        )

        # Create nested cache directory structure
        nested_cache = temp_project / ".index_cache" / ".embedding_cache" / "voyage"
        nested_cache.mkdir(parents=True)
        nested_file = nested_cache / "index.json"
        nested_file.write_text("{}")

        # Should be ignored
        assert handler._should_process_file(nested_file) is False

    def test_watcher_ignores_gitignored_files(self, temp_project):
        """Test that watcher respects .gitignore patterns."""
        from claude_indexer.watcher.handler import IndexingEventHandler

        # Create .gitignore
        gitignore = temp_project / ".gitignore"
        gitignore.write_text("secret.env\ncustom_ignore/\n")

        handler = IndexingEventHandler(
            project_path=str(temp_project),
            collection_name="test",
        )

        # Create files that should be ignored
        secret_file = temp_project / "secret.env"
        secret_file.write_text("SECRET=abc123")

        custom_dir = temp_project / "custom_ignore"
        custom_dir.mkdir()
        custom_file = custom_dir / "data.txt"
        custom_file.write_text("data")

        # Should be ignored via HierarchicalIgnoreManager
        assert handler._should_process_file(secret_file) is False
        assert handler._should_process_file(custom_file) is False

    def test_watcher_allows_normal_files(self, temp_project):
        """Test that watcher allows normal Python files."""
        from claude_indexer.watcher.handler import IndexingEventHandler

        handler = IndexingEventHandler(
            project_path=str(temp_project),
            collection_name="test",
        )

        # Create a normal Python file
        py_file = temp_project / "main.py"
        py_file.write_text("def main(): pass")

        # Should NOT be ignored (matches *.py watch pattern)
        assert handler._should_process_file(py_file) is True

    def test_watcher_ignores_universal_excludes(self, temp_project):
        """Test that watcher ignores files from UNIVERSAL_EXCLUDES."""
        from claude_indexer.watcher.handler import IndexingEventHandler

        handler = IndexingEventHandler(
            project_path=str(temp_project),
            collection_name="test",
        )

        # Create various files that should be universally excluded
        git_dir = temp_project / ".git"
        git_dir.mkdir()
        git_config = git_dir / "config"
        git_config.write_text("[core]")

        pycache_dir = temp_project / "__pycache__"
        pycache_dir.mkdir()
        pyc_file = pycache_dir / "module.pyc"
        pyc_file.write_bytes(b"pyc content")

        node_modules = temp_project / "node_modules"
        node_modules.mkdir()
        node_file = node_modules / "package.json"
        node_file.write_text("{}")

        # All should be ignored
        assert handler._should_process_file(git_config) is False
        assert handler._should_process_file(pyc_file) is False
        assert handler._should_process_file(node_file) is False

    def test_hierarchical_ignore_manager_initialized(self, temp_project):
        """Test that HierarchicalIgnoreManager is properly initialized."""
        from claude_indexer.watcher.handler import IndexingEventHandler

        handler = IndexingEventHandler(
            project_path=str(temp_project),
            collection_name="test",
        )

        # Should have an ignore manager
        assert handler._ignore_manager is not None

    def test_watcher_handles_missing_ignore_manager_gracefully(self, temp_project):
        """Test that watcher still works if HierarchicalIgnoreManager fails."""
        from claude_indexer.watcher.handler import IndexingEventHandler

        handler = IndexingEventHandler(
            project_path=str(temp_project),
            collection_name="test",
        )

        # Manually set ignore_manager to None to simulate failure
        handler._ignore_manager = None

        # Create a cache file
        cache_dir = temp_project / ".index_cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "state.json"
        cache_file.write_text("{}")

        # Should still be ignored via fallback ignore_patterns
        # (json files are not in watch_patterns by default, so it should be False)
        assert handler._should_process_file(cache_file) is False
