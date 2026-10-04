# Fixtures

The fixtures are a set of reference frames that conform to the protocol. Each side uses them to verify its own implementation: the frames a Server produces should match the structure of the corresponding scenario; a Client should be able to decode and correctly handle every scenario. The Client's MockServer replays these frames scenario by scenario.

## Layout and file names

```
fixtures/
├── src/<scenario>/NN-<direction>-<name>.json    Sources, maintained by hand
└── bin/<scenario>/
    ├── NN-<direction>-<name>.bin                Generated from the sources by flatc, checked in
    ├── c2s.stream                               Every frame the Client sends in the scenario, the exact bytes on the wire
    └── s2c.stream                               Every frame the Server sends in the scenario, the exact bytes on the wire
```

- `NN` is a two-digit sequence number. Within a scenario, sorting by file name gives the order of the frames.
- The direction is `c2s` (Client to Server) or `s2c` (Server to Client).
- Each `.json` and `.bin` is one `Frame`.

## Two kinds of binary file

- **`.bin`** is an ordinary FlatBuffer with no length prefix, with file identifier `CTWY`. It is for testing "decode one buffer".
- **`.stream`** is the frames of one direction joined in order, each preceded by a 4-byte little-endian length (P-FRAME-01 in `PROTOCOL.md`). It is exactly the bytes in that direction of the TCP connection, for testing "split frames out of a byte stream".

`.stream` pins down the wire format: the length is followed by an ordinary buffer, not FlatBuffers' own size-prefixed buffer.

`flatc` does not write fields equal to their defaults. After decoding, those fields read as their defaults: 0 for numbers, false for booleans, the first member for enums.

## `request_id` when replaying

A `request_id` in the fixtures only shows which frames in a scenario belong together; the value itself has no meaning. A replayer (for example the MockServer) should not require the Client to use the same values: it matches the requests it receives by message type and order, decodes the corresponding response in the scenario, replaces its `request_id` with the one the Client actually used, and encodes it again before sending. Frames with `request_id` 0 are sent as they are.

## Regenerating

After changing `src/` or the schema:

```bash
scripts/build-fixtures.sh fixtures/bin
```

`scripts/verify.sh` regenerates them and compares the result with `bin/`, failing on any difference; it also uses `scripts/check-fixtures.py` to check the fixtures against the clauses the schema cannot express (sequence numbers, chunk counts, how responses match requests, image sizes). Do not edit the files under `bin/` by hand.

## Scenarios

| Scenario | Content | Clauses verified |
|---|---|---|
| `handshake` | A successful handshake, after which the Server sends the current state | P-HELLO-01, 02; P-EVT-01, 02 |
| `handshake-version-mismatch` | The Client's major version is 1; the Server still replies with its own `Hello` (0.2), then closes the connection | P-HELLO-02, 03 |
| `busy` | The only frame received when connecting to a Server that already has a Client | P-TRANS-03 |
| `app-icon` | Getting the app icon | P-REQ-02; P-ICON-01; P-IMG-01 |
| `hierarchy` | A hierarchy of one window and nine nodes, with view controllers and member variables | P-HIER-01 to 04, 06 to 09 |
| `layer-details` | Details of three layers in two chunks, ending normally | P-REQ-03; P-DET-01, 02, 04, 07; P-ATTR-01, 02 |
| `layer-details-edge` | An omitted solo, an image with row padding, a failed capture with attributes, a request that wants nothing | P-DET-03, 04; P-IMG-02 |
| `layer-details-cancelled` | A details stream cancelled after its first chunk | P-REQ-01, 04, 06 |
| `app-not-active` | Requesting the hierarchy after the app goes to the background | P-APP-01; P-REQ-05 |
| `layer-details-failed` | The app leaves the active state while a details stream is in progress | P-APP-01; P-EVT-02; P-REQ-05 |

Clauses no fixture covers: in P-HIER-01, the ordering of siblings with different `zPosition` (it is already done on the wire; a fixture can only give the result, not the `sublayers` before sorting); P-HIER-05 and P-ATTR-05 (non-finite numbers sent as 0); P-HELLO-04 (a handshake with different minor versions); P-IMG-03 (`scale` is nominal); P-DET-05 and P-DET-08 (scaling down oversized images); P-DET-06 (the chunk size limit); P-FRAME-03 (malformed frames); P-HELLO-05, 06 and P-REQ-08. These rely on each side's own tests.

## Nodes of the `hierarchy` scenario

