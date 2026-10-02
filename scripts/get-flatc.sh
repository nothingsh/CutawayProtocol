#!/bin/bash
# Installs the pinned flatc and prints its path.
# Usage: get-flatc.sh [destination-dir]   (default: <protocol repo>/.tools)
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
protocol_root="$(cd "$script_dir/.." && pwd)"
version="$(tr -d '[:space:]' <"$protocol_root/FLATBUFFERS_VERSION")"
dest="${1:-$protocol_root/.tools}"
flatc="$dest/flatc"

fail() {
  echo "get-flatc: $1" >&2
  exit 1
}

if [[ -x "$flatc" ]] && [[ "$("$flatc" --version)" == "flatc version $version" ]]; then
  echo "$flatc"
  exit 0
fi

case "$(uname -m)" in
  arm64) asset="Mac.flatc.binary.zip" ;;
  x86_64) asset="MacIntel.flatc.binary.zip" ;;
  *) fail "unsupported architecture $(uname -m)" ;;
esac

expected_sha="$(awk -v a="$asset" '$2 == a { print $1 }' "$protocol_root/FLATC_SHA256")"
[[ -n "$expected_sha" ]] || fail "no checksum for $asset in FLATC_SHA256"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

url="https://github.com/google/flatbuffers/releases/download/v$version/$asset"
curl --fail --location --silent --show-error -o "$work/flatc.zip" "$url" ||
  fail "download failed: $url"

actual_sha="$(shasum -a 256 "$work/flatc.zip" | awk '{ print $1 }')"
[[ "$actual_sha" == "$expected_sha" ]] ||
  fail "checksum mismatch for $asset: expected $expected_sha, got $actual_sha"

unzip -q "$work/flatc.zip" -d "$work"
[[ -f "$work/flatc" ]] || fail "archive does not contain flatc"

mkdir -p "$dest"
mv "$work/flatc" "$flatc"
chmod +x "$flatc"

actual_version="$("$flatc" --version)"
[[ "$actual_version" == "flatc version $version" ]] ||
  fail "installed flatc reports '$actual_version', expected 'flatc version $version'"

echo "$flatc"
