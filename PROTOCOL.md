# Cutaway Protocol

The Cutaway protocol is the contract between CutawayServer (an SDK embedded in an iOS app) and Cutaway (a macOS app). The Server listens on a local port; once the Client connects, it retrieves the app's layer hierarchy, images and attributes by request and response. This document is normative: both implementations follow this document and `schema/cutaway.fbs`.

Protocol version: 0.2

Numbered paragraphs are normative clauses. "Must" and "must not" state requirements; "may" states what is allowed but not required. Everything else is explanation.

## Messages

The payload of every frame is a `Frame`, whose `body` is one of the following messages.

| Message | Direction | Description |
|---|---|---|
| `Hello` | Both | Handshake |
| `GetAppIcon` | Client → Server | Gets the app icon |
| `AppIcon` | Server → Client | Response to `GetAppIcon` |
| `GetHierarchy` | Client → Server | Gets the whole layer tree, without images or attributes |
| `Hierarchy` | Server → Client | Response to `GetHierarchy` |
| `GetLayerDetails` | Client → Server | Gets images and attributes by layer ID; streamed |
| `LayerDetailsChunk` | Server → Client | One chunk of the response to `GetLayerDetails` |
| `StreamEnd` | Server → Client | The frame that ends a stream |
| `Cancel` | Client → Server | Cancels a stream in progress |
| `Error` | Server → Client | Error |
| `AppStateChanged` | Server → Client | Event: the app's active state changed |

## Transport

**P-TRANS-01** The Server must listen for TCP on the loopback address only, and must not listen on any other network interface.

**P-TRANS-02** The port range is 48160 to 48167. The Server must try the ports in order from 48160 and bind the first one available. When every port in the range is taken, the Server does not listen, and retries the next time the app becomes active.

**P-TRANS-03** A Server serves one Client at a time. While a connection exists, the Server must send `Error` (code `Busy`, `request_id` 0) to a new connection and then close it; the existing connection is unaffected.

**P-TRANS-04** After a connection closes, the Server must return to listening, preferring the port it used before.

An app in the simulator shares the Mac's loopback address, and the Client connects to `127.0.0.1` directly. For a device connected over USB, the Client forwards to the device's loopback port through macOS's usbmuxd; the Server needs to do nothing for this.

## Frames

**P-FRAME-01** A frame is a 4-byte little-endian unsigned integer N followed by N bytes. Those N bytes are one complete, ordinary FlatBuffer: its first 4 bytes are the offset of the root table, and bytes 5 to 8 are the file identifier. N does not include the 4 bytes of the length field itself.

**P-FRAME-02** The FlatBuffer's file identifier must be `CTWY` and its root type must be `Frame`.

**P-FRAME-03** On receiving any of the following frames, the receiver must close the connection; before closing, the Server must send `Error` (code `MalformedFrame`, `request_id` 0): N exceeds 268435456 (256 MiB); the file identifier is not `CTWY`; the buffer fails verification.

**P-FRAME-04** The receiver must verify the whole buffer before reading any field. No field of a buffer that fails verification may be used.

**P-FRAME-05** The byte order of multi-byte values inside the buffer is set by FlatBuffers: little-endian.

Note: this is not FlatBuffers' own size-prefixed buffer. That format is aligned differently, so the bytes of the two differ and they are not interchangeable. A sender should build an ordinary buffer first and then write its length in front of it; a receiver reads the length, takes N bytes, and verifies those N bytes as an ordinary buffer. The `.stream` files under `fixtures/bin/` give the exact bytes on the wire.

## Handshake and versions

**P-HELLO-01** The first frame the Client sends after the connection is established must be `Hello`, with `role` `Client`, `request_id` 0, and the `client` field.

**P-HELLO-02** The Server must reply with a `Hello` with `role` `Server`, `request_id` 0, `protocol` set to the Server's own protocol version, and the `app` field. The Server sends this frame whether or not the major versions match.

**P-HELLO-03** When the major versions differ, the handshake fails: the Server must close the connection after sending its own `Hello`; the Client must close the connection on receiving a `Hello` whose major version differs from its own. When the handshake fails, neither side may send any other message.

**P-HELLO-04** When the minor versions differ, the handshake succeeds and both sides work at the lower minor version: neither may send a message, field value, enum value or union member that does not exist in that minor version. Table fields are exempt: a sender may write table fields appended in higher minor versions as usual, without choosing by the negotiated minor version, because a receiver ignores fields it does not know.

