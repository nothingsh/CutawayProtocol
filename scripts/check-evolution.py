#!/usr/bin/env python3
"""Checks that a schema is an allowed evolution of a released one (PROTOCOL.md, P-EVO).

Usage: check-evolution.py <released.fbs> <released-version> <current.fbs> <current-version>

Versions look like MAJOR.MINOR. Rules:
  - A higher major version declares a breaking change. Only what the handshake
    needs is checked (P-EVO-05): the file identifier and the root type, the
    existing members of the handshake types, and the first members of Body.
  - Otherwise tables may only gain fields at the end; enums and unions may only
    gain members at the end; structs, the file identifier and the root type do
    not change; nothing is removed or renamed.
  - Any change to the schema needs a higher version.

flatc --conform checks field offsets only; this covers what it lets through.
"""

import re
import sys

# P-EVO-05: what a handshake, and an error sent around it, needs in every major version.
HANDSHAKE = ("Frame", "Hello", "Version", "Role", "ClientInfo", "AppInfo", "DeviceKind", "Size",
             "Error", "ErrorCode", "Body")
# Of these unions only a prefix is fixed: Body's members Hello to Error.
HANDSHAKE_PREFIX = {"Body": 10}


def parse(path):
    text = re.sub(r"//[^\n]*", "", open(path, encoding="utf-8").read())
    schema = {"decls": {}, "order": []}
    identifier = re.search(r'file_identifier\s+"([^"]*)"\s*;', text)
    root = re.search(r"root_type\s+(\w+)\s*;", text)
    schema["file_identifier"] = identifier.group(1) if identifier else None
    schema["root_type"] = root.group(1) if root else None
    for kind, name, base, body in re.findall(r"\b(struct|table|enum|union)\s+(\w+)\s*(?::\s*(\w+))?\s*\{([^}]*)\}", text):
        separator = ";" if kind in ("struct", "table") else ","
        members = []
        for raw in body.split(separator):
            member = " ".join(raw.split())
            if not member:
                continue
            member = re.sub(r"\s*\((?:[^()]*)\)\s*$", "", member)  # attributes such as (deprecated)
            members.append(re.sub(r"\s*([:=])\s*", r"\1", member))
        schema["decls"][name] = (kind, base, members)
        schema["order"].append(name)
    return schema


def version(text):
    match = re.fullmatch(r"(\d+)\.(\d+)", text.strip())
    if not match:
        sys.exit("check-evolution: version must look like MAJOR.MINOR, got %r" % text)
    return int(match.group(1)), int(match.group(2))


def compare(old, new, names=None, prefixes=None):
    problems = []
    if old["file_identifier"] != new["file_identifier"]:
        problems.append("file_identifier changed: %r -> %r" % (old["file_identifier"], new["file_identifier"]))
    if old["root_type"] != new["root_type"]:
        problems.append("root_type changed: %r -> %r" % (old["root_type"], new["root_type"]))
    for name in (names or old["order"]):
        if name not in old["decls"]:
            continue
        kind, base, members = old["decls"][name]
        if prefixes and name in prefixes:
            members = members[:prefixes[name]]
        if name not in new["decls"]:
            problems.append("%s %s was removed or renamed" % (kind, name))
            continue
        new_kind, new_base, new_members = new["decls"][name]
        if (kind, base) != (new_kind, new_base):
            problems.append("%s %s changed its kind or underlying type" % (kind, name))
            continue
        if kind == "struct":
            if members != new_members:
                problems.append("struct %s changed; structs never change" % name)
            continue
        if new_members[:len(members)] != members:
            for index, member in enumerate(members):
                found = new_members[index] if index < len(new_members) else None
                if found != member:
                    problems.append("%s %s: member %d was %r, now %r" % (kind, name, index + 1, member, found))
                    break
    return problems


def main():
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    old, new = parse(sys.argv[1]), parse(sys.argv[3])
    old_version, new_version = version(sys.argv[2]), version(sys.argv[4])
    changed = (old["decls"], old["file_identifier"], old["root_type"]) != (new["decls"], new["file_identifier"], new["root_type"])

    if new_version < old_version:
        sys.exit("check-evolution: version went backwards: %s -> %s" % (sys.argv[2], sys.argv[4]))

    if new_version[0] > old_version[0]:
        problems = compare(old, new, names=HANDSHAKE, prefixes=HANDSHAKE_PREFIX)
        if problems:
            print("check-evolution: what the handshake needs must not change in any major version (P-EVO-05):")
            for problem in problems:
                print("  - " + problem)
            sys.exit(1)
        print("check-evolution: major version changed (%s -> %s); breaking changes are declared" % (sys.argv[2], sys.argv[4]))
        return

    problems = compare(old, new)
    if problems:
        print("check-evolution: the schema is not an append-only evolution of %s:" % sys.argv[2])
        for problem in problems:
            print("  - " + problem)
        print("Fix the schema, or raise the major version in PROTOCOL_VERSION.")
        sys.exit(1)
    if changed and new_version == old_version:
        sys.exit("check-evolution: the schema changed but the version is still %s (P-EVO-03)" % sys.argv[2])
    print("check-evolution: ok (%s -> %s%s)" % (sys.argv[2], sys.argv[4], ", schema changed" if changed else ""))


if __name__ == "__main__":
    main()
