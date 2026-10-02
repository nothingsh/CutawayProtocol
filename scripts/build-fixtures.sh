#!/bin/bash
# Compiles every fixtures/src/**/*.json into <output-dir>/**/*.bin, and joins each
# scenario's frames into c2s.stream and s2c.stream: the exact bytes on the wire.
# Usage: build-fixtures.sh <output-dir>
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
protocol_root="$(cd "$script_dir/.." && pwd)"
out="${1:?usage: build-fixtures.sh <output-dir>}"
mkdir -p "$out"
out="$(cd "$out" && pwd)" # resolve before changing directory
flatc="$("$script_dir/get-flatc.sh")"

cd "$protocol_root/fixtures/src"
count=0
while IFS= read -r -d '' json; do
  dir="$(dirname "$json")"
  mkdir -p "$out/$dir"
  "$flatc" --binary --strict-json -o "$out/$dir" "$protocol_root/schema/cutaway.fbs" "$json"
  count=$((count + 1))
done < <(find . -name '*.json' -print0 | sort -z)

[[ "$count" -gt 0 ]] || { echo "build-fixtures: no fixture sources found" >&2; exit 1; }

/usr/bin/python3 - "$out" <<'PY'
import glob, os, struct, sys

out = sys.argv[1]
for scenario in sorted(os.listdir(out)):
    directory = os.path.join(out, scenario)
    if not os.path.isdir(directory):
        continue
    for direction in ("c2s", "s2c"):
        frames = sorted(glob.glob(os.path.join(directory, "[0-9][0-9]-%s-*.bin" % direction)))
        stream = os.path.join(directory, direction + ".stream")
        if not frames:
            if os.path.exists(stream):
                os.remove(stream)
            continue
        with open(stream, "wb") as handle:
            for path in frames:
                payload = open(path, "rb").read()
                handle.write(struct.pack("<I", len(payload)))
                handle.write(payload)
PY

echo "build-fixtures: compiled $count fixture(s) into $out"
