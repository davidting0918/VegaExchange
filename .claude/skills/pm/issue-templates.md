# Issue Templates for VegaExchange

## Standard Issue Template

All issues MUST follow this format:

```markdown
## Summary (故事線)
<!-- 1-3 sentences explaining WHAT this issue addresses and WHY it matters.
     Written for someone who doesn't know the codebase. -->

[Brief storyline: what problem exists, what change is needed, and what outcome we expect]

## Technical Details (技術細節)
<!-- Concrete technical changes needed. Be specific about files, functions, patterns. -->

### What needs to change
- [ ] [Specific technical change 1]
- [ ] [Specific technical change 2]
- [ ] [Specific technical change 3]

### Affected components
- **Backend**: [files/modules affected]
- **Frontend**: [components/pages affected]
- **Database**: [schema changes if any]
- **Engine**: [engine modifications if any]

### Technical considerations
<!-- Edge cases, performance concerns, compatibility notes -->
- [Consideration 1]
- [Consideration 2]

## Acceptance Criteria (驗收標準)
- [ ] [Testable criterion 1]
- [ ] [Testable criterion 2]
- [ ] [Testable criterion 3]

## References (參考)
<!-- Links to docs, similar implementations in other exchanges, related issues -->
- [Reference 1]
```

## Feature Issue Template

For new features, extend the standard template with:

```markdown
## Summary (故事線)
[storyline]

## Motivation (動機)
<!-- Why this feature? What user problem does it solve?
     Reference real exchange behavior if applicable. -->

### Real-world reference
- **CEX examples**: [How Binance/OKX/Bybit implements this]
- **DEX examples**: [How Uniswap/dYdX/GMX implements this]

## Technical Details (技術細節)
[same as standard]

## Design Decisions (設計決策)
<!-- Key architectural choices and why -->
| Decision | Choice | Rationale |
|----------|--------|-----------|
| [Decision 1] | [Choice] | [Why] |

## Acceptance Criteria (驗收標準)
[same as standard]

## Dependencies (依賴)
<!-- Issues or milestones that must be completed first -->
- Depends on: #[issue-number]
- Blocks: #[issue-number]
```

## Bug Issue Template

```markdown
## Summary (故事線)
[What's broken and what impact it has]

## Steps to Reproduce (重現步驟)
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Expected Behavior (預期行為)
[What should happen]

## Actual Behavior (實際行為)
[What actually happens]

## Technical Details (技術細節)
### Root cause analysis
[Analysis of why the bug occurs]

### Fix approach
- [ ] [Specific fix 1]
- [ ] [Specific fix 2]

## Acceptance Criteria (驗收標準)
- [ ] Bug no longer reproducible
- [ ] [Additional criteria]
```

## Refactor Issue Template

```markdown
## Summary (故事線)
[What's being refactored and why — not just "clean up code"]

## Current State (現狀)
[What the code looks like now and why it's problematic]

## Target State (目標狀態)
[What the code should look like after refactoring]

## Technical Details (技術細節)
### Changes needed
- [ ] [Change 1]
- [ ] [Change 2]

### Risk assessment
- **Breaking changes**: [Yes/No — what might break]
- **Migration needed**: [Yes/No — data migration details]
- **Rollback plan**: [How to revert if needed]

## Acceptance Criteria (驗收標準)
- [ ] All existing tests pass
- [ ] No behavior change (unless intentional)
- [ ] [Additional criteria]
```

## Research / Spike Issue Template

```markdown
## Summary (故事線)
[What we're investigating and why]

## Research Questions (研究問題)
1. [Question 1]
2. [Question 2]
3. [Question 3]

## Scope (範圍)
- **Time-box**: [e.g., 2 days]
- **Deliverable**: [e.g., decision document, prototype, benchmark results]

## Context (背景)
### Industry references
- [How other exchanges solve this]
- [Relevant papers or articles]

## Expected Output (預期產出)
- [ ] [Deliverable 1]
- [ ] [Deliverable 2]
```
