# .claudeignore Reference

## Overview

`.claudeignore` controls which files are excluded from semantic indexing into Claude Code memory. It works exactly like `.gitignore` but specifically for the indexing process.

## Why Use .claudeignore?

- **Secrets Protection**: Ensure API keys, credentials, and sensitive data are never indexed
- **Performance**: Skip large binary files, datasets, and ML models
- **Relevance**: Exclude personal notes, debug artifacts, and temporary files
- **Privacy**: Keep personal development files out of the knowledge graph

## File Locations

### Hierarchical Loading

The system loads patterns from multiple sources with the following precedence:

1. **Universal Defaults** (always applied)
   - Core system directories (`.git/`, `node_modules/`, `__pycache__/`)
   - Binary files and archives
   - Package lock files
   - OS artifacts

2. **Global .claudeignore** (`~/.claude-indexer/.claudeignore`)
   - User-wide patterns applied to all projects
   - Good for patterns you always want ignored

3. **Project .claudeignore** (`.claudeignore` in project root)
   - Project-specific patterns
   - Can negate global patterns with `!`

## Syntax Reference

The syntax is identical to `.gitignore`:

### Basic Patterns

```gitignore
# Comments start with #
*.log           # Ignore all .log files
debug/          # Ignore debug directory
/config.json    # Ignore config.json in root only
```

### Wildcards

| Pattern | Meaning |
|---------|---------|
| `*` | Matches any string except `/` |
| `**` | Matches any string including `/` |
| `?` | Matches any single character |

### Examples

```gitignore
# Match all Python cache files
*.pyc
__pycache__/

# Match all .env files except examples
.env
.env.*
!.env.example
!.env.template

# Match nested files
**/secrets/**
**/*.key

# Root-relative pattern (only matches at project root)
/dist/
/build/
```

### Negation

Use `!` to include files that would otherwise be ignored:

```gitignore
# Ignore all log files
*.log

# But keep important.log
!important.log

# Ignore all env files
.env.*

# But keep example files
!.env.example
!.env.template
```

## CLI Commands

### Initialize .claudeignore

```bash
# Create project .claudeignore from template
claude-indexer ignore init

# Create global .claudeignore
claude-indexer ignore init --global

# Overwrite existing file
claude-indexer ignore init --force
```

### Add Patterns

```bash
# Add to project .claudeignore
claude-indexer ignore add "*.log"

# Add to global .claudeignore
claude-indexer ignore add --global ".env"
```

### List Patterns

```bash
# List project patterns
claude-indexer ignore list

# List global patterns
claude-indexer ignore list --global

# List all patterns (universal + global + project)
claude-indexer ignore list --all

# Show all patterns verbosely
claude-indexer ignore list --all -v
```

### Test Paths

```bash
# Check if a path would be ignored
claude-indexer ignore test src/secret.key
# Output: IGNORED: src/secret.key
#         Reason: Matched pattern '*.key' from project

claude-indexer ignore test src/main.py
# Output: INCLUDED: src/main.py
#         (Does not match any ignore patterns)
```

## Common Patterns by Project Type

### Python Projects

```gitignore
# Virtual environments
.venv/
venv/
env/
.env

# Cache
__pycache__/
*.pyc
*.pyo
.mypy_cache/
.pytest_cache/

# Coverage
.coverage
htmlcov/
coverage.xml
```

### JavaScript/TypeScript Projects

```gitignore
# Dependencies
node_modules/

# Build output
dist/
build/
.next/

# Lock files (already in universal defaults)
# package-lock.json
# yarn.lock
```

### AI/ML Projects

```gitignore
# Model files
*.h5
*.pkl
*.pt
*.pth
*.safetensors
*.onnx

# Datasets
*.csv
*.parquet
data/raw/
data/processed/

# Training outputs
checkpoints/
runs/
wandb/
```

## Secrets Protection Patterns

**Critical**: Always include these patterns to prevent indexing of sensitive data:

```gitignore
# Environment files
.env
.env.*
!.env.example
!.env.template

# Credentials
**/credentials.json
**/secrets.json
**/serviceAccountKey.json
**/*.pem
**/*.key
**/*.p12

# Cloud credentials
**/.aws/credentials
**/.gcloud/
**/google-cloud-credentials*.json

# SSH keys
**/.ssh/
**/id_rsa*
**/id_ed25519*
```

## Integration with Indexer

The `.claudeignore` system integrates automatically with the indexer:

```bash
# Index a project (claudeignore is respected automatically)
claude-indexer index -p /path/to/project -c collection-name

# View which files would be indexed
claude-indexer index -p /path/to/project -c collection-name --dry-run
```

## MCP Server Filtering

When `PROJECT_PATH` environment variable is set, the MCP server will also filter search results against `.claudeignore` patterns:

```json
{
  "mcpServers": {
    "memory": {
      "command": "node",
      "args": ["/path/to/mcp-qdrant-memory/dist/index.js"],
      "env": {
        "PROJECT_PATH": "/path/to/project",
        "QDRANT_URL": "http://localhost:6333",
        "QDRANT_COLLECTION_NAME": "my-project"
      }
    }
  }
}
```

## Troubleshooting

### File is still being indexed

1. Check if the pattern is correct:
   ```bash
   claude-indexer ignore test path/to/file
   ```

2. Verify the pattern is loaded:
   ```bash
   claude-indexer ignore list --all -v
   ```

3. Make sure the `.claudeignore` file is in the project root

### Negation not working

Negation only works for patterns in the same file or earlier sources. Make sure:
1. The negation pattern comes AFTER the pattern it negates
2. The negation pattern exactly matches the file path

### Universal defaults ignoring too much

If universal defaults are ignoring files you need, create a project `.claudeignore` with negation:

```gitignore
# Include specific lock file for analysis
!package-lock.json
```

## Default Template

Run `claude-indexer ignore init` to create a `.claudeignore` with these sections:

- **Secrets and Credentials** - .env files, API keys, certificates
- **AI/ML Artifacts** - Model files, datasets, embeddings
- **Personal Development** - Notes, scratch files
- **Test Artifacts** - Coverage reports, test outputs
- **Debug and Profiling** - Debug logs, profiling data
- **Temporary Files** - tmp/, temp/, backup files

## See Also

- [CLI Reference](CLI_REFERENCE.md) - Complete CLI command documentation
- [Configuration Guide](CONFIGURATION.md) - Project configuration options
- [Memory Guard](MEMORY_GUARD.md) - Quality enforcement rules
