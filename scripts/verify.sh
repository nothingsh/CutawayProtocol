#!/bin/bash
# The single acceptance gate for this repository.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

step() { printf '\n== %s\n' "$1"; }
fail() {
  echo "verify: FAILED: $1" >&2
  exit 1
}

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

step "pinned flatc"
flatc="$(scripts/get-flatc.sh)" || fail "could not install the pinned flatc"
"$flatc" --version

step "schema compiles to Swift"
"$flatc" --swift --gen-object-api -o "$work/swift" schema/cutaway.fbs ||
  fail "schema does not compile"

step "fixtures match their sources"
scripts/build-fixtures.sh "$work/fixtures" || fail "fixtures do not build"
diff -r "$work/fixtures" fixtures/bin ||
  fail "fixtures/bin is out of date; run: scripts/build-fixtures.sh fixtures/bin"

step "fixtures obey the protocol"
scripts/check-fixtures.py fixtures/src || fail "fixtures violate the protocol"

step "protocol version is consistent"
version="$(tr -d '[:space:]' <PROTOCOL_VERSION)"
[[ "$version" =~ ^[0-9]+\.[0-9]+$ ]] || fail "PROTOCOL_VERSION must look like MAJOR.MINOR"
grep -q "^Protocol version: $version\$" PROTOCOL.md ||
  fail "PROTOCOL.md does not state version $version"
echo "protocol $version"

step "schema evolution"
scripts/test-check-evolution.sh >"$work/evolution.log" 2>&1 || {
  cat "$work/evolution.log"
  fail "evolution checker tests"
}
tail -1 "$work/evolution.log"
released="$(ls schema/released/v*.fbs 2>/dev/null | sort -t v -k 2 -V | tail -1)"
[[ -n "$released" ]] || fail "schema/released/ holds no released schema to compare against"
released_version="$(basename "$released" .fbs)"
released_version="${released_version#v}"
scripts/check-evolution.py "$released" "$released_version" schema/cutaway.fbs "$version" ||
  fail "schema evolution"
if [[ "${released_version%%.*}" == "${version%%.*}" ]]; then
  "$flatc" --conform "$released" schema/cutaway.fbs ||
    fail "flatc --conform: field offsets changed since $released_version"
fi
[[ -f "schema/released/v$version.fbs" ]] ||
  echo "note: version $version is not released yet (no schema/released/v$version.fbs)"

printf '\nverify: OK\n'
