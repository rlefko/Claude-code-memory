---
description: Diagnose documentation quality issues (coverage, usefulness, freshness)
argument-hint: [count] [module-focus]
---

# Documentation Quality Analysis

You are analyzing this codebase for **documentation quality issues**. Find the top $1 issues (default: 3 if not specified).

**Module focus**: $2 (if specified, only analyze code related to this module/area)

**This command completes the tech debt diagnosis trilogy:**
| Command | Focus | Level |
|---------|-------|-------|
| /refactor | SOLID, DRY, orphaned code | Function/class |
| /restructure | Cycles, coupling, stability | Module/architecture |
| /redocument | Coverage, usefulness, freshness | Documentation |

**Priority order**: Undocumented Tier A > Stale docs > Missing contract > Missing error docs > Tautology > Unexplained suppressions

---

## Documentation Constitution (Core Principles)

1. **Public surfaces must be documented** with intent + contract
2. **Risky/complex code must explain** invariants/gotchas
3. **Docs must not lie** - drift is a failure
4. **Don't add noise** - comments explain "why", not "what"

---

## Scope Classification (Tier System)

### Tier A - FAIL if undocumented
Public/external surface area:
- Exported/public functions, methods, classes, interfaces
- Public modules/packages
- CLI commands, API endpoints
- Config schema keys, events/messages

### Tier B - WARN (FAIL if "non-obvious")
Shared internal reusable components:
- Referenced across multiple directories
- Imported by many modules
- In `core/`, `shared/`, `utils/`, `lib/` paths

### Tier C - INFO only
Local/private helpers and trivial glue code.

### "Non-obvious" Escalation Triggers
These bump requirements up a tier:
- Concurrency/async, locking, shared state
- Security/auth/permissions/crypto
- IO/network/retries/timeouts
- Parsing/serialization/regex-heavy
- Caching, memoization, precision/units
- High cyclomatic complexity / deep nesting

---

## Analysis Protocol

Execute this multi-phase analysis using the memory MCP tools available to you.

### Phase 0: Module Focus (if specified)

If a module focus was provided (e.g., "payments", "auth", "api"):

1. **Discover related entities**: Use `search_similar("$2", limit=50)` to find all code related to the module
2. **Map the module boundary**: Use `read_graph(entity="<top_match>", mode="relationships")` for key entities
3. **Scope limitation**: ALL subsequent analysis phases only consider entities discovered here

**If no module focus**: Analyze the entire codebase.

---

### Phase 1: Symbol Discovery & Classification

1. Use `read_graph(mode="entities")` to get all code entities
2. Classify each entity into Tier A/B/C:
   - **Tier A**: Check visibility (public/exported), look for `export`, `public`, `__all__`
   - **Tier B**: Check usage count via `read_graph(entity=X, mode="relationships")` - many importers = Tier B
   - **Tier C**: Private/local helpers (starts with `_`, not exported, single-file usage)
3. Apply "non-obvious" escalation triggers by searching for keywords:
   - `search_similar("async await threading lock", entityTypes=["function"])` for concurrency
   - `search_similar("auth permission crypto token", entityTypes=["function"])` for security
   - `search_similar("http request database query", entityTypes=["function"])` for IO

---

### Phase 2: Documentation Extraction

For each symbol identified:

1. Use `get_implementation(name, scope="logical")` to get the code
2. Parse for documentation based on language:
   - **Python**: Docstrings (triple quotes after def/class)
   - **JavaScript/TypeScript**: JSDoc comments (`/** ... */`)
   - **Other**: Block comments immediately preceding definition
3. Extract these elements if present:
   - Summary/intent (first sentence)
   - Parameters/arguments
   - Return value
   - Raises/throws (error conditions)
   - Side effects
   - Examples

---

### Phase 3: Coverage Analysis

**For each Tier A symbol, check:**
- [ ] Documentation exists (FAIL if missing)
- [ ] Intent is clear, not tautological (FAIL if "Gets X" for `get_x()`)
- [ ] Contract is documented (params, returns for functions)
- [ ] Error conditions documented (if code can throw/raise)
- [ ] Side effects documented (if code has IO/mutation)

**For each Tier B symbol, check:**
- [ ] Documentation exists (WARN, or FAIL if non-obvious trigger)
- [ ] At least summary + one of: invariants, gotchas, side effects

**Tier C**: INFO only - suggestions for improvement

---

### Phase 4: Usefulness Analysis

**Detect tautological docs:**
1. Tokenize symbol name: `get_user_by_id` → ["get", "user", "by", "id"]
2. Tokenize first doc sentence
3. Calculate overlap ratio
4. Flag if overlap > 70% with < 3 new meaningful words

**Examples of tautology to flag:**
- "Gets the value" for `get_value()`
- "Handles the request" for `handle_request()`
- "Helper function" (adds nothing)
- "Does the thing" (vague)

**Detect implementation narration:**
- Flag docs that describe steps ("First we loop, then we increment...")
- Without stating purpose, contract, or constraints

---

### Phase 5: Freshness/Drift Detection

**Parameter drift:**
1. Extract parameter names from function signature
2. Extract parameter names mentioned in docs (@param, Args:, etc.)
3. Flag mismatches:
   - Doc mentions param that doesn't exist → STALE
   - Signature has param not in docs → MISSING

**Error drift:**
1. Extract raised/thrown exception types from code
2. Extract "Raises:" or "Throws:" section from docs
3. Flag undocumented exceptions

---

### Phase 6: Suppression Audit

