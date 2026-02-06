# VS Code Codex · Skills Usage (Ultra-Compact)
统一采用 UTF-8（无 BOM）编码，禁止使用特殊符号、Emoji、全角字符与非标准引号，所有配置与规则文件仅允许 ASCII 可见字符。



Scope: VS Code Codex.  
Purpose: describe skill usage only. No agents, roles, or restrictions.

Skills are callable capability units. They can be invoked at any time, reused, chained, and combined.

Skill discovery paths:
.ai/skills/  
.vscode/ai/skills/  
codex/skills/

Invocation flow:
analyze context → select capability → invoke skill → continue with result

Confirmed skill set:

Execution & Change:
filesystem, exec, process, git, fetch

Testing & Verification:
test-runner, regression-guard, negative-test-required, final-verification-gate

State & Consistency:
state-minimization, invariant-check, source-of-truth-lock, config-drift-detect, deterministic-ordering

Pre/Post Conditions:
precondition-assert, postcondition-assert, read-before-write, write-after-verify

Risk & Impact:
change-impact-scan, blast-radius-limit, data-loss-prevention, noop-on-unknown, fast-fail-on-ambiguity

Execution Stability:
atomic-change-set, idempotent-operations, bounded-retries, strict-time-bounds

Permissions & Audit:
permission-scope-limit, minimal-permissions, audit-evidence-required, immutable-artifacts

Output & Contract:
output-schema-lock, schema-diff-guard, contract-first

Skills may be called sequentially or repeatedly; outputs may feed subsequent skills.

New skills are added by placing them in a skills directory and are auto-detected.

Output format and length are task-defined, unconstrained.
