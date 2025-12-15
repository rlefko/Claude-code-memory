# Claude Code Memory - System Architecture

> **Semantic code memory for Claude Code** - Instant recall across your entire codebase

This document provides a comprehensive overview of the Claude Code Memory system architecture, including component interactions, data flows, and key design decisions.

---

## High-Level Overview

```mermaid
graph TB
    subgraph "Claude Code IDE"
        CC[Claude Code]
        subgraph "Hooks System"
            SS[SessionStart]
            UP[UserPromptSubmit]
            PT[PreToolUse]
            PO[PostToolUse]
        end
    end

    subgraph "Memory System"
        MCP[MCP Server<br/>Node.js]
        IDX[Python Indexer<br/>claude-indexer]
        QD[(Qdrant DB<br/>Vector Store)]
    end

    CC <-->|MCP Protocol| MCP
    MCP <-->|Vector Ops| QD
    IDX -->|Index Vectors| QD

    CC --> SS
    CC --> UP
    CC --> PT
    CC --> PO

    PO -.->|Trigger| IDX
    PT -.->|Memory Guard| MCP

    style CC fill:#6366f1,stroke:#4f46e5,color:#fff
    style MCP fill:#10b981,stroke:#059669,color:#fff
    style IDX fill:#f59e0b,stroke:#d97706,color:#fff
    style QD fill:#3b82f6,stroke:#2563eb,color:#fff
```

### Component Summary

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Claude Code** | VS Code Extension | AI-powered coding assistant |
| **MCP Server** | Node.js/TypeScript | Memory retrieval and graph operations |
| **Python Indexer** | Python 3.12 | AST parsing, embedding generation, indexing |
| **Qdrant** | Vector Database | Semantic storage with hybrid search |
| **Hooks** | Bash/Python | Automation triggers for memory operations |

---

## Component Architecture

### 1. Python Indexer (`claude_indexer/`)

The indexer is responsible for parsing source code and generating semantic embeddings.

```mermaid
flowchart LR
    subgraph "File Discovery"
        A[Scan Project] --> B[Apply Filters]
        B --> C[.gitignore]
        B --> D[.claudeignore]
    end

    subgraph "AST Analysis"
        E[Tree-sitter Parse] --> F[Extract Entities]
        E --> G[Extract Relations]
        F --> H[Functions]
        F --> I[Classes]
        F --> J[Documentation]
    end

    subgraph "Embedding"
        K[Voyage AI] --> L[voyage-3-lite]
        L --> M[512-dim vectors]
    end

    subgraph "Storage"
        N[Qdrant Upsert]
        O[State Tracking]
    end

    C --> E
    D --> E
    H --> K
    I --> K
    J --> K
    G --> K
    M --> N
    N --> O

    style K fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style N fill:#3b82f6,stroke:#2563eb,color:#fff
```

#### Key Modules

| Module | File | Responsibility |
|--------|------|----------------|
| **CLI** | `cli_full.py` | Command-line interface with Click |
| **Indexer** | `indexer.py` | Core indexing logic and batch processing |
| **Parser** | `analysis/parser.py` | Tree-sitter AST parsing |
| **Language Parsers** | `analysis/*.py` | Python, JS, TS, JSON, YAML, etc. |
| **Embeddings** | `embeddings/voyage.py` | Voyage AI embedding generation |
| **Storage** | `storage/qdrant.py` | Qdrant vector operations |

#### Supported Languages

| Language | Parser | Features |
|----------|--------|----------|
| Python | Tree-sitter + Jedi | Functions, classes, decorators, docstrings |
| JavaScript/TypeScript | Tree-sitter | Functions, classes, exports, JSDoc |
| JSON | Native | Schema extraction, key-value pairs |
| YAML | Native | Configuration parsing |
| HTML | Tree-sitter | Tags, attributes, structure |
| CSS | Tree-sitter | Selectors, rules, variables |
| Markdown | Native | Headers, code blocks, links |

