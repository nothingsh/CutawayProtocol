<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="Resources/readme/cutaway-protocol-dark.svg">
    <img src="Resources/readme/cutaway-protocol-light.svg" alt="CutawayProtocol — The shared language of client and server." width="850">
  </picture>
</p>

[![FlatBuffers](https://img.shields.io/badge/FlatBuffers-schema-blue)](schema/cutaway.fbs)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

**English** | [简体中文](Resources/readme/README.zh-Hans.md) | [繁體中文](Resources/readme/README.zh-Hant.md) | [日本語](Resources/readme/README.ja.md) | [한국어](Resources/readme/README.ko.md) | [Español](Resources/readme/README.es.md) | [Français](Resources/readme/README.fr.md) | [Deutsch](Resources/readme/README.de.md)

# Cutaway Protocol

The wire protocol between **CutawayServer**, an iOS SDK embedded in the app being inspected, and **Cutaway**, a macOS app. Cutaway connects to the server over TCP and retrieves the app's layer hierarchy, screenshots, attributes and Auto Layout constraints, and can modify attributes while the app runs.

This repository is the single source of truth for that protocol. It contains no Swift code: both ends pin a tag of this repository as a git submodule and generate their code from the schema.

## Contents

| Path | What it is |
|---|---|
| `PROTOCOL.md` | The normative specification. Numbered clauses (`P-TRANS-01`, `P-FRAME-03`, …) are requirements; everything else is explanation. |
| `schema/cutaway.fbs` | The [FlatBuffers](https://flatbuffers.dev) schema. Every frame's payload is a `Frame` defined here. |
| `schema/released/` | A snapshot of the schema for every released `MAJOR.MINOR`. Never edited after release. |
| `fixtures/` | Reference frames for testing an implementation. `src/` holds JSON sources, `bin/` the compiled buffers and the exact bytes on the wire. See `fixtures/README.md`. |
| `scripts/` | `verify.sh` is the acceptance gate for this repository. The other scripts build fixtures and check schema evolution. |
| `PROTOCOL_VERSION` | The current protocol version, `MAJOR.MINOR`. |
| `FLATBUFFERS_VERSION`, `FLATC_SHA256` | The pinned `flatc` release and the checksum of its macOS binary. |

## The protocol at a glance

- **Transport.** The server listens on TCP, loopback only, trying ports 48160 through 48167 in order. A simulator shares the Mac's loopback; a USB-connected device is reached through macOS's usbmuxd, which the server knows nothing about. One client at a time.
- **Framing.** A frame is a 4-byte little-endian length `N` followed by `N` bytes holding one ordinary FlatBuffer with root type `Frame` and file identifier `CTWY`. This is **not** FlatBuffers' size-prefixed format; the `.stream` fixtures show the exact bytes. `N` may not exceed 256 MiB, and a receiver verifies the whole buffer before reading any field.
- **Handshake.** The client's first frame is `Hello`; the server always answers with its own `Hello`. Major versions must match, or both sides close. When minor versions differ, both sides work at the lower one.
- **Requests.** The client assigns a monotonically increasing `request_id`. Ordinary requests (`GetAppIcon`, `GetHierarchy`, `GetSubtree`, `SetAttribute`) get exactly one response. `GetLayerDetails` is a stream: zero or more `LayerDetailsChunk` frames, then one `StreamEnd`. `Cancel` ends a stream early and has no response of its own. The server handles requests in order.
- **Events.** The server sends `AppStateChanged` with `request_id` 0 after the handshake and whenever the app's active state changes.
- **Errors.** `Error` carries a stable `ErrorCode` and a human-readable message. Clients branch on the code, never on the text.

Every rule above is a clause in `PROTOCOL.md`; this list is only an orientation.

## Versioning and evolution

The protocol version is `MAJOR.MINOR` in `PROTOCOL_VERSION`; releases are tagged `vMAJOR.MINOR.PATCH`. The schema evolves by appending only: fields at the end of tables, members at the end of enums and unions. Structs, the file identifier and the root type never change. Anything else is a major version bump. A `PATCH` release changes wording or fixtures without touching the schema. The full rules are the `P-EVO` clauses in `PROTOCOL.md`.

The protocol is currently **0.x and not yet frozen**. Freezing it as 1.0 will be a major version bump: a 0.x peer and a 1.x peer will fail the handshake by design.

## Implementing a peer

1. Read `PROTOCOL.md` end to end. The clauses are short and cross-referenced.
2. Generate code from `schema/cutaway.fbs` with the pinned `flatc` (see `FLATBUFFERS_VERSION`). `scripts/get-flatc.sh` downloads that exact release into `.tools/`.
3. Test against `fixtures/bin/`. Each `.bin` is one buffer for testing decoding; each `.stream` is one direction of a whole scenario for testing framing. Remember that `flatc` omits fields equal to their default, so a decoder reads them back as 0, false or the enum's first member.
4. Raise the FlatBuffers verifier's table limit if your runtime has one: the protocol allows frames with far more tables than most defaults (`P-FRAME-06`).

## Verifying this repository

```bash
scripts/verify.sh
```

It downloads the pinned `flatc`, compiles the schema, rebuilds every fixture and compares the result with `fixtures/bin/`, checks the fixtures against the clauses the schema cannot express, and checks that the current schema is an allowed evolution of the latest released snapshot. It needs `bash`, `curl` and `python3`, and runs on macOS only: the fixture checks decompress images with `compression_tool`, and `get-flatc.sh` downloads the macOS build of `flatc`.

After editing `fixtures/src/` or the schema:

```bash
scripts/build-fixtures.sh fixtures/bin
```

## License

MIT. See `LICENSE`.