**P-HELLO-05** Before the handshake completes, when the Server receives any message other than `Hello`, it must reply with `Error` (code `UnexpectedMessage`) and close the connection. The same applies when the `Hello` received has a `role` other than `Client`, or has no `protocol` field.

**P-HELLO-06** If no `Hello` arrives within 5 seconds of the connection being established, the Server must close the connection.

Because the Server still replies with its own `Hello` when the major versions do not match, the Client learns the other side's version and app information, and can tell the user why this app cannot be inspected.

## Requests, responses and streams

**P-REQ-01** `request_id` is assigned by the Client, starts at 1, and increases monotonically within a connection. Every frame the Client sends (including `Cancel`) takes its own `request_id`. 0 is reserved for the handshake, events, and errors that answer no particular request. This clause binds only the Client: the Server does not check that `request_id` increases, and uses the value it received as is in the corresponding response.

**P-REQ-02** An ordinary request gets exactly one response frame, with the same `request_id` as the request. `GetAppIcon` and `GetHierarchy` are ordinary requests.

**P-REQ-03** The response to a streaming request is zero or more `LayerDetailsChunk` frames followed by exactly one `StreamEnd`, all with the same `request_id` as the request. `sequence` starts at 0 and increases by 1 per chunk. The `chunk_count` of `StreamEnd` must equal the number of chunks sent. `GetLayerDetails` is a streaming request.

**P-REQ-04** `Cancel` has no response of its own. When `target_request_id` refers to a stream that has not ended, that stream must end with `StreamEnd` (status `Cancelled`); when the Server has not started handling the stream yet, it captures nothing more for it, and ends it with `StreamEnd` (status `Cancelled`, `chunk_count` 0) when its turn comes under P-REQ-06, so the responses still come in the order of the requests. The Server uses `Cancelled` only to answer a `Cancel`; when the Server itself cannot continue a stream, it ends it with `Failed` (P-REQ-05). When `target_request_id` refers to an ordinary request, a request that does not exist, or a request that has already ended, the Server must ignore the `Cancel`.

**P-REQ-05** When an ordinary request fails, the response is `Error`, with the same `request_id` as the request. When a streaming request fails, its response ends with `StreamEnd` (status `Failed`, with `error`).

**P-REQ-06** The Server handles requests one at a time, in the order received. `Cancel` is the exception: the Server must handle it while the current request is in progress.

**P-REQ-07** A frame whose `body` is a union member the receiver does not know fails verification, and is handled under P-FRAME-03. A peer that follows P-HELLO-04 does not send such frames.

**P-REQ-08** After the handshake completes, on receiving a frame that passes verification but should not appear (`body` absent, another `Hello`, or a message only this side should send), the Server must reply with `Error` (code `UnexpectedMessage`, `request_id` the same as that frame's) and keep the connection; the Client must close the connection.

## Events and app state

**P-EVT-01** Events are sent by the Server on its own initiative, with `request_id` 0. This version has one event: `AppStateChanged`.

**P-EVT-02** The Server must send the current state once right after a successful handshake, and then every time the state changes.

**P-APP-01** When the app's state is not `Active`, the Server must reply to `GetHierarchy` with `Error` (code `AppNotActive`), and end `GetLayerDetails` with `StreamEnd` (status `Failed`, code `AppNotActive`). `GetAppIcon` is not affected by the app's state.

## App icon

**P-ICON-01** The response to `GetAppIcon` is `AppIcon`. When the app has no icon, the `image` field is absent.

## Hierarchy

**P-HIER-01** The response to `GetHierarchy` is `Hierarchy`. `nodes` is in pre-order: a parent must come before all its descendants, and siblings under the same parent are in back-to-front drawing order. Drawing order is ascending `zPosition`; siblings with the same `zPosition` keep their order in `sublayers`. The Server must order siblings this way; the Client draws in wire order and does not need to sort by `z_position` again.

**P-HIER-02** The root nodes are the root layers of the windows; their `parent_id` is 0, and they are ordered from the back window to the front.

**P-HIER-03** A layer ID must not be 0. Within a connection, the same layer object keeps the same ID; after the object is released, its ID must not be assigned to another object.

**P-HIER-04** `view_class_name` and `view_display_class_name` are given only when the layer backs a view, and are absent otherwise.

**P-HIER-05** Geometry fields take the layer's model values. Non-finite numbers (NaN, positive and negative infinity) must be sent as 0.

**P-HIER-06** `bounds` and `position` are in points. `position` is in the parent layer's coordinate space; a root layer's `position` is the window layer's model value (P-HIER-05), in the coordinate space of the window's scene. On iPhone the scene's coordinate space is the screen's; under Split View and Stage Manager on iPad it is not, and the value is then not the layer's position on screen. To convert a point p in a layer's own coordinate space to its parent's: first subtract the anchor a, where a = `bounds.origin` + `anchor_point` × `bounds.size` (component-wise); then multiply by `transform`; finally add `position`.

`transform` has the same layout as Core Animation's `CATransform3D`, with points as row vectors multiplied on the left: the point (x, y) becomes (x·m11 + y·m21 + m41, x·m12 + y·m22 + m42). The typical case of a non-zero `bounds.origin` is a scroll view, where it is the current scroll offset.

`class_name` is the raw runtime class name; `display_class_name` is a readable class name restored by the Server for display, so the Client need not demangle Swift symbols itself.

**P-HIER-07** `view_controller_class_name` and `view_controller_display_class_name` are given only when the layer backs the root view (`view`) of a view controller, and are absent otherwise. The Server must not load a view controller's view for this if it is not loaded yet.

**P-HIER-08** `member_references` lists the instance variables that hold this layer, or the view it backs. The holders are limited to the views backed by this layer's ancestor layers, and the view controllers whose root views are those views, UIKit's own classes included. Entries are ordered from the nearest holder to the farthest; several entries of the same holder are ordered first by the class declaring them, from subclass to superclass, and then by declaration order within the same class. The Server may give only some of them, and the Client must not rely on the list being complete. When there are none, it is empty or absent.

**P-HIER-09** A `MemberReference`'s `owner_class_name` is the runtime class name of the class that declares the variable, and `owner_display_class_name` is its readable class name (by the same rule as `display_class_name`). `name` is the declared name: for a Swift stored property, its name without the internal prefixes the Swift compiler adds (for example the prefix of a `lazy` property's storage name); for an Objective-C instance variable, its name as is, with any leading underscore kept (for example `_titleLabel`).