---

### 2. MCP Server (`mcp-qdrant-memory/`)

The MCP (Model Context Protocol) server provides memory retrieval capabilities to Claude Code.

```mermaid
flowchart TB
    subgraph "MCP Protocol Layer"
        T[Tool Handlers]
        V[Validation]
    end

    subgraph "Search Engine"
        S[Semantic Search<br/>Vector Similarity]
        K[Keyword Search<br/>BM25]
        RRF[RRF Fusion<br/>70% + 30%]
    end

    subgraph "Response Building"
        SR[Streaming Builder]
        TC[Token Counter]
        AR[Auto-Reduce]
    end

    subgraph "Persistence"
        QC[Qdrant Client]
        JF[JSON Fallback]
    end

    T --> V
    V --> S
    V --> K
    S --> RRF
    K --> RRF
    RRF --> SR
    SR --> TC
    TC --> AR
    AR --> QC
    QC -.-> JF

    style T fill:#10b981,stroke:#059669,color:#fff
    style RRF fill:#8b5cf6,stroke:#7c3aed,color:#fff
    style QC fill:#3b82f6,stroke:#2563eb,color:#fff
```

#### Available Tools

| Tool | Purpose | Key Parameters |
|------|---------|----------------|
| `search_similar` | Semantic + keyword search | `query`, `limit`, `entityTypes`, `searchMode` |
| `read_graph` | Entity relationship exploration | `entity`, `mode` (smart/entities/relationships/raw) |
| `get_implementation` | Retrieve code with context | `name`, `scope` (exact/logical/dependencies) |
| `create_entities` | Add new knowledge | `entities[]` with name, type, observations |
| `add_observations` | Update existing entities | `observations[]` with entityName, contents |
| `delete_entities` | Remove entities | `entityNames[]` |
| `create_relations` | Link entities | `relations[]` with from, to, type |
| `delete_relations` | Remove links | `relations[]` |

#### Search Modes

```mermaid
flowchart LR
    Q[Query] --> M{Mode?}

    M -->|semantic| SEM[Vector Search<br/>Concept matching]
    M -->|keyword| KW[BM25 Search<br/>Exact terms]
    M -->|hybrid| HYB[Both + RRF<br/>Best of both]

    SEM --> R1[Results 0.6-0.8]
    KW --> R2[Results 1.5+]
    HYB --> R3[Results 0.4-1.2]

    style HYB fill:#10b981,stroke:#059669,color:#fff
```

---

### 3. Claude Code Hooks

Hooks automate memory operations at key points in the development workflow.

```mermaid
sequenceDiagram
    participant U as User
    participant CC as Claude Code
    participant SS as SessionStart
    participant UP as UserPromptSubmit
    participant PT as PreToolUse
    participant PO as PostToolUse
    participant MCP as MCP Server
    participant IDX as Indexer

    U->>CC: Start Session
    CC->>SS: Trigger
    SS-->>CC: Git context + Memory reminder

    U->>CC: Submit Prompt
    CC->>UP: Analyze Prompt
    UP-->>CC: Tool suggestions based on intent

    CC->>PT: Write/Edit Tool
    PT->>PT: Memory Guard (27 checks)
    PT-->>CC: Allow/Warn/Block

    CC->>CC: Execute Tool

    CC->>PO: Tool Complete
    PO->>IDX: Index changed file
    IDX-->>PO: Updated

    Note over SS,PO: All hooks have <300ms latency target
```

#### Hook Details

| Hook | File | Trigger | Performance |
|------|------|---------|-------------|
| **SessionStart** | `session_start.py` | Session begins | <100ms |
| **UserPromptSubmit** | `prompt_handler.py` | Before Claude processes | <50ms |
| **PreToolUse** | `pre-tool-guard.sh` | Before Write/Edit/Bash | <300ms |
| **PostToolUse** | `post-file-change.sh` | After Write/Edit | ~100ms/file |

