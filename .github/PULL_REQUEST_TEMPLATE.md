## Summary

<!-- What this changes and why. Link the issue it resolves, e.g. "Closes #12". -->

## Kind of change

- [ ] Schema change (append only, minor version)
- [ ] Breaking schema change (major version)
- [ ] Normative clause change, no schema change (version per P-EVO-08)
- [ ] Wording or explanation only (patch)
- [ ] Fixtures only
- [ ] Scripts or tooling
- [ ] README or other non-normative docs

## Checklist

- [ ] A schema change comes with the matching clauses in `PROTOCOL.md` and fixtures.
- [ ] New schema content is covered by at least one fixture, and `fixtures/README.md` is updated.
- [ ] Fixtures are rebuilt with `scripts/build-fixtures.sh fixtures/bin`.
- [ ] `PROTOCOL_VERSION` and the `Protocol version: X.Y` line in `PROTOCOL.md` are updated when the version changes.
- [ ] Existing clause numbers are not reused or renumbered.
- [ ] `scripts/verify.sh` passes.

## Impact on peers

<!-- What CutawayServer and Cutaway need to change, if anything. For a major version bump, the impact on Cutaway's archives and on released servers (P-EVO-04). -->
