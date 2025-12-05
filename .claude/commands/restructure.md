---
description: Diagnose architectural tech debt (cycles, coupling, stability, module structure)
argument-hint: [count] [module-focus]
---

# Architectural Restructuring Analysis

You are analyzing this codebase for **architectural-level** restructuring opportunities. Find the top $1 issues (default: 3 if not specified).

**Module focus**: $2 (if specified, only analyze code related to this module/area)

**This command differs from /refactor:**
| Aspect | /refactor | /restructure |
|--------|-----------|--------------|
| Granularity | Function/class level | File/module level |
| Focus | Individual code issues | Dependency graph structure |
| Principles | SOLID, DRY at code level | Package principles, Clean Architecture |
| Actions | Rename, extract method | Move files, create modules, add interfaces |

**Priority order**: Cycles > Internal imports > Stability violations > Extraction candidates > Missing abstractions > Coupling > Cohesion

---

## Principles Being Enforced

### Package Design Principles (Robert C. Martin)
- **ADP**: Acyclic Dependencies Principle - dependency graph must be a DAG
- **SDP**: Stable Dependencies Principle - volatile modules should only depend on stable modules
- **CCP**: Common Closure Principle - group things that change together
- **CRP**: Common Reuse Principle - don't force unused dependencies on consumers

### Clean Architecture / Hexagonal Layering
- Dependencies point **inward** toward stable core/domain
- Features don't reach **sideways** into other features' internals
- Shared utilities sit **below** features

### SOLID at Architecture Level
- **SRP**: Each module has one reason to change
- **DIP**: Depend on abstractions, not concrete feature internals

---

## Analysis Protocol

Execute this multi-phase analysis using the memory MCP tools available to you.

### Phase 0: Module Focus (if specified)

If a module focus was provided (e.g., "payments", "auth", "users"):

1. **Discover related entities**: Use `search_similar("$2", limit=50)` to find all code related to the module
2. **Map the module boundary**: Use `read_graph(entity="<top_match>", mode="relationships")` for key entities
3. **Include dependencies**: Add immediate dependencies (1-2 hops) to the analysis scope
4. **Scope limitation**: ALL subsequent analysis phases only consider entities discovered here

**If no module focus**: Analyze the entire codebase.

---

### Phase 1: Build Dependency Graph

1. Use `read_graph(mode="raw")` to get all entities and relations
2. Filter to "imports", "uses", "calls" relation types
3. Aggregate to **file-level**: source_file → target_file
4. Aggregate to **module-level**: source_dir → target_dir
5. Calculate metrics for each module:
   - **Ca** (afferent coupling): count of incoming edges
   - **Ce** (efferent coupling): count of outgoing edges
   - **I** (instability): Ce / (Ca + Ce) — ranges from 0 (stable) to 1 (volatile)

---

### Phase 2: Cycle Detection (ADP - Acyclic Dependencies Principle)

**Rule**: The dependency graph must be a Directed Acyclic Graph (DAG).

1. Run Tarjan's algorithm (or equivalent) on file-level graph
2. Identify all Strongly Connected Components (SCCs) with >1 node (these are cycles)
3. For each cycle:
   - Trace the full circular path
   - Find the **weakest edge** (fewest actual usages/imports)
   - Suggest extraction point to break the cycle

**Issue format**:
```
[CYCLE] Circular dependency: moduleA ↔ moduleB
Path: moduleA/file.py → moduleB/other.py → moduleA/file.py
Weakest link: moduleB/other.py imports only `helper_func` (2 usages)
Impact: N files in cycle, blocks independent testing
Suggestion: Extract `helper_func()` to `shared/helpers.py`
```

---

### Phase 3: Internal Import Violations (Cross-Feature Coupling)

**Rule**: FeatureA can only import FeatureB's PUBLIC API, not internal code.

1. Identify "internal" patterns: `_internal/`, `internal/`, `_private/`, `helpers/`, files starting with `_`
2. For each import relation crossing module boundaries:
   - Check if target is in an internal path
   - Flag as violation
3. Suggest: Use public API OR extract to shared module

**Issue format**:
```
[INTERNAL] Feature 'orders' imports internal from 'payments'
Violation: orders/checkout.py imports payments/_internal/gateway_utils.py
This creates tight coupling across feature boundaries
Suggestion: Use payments.gateway (public API) OR extract to shared/
```

---

### Phase 4: Stability Analysis (SDP - Stable Dependencies Principle)

**Rule**: Volatile modules should depend on stable modules, not vice versa.

1. Use the instability metric I = Ce/(Ca+Ce) calculated in Phase 1
2. For each dependency edge from module A to module B:
   - If I(A) < I(B) → stable module depends on volatile module → **violation**
3. Suggest: Introduce abstraction layer, or move code to appropriate stability level