---

### 4. Memory Guard System

Memory Guard enforces code quality through pattern-based checks.

```mermaid
flowchart TD
    A[Code Change] --> B{Operation Type}

    B -->|Write/Edit| C{FAST Mode}
    B -->|git commit| D[FULL Mode]

    C --> E[Tier 0: Skip Trivial<br/>5ms]
    E --> F[Tier 1: Pattern Checks<br/>27 rules, 50ms]
    F --> G[Tier 2: Semantic Analysis<br/>150ms]

    D --> H[Full Analysis<br/>5-30s]

    G --> I{Severity?}
    H --> I

    I -->|CRITICAL| J[Block Operation]
    I -->|HIGH/MEDIUM| K[Warn & Allow]
    I -->|LOW/None| L[Allow]

    style J fill:#ef4444,stroke:#dc2626,color:#fff
    style K fill:#f59e0b,stroke:#d97706,color:#fff
    style L fill:#10b981,stroke:#059669,color:#fff
```

#### Check Categories (27 Total)

| Category | Count | Examples |
|----------|-------|----------|
| **Security** | 11 | SQL injection, XSS, secrets, crypto |
| **Tech Debt** | 9 | TODO, FIXME, debug statements, bare except |
| **Documentation** | 2 | Missing docstrings, JSDoc |
| **Resilience** | 2 | Swallowed exceptions, HTTP timeouts |
| **Git Safety** | 3 | Force push, hard reset, destructive rm |

---

## Data Flow

### Indexing Pipeline

```mermaid
sequenceDiagram
    participant FS as File System
    participant IDX as Indexer
    participant TS as Tree-sitter
    participant VOY as Voyage AI
    participant QD as Qdrant

    FS->>IDX: File changed
    IDX->>IDX: Check .gitignore/.claudeignore
    IDX->>TS: Parse AST
    TS-->>IDX: Entities + Relations

    loop Batch Processing
        IDX->>VOY: Embed batch (100 entities)
        VOY-->>IDX: 512-dim vectors
    end

    IDX->>QD: Upsert vectors
    QD-->>IDX: Confirm
    IDX->>IDX: Update state file
```

### Query Pipeline

```mermaid
sequenceDiagram
    participant CC as Claude Code
    participant MCP as MCP Server
    participant BM25 as BM25 Index
    participant QD as Qdrant

    CC->>MCP: search_similar("auth pattern")

    par Parallel Search
        MCP->>QD: Vector search
        MCP->>BM25: Keyword search
    end

    QD-->>MCP: Semantic results
    BM25-->>MCP: Keyword results

    MCP->>MCP: RRF Fusion (70/30)
    MCP->>MCP: Build streaming response
    MCP->>MCP: Check token budget (25k)

    MCP-->>CC: Ranked results
```

---

## Search Architecture

### Hybrid Search with RRF Fusion

```mermaid
flowchart LR
    subgraph "Input"
        Q[Query: 'validate user token']
    end

    subgraph "Semantic Path"
        SE[Embed Query]
        SV[Vector Search]
        SR[Conceptual Matches<br/>validate, auth, verify]
    end

    subgraph "Keyword Path"
        KT[Tokenize]
        KB[BM25 Rank]
        KR[Exact Matches<br/>'validate', 'user', 'token']
    end

    subgraph "Fusion"
        RRF[RRF Algorithm<br/>1/(k+rank)]
        W[Weighted Combine<br/>70% semantic<br/>30% keyword]
    end

    subgraph "Output"
        R[Ranked Results]
    end

    Q --> SE --> SV --> SR --> RRF
    Q --> KT --> KB --> KR --> RRF
    RRF --> W --> R

    style RRF fill:#8b5cf6,stroke:#7c3aed,color:#fff
```

### Entity Types

