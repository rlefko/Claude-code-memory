# Plan Mode Integration - Implementation Milestones

## Implementation Milestones

> **Version**: 1.0
> **Based On**: PRD.md and TDD.md (Plan Mode Integration)
> **Target**: Deepen Plan Mode integration with quality guardrails and rich context
> **Prerequisites**: Phases 0-6 complete (v2.9.20+)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Phase 7: Foundation - Plan Mode Detection & Hook Infrastructure](#phase-7-foundation---plan-mode-detection--hook-infrastructure)
3. [Phase 8: MCP Context Integration](#phase-8-mcp-context-integration)
4. [Phase 9: Quality Guardrails Framework](#phase-9-quality-guardrails-framework)
5. [Phase 10: Auto-Revision System](#phase-10-auto-revision-system)
6. [Phase 11: Prompt Augmentation & Exploration Hints](#phase-11-prompt-augmentation--exploration-hints)
7. [Phase 12: Plan QA Verification](#phase-12-plan-qa-verification)
8. [Phase 13: Polish, Testing & Documentation](#phase-13-polish-testing--documentation)
9. [Appendix: Rule Specifications](#appendix-plan-guardrail-rule-specifications)

---

## Executive Summary

### Vision
Enhance Claude Code's Plan Mode to produce implementation plans that are thorough, context-aware, and aligned with project best practices. The system proactively catches architectural/design issues during planning and ensures plans include necessary tasks (testing, documentation) while avoiding redundant or ill-advised changes.

### Key Design Decisions
1. **Hook into Claude Code's Plan Mode** - Use hooks/MCP to enhance native Plan Mode behavior
2. **Auto-revise plans** - Automatically add missing tasks before showing to user
3. **Full MCP context** - Code index, design docs, and issue tracking (Linear, GitHub)
4. **Hybrid parallelism** - Inject prompts that guide Claude Code's sub-agent exploration

### Current State (Prerequisites Complete)
| Component | Status | Notes |
|-----------|--------|-------|
| CLI Infrastructure | v2.9.20 | Full claude-indexer with hooks |
| MCP Server | Complete | 8+ tools, streaming responses |
| Hook Framework | Complete | SessionStart, UserPromptSubmit, PreToolUse, PostToolUse |
| Memory Guard v4.3 | Complete | 27 pattern checks |
| UI Consistency | Complete | 15+ rules, 3-tier architecture |

### Success Metrics (from PRD)
- **Plan Completeness**: >90% of plans include test/doc tasks when appropriate
- **Duplicate Detection**: Existing code reuse suggested in >80% of applicable cases
- **Plan Approval Rate**: <10% of plans require user revision before approval
- **User Confidence**: Reviewers have minimal additional pointers to add
- **Performance**: <100ms overhead for plan augmentation

---

## Phase 7: Foundation - Plan Mode Detection & Hook Infrastructure

**Goal**: Establish the infrastructure for detecting Plan Mode activation and intercepting plan generation.

### Milestone 7.1: Plan Mode Detection

**Objective**: Reliably detect when Claude Code enters Plan Mode.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 7.1.1 | Create `hooks/plan_mode_detector.py` with pattern detection | HIGH | DONE |
| 7.1.2 | Implement explicit marker detection (`@agent-plan`, `@plan`) | HIGH | DONE |
| 7.1.3 | Add planning keyword detection (confidence scoring) | MEDIUM | DONE |
| 7.1.4 | Implement environment variable detection (CLAUDE_PLAN_MODE) | MEDIUM | DONE |
| 7.1.5 | Create session state tracking for Plan Mode persistence | MEDIUM | DONE |
| 7.1.6 | Add unit tests for detection accuracy (>95% target) | HIGH | DONE |

**Detection Patterns**:
```python
# Explicit markers (1.0 confidence)
EXPLICIT_PATTERNS = r'@agent-plan|@plan\b|--plan\b|plan\s*mode'

# Planning keywords (0.7 confidence)
PLANNING_KEYWORDS = r'\b(create|make|write|design|implement)\s+(a\s+)?plan\b'
```

**Testing Requirements**:
- [x] Unit tests for each detection method
- [x] Test with real Claude Code Plan Mode sessions
- [x] Verify <10ms detection latency

**Success Criteria**:
- [x] >95% detection accuracy for Plan Mode (achieved: 100% on 30-case benchmark)
- [x] <10ms detection latency (achieved: <1ms average)
- [x] Zero false positives on non-plan prompts

---

### Milestone 7.2: Hook Infrastructure Extension

**Objective**: Extend existing hook system to support Plan Mode interception.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 7.2.1 | Extend `UserPromptSubmit` hook for Plan Mode detection | HIGH | DONE |
| 7.2.2 | Create plan context injection mechanism | HIGH | DONE |
| 7.2.3 | Implement hook chaining for plan augmentation | MEDIUM | DONE |
| 7.2.4 | Add Plan Mode state to SessionContext | MEDIUM | DONE |
| 7.2.5 | Create `PlanModeContext` dataclass for state tracking | MEDIUM | DONE |
| 7.2.6 | Update `.claude/settings.json` template for Plan hooks | LOW | DONE |

**Implementation Details** (Milestone 7.2 Complete):
- Created `claude_indexer/hooks/planning/` package with:
  - `guidelines.py` - PlanningGuidelinesGenerator (<20ms)
  - `exploration.py` - ExplorationHintsGenerator (<30ms)
  - `injector.py` - PlanContextInjector (<50ms total)
- Modified `hooks/prompt_handler.py` to inject guidelines and hints
- Configuration via `CLAUDE_PLAN_MODE_CONFIG` env var or `CLAUDE_PLAN_MODE_COMPACT`

**Hook Flow**:
```
UserPromptSubmit Hook
       |
       +---> Plan Mode Detection
       |        |
       |        +---> (Yes) -> Inject Planning Guidelines
       |        |               |
       |        |               +---> Generate Exploration Hints
       |        |               |
       |        |               +---> Enable Plan QA Verification
       |        |
       |        +---> (No) -> Pass through unchanged
       |
       +---> Continue to Claude
```

**Testing Requirements**:
- [x] Test hook invocation order
- [x] Test state persistence across turns
- [x] Verify non-blocking behavior

**Documentation**:
- [x] Update HOOKS.md with Plan Mode hooks
- [x] Add configuration examples

**Success Criteria**:
- [x] Hooks execute in correct order
- [x] State persists correctly (via SessionContext.plan_mode)
- [x] <20ms hook overhead (guidelines <20ms, hints <30ms, total <50ms)

---

## Phase 8: MCP Context Integration

**Goal**: Enable Plan Mode to query rich context via MCP - code index, design docs, and issue trackers.

### Milestone 8.1: Design Document Indexing

**Objective**: Index and search design documents (PRD, TDD, ADR, specs).

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 8.1.1 | Create new EntityTypes: SPEC, PRD, TDD, ADR, REQUIREMENT | HIGH | DONE |
| 8.1.2 | Implement `DesignDocParser` in `claude_indexer/analysis/` | HIGH | DONE |
| 8.1.3 | Add document type detection (patterns in filename/content) | HIGH | DONE |
| 8.1.4 | Implement section extraction from markdown | MEDIUM | DONE |
| 8.1.5 | Extract individual requirements as separate entities | MEDIUM | DONE |
| 8.1.6 | Create relations between docs and code components | MEDIUM | DONE |
| 8.1.7 | Add design doc paths to configuration | LOW | DONE |

**Entity Types**:
```python
class EntityType(Enum):
    # Existing types...
    SPEC = "spec"                    # Design specifications
    PRD = "prd"                      # Product requirements documents
    TDD = "tdd"                      # Technical design documents
    ADR = "adr"                      # Architecture decision records
    REQUIREMENT = "requirement"      # Individual requirements from specs
```

**DesignDocParser**:
```python
class DesignDocParser(CodeParser):
    """Parser for design documents (PRD, TDD, ADR, specs)."""

    DOC_TYPE_PATTERNS = {
        "prd": [r"product\s+requirements?\s+document", r"^prd"],
        "tdd": [r"technical\s+design\s+document", r"^tdd"],
        "adr": [r"architecture\s+decision\s+record", r"^adr"],
        "spec": [r"specification", r"^spec"],
    }

    def parse(self, file_path: Path) -> ParserResult:
        # Extract sections, requirements, decisions
        ...
```

**Configuration** (in unified_config.py):
```python
class DesignDocsConfig(BaseModel):
    enabled: bool = True
    paths: list[str] = ["docs/", "specs/", "design/", "*.md"]
    doc_patterns: dict[str, str] = {
        "prd": "**/PRD*.md",
        "tdd": "**/TDD*.md",
        "adr": "**/adr/*.md",
    }
```

**Testing Requirements**:
- [x] Test document type detection with various formats
- [x] Test section extraction from real PRD/TDD files
- [x] Test requirement entity creation
- [x] Verify relations to code components

**Success Criteria**:
- [x] Auto-detect document type with >90% accuracy
- [x] Extract sections and requirements correctly
- [x] Create searchable entities for all design docs

**Implementation Details** (Milestone 8.1 Complete):
- Created `claude_indexer/analysis/design_doc_parser.py` with DesignDocParser
- Added 5 new EntityTypes: SPEC, PRD, TDD, ADR, REQUIREMENT
- Added DesignDocsConfig to `claude_indexer/config/unified_config.py`
- Document type detection via filename patterns and content patterns
- Section extraction respects configurable max_section_depth
- Requirement extraction supports RFC 2119 (MUST/SHALL/SHOULD/MAY), [REQ-XXX], and numbered lists
- Relations created between documents, sections, and requirements
- Tests: 30 unit tests covering all functionality

---

### Milestone 8.2: New MCP Tools for Documents

**Objective**: Add MCP tools for searching and retrieving design documents.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 8.2.1 | Add `search_docs` tool to MCP server | HIGH | DONE |
| 8.2.2 | Add `get_doc` tool for full document retrieval | HIGH | DONE |
| 8.2.3 | Implement docTypes filtering (prd, tdd, adr, spec) | MEDIUM | DONE |
| 8.2.4 | Add section-specific retrieval | LOW | DONE |
| 8.2.5 | Create TypeScript interfaces for doc tools | MEDIUM | DONE |
| 8.2.6 | Add validation for doc tool inputs | MEDIUM | DONE |

**MCP Tool: search_docs**:
```typescript
{
  name: "search_docs",
  description: "Search design documents, specifications, PRDs, and ADRs",
  inputSchema: {
    type: "object",
    properties: {
      query: { type: "string", description: "Search query" },
      docTypes: {
        type: "array",
        items: { type: "string" },
        description: "Filter: prd, tdd, spec, adr"
      },
      limit: { type: "number", default: 10 }
    },
    required: ["query"]
  }
}
```

**MCP Tool: get_doc**:
```typescript
{
  name: "get_doc",
  description: "Retrieve full content of a specific design document",
  inputSchema: {
    type: "object",
    properties: {
      docId: { type: "string", description: "Document ID or file path" },
      section: { type: "string", description: "Optional: specific section" }
    },
    required: ["docId"]
  }
}
```

**Testing Requirements**:
- [x] Test search with various queries
- [x] Test filtering by document type
- [x] Test full document retrieval
- [x] Benchmark search latency (<50ms)

**Success Criteria**:
- [x] Both tools implemented and tested
- [x] Filter by document type works correctly
- [x] <50ms search latency

**Implementation Details** (Milestone 8.2 Complete):
- Created `DocSearchResult` and `DocContent` interfaces in `mcp-qdrant-memory/src/types.ts`
- Added `SearchDocsRequest` and `GetDocRequest` interfaces in `validation.ts`
- Implemented `validateSearchDocsRequest` and `validateGetDocRequest` validators
- Added `searchDocs()` and `getDoc()` methods to `QdrantPersistence` class
- Added `search_docs` and `get_doc` tool definitions to MCP server
- Supports docTypes filtering: prd, tdd, adr, spec
- Section-specific retrieval via `section` parameter
- Multi-project support via `collection` parameter
- Returns sections sorted by line number, requirements with type classification

---

### Milestone 8.3: Issue Tracker Integration

**Objective**: Enable querying tickets from Linear and GitHub Issues.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 8.3.1 | Create `claude_indexer/integrations/` package | HIGH | DONE |
| 8.3.2 | Implement `LinearClient` with GraphQL queries | HIGH | DONE |
| 8.3.3 | Implement `GitHubIssuesClient` with REST API | HIGH | DONE |
| 8.3.4 | Create `TicketEntity` data model | HIGH | DONE |
| 8.3.5 | Add `search_tickets` MCP tool | HIGH | DONE |
| 8.3.6 | Add `get_ticket` MCP tool with comments/PRs | HIGH | DONE |
| 8.3.7 | Implement authentication configuration | MEDIUM | DONE |
| 8.3.8 | Add rate limiting and caching | MEDIUM | DONE |
| 8.3.9 | Create ticket sync service (background) | LOW | DEFERRED |

**TicketEntity Data Model**:
```python
@dataclass
class TicketEntity:
    id: str                           # e.g., "AVO-123", "github#456"
    source: str                       # "linear", "github"
    title: str
    description: str
    status: str                       # "open", "in_progress", "done"
    assignee: str | None
    labels: list[str]
    priority: str | None
    acceptance_criteria: list[str]    # Extracted requirements
    linked_prs: list[str]             # PR references

    def to_entity(self) -> Entity:
        """Convert to standard Entity for indexing."""
        ...
```

**LinearClient**:
```python
class LinearClient:
    BASE_URL = "https://api.linear.app/graphql"

    async def search_issues(
        self,
        query: str,
        status: list[str] | None = None,
        labels: list[str] | None = None,
        limit: int = 20
    ) -> list[TicketEntity]:
        ...

    async def get_issue(self, identifier: str) -> TicketEntity:
        ...
```

**MCP Tool: search_tickets**:
```typescript
{
  name: "search_tickets",
  description: "Search issue tracker for relevant tickets (Linear, GitHub)",
  inputSchema: {
    type: "object",
    properties: {
      query: { type: "string" },
      status: { type: "array", items: { type: "string" } },
      labels: { type: "array", items: { type: "string" } },
      source: { type: "string", enum: ["linear", "github", "all"] }
    },
    required: ["query"]
  }
}
```

**Configuration**:
```python
class LinearConfig(BaseModel):
    enabled: bool = False
    api_key: str = ""  # From LINEAR_API_KEY env var
    team_id: str = ""

class GitHubIssuesConfig(BaseModel):
    enabled: bool = False
    token: str = ""  # From GITHUB_TOKEN env var
    owner: str = ""
    repo: str = ""
```

**Testing Requirements**:
- [ ] Test Linear API integration (mock responses)
- [ ] Test GitHub API integration (mock responses)
- [ ] Test authentication handling
- [ ] Test rate limiting

**Documentation**:
- [ ] API key configuration guide
- [ ] Ticket search examples

**Success Criteria**:
- Both integrations work with API keys
- Search returns relevant tickets
- Acceptance criteria extracted correctly

---

### Milestone 8.4: Plan Mode Tool Access Control

**Objective**: Ensure Plan Mode only has read-only access to MCP tools.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 8.4.1 | Create `PlanModeGuard` class in MCP server | HIGH | DONE |
| 8.4.2 | Define allowed tools list for Plan Mode | HIGH | DONE |
| 8.4.3 | Define blocked tools list (write operations) | HIGH | DONE |
| 8.4.4 | Integrate guard into MCP request handler | HIGH | DONE |
| 8.4.5 | Add `set_plan_mode` internal tool | MEDIUM | DONE |
| 8.4.6 | Create clear error messages for blocked tools | MEDIUM | DONE |

**PlanModeGuard**:
```typescript
const PLAN_MODE_ALLOWED = [
  // Read-only code memory
  "search_similar", "read_graph", "get_implementation",
  // Read-only documents
  "search_docs", "get_doc",
  // Read-only tickets
  "search_tickets", "get_ticket",
];

const PLAN_MODE_BLOCKED = [
  // Write operations
  "create_entities", "create_relations", "add_observations",
  "delete_entities", "delete_observations", "delete_relations",
];

class PlanModeGuard {
  private isPlanMode: boolean = false;

  setPlanMode(enabled: boolean): void { ... }

  isToolAllowed(toolName: string): boolean {
    if (!this.isPlanMode) return true;
    return !PLAN_MODE_BLOCKED.includes(toolName);
  }
}
```

**Testing Requirements**:
- [x] Test tool blocking in Plan Mode
- [x] Test allowed tools work correctly
- [x] Verify error messages are clear

**Success Criteria**:
- [x] Write tools blocked in Plan Mode
- [x] Clear error messages for blocked operations
- [x] No security bypass possible

**Implementation Details** (Milestone 8.4 Complete):
- Created `mcp-qdrant-memory/src/plan-mode-guard.ts` with PlanModeGuard class
- Environment variable detection via `CLAUDE_PLAN_MODE` (matches Python implementation)
- Blocked tools: create_entities, create_relations, add_observations, delete_entities, delete_observations, delete_relations
- Allowed tools: search_similar, read_graph, get_implementation, search_docs, get_doc, search_tickets, get_ticket, set_plan_mode
- Added `set_plan_mode` MCP tool to enable/disable Plan Mode
- Error responses include blocked tools list and hint for resolution
- Version bumped to 0.6.4

---

## Phase 9: Quality Guardrails Framework

**Goal**: Create the framework for validating implementation plans against quality rules.

### Milestone 9.1: Core Guardrails Data Model

**Objective**: Define data structures for plan validation rules.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 9.1.1 | Create `claude_indexer/ui/plan/guardrails/` package | HIGH | DONE |
| 9.1.2 | Define `PlanValidationContext` dataclass | HIGH | DONE |
| 9.1.3 | Define `PlanValidationFinding` dataclass | HIGH | DONE |
| 9.1.4 | Define `PlanRevision` and `RevisionType` | HIGH | DONE |
| 9.1.5 | Create abstract `PlanValidationRule` base class | HIGH | DONE |
| 9.1.6 | Create `PlanGuardrailConfig` for rule configuration | MEDIUM | DONE |

**Core Data Structures**:
```python
# claude_indexer/ui/plan/guardrails/base.py

class RevisionType(Enum):
    ADD_TASK = "add_task"
    MODIFY_TASK = "modify_task"
    REMOVE_TASK = "remove_task"
    ADD_DEPENDENCY = "add_dependency"
    REORDER_TASKS = "reorder_tasks"

@dataclass
class PlanValidationContext:
    plan: ImplementationPlan
    memory_client: Any | None = None
    collection_name: str | None = None
    project_path: Path = field(default_factory=Path.cwd)
    config: PlanGuardrailConfig = None
    source_requirements: str = ""

    def search_memory(self, query: str, **kwargs) -> list[dict]:
        """Search semantic memory for similar code/patterns."""
        ...

@dataclass
class PlanValidationFinding:
    rule_id: str
    severity: Severity
    summary: str
    affected_tasks: list[str] = field(default_factory=list)
    suggestion: str | None = None
    can_auto_revise: bool = False
    confidence: float = 1.0
    evidence: list[Evidence] = field(default_factory=list)
    suggested_revision: PlanRevision | None = None

@dataclass
class PlanRevision:
    revision_type: RevisionType
    rationale: str
    target_task_id: str | None = None
    new_task: Task | None = None
    modifications: dict[str, Any] = field(default_factory=dict)
    dependency_additions: list[tuple[str, str]] = field(default_factory=list)

class PlanValidationRule(ABC):
    @property
    @abstractmethod
    def rule_id(self) -> str: ...

    @property
    @abstractmethod
    def category(self) -> str: ...  # coverage, consistency, architecture, performance

    @abstractmethod
    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]: ...

    @abstractmethod
    def suggest_revision(self, finding: PlanValidationFinding, context: PlanValidationContext) -> PlanRevision | None: ...
```

**Testing Requirements**:
- [x] Unit tests for all data classes
- [x] Test serialization/deserialization
- [x] Test validation context memory search

**Success Criteria**:
- [x] All data structures defined and tested
- [x] Follows existing pattern from claude_indexer/rules/base.py
- [x] Memory search integration works

**Implementation Details** (Milestone 9.1 Complete):
- Created `claude_indexer/ui/plan/guardrails/` package with base.py, config.py, __init__.py
- RevisionType enum with ADD_TASK, MODIFY_TASK, REMOVE_TASK, ADD_DEPENDENCY, REORDER_TASKS
- PlanRevision dataclass with serialization support
- PlanValidationFinding dataclass with evidence and suggested revision
- PlanValidationContext with plan, config, memory search integration
- PlanValidationRule ABC following rules/base.py pattern
- PlanGuardrailConfig Pydantic model with category toggles, auto-revise settings
- Added plan_guardrails to UnifiedConfig
- Tests: 52 unit tests covering all functionality

---

### Milestone 9.2: Plan Guardrail Engine

**Objective**: Create the engine that orchestrates rule validation.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 9.2.1 | Create `PlanGuardrailEngine` coordinator class | HIGH | DONE |
| 9.2.2 | Implement rule discovery (auto-load from directory) | HIGH | DONE |
| 9.2.3 | Add parallel rule execution support | MEDIUM | DEFERRED |
| 9.2.4 | Implement severity filtering | MEDIUM | DONE |
| 9.2.5 | Create `PlanGuardrailResult` aggregation | MEDIUM | DONE |
| 9.2.6 | Add performance timing for rules | LOW | DONE |

**PlanGuardrailEngine**:
```python
class PlanGuardrailEngine:
    def __init__(self, config: PlanGuardrailConfig):
        self.config = config
        self.rules: dict[str, PlanValidationRule] = {}
        self._discover_rules()

    def _discover_rules(self) -> None:
        """Auto-discover rules from guardrails/rules/ directory."""
        ...

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        """Run all enabled rules against the plan."""
        findings = []
        for rule_id, rule in self.rules.items():
            if self.config.is_rule_enabled(rule_id):
                findings.extend(rule.validate(context))
        return findings

    def auto_revise(
        self,
        plan: ImplementationPlan,
        findings: list[PlanValidationFinding]
    ) -> RevisedPlan:
        """Apply auto-revisions based on findings."""
        ...
```

**Testing Requirements**:
- [x] Test rule discovery
- [ ] Test parallel execution (DEFERRED: flag added, implementation pending)
- [x] Test severity filtering
- [x] Benchmark validation latency

**Success Criteria**:
- [x] Rules auto-discovered from directory
- [ ] Parallel execution reduces latency (DEFERRED: sequential first)
- [x] <500ms total validation time

**Implementation Details** (Milestone 9.2 Complete):
- Created `claude_indexer/ui/plan/guardrails/engine.py` with:
  - `PlanGuardrailEngineConfig` dataclass (timeout, error handling, confidence threshold)
  - `RuleExecutionResult` dataclass for individual rule results
  - `PlanGuardrailResult` dataclass with findings, statistics, error tracking
  - `PlanGuardrailEngine` class with full rule lifecycle management
- Key features:
  - `register()` / `unregister()` for manual rule registration
  - `discover_rules()` for auto-discovery from directory
  - `validate()` runs all enabled rules with configurable filtering
  - `validate_fast()` runs only fast rules (<100ms) for sync checks
  - `validate_category()` runs rules in specific category
  - Confidence threshold filtering
  - Max findings per rule limiting
  - Error handling with continue_on_error option
  - Performance timing recorded per rule and total
- Tests: 42 unit tests covering all functionality

---

### Milestone 9.3: Plan Validation Rules (5 Rules)

**Objective**: Implement the core quality validation rules.

#### Tasks

| ID | Task | Priority | Rule Name | Category | Status |
|----|------|----------|-----------|----------|--------|
| 9.3.1 | Test Requirement Detection | HIGH | `PLAN.TEST_REQUIREMENT` | coverage | NEW |
| 9.3.2 | Documentation Requirement Detection | HIGH | `PLAN.DOC_REQUIREMENT` | coverage | NEW |
| 9.3.3 | Duplicate Code Detection | HIGH | `PLAN.DUPLICATE_DETECTION` | consistency | NEW |
| 9.3.4 | Architectural Consistency Check | MEDIUM | `PLAN.ARCHITECTURAL_CONSISTENCY` | architecture | NEW |
| 9.3.5 | Performance Pattern Detection | MEDIUM | `PLAN.PERFORMANCE_PATTERN` | performance | NEW |

**Implementation Location**: `claude_indexer/ui/plan/guardrails/rules/`

#### Rule 1: TestRequirementRule

```python
class TestRequirementRule(PlanValidationRule):
    """Ensures new features have corresponding test tasks."""

    FEATURE_KEYWORDS = ["implement", "add", "create", "build", "develop", "new"]
    TEST_KEYWORDS = ["test", "spec", "unittest", "pytest", "jest"]
    TRIVIAL_PATTERNS = [r"^(fix|rename|move|delete)\s+(typo|comment|readme)"]

    @property
    def rule_id(self) -> str:
        return "PLAN.TEST_REQUIREMENT"

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        findings = []
        for task in context.plan.all_tasks:
            if self._is_feature_task(task) and not self._has_test_task(task, context.plan):
                if not self._is_trivial(task):
                    findings.append(self._create_finding(task))
        return findings

    def suggest_revision(self, finding, context) -> PlanRevision:
        """Auto-add test task."""
        feature_task = self._get_task(finding.affected_tasks[0], context.plan)
        test_task = Task(
            id=f"TASK-TST-{feature_task.id[-4:]}",
            title=f"Add tests for {feature_task.title}",
            description=f"Write tests for {feature_task.title}",
            scope=feature_task.scope,
            priority=feature_task.priority + 1,
            estimated_effort="low",
            impact=feature_task.impact * 0.8,
            acceptance_criteria=["Unit tests cover main functionality", "Tests pass in CI"],
            dependencies=[feature_task.id],
            tags=["testing", "quality"],
        )
        return PlanRevision(
            revision_type=RevisionType.ADD_TASK,
            rationale=f"Feature '{feature_task.title}' needs test coverage",
            new_task=test_task,
        )
```

#### Rule 2: DuplicateDetectionRule

```python
class DuplicateDetectionRule(PlanValidationRule):
    """Detects tasks that might duplicate existing functionality."""

    SIMILARITY_THRESHOLD = 0.70

    @property
    def rule_id(self) -> str:
        return "PLAN.DUPLICATE_DETECTION"

    def validate(self, context: PlanValidationContext) -> list[PlanValidationFinding]:
        findings = []
        if context.memory_client is None:
            return findings

        for task in context.plan.all_tasks:
            query = f"{task.title} {task.description[:200]}"
            results = context.search_memory(
                query=query,
                entity_types=["function", "class", "implementation_pattern"]
            )

            for result in results:
                if result.get("score", 0) >= self.SIMILARITY_THRESHOLD:
                    findings.append(self._create_finding(task, result))

        return findings

    def suggest_revision(self, finding, context) -> PlanRevision:
        """Modify task to reference existing code."""
        return PlanRevision(
            revision_type=RevisionType.MODIFY_TASK,
            target_task_id=finding.affected_tasks[0],
            rationale="Potential duplicate detected",
            modifications={
                "description": f"{task.description}\n\n**Note:** Review existing implementation before proceeding.",
                "acceptance_criteria": task.acceptance_criteria + [
                    f"Verified no duplication with existing code"
                ],
            }
        )
```

**Testing Requirements**:
- [ ] Unit tests for each rule with positive/negative cases
- [ ] Test auto-revision generation
- [ ] Test with real implementation plans
- [ ] Measure false positive rate (<10% target)

**Documentation**:
- [ ] Rule reference documentation
- [ ] Configuration examples
- [ ] Override mechanisms

**Success Criteria**:
- All 5 rules implemented and tested
- <10% false positive rate
- Clear, actionable findings

---

## Phase 10: Auto-Revision System

**Goal**: Automatically apply revisions to plans based on validation findings.

### Milestone 10.1: Auto-Revision Engine

**Objective**: Create the engine that applies plan revisions automatically.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 10.1.1 | Create `AutoRevisionEngine` class | HIGH | NEW |
| 10.1.2 | Implement revision sorting by severity | HIGH | NEW |
| 10.1.3 | Implement conflict detection | HIGH | NEW |
| 10.1.4 | Add circular dependency prevention | HIGH | NEW |
| 10.1.5 | Implement revision application methods | HIGH | NEW |
| 10.1.6 | Create `RevisedPlan` result dataclass | MEDIUM | NEW |
| 10.1.7 | Add post-revision dependency resolution | MEDIUM | NEW |
| 10.1.8 | Add iteration limit (prevent infinite loops) | HIGH | NEW |

**AutoRevisionEngine**:
```python
@dataclass
class AppliedRevision:
    revision: PlanRevision
    finding: PlanValidationFinding
    success: bool
    error: str | None = None

@dataclass
class RevisedPlan:
    original_plan: ImplementationPlan
    revised_plan: ImplementationPlan
    revisions_applied: list[AppliedRevision] = field(default_factory=list)
    revisions_skipped: list[tuple[PlanRevision, str]] = field(default_factory=list)
    qa_passed: bool = False

class AutoRevisionEngine:
    MAX_ITERATIONS = 3

    def revise_plan(
        self,
        plan: ImplementationPlan,
        findings: list[PlanValidationFinding],
        rules: dict[str, PlanValidationRule]
    ) -> RevisedPlan:
        """
        Apply revisions based on findings.

        Algorithm:
        1. Sort findings by severity (CRITICAL > HIGH > MEDIUM > LOW)
        2. For each finding that can be auto-revised:
           a. Get revision suggestion from rule
           b. Check for conflicts
           c. Apply revision if safe
        3. Re-resolve dependencies
        4. Update priorities
        """
        ...

    def _check_conflicts(self, plan: ImplementationPlan, revision: PlanRevision) -> str | None:
        """Check if revision would create conflicts."""
        if revision.revision_type == RevisionType.ADD_TASK:
            if any(t.id == revision.new_task.id for t in plan.all_tasks):
                return f"Task ID '{revision.new_task.id}' already exists"

        if revision.revision_type == RevisionType.ADD_DEPENDENCY:
            for from_id, to_id in revision.dependency_additions:
                if self._would_create_cycle(plan, from_id, to_id):
                    return f"Would create circular dependency"

        return None

    def _would_create_cycle(self, plan, from_id, to_id) -> bool:
        """DFS to detect circular dependencies."""
        ...
```

**Testing Requirements**:
- [ ] Test revision application for each type
- [ ] Test conflict detection
- [ ] Test circular dependency prevention
- [ ] Test iteration limit enforcement

**Success Criteria**:
- Revisions applied without conflicts
- No circular dependencies introduced
- Iteration limit prevents infinite loops

---

### Milestone 10.2: Revision Audit Trail

**Objective**: Track all revisions for transparency and debugging.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 10.2.1 | Add revision history to ImplementationPlan | MEDIUM | NEW |
| 10.2.2 | Create human-readable revision summary | MEDIUM | NEW |
| 10.2.3 | Add revision rollback capability | LOW | NEW |
| 10.2.4 | Implement revision persistence | LOW | NEW |

**Audit Trail Format**:
```markdown
## Plan Revisions Applied

### 1. Added Test Task (PLAN.TEST_REQUIREMENT)
- **Reason**: Feature 'Add user authentication' needs test coverage
- **Added**: TASK-TST-0001 "Add tests for user authentication"
- **Confidence**: 95%

### 2. Modified Task (PLAN.DUPLICATE_DETECTION)
- **Reason**: Potential duplicate of existing 'AuthService.login()'
- **Modified**: TASK-0002 description to reference existing code
- **Confidence**: 78%
```

**Testing Requirements**:
- [ ] Test audit trail generation
- [ ] Test revision summary formatting
- [ ] Verify all revisions tracked

**Success Criteria**:
- Complete audit trail for all revisions
- Human-readable summaries
- Transparency for user review

---

## Phase 11: Prompt Augmentation & Exploration Hints

**Goal**: Inject planning guidelines and exploration hints into Claude's context.

### Milestone 11.1: Planning Guidelines Generator

**Objective**: Generate contextual planning guidelines for injection.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 11.1.1 | Create `hooks/planning_guidelines.py` | HIGH | NEW |
| 11.1.2 | Define guidelines template with placeholders | HIGH | NEW |
| 11.1.3 | Load project patterns from CLAUDE.md | MEDIUM | NEW |
| 11.1.4 | Generate collection-specific MCP commands | MEDIUM | NEW |
| 11.1.5 | Add configuration for guideline customization | LOW | NEW |

**Planning Guidelines Template**:
```python
PLANNING_GUIDELINES_TEMPLATE = """
=== PLANNING QUALITY GUIDELINES ===

When formulating this implementation plan, follow these guidelines:

## 1. Code Reuse Check (CRITICAL)
Before proposing ANY new function, class, or component:
- Search the codebase: `{mcp_prefix}search_similar("functionality")`
- Check existing patterns: `{mcp_prefix}read_graph(entity="Component", mode="relationships")`
- If similar exists, plan to REUSE or EXTEND it
- State explicitly: "Verified no existing implementation" or "Will extend existing Y"

## 2. Testing Requirements
Every plan that modifies code MUST include:
- [ ] Unit tests for new/modified functions
- [ ] Integration tests for API changes
- Task format: "Add tests for [feature] in [test_file]"

## 3. Documentation Requirements
Include documentation tasks when:
- Adding public APIs -> Update API docs
- Changing user-facing behavior -> Update README
- Adding configuration -> Update config docs

## 4. Architecture Alignment
Your plan MUST align with project patterns:
{project_patterns}

## 5. Performance Considerations
Flag any step that may introduce:
- O(n^2) or worse complexity
- Unbounded memory usage
- Missing timeouts on network calls

== END PLANNING GUIDELINES ==
"""

def generate_planning_guidelines(
    collection_name: str,
    project_patterns: str = "",
    exploration_hints: list[str] = None
) -> str:
    """Generate planning guidelines with project context."""
    mcp_prefix = f"mcp__{collection_name}-memory__"
    ...
```

**Testing Requirements**:
- [ ] Test template rendering
- [ ] Test project pattern loading
- [ ] Test MCP prefix generation

**Success Criteria**:
- Guidelines correctly formatted
- Project-specific patterns included
- MCP commands use correct collection

---

### Milestone 11.2: Exploration Hints Generator

**Objective**: Generate hints to guide Claude's sub-agent parallel exploration.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 11.2.1 | Create `hooks/exploration_hints.py` | HIGH | NEW |
| 11.2.2 | Implement entity extraction from prompts | HIGH | NEW |
| 11.2.3 | Generate duplicate-check hints | HIGH | NEW |
| 11.2.4 | Generate test-discovery hints | MEDIUM | NEW |
| 11.2.5 | Generate documentation hints | MEDIUM | NEW |
| 11.2.6 | Generate architecture hints | LOW | NEW |

**Exploration Hints Generator**:
```python
def generate_exploration_hints(prompt: str, collection_name: str) -> list[str]:
    """Generate exploration hints for parallel sub-agents."""
    mcp_prefix = f"mcp__{collection_name}-memory__"
    entities = extract_entities(prompt)

    hints = [
        # Duplicate Check
        f"## Duplicate Check\n{mcp_prefix}search_similar('{entities[0]}', entityTypes=['function', 'class'])",

        # Test Discovery
        f"## Test Discovery\n{mcp_prefix}search_similar('test', entityTypes=['file'])",

        # Documentation
        f"## Documentation\n{mcp_prefix}search_similar('docs', entityTypes=['documentation'])",
    ]

    # Entity-specific hints
    for entity in entities[:3]:
        hints.append(
            f"## {entity} Analysis\n{mcp_prefix}read_graph(entity='{entity}', mode='smart')"
        )

    return hints

def extract_entities(prompt: str) -> list[str]:
    """Extract likely code entities from prompt."""
    patterns = [
        r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b',  # CamelCase
        r'\b[a-z]+(?:_[a-z]+)+\b',            # snake_case
        r'["\']([^"\']+)["\']',               # Quoted terms
    ]
    ...
```

**Testing Requirements**:
- [ ] Test entity extraction accuracy
- [ ] Test hint generation with various prompts
- [ ] Verify MCP commands are valid

**Success Criteria**:
- Entities extracted with >80% accuracy
- Hints guide toward quality checks
- MCP commands are executable

---

### Milestone 11.3: Prompt Handler Integration

**Objective**: Integrate guidelines and hints into UserPromptSubmit hook.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 11.3.1 | Modify `hooks/prompt_handler.py` for Plan Mode | HIGH | NEW |
| 11.3.2 | Implement guidelines injection | HIGH | NEW |
| 11.3.3 | Implement hints injection | HIGH | NEW |
| 11.3.4 | Add configuration toggle | MEDIUM | NEW |
| 11.3.5 | Measure injection latency (<50ms target) | MEDIUM | NEW |

**Testing Requirements**:
- [ ] Test full hook flow with Plan Mode
- [ ] Test injection timing
- [ ] Verify guidelines appear in context

**Success Criteria**:
- Guidelines injected for Plan Mode
- <50ms injection latency
- Claude follows guidelines

---

## Phase 12: Plan QA Verification

**Goal**: Verify generated plans meet quality standards before user approval.

### Milestone 12.1: Plan QA Verifier

**Objective**: Post-generation verification of plan quality.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 12.1.1 | Create `claude_indexer/hooks/plan_qa.py` | HIGH | NEW |
| 12.1.2 | Implement missing test detection | HIGH | NEW |
| 12.1.3 | Implement missing doc detection | HIGH | NEW |
| 12.1.4 | Implement duplicate check verification | HIGH | NEW |
| 12.1.5 | Create `PlanQAResult` dataclass | MEDIUM | NEW |
| 12.1.6 | Generate human-readable feedback | MEDIUM | NEW |
| 12.1.7 | Integrate with plan output | MEDIUM | NEW |

**PlanQAVerifier**:
```python
@dataclass
class PlanQAResult:
    is_valid: bool = True
    missing_tests: list[str] = field(default_factory=list)
    missing_docs: list[str] = field(default_factory=list)
    potential_duplicates: list[str] = field(default_factory=list)
    architecture_warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def has_issues(self) -> bool:
        return bool(self.missing_tests or self.missing_docs or
                    self.potential_duplicates or self.architecture_warnings)

    def format_feedback(self) -> str:
        """Format feedback for plan output."""
        if not self.has_issues():
            return "\n[Plan QA: All quality checks passed]"

        lines = ["\n=== Plan QA Feedback ==="]
        if self.missing_tests:
            lines.append("\n[WARN] Missing Test Coverage:")
            for item in self.missing_tests:
                lines.append(f"  - {item}")
        ...
        return "\n".join(lines)

class PlanQAVerifier:
    CODE_CHANGE_PATTERNS = re.compile(
        r'(add|create|implement|modify)\s+(?:a\s+)?(function|class|component)',
        re.IGNORECASE
    )

    def verify_plan(self, plan_text: str) -> PlanQAResult:
        """Verify a plan meets quality standards."""
        result = PlanQAResult()

        if self._needs_tests(plan_text) and not self._has_test_tasks(plan_text):
            result.missing_tests.append("Plan modifies code but includes no test tasks")
            result.suggestions.append("Add unit/integration test task")

        if self._is_user_facing(plan_text) and not self._has_doc_tasks(plan_text):
            result.missing_docs.append("User-facing changes without doc update")

        if self._creates_new_code(plan_text) and not self._mentions_reuse_check(plan_text):
            result.potential_duplicates.append("New code without explicit duplicate check")

        return result
```

**Testing Requirements**:
- [ ] Test with plans missing tests
- [ ] Test with plans missing docs
- [ ] Test with complete plans
- [ ] Verify feedback formatting

**Success Criteria**:
- Detects missing test/doc tasks
- Generates actionable feedback
- <50ms verification latency

---

### Milestone 12.2: QA Integration Points

**Objective**: Integrate QA verification into the planning workflow.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 12.2.1 | Add QA check after guardrail validation | HIGH | NEW |
| 12.2.2 | Append QA feedback to plan output | HIGH | NEW |
| 12.2.3 | Track QA pass/fail metrics | LOW | NEW |
| 12.2.4 | Add QA override configuration | LOW | NEW |

**Testing Requirements**:
- [ ] Test end-to-end QA flow
- [ ] Test feedback appears in plan
- [ ] Test override configuration

**Success Criteria**:
- QA feedback visible to user
- Metrics tracked for analysis
- Override available for edge cases

---

## Phase 13: Polish, Testing & Documentation

**Goal**: Ensure production readiness with comprehensive testing and documentation.

### Milestone 13.1: Integration Testing

**Objective**: End-to-end testing of Plan Mode integration.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 13.1.1 | Create `tests/integration/test_plan_mode.py` | HIGH | NEW |
| 13.1.2 | Test full Plan Mode flow (detect -> augment -> validate -> revise) | HIGH | NEW |
| 13.1.3 | Test MCP tool integration | HIGH | NEW |
| 13.1.4 | Test issue tracker integration | MEDIUM | NEW |
| 13.1.5 | Test design doc indexing | MEDIUM | NEW |
| 13.1.6 | Create mock Claude Code Plan Mode responses | MEDIUM | NEW |

**Integration Test Scenarios**:
```python
class TestPlanModeIntegration:
    def test_full_plan_mode_flow(self):
        """Test complete Plan Mode integration."""
        # 1. Detect Plan Mode
        # 2. Inject guidelines
        # 3. Validate plan
        # 4. Apply auto-revisions
        # 5. Run QA check
        # 6. Verify output
        ...

    def test_plan_with_missing_tests(self):
        """Verify test tasks auto-added."""
        ...

    def test_duplicate_detection(self):
        """Verify duplicate warning generated."""
        ...

    def test_doc_requirement(self):
        """Verify doc tasks auto-added for user-facing changes."""
        ...
```

**Testing Requirements**:
- [ ] >80% code coverage for new components
- [ ] All scenarios covered
- [ ] Performance benchmarks included

**Success Criteria**:
- All integration tests pass
- >80% coverage
- Performance within targets

---

### Milestone 13.2: Performance Optimization

**Objective**: Meet all performance targets.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 13.2.1 | Profile Plan Mode detection latency | HIGH | NEW |
| 13.2.2 | Profile guidelines injection latency | HIGH | NEW |
| 13.2.3 | Profile validation latency | HIGH | NEW |
| 13.2.4 | Optimize hot paths | MEDIUM | NEW |
| 13.2.5 | Add caching where beneficial | MEDIUM | NEW |
| 13.2.6 | Create performance benchmarks | MEDIUM | NEW |

**Performance Targets**:
| Operation | Target | Budget |
|-----------|--------|--------|
| Plan Mode Detection | <10ms | Pattern matching |
| Guidelines Generation | <20ms | Template substitution |
| Exploration Hints | <30ms | Entity extraction |
| Plan Validation | <500ms | 5 rules |
| Auto-Revision | <200ms | Conflict checking |
| Plan QA | <50ms | Pattern matching |
| **Total Overhead** | **<100ms** | (excluding validation) |

**Testing Requirements**:
- [ ] Benchmark all operations
- [ ] Test under load
- [ ] Verify targets met

**Success Criteria**:
- All performance targets met
- No regression from baseline
- Clear metrics dashboard

---

### Milestone 13.3: Documentation

**Objective**: Comprehensive documentation for Plan Mode integration.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 13.3.1 | Update README.md with Plan Mode features | HIGH | NEW |
| 13.3.2 | Create `docs/PLAN_MODE.md` comprehensive guide | HIGH | NEW |
| 13.3.3 | Update HOOKS.md with Plan hooks | HIGH | NEW |
| 13.3.4 | Document all configuration options | MEDIUM | NEW |
| 13.3.5 | Create plan guardrail rule reference | MEDIUM | NEW |
| 13.3.6 | Add troubleshooting section | MEDIUM | NEW |
| 13.3.7 | Update CLAUDE.md with Plan guidelines | LOW | NEW |

**Documentation Structure**:
```
docs/
├── PLAN_MODE.md          # Comprehensive Plan Mode guide
│   ├── Overview
│   ├── Configuration
│   ├── Quality Guardrails
│   ├── Auto-Revision Behavior
│   ├── MCP Context Integration
│   └── Troubleshooting
├── HOOKS.md              # Updated with Plan hooks
└── memory-functions.md   # Updated with new MCP tools
```

**Testing Requirements**:
- [ ] All documentation accurate
- [ ] Examples tested and working
- [ ] No broken links

**Success Criteria**:
- New user understands Plan Mode in <10 minutes
- All features documented
- Examples are copy-paste ready

---

### Milestone 13.4: User Experience Validation

**Objective**: Validate the "magical" UX described in PRD.

#### Tasks

| ID | Task | Priority | Status |
|----|------|----------|--------|
| 13.4.1 | Conduct user testing sessions | HIGH | NEW |
| 13.4.2 | Collect feedback on plan quality | HIGH | NEW |
| 13.4.3 | Measure plan approval rate | MEDIUM | NEW |
| 13.4.4 | Iterate on findings format | MEDIUM | NEW |
| 13.4.5 | Add configuration for thoroughness level | LOW | NEW |

**Success Metrics Validation**:
- [ ] >90% of plans include test/doc tasks when appropriate
- [ ] <10% of plans require user revision
- [ ] Existing code reuse suggested in >80% of applicable cases
- [ ] Users report plans "feel like senior engineer's work"

**Success Criteria**:
- All PRD success metrics met
- Positive user feedback
- No major UX complaints

---

## Appendix: Plan Guardrail Rule Specifications

### A.1 Coverage Rules (2)

| # | Rule | Severity | Detection | Auto-Fix |
|---|------|----------|-----------|----------|
| 1 | `PLAN.TEST_REQUIREMENT` | MEDIUM | Feature task without test dependency | Add test task |
| 2 | `PLAN.DOC_REQUIREMENT` | LOW | User-facing change without doc task | Add doc task |

### A.2 Consistency Rules (1)

| # | Rule | Severity | Detection | Auto-Fix |
|---|------|----------|-----------|----------|
| 1 | `PLAN.DUPLICATE_DETECTION` | HIGH | Semantic similarity >70% with existing code | Modify task to reference existing |

### A.3 Architecture Rules (1)

| # | Rule | Severity | Detection | Auto-Fix |
|---|------|----------|-----------|----------|
| 1 | `PLAN.ARCHITECTURAL_CONSISTENCY` | MEDIUM | File paths outside established patterns | Add warning to task |

### A.4 Performance Rules (1)

| # | Rule | Severity | Detection | Auto-Fix |
|---|------|----------|-----------|----------|
| 1 | `PLAN.PERFORMANCE_PATTERN` | LOW | Known anti-patterns (N+1, no caching) | Add performance note |

---

## Implementation Order Summary

### Critical Path

1. **Phase 7**: Plan Mode Detection & Hook Infrastructure (foundation)
2. **Phase 9**: Quality Guardrails Framework (core value)
3. **Phase 10**: Auto-Revision System (key differentiator)
4. **Phase 11**: Prompt Augmentation (guidance injection)

### High Priority

5. **Phase 8**: MCP Context Integration (rich context)
6. **Phase 12**: Plan QA Verification (quality assurance)

### Lower Priority

7. **Phase 13**: Polish, Testing & Documentation (production readiness)

---

## Dependencies Graph

```
Phase 7 (Detection/Hooks)
       |
       +----------------------+
       v                      v
Phase 9 (Guardrails)    Phase 8 (MCP Context)
       |                      |
       v                      |
Phase 10 (Auto-Revision) <----+
       |
       v
Phase 11 (Prompt Augmentation)
       |
       v
Phase 12 (Plan QA)
       |
       v
Phase 13 (Polish/Testing/Docs)
```

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| False positives annoying | HIGH | Configurable thresholds, easy overrides |
| Performance too slow | MEDIUM | Parallel validation, caching |
| Auto-revision conflicts | HIGH | Conflict detection, iteration limits |
| Issue tracker API failures | MEDIUM | Graceful degradation, caching |
| Plan Mode detection fails | HIGH | Multiple detection methods, fallbacks |

---

## Success Criteria Summary

- [ ] Plan Mode detected with >95% accuracy
- [ ] <100ms overhead for plan augmentation
- [ ] >90% of plans include test/doc tasks when appropriate
- [ ] Existing code reuse suggested in >80% of applicable cases
- [ ] <10% of plans require user revision before approval
- [ ] All 5 guardrail rules implemented and tested
- [ ] MCP tools for docs and tickets functional
- [ ] Documentation complete

---

*Generated from PRD.md and TDD.md (Plan Mode Integration)*
