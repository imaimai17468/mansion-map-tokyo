---
name: coding-guidelines
description: Provides React/Next.js component guidelines focusing on testability, colocation, and directory structure. Use when implementing components, refactoring code, organizing project structure, extracting conditional branches, or ensuring code quality standards.
---

# Coding Guidelines

Guidelines for React/Next.js development focusing on testability and proper architecture. Each guideline file contains principles, code examples, and anti-patterns to avoid.

---

## Quick Reference

- **Testability & Props Control** → [testability.md](testability.md)
- **useEffect Guidelines & Dependencies** → [useeffect-guidelines.md](useeffect-guidelines.md)
- **Architecture & Patterns** → [architecture.md](architecture.md)
- **Test Guidelines (Vitest/RTL)** → [test-guidelines.md](test-guidelines.md)

---

## When to Use What

### Testability

**When**: Writing "use client" components, useEffect, or event handlers
**Read**: [testability.md](testability.md)

Key topics:
- Props Control (all states controllable via props)
- Closure Variable Dependencies (extract to pure functions)
- Conditional Branch Extraction (JSX → components, useEffect → pure functions)

### useEffect Guidelines & Dependencies

**When**: Deciding whether to use useEffect, managing dependencies, or avoiding unnecessary re-renders
**Read**: [useeffect-guidelines.md](useeffect-guidelines.md)

Key topics:
- When you DON'T need useEffect (data transformation, expensive calculations)
- When you DO need useEffect (external system synchronization)
- Event handlers vs Effects decision framework
- Data fetching patterns and race conditions
- Separating reactive and non-reactive logic
- Managing dependencies (updater functions, useEffectEvent, avoiding objects/functions)
- Reactive values and dependency array rules
- Never suppress the exhaustive-deps linter

### Architecture

**When**: Creating files, functions, or organizing code structure
**Read**: [architecture.md](architecture.md)

Key topics:
- 🔥 Colocation First (everything next to what uses it)
- Directory Structure (kebab-case pages, PascalCase components)
- Data Fetching (queries.ts collocated with components)
- Function Extraction (pure functions, no closures)
- Presenter Pattern (conditional text)

### Test Guidelines

**When**: Creating or updating test code during Phase 2 (Testing & Stories)
**Read**: [test-guidelines.md](test-guidelines.md)

Key topics:
- AAA Pattern (Arrange-Act-Assert)
- Test Structure (describe/test descriptions in Japanese)
- Coverage Standards (branch coverage, exception paths)
- React Testing Library best practices
- Snapshot testing guidelines

---

## Core Principles

1. 🔥 **COLLOCATE EVERYTHING**: Code lives next to what uses it. NO `utils/`, `api/`, `services/`, `lib/`, `helpers/` directories
2. **Props Control Everything**: All UI states must be controllable via props for testability
3. **Pure Functions**: Extract all conditional logic from useEffect/handlers
4. **No Closure Dependencies**: Pass all variables as function arguments