| Type | Description | Use Case |
|------|-------------|----------|
| `function` | Functions and methods | Implementation lookup |
| `class` | Classes and components | Architecture exploration |
| `file` | File-level metadata | Quick overview |
| `documentation` | Code documentation | Understanding context |
| `relation` | Entity connections | Dependency analysis |
| `metadata` | Fast entity overview | Quick search |
| `implementation` | Detailed code chunks | Deep dive |
| `*_pattern` | Learned patterns | Best practices |

---

## Progressive Disclosure Architecture

The system uses a two-tier approach for optimal performance:

```mermaid
flowchart TD
    subgraph "Tier 1: Metadata (Default)"
        M1[Entity Name]
        M2[Type & Location]
        M3[Signature/Interface]
        M4[Key Observations]
    end

    subgraph "Tier 2: Implementation (On-Demand)"
        I1[Full Source Code]
        I2[Helper Functions]
        I3[Dependencies]
        I4[Related Entities]
    end

    Q[Query] --> T1{Need Details?}
    T1 -->|No| M1
    T1 -->|Yes| I1

    M1 --> R1[Fast Response<br/>3-5ms]
    I1 --> R2[Complete Response<br/>50-100ms]

    style M1 fill:#10b981,stroke:#059669,color:#fff
    style I1 fill:#3b82f6,stroke:#2563eb,color:#fff
```

---

## Multi-Project Support

Each project maintains isolated memory with unique collection names:

```mermaid
flowchart TB
    subgraph "Project A"
        PA[project-a-memory]
        QA[(Collection: project-a)]
    end

    subgraph "Project B"
        PB[project-b-memory]
        QB[(Collection: project-b)]
    end

    subgraph "Project C"
        PC[project-c-memory]
        QC[(Collection: project-c)]
    end

    MCP[Shared MCP Server]

    PA --> MCP
    PB --> MCP
    PC --> MCP

    MCP --> QA
    MCP --> QB
    MCP --> QC

    style MCP fill:#10b981,stroke:#059669,color:#fff
```

### Collection Naming

- Format: `{project-name}-sanitized`
- Characters: lowercase, hyphens only
- Example: `my-awesome-project` → `my-awesome-project`

---

## Performance Characteristics

### Latency Targets

| Operation | Target | Actual |
|-----------|--------|--------|
| Metadata search | <10ms | 3-5ms |
| Full entity search | <100ms | 50-80ms |
| Single file index | <500ms | 100-300ms |
| Batch index (100 files) | <30s | 10-20s |
| Memory Guard (FAST) | <300ms | 150-250ms |

### Scaling

| Metric | Capacity |
|--------|----------|
| Vectors per collection | 100,000+ |
| Files per project | 10,000+ |
| Concurrent searches | 100+ |
| Embedding batch size | 100 entities |

---

## Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| `.mcp.json` | Project root | MCP server configuration |
| `settings.local.json` | `.claude/` | Hook configuration |
| `.claudeignore` | Project root | Indexing exclusions |
| `settings.txt` | Memory project | API keys and settings |

---

## Technology Stack

### Core Technologies

| Layer | Technology | Version |
|-------|------------|---------|
| **Runtime** | Python | 3.12+ |
| **Runtime** | Node.js | 18+ |
| **Vector DB** | Qdrant | 1.7+ |
| **Embeddings** | Voyage AI | voyage-3-lite |
| **AST Parsing** | Tree-sitter | Latest |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `qdrant-client` | Vector database client |
| `voyageai` | Embedding generation |
| `tree-sitter` | AST parsing |
| `click` | CLI framework |
| `@modelcontextprotocol/sdk` | MCP server framework |

---

## Further Reading

- [CLI Reference](docs/CLI_REFERENCE.md) - Complete command documentation
- [Memory Guard](docs/MEMORY_GUARD.md) - Quality check details
- [Hooks System](docs/HOOKS.md) - Hook configuration guide
- [MCP Server](mcp-qdrant-memory/README.md) - Server implementation details