**Issue format**:
```
[STABILITY] Stable 'core/' depends on volatile 'features/billing'
core/notifications.py imports features/billing/formatters.py
Stability scores: core/ (I=0.15 stable), billing/ (I=0.78 volatile)
Suggestion: Extract format_invoice() to core/formatters.py
```

---

### Phase 5: Shared-or-API Check (CRP - Common Reuse Principle)

**Rule**: If a helper is used by multiple features, it must be in shared OR exposed as public API.

1. Find all helpers/functions imported by >1 module
2. Check if they are in `shared/`, `core/`, `lib/`, `common/` OR explicitly exported as public API
3. If neither → violation

**Issue format**:
```
[EXTRACT] validate_email() used by 4 features
Found in: users/, orders/, notifications/, auth/
Currently duplicated or reaching into users/validators.py
Suggestion: Extract to shared/validation.py
```

---

### Phase 6: Abstraction Opportunities (DIP - Dependency Inversion)

**Rule**: If FeatureA needs a capability from FeatureB, it should depend on an abstraction.

1. Find concrete classes used across module boundaries
2. Focus on: services, gateways, clients, repositories, handlers
3. If multiple modules depend on a concrete implementation → suggest interface

**Issue format**:
```
[ABSTRACT] 3 services directly depend on PaymentGateway concrete class
Consumers: OrderService, SubscriptionService, RefundService
Problem: Can't mock, can't swap implementations, tight coupling
Suggestion: Create interfaces/payment.py::IPaymentGateway
```

---

### Phase 7: Coupling/Cohesion Metrics

**High Coupling Detection**:
1. Flag modules with Ce > 15 (too many outgoing dependencies)
2. Flag modules that are both high-Ce AND high-Ca (unstable hubs)

**Low Cohesion Detection**:
1. Calculate internal edge ratio: edges within module / total edges
2. Flag modules with <20% internal edges (low cohesion)
3. Suggest splits or consolidation

**Issue formats**:
```
[COUPLING] services/order.py has 23 dependencies (efferent)
High instability (I=0.85) but 12 files depend on it
This is a "hub" that's both unstable and central
Suggestion: Split into smaller, focused modules

[COHESION] utils/ has only 12% internal dependencies
Files: validators, formatters, http_client, cache, logging
These are unrelated concerns bundled together
Suggestion: Split into validation/, http/, cache/, logging/
```

---

## Issue Grouping

Group related issues together by:
1. **Same module** - Multiple issues in one module should be presented together
2. **Dependency chain** - If module A depends on B and both have issues, group them
3. **Common fix** - Issues that could be resolved by the same restructuring action

---

## Output Format

Present your findings as:

```
## Architectural Restructuring Analysis

**Scope**: [Entire codebase | Focus: $2]
**Modules analyzed**: N
**Total dependencies**: N
**Cycles found**: N

---

**Restructuring Opportunities Found:**

1. **[CYCLE]** `moduleA ↔ moduleB`
   - Path: moduleA/file.py → moduleB/other.py → moduleA/file.py
   - Weakest link: moduleB/other.py imports only `helper_func` (2 usages)
   - Impact: 15 files in cycle, blocks independent testing
   - Suggestion: Extract `helper_func()` to `shared/helpers.py`

2. **[INTERNAL]** Feature 'orders' imports internal from 'payments'
   - Violation: orders/checkout.py → payments/_internal/gateway_utils.py
   - Impact: Tight coupling across feature boundaries
   - Suggestion: Use payments.gateway (public API) OR extract to shared/

3. **[STABILITY]** Stable 'core/' depends on volatile 'features/billing'
   - core/notifications.py → features/billing/formatters.py
   - Stability: core/ (I=0.15), billing/ (I=0.78)
   - Suggestion: Extract format_invoice() to core/formatters.py

---

Which issues would you like me to address? Enter numbers (e.g., '1,3') or 'all':
```

---

## User Delegation

After presenting findings, ask the user which issues to address.

Based on their selection, take the appropriate action:

| Issue Type | Action |
|------------|--------|
| **[CYCLE]** | Extract function to shared module, create interface to break dependency, or suggest file relocation |
| **[INTERNAL]** | Show public API alternative, or extract internal code to shared module |
| **[STABILITY]** | Create abstraction layer, or move code to appropriate stability level |
| **[EXTRACT]** | Create new shared module with the extracted code, update all import sites |
| **[ABSTRACT]** | Create interface file in core/interfaces/, update all consumers to use interface |
| **[COUPLING]** | Propose module split with specific file assignments |
| **[COHESION]** | Propose module reorganization with new directory structure |

For each selected issue:
1. **Show the proposed change** with before/after structure
2. **List all files that will be affected**
3. **Wait for user confirmation** before making changes
4. **Execute the restructuring** systematically, updating all imports

Wait for user input before making any changes.