| ID | Parent | Layer class | View class | bounds (x, y, width, height) | position | Notable |
|---|---|---|---|---|---|---|
| 1 | 0 | `UIWindowLayer` | `UIWindow` | 0, 0, 393, 852 | 196.5, 426 | The window's root layer |
| 2 | 1 | `CALayer` | `UIView` | 0, 0, 393, 852 | 196.5, 426 | |
| 3 | 2 | `_UILabelLayer` | `UILabel` | 0, 0, 200, 24 | 196.5, 120 | |
| 4 | 2 | `CALayer` | `Demo.CardView` | 0, 0, 300, 180 | 196.5, 300 | Rotated 30° about the z axis; clips its sublayers; the view's readable class name is `CardView` |
| 5 | 4 | `CAShapeLayer` | None | 0, 0, 40, 40 | 40, 40 | Hidden; opacity 0.5; does not back a view |
| 6 | 2 | `CALayer` | `UIScrollView` | 0, 100, 300, 200 | 196.5, 600 | Non-zero `bounds.origin`: scrolled down 100 points; clips its sublayers |
| 7 | 6 | `_UILabelLayer` | `UILabel` | 0, 0, 100, 40 | 150, 150 | Inside the scrolled content, affected by the parent's `bounds.origin` |
| 8 | 2 | `CALayer` | None | 0, 0, 60, 30 | 10, 10 | `anchor_point` 0, 0 |
| 9 | 2 | `CALayer` | `UIView` | 0, 0, 0, 0 | 300, 700 | Zero size |

Except for node 8, `anchor_point` is 0.5, 0.5. In node 4's `transform`, m11 = m22 = 0.8660254037844387, m12 = 0.5, m21 = -0.5, and the rest is the same as the identity matrix. The other nodes' `transform` is the identity matrix.

### View controllers and member variables (0.2)

Node 2 backs the root view of the view controller `Demo.HomeViewController` (readable class name `HomeViewController`) (P-HIER-07); no other node has the view controller fields.

| Node | `member_references` (readable name of the declaring class . variable name, nearest first) | Notes |
|---|---|---|
| 3 | `HomeViewController.titleLabel` | The holder is the view controller of ancestor node 2 |
| 4 | `HomeViewController.cardView` | |
| 5 | `CardView.badgeLayer`, `HomeViewController.cardBadge` | Two entries: the view of parent node 4 is nearer than the view controller of node 2; node 5 does not back a view, so the layer itself is referenced |
| 6 | `HomeViewController.scrollView` | |
| 8 | `DMBaseViewController._dividerLayer` | An Objective-C instance variable, underscore kept (P-HIER-09); it is declared by the superclass of `HomeViewController`, so its runtime class name differs from every ancestor's class names |

Nodes 1, 2, 7 and 9 have no `member_references`. The runtime class names of the entries: `HomeViewController` is `Demo.HomeViewController`, `CardView` is `Demo.CardView`, and `DMBaseViewController` is the same in both.

## Images

The image in the icon scenario is 2×2 pixels, with `bytes_per_row` 8 and `scale` 1. The 16 bytes after decompression, in rows from top to bottom:

| Position | Color | Bytes (B G R A) |
|---|---|---|
| Top left | Opaque red | `00 00 FF FF` |
| Top right | Opaque green | `00 FF 00 FF` |
| Bottom left | Opaque blue | `FF 00 00 FF` |
| Bottom right | Fully transparent | `00 00 00 00` |

The images in layer details are all single-colored, with `scale` 1 and a pixel size equal to the layer's `bounds` size (P-DET-07):

| Scenario | Layer | Image | Pixel size | Bytes of every pixel (B G R A) |
|---|---|---|---|---|
| `layer-details`, `layer-details-edge` | 3 | group | 200×24 | `00 00 FF FF` opaque red |
| `layer-details` | 4 | solo, group | 300×180 | `00 FF 00 FF` opaque green |
| `layer-details-edge` | 8 | group | 60×30 | `00 80 FF FF` opaque orange; `bytes_per_row` 256, with 16 padding bytes of value `AA` at the end of each row |
| `layer-details-cancelled` | 2 | group | 393×852 | `80 00 00 80` translucent blue (premultiplied) |

## Attributes of the `layer-details` scenario

Layer 3 has three groups with 12 attributes in all, covering all 11 members of `AttributeValue` and one attribute whose value is nil (`layer.backgroundColor`):

| Group | Attributes | Value types |
|---|---|---|
| `layer` | 8 | `RectValue`, `PointValue`, `SizeValue`, `DoubleValue`, `BoolValue`, nil, `ColorValue`, `TransformValue` |
| `label` | 3 | `StringValue`, `IntValue`, `EnumValue` |
| `view` | 1 | `InsetsValue` |

Layer 4 has both a `solo` and a `group` image, and no attributes were requested. Layer 99 does not exist; its `status` is `LayerNotFound`.

## The `layer-details-edge` scenario

| Layer | Request | Response | Notes |
|---|---|---|---|
| 3 | solo and group | group only | Layer 3 has no sublayers, so the Server omitted solo; the Client treats it as the same as group (P-DET-04) |
| 8 | group | group, with row padding | P-IMG-02 |
| 9 | group and attributes | `CaptureFailed`, no images, with attributes | A layer of zero size (P-DET-03) |
| 7 | nothing | only `layer_id` and `status` | |