Only root views are marked with their view controller, rather than every layer carrying the controller it belongs to: the former is a precise fact, and the Client derives the latter by walking up the parents to the first node with `view_controller_class_name`. The class that declares a variable may be a superclass of the holder, so `owner_class_name` is not necessarily equal to any ancestor's `view_class_name` or `view_controller_class_name`.

## Layer details

**P-DET-01** In a stream that completes normally, each layer in the request must appear in exactly one `LayerDetail`. A cancelled or failed stream may contain only some of them.

**P-DET-02** When a requested layer does not exist, the corresponding `LayerDetail` has `status` `LayerNotFound`, its other fields are absent or empty (for example `attribute_groups` of length 0), and the stream continues.

**P-DET-03** When capturing fails (for example because the layer has zero size), the corresponding `LayerDetail` has `status` `CaptureFailed` and its image fields are absent; attributes may still be given.

**P-DET-04** `solo` is the rendering of the layer itself, without its sublayers. `group` is the rendering of the layer together with its whole subtree. When both are requested and the layer has no sublayers, the Server may send only `group`; the Client must then treat the absent `solo` as the same as `group`.

**P-DET-05** When `max_texture_dimension` is not 0, neither side of an image may exceed it. Where one would, the Server must scale the image down proportionally and reduce `scale` accordingly.

**P-DET-06** The Server must produce the `LayerDetail`s in the order of the request list. The total uncompressed pixel data of all images in one `LayerDetailsChunk` must not exceed 16777216 bytes (16 MiB); a single `LayerDetail` that exceeds this by itself takes a chunk of its own.

**P-DET-07** `solo` and `group` each cover exactly the layer's `bounds` rectangle: the image's top-left corner corresponds to `bounds.origin`, and the image's size in points equals `bounds.size`. Content outside `bounds` is not in the image. The image does not include the effects of the layer's own `opacity`, `hidden` and `transform`: it shows the layer at opacity 1, visible and untransformed. Sublayers in `group` are rendered with their own properties.

**P-DET-08** The uncompressed pixel data of a single image must not exceed 67108864 bytes (64 MiB). Where it would, the Server must scale the image down proportionally and reduce `scale` accordingly. This holds whatever the value of `max_texture_dimension`.

`want_solo`, `want_group` and `want_attributes` each say whether the corresponding content is wanted. A request with all three false still gets a `LayerDetail` that holds only `layer_id` and `status`.

What P-DET-07 means: the Client pins the image to the four corners of the layer's `bounds`, and then applies the layer's transform and opacity itself. P-DET-08 ensures that a `LayerDetail` with two images does not exceed the limit of a single frame.

