#!/bin/bash
# Tests for check-evolution.py: each case mutates a copy of the schema and
# states whether the check must pass or fail.
set -eo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
schema="$script_dir/../schema/cutaway.fbs"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
failures=0
passes=0

mutate() { # python expression over the schema text `s`, result written to $work/new.fbs
  # The expression is evaluated with eval(). That is safe here: every expression
  # is a literal written in this file, never input from outside.
  /usr/bin/python3 - "$schema" "$work/new.fbs" "$1" <<'PY'
import re, sys
s = open(sys.argv[1], encoding="utf-8").read()
before = s
s = eval(sys.argv[3])
if s == before and sys.argv[3] != "s":
    sys.exit("mutation changed nothing: " + sys.argv[3])
open(sys.argv[2], "w", encoding="utf-8").write(s)
PY
}

expect() { # name, pass|fail, mutation, new version
  mutate "$3"
  local result="pass"
  /usr/bin/python3 "$script_dir/check-evolution.py" "$schema" 0.1 "$work/new.fbs" "$4" >"$work/out.txt" 2>&1 || result="fail"
  if [[ "$result" == "$2" ]]; then
    passes=$((passes + 1))
  else
    echo "FAIL $1: expected $2, got $result"
    sed 's/^/     /' "$work/out.txt"
    failures=$((failures + 1))
  fi
}

expect "identical, same version"            pass 's' 0.1
expect "append a table field, minor bump"   pass 're.sub(r"(table LayerNode \{[^}]*)\}", r"\1  corner_radius: double;\n}", s)' 0.2
expect "append a table field, no bump"      fail 're.sub(r"(table LayerNode \{[^}]*)\}", r"\1  corner_radius: double;\n}", s)' 0.1
expect "append an enum value, minor bump"   pass 's.replace("  NotSupported = 9", "  NotSupported = 9,\n  Cancelled = 10")' 0.2
expect "append a union member, minor bump"  pass 's.replace("WatchHierarchy, WatchHierarchyResult, HierarchyChanged\n}", "WatchHierarchy, WatchHierarchyResult, HierarchyChanged, GetAppIcon2\n}").replace("table GetAppIcon {}", "table GetAppIcon {}\ntable GetAppIcon2 {}")' 0.2
expect "deprecate a field, minor bump"      pass 's.replace("  z_position: double;", "  z_position: double (deprecated);")' 0.2

expect "remove a table field"               fail 's.replace("  hidden: bool;\n", "")' 0.2
expect "rename a table field"               fail 's.replace("  hidden: bool;", "  is_hidden: bool;")' 0.2
expect "change a field type"                fail 's.replace("  opacity: float;", "  opacity: double;")' 0.2
expect "insert a field in the middle"       fail 's.replace("  hidden: bool;", "  corner_radius: double;\n  hidden: bool;")' 0.2
expect "append to a struct"                 fail 's.replace("struct Point { x: double; y: double; }", "struct Point { x: double; y: double; z: double; }")' 0.2
expect "remove the last enum value"         fail 's.replace("enum DeviceKind : ubyte { Unknown = 0, Phone = 1, Pad = 2, Mac = 3 }", "enum DeviceKind : ubyte { Unknown = 0, Phone = 1, Pad = 2 }")' 0.2
expect "insert an enum value in the middle" fail 's.replace("Phone = 1, Pad = 2, Mac = 3", "Phone = 1, Watch = 4, Pad = 2, Mac = 3")' 0.2
expect "renumber an enum value"             fail 's.replace("Pad = 2, Mac = 3", "Pad = 3, Mac = 2")' 0.2
expect "change an enum underlying type"     fail 's.replace("enum Role : ubyte", "enum Role : ushort")' 0.2
expect "remove the last union member"       fail 's.replace("WatchHierarchy, WatchHierarchyResult, HierarchyChanged\n}", "WatchHierarchy, WatchHierarchyResult\n}")' 0.2
expect "remove a table"                     fail 's.replace("table GetAppIcon {}\n", "").replace("Hello, GetAppIcon, AppIcon", "Hello, AppIcon")' 0.2
expect "change the file identifier"         fail 's.replace("file_identifier \"CTWY\";", "file_identifier \"XXXX\";")' 0.2
expect "change the root type"               fail 's.replace("root_type Frame;", "root_type Hello;")' 0.2
expect "version goes backwards"             fail 's' 0.0

expect "breaking change with a major bump"  pass 's.replace("  hidden: bool;\n", "")' 1.0
expect "major bump that breaks the handshake" fail 's.replace("  role: Role;\n", "")' 1.0
expect "major bump that moves Hello in Body"  fail 's.replace("Hello, GetAppIcon, AppIcon", "GetAppIcon, Hello, AppIcon")' 1.0
expect "major bump that drops a message before Error" fail 's.replace("StreamEnd, Cancel, Error,", "StreamEnd, Error,")' 1.0
expect "major bump that changes AppInfo"     fail 's.replace("  bundle_id: string;", "  bundle_id: [ubyte];")' 1.0
expect "major bump that renumbers an error code" fail 's.replace("  Busy = 3,", "  Busy = 9,")' 1.0
expect "major bump that changes the file identifier" fail 's.replace("file_identifier \"CTWY\";", "file_identifier \"XXXX\";")' 1.0
expect "major bump that changes the root type" fail 's.replace("root_type Frame;", "root_type Hello;")' 1.0
expect "major bump that changes Body after Error" pass 's.replace("Cancel, Error, AppStateChanged,", "Cancel, Error,")' 1.0
expect "major bump that appends to AppInfo"  pass 're.sub(r"(table AppInfo \{[^}]*)\}", r"\1  locale: string;\n}", s)' 1.0

echo "$passes passed, $failures failed"
[[ "$failures" -eq 0 ]] || exit 1
echo "all evolution cases passed"