Search for suppression patterns and check for explanations:

**Python:**
- `# type: ignore` - requires explanation
- `# noqa` - requires explanation
- `# nosec` - requires explanation
- `# pylint: disable` - requires explanation

**JavaScript/TypeScript:**
- `// @ts-ignore` - requires explanation
- `// @ts-expect-error` - requires explanation
- `// eslint-disable` - requires explanation

**Rust:**
- `unsafe {}` - requires explanation
- `#[allow(...)]` - requires explanation

**Rule**: If you suppress a safety check, you must explain why in an adjacent comment.

---

## Issue Categories

Report findings using these categories:

### [UNDOC] - Missing Documentation
```
[UNDOC] Tier A: Public function lacks documentation
Symbol: process_payment() in payments/service.py:45
Visibility: Exported (public API)
Complexity: High (async, network IO, error handling)
Suggestion: Add docstring with intent, parameters, return value, and error conditions
```

### [INTENT] - Missing Intent/Purpose
```
[INTENT] Documentation lacks clear purpose statement
Symbol: UserValidator class in auth/validators.py:12
Current: "Validator for users"
Problem: Tautological - restates the name without adding value
Suggestion: Describe WHAT it validates, WHY, and key validation rules
```

### [CONTRACT] - Missing Contract Details
```
[CONTRACT] Function docs missing parameter/return info
Symbol: calculate_discount(user, cart, promo_code) in orders/pricing.py:89
Missing: Parameter descriptions, return type, valid ranges
Suggestion: Document each parameter's purpose and constraints
```

### [SIDEEFFECT] - Undocumented Side Effects
```
[SIDEEFFECT] Side effects not documented
Symbol: sync_inventory() in warehouse/sync.py:156
Detected: Database writes, external API calls, logging
Problem: Caller unaware of mutations and external dependencies
Suggestion: Document "Modifies: inventory table" and "Calls: warehouse API"
```

### [ERROR] - Missing Error Documentation
```
[ERROR] Error conditions not documented
Symbol: authenticate_user() in auth/service.py:34
Detected throws: AuthenticationError, RateLimitError, NetworkError
Problem: Callers don't know what to catch
Suggestion: Add "Raises:" section listing possible exceptions
```

### [STALE] - Stale/Drifted Documentation
```
[STALE] Documentation references non-existent parameter
Symbol: send_notification(user_id, message, priority) in notify/sender.py:67
Doc mentions: "channel" parameter (removed)
Problem: Misleading documentation causes confusion
Suggestion: Remove reference to "channel", add "priority" documentation
```

### [TAUTOLOGY] - Low-Value Documentation
```
[TAUTOLOGY] Documentation restates code without adding value
Symbol: get_user_by_id() in users/repository.py:23
Current: "Gets a user by their ID"
Problem: Says nothing the function name doesn't already say
Suggestion: Explain return behavior (None vs exception), caching, etc.
```

### [SUPPRESS] - Unexplained Suppressions
```
[SUPPRESS] Safety suppression without explanation
Symbol: data_processing() in utils/parser.py:89
Suppression: # type: ignore
Problem: Future maintainers don't know why safety was bypassed
Suggestion: Add comment explaining why suppression is safe here
```

---

## Output Format

Present your findings as:

```
## Documentation Quality Analysis

**Scope**: [Entire codebase | Focus: $2]
**Symbols analyzed**: N
**Tier A coverage**: X% (Y/Z documented)
**Tier B coverage**: X% (Y/Z documented)

---

**Documentation Issues Found:**

1. **[UNDOC]** `process_payment()` - Tier A public function undocumented
   - Location: payments/service.py:45
   - Visibility: Exported, used by 12 files
   - Complexity: High (async, network, error handling)
   - Suggestion: Add docstring with intent, params, returns, raises

2. **[STALE]** `send_notification()` - Parameter mismatch
   - Location: notify/sender.py:67
   - Doc mentions: "channel" (doesn't exist)
   - Missing from docs: "priority" (new param)
   - Suggestion: Update parameter documentation

3. **[TAUTOLOGY]** `get_user_by_id()` - Low-value documentation
   - Location: users/repository.py:23
   - Current: "Gets a user by their ID"
   - Problem: Restates name, adds no information
   - Suggestion: Document return behavior, caching, error cases

---

Which issues would you like me to address? Enter numbers (e.g., '1,3') or 'all':
```

---

## User Delegation

After presenting findings, ask the user which issues to address.

Based on their selection, take the appropriate action:

| Issue Type | Action |
|------------|--------|
| **[UNDOC]** | Generate documentation template with inferred intent/params/returns based on code analysis |
| **[INTENT]** | Rewrite summary to describe purpose, not restate the symbol name |
| **[CONTRACT]** | Add parameter descriptions, return value documentation, type hints |
| **[SIDEEFFECT]** | Add "Side Effects:" or "Modifies:" section documenting mutations and IO |
| **[ERROR]** | Add "Raises:" or "Throws:" section listing exception types and conditions |
| **[STALE]** | Update docs to match current signature, remove obsolete references |
| **[TAUTOLOGY]** | Rewrite to add useful information (behavior, edge cases, performance) |
| **[SUPPRESS]** | Add inline comment explaining why the suppression is safe/necessary |

For each selected issue:
1. **Analyze the code** to understand what documentation should say
2. **Generate appropriate documentation** in the idiomatic format for the language
3. **Show the proposed change** with before/after
4. **Wait for user confirmation** before making changes

Wait for user input before making any changes.