## Images

**P-IMG-01** Encoding `Bgra8PremultipliedLzfse`: pixels are BGRA with 8 bits per channel, premultiplied alpha, in the sRGB color space, in rows from top to bottom. `data` is the LZFSE compression of `bytes_per_row × pixel_height` bytes.

**P-IMG-02** `bytes_per_row` must be at least `pixel_width × 4`. The bytes of each row beyond `pixel_width × 4` are padding, with unspecified content.

**P-IMG-03** `scale` is nominal: the number of pixels per point. Pixel sizes are rounded, so `pixel_width / scale` and `pixel_height / scale` may differ from the layer's `bounds.size` by up to one pixel, plus the rounding from representing `scale` as a `float`. The Client must pin the image to `bounds` as P-DET-07 says, and must not derive the layer's size from `scale`.

## Attributes

**P-ATTR-01** The `id` of an `AttributeGroup` and the `id` of an `Attribute` are stable identifiers: once released, the meaning of an ID must not change. `title` is for display only, and may change between versions.

**P-ATTR-02** An absent `value` in an `Attribute` means the attribute's value is nil.

**P-ATTR-03** The Client must not rely on a fixed list of attributes: it must be able to display a group or an attribute of any `id` from its `title` and `value`. The Server may use only the `AttributeValue` members that exist in the negotiated minor version; when a value cannot be expressed with those members, the Server sends a text description of it as a `StringValue`.

**P-ATTR-04** The components of a `ColorValue` are in the sRGB color space (as in P-IMG-01) and range from 0 to 1, with alpha not premultiplied. The Server clamps colors outside the sRGB gamut into this range.

**P-ATTR-05** Non-finite numbers (NaN, positive and negative infinity) in attribute values must be sent as 0, as P-HIER-05 requires for geometry fields.

Attributes are self-describing: the Server decides which groups and attributes to give, and the Client displays what it receives. An `EnumValue` gives the current value, the names of all cases and the name of the current case.

## Error codes

| Code | Meaning |
|---|---|
| `Unknown` | An unclassified error |
| `MalformedFrame` | The frame's length, file identifier or verification is invalid |
| `UnexpectedMessage` | A message that should not appear in the current state |
| `Busy` | The Server is already serving another Client |
| `AppNotActive` | The app is not active and cannot be captured |
| `Internal` | An internal Server error |

The `message` of `Error` is an English explanation for people to read; the Client must not make decisions based on its content.

## Evolution

**P-EVO-01** Tables may only gain fields at the end. An existing field's type or name must not change, an existing field's slot must not be reused, and no field may be removed. Obsolete fields are marked `deprecated`.

**P-EVO-02** Enums and unions may only gain members at the end; the names and values of existing members must not change. A struct must not change once released. The file identifier and the root type must not change.

**P-EVO-03** A change that consists only of appends increases the minor version by 1. Any other change increases the major version by 1 and resets the minor version to 0. Any change to the schema must come with a change of version.

**P-EVO-04** Changes that change the major version are allowed before 1.0.

**P-EVO-05** The existing fields of `Frame`, `Hello` and `Version` must not change in any major version, so that the handshake between any two versions can always be read.

A receiver ignores table fields it does not know, so appending fields is safe. Unknown enum values and union members are not: the former are read as the enum's first member, and the latter fail verification. So new enum values and union members may be used only when the peer's minor version includes them too (P-HELLO-04).

## An example session

The frame sequence below corresponds to the scenarios in `fixtures/`, and is for illustration only.

| Direction | `request_id` | Message | Notes |
|---|---|---|---|
| Client → Server | 0 | `Hello` | Protocol 0.2, `role` `Client` |
| Server → Client | 0 | `Hello` | Protocol 0.2, `role` `Server`, with app information |
| Server → Client | 0 | `AppStateChanged` | Current state `Active` |
| Client → Server | 1 | `GetAppIcon` | |
| Server → Client | 1 | `AppIcon` | |
| Client → Server | 2 | `GetHierarchy` | |
| Server → Client | 2 | `Hierarchy` | Nine nodes |
| Client → Server | 3 | `GetLayerDetails` | Requests three layers |
| Server → Client | 3 | `LayerDetailsChunk` | `sequence` 0 |
| Server → Client | 3 | `LayerDetailsChunk` | `sequence` 1 |
| Server → Client | 3 | `StreamEnd` | Status `Completed`, `chunk_count` 2 |
