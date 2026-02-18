---
alwaysApply: false
---

# Adding a feature

When you want to add a new feature to the CLI, you should take the following steps:

1. Begin by making updates to the [spec](../../spec/index.md) so that the feature is described well in English
2. Implement the feature to align with the spec, writing unit tests for any pure functions as you go
3. Check that the tests pass and fix any problems
4. If a new command was added, or a change was made that would alter the behavior of a command, make sure to update the golden file tests
