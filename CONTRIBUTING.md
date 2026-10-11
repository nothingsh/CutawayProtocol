# Contributing to the Cutaway protocol

Thanks for helping. This page says where changes go and how they are reviewed. How the protocol
evolves is in [Versioning and evolution](README.md#versioning-and-evolution) in the README and in
the `P-EVO` clauses of `PROTOCOL.md`.

## Branches

- `main` is the only long-lived branch. Releases are tags `vMAJOR.MINOR.PATCH` on `main`.
- Open pull requests against `main`.

## Issues and planning

- Propose a new message, field, enum value or behavior with the "Protocol change proposal"
  template, and agree on it in the issue before opening a pull request.
- Report unclear or contradictory clauses with "Specification issue", and problems with fixtures
  or scripts with "Fixture or tooling bug".
- Each protocol version is a milestone. An issue in a milestone is planned for that version; an
  issue without one is not scheduled yet.
- The `breaking` label marks a change that needs a new major version. Since 1.0 the schema only
  grows by appending, so such a change needs a strong reason.

## Pull requests

- Keep one change per pull request and link the issue it resolves, e.g. "Closes #12".
- Use a [Conventional Commits](https://www.conventionalcommits.org/) prefix in the title, e.g.
  `feat: ...`, `fix: ...`, `docs: ...`.
- Run `scripts/verify.sh` and say in the pull request that it passes. There is no CI in this
  repository, so this is the check.
- The maintainer reviews every change. History is linear: pull requests are merged by rebase, so
  rebase onto `main` rather than merging it in.
