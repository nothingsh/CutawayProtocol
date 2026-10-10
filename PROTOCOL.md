# Cutaway Protocol

The Cutaway protocol is the contract between CutawayServer (an SDK embedded in an iOS app) and Cutaway (a macOS app). The Server listens on a local port; once the Client connects, it retrieves the app's layer hierarchy, images, attributes and Auto Layout constraints by request and response, and can modify attributes. This document is normative: both implementations follow this document and `schema/cutaway.fbs`.

Protocol version: 0.5

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
| `GetLayerDetails` | Client → Server | Gets images, attributes and constraints by layer ID; streamed |
| `LayerDetailsChunk` | Server → Client | One chunk of the response to `GetLayerDetails` |
| `StreamEnd` | Server → Client | The frame that ends a stream |
| `Cancel` | Client → Server | Cancels a stream that has not ended |
| `Error` | Server → Client | Error |
| `AppStateChanged` | Server → Client | Event: the app's active state changed |
| `SetAttribute` | Client → Server | Modifies one attribute of one layer (0.3) |
| `SetAttributeResult` | Server → Client | Response to `SetAttribute` (0.3) |
| `GetSubtree` | Client → Server | Gets a layer and all its descendants; the response is a `Hierarchy` (0.3) |

## Transport

**P-TRANS-01** The Server must listen for TCP on the loopback address only, and must not listen on any other network interface. Transports beyond loopback (for example Wi-Fi) are left to a later version; such a transport must authenticate and encrypt the connection, and authentication happens outside the frames, leaving this document's frame format and handshake unchanged. (The second sentence since 0.5.2.)

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

**P-FRAME-06** When verifying, the receiver must not reject a buffer whose length is within the limit of P-FRAME-03 and whose content conforms to this protocol because of its number of tables, its nesting depth or its apparent size. (Since 0.5.2.)

Note: this is not FlatBuffers' own size-prefixed buffer. That format is aligned differently, so the bytes of the two differ and they are not interchangeable. A sender should build an ordinary buffer first and then write its length in front of it; a receiver reads the length, takes N bytes, and verifies those N bytes as an ordinary buffer. The `.stream` files under `fixtures/bin/` give the exact bytes on the wire.

P-FRAME-06 is aimed at verifiers' default limits. The FlatBuffers Swift runtime allows at most 1,000,000 tables by default, while P-DET-06 limits a chunk only by the pixels of its images, so a few tens of thousands of details without images in one chunk exceed it. With this runtime, set `maxTableCount` in `VerifierOptions` to at least 67108864 (2^26): every table takes at least 4 bytes, so a 256 MiB buffer holds at most that many. The default depth limit of 64 is enough, since this protocol nests tables at most six deep; the default apparent size limit of 2^31 is 8 times the frame limit.

## Handshake and versions

**P-HELLO-01** The first frame the Client sends after the connection is established must be `Hello`, with `role` `Client`, `request_id` 0, and the `client` field.

**P-HELLO-02** The Server must reply with a `Hello` with `role` `Server`, `request_id` 0, `protocol` set to the protocol version the Server uses on this connection, and the `app` field. A Server that supports one major version gives its own version; a Server that supports several major versions may choose the one that matches the Client's major version, and gives the highest version it supports within that major version. The Server sends this frame whether or not the major versions match. ("Uses on this connection" since 0.5.2; before, it read "the Server's own", which is the same for a Server that supports one major version.)

**P-HELLO-03** When the major versions differ, the handshake fails: the Server must close the connection after sending its own `Hello`; the Client must close the connection on receiving a `Hello` whose major version differs from its own. When the handshake fails, neither side may send any other message.

**P-HELLO-04** When the minor versions differ, the handshake succeeds and both sides work at the lower minor version: neither may send a message, field value, enum value or union member that does not exist in that minor version, nor content that can only be understood correctly under the clauses of a higher minor version (for example, a later version letting objects that did not appear before appear as hierarchy nodes). Table fields are exempt: a sender may write table fields appended in higher minor versions as usual, without choosing by the negotiated minor version, because a receiver ignores fields it does not know, and P-EVO-07 ensures that ignoring them does not lead it to misread other fields. ("Content that can only be understood correctly under the clauses of a higher minor version" stated explicitly since 0.5.2.)

**P-HELLO-05** Before the handshake completes, when the Server receives any message other than `Hello`, it must reply with `Error` (code `UnexpectedMessage`, `request_id` the same as that frame's) and close the connection. The same applies when the `Hello` received has a `role` other than `Client`, or has no `protocol` field. ("`request_id` the same as that frame's" stated explicitly since 0.5.6; Servers already did so.)

**P-HELLO-06** If no `Hello` arrives within 5 seconds of the connection being established, the Server must close the connection.

**P-HELLO-07** Before the handshake completes, when the Client receives any frame other than `Hello`, it must treat the handshake as failed and close the connection, sending no other message. Such a frame can only be an `Error` (`Busy` from P-TRANS-03, `MalformedFrame` from P-FRAME-03, `UnexpectedMessage` from P-HELLO-05), and the Client may use its code to tell the user why. (Since 0.5.6.)

Because the Server still replies with its own `Hello` when the major versions do not match, the Client learns the other side's version and app information, and can tell the user why this app cannot be inspected.

## Requests, responses and streams

**P-REQ-01** `request_id` is assigned by the Client, starts at 1, and increases monotonically within a connection. Every frame the Client sends (including `Cancel`) takes its own `request_id`. 0 is reserved for the handshake, events, and errors that answer no particular request. This clause binds only the Client: the Server does not check that `request_id` increases, and uses the value it received as is in the corresponding response.

**P-REQ-02** An ordinary request gets exactly one response frame, with the same `request_id` as the request. `GetAppIcon`, `GetHierarchy`, `GetSubtree` and `SetAttribute` are ordinary requests.

**P-REQ-03** The response to a streaming request is zero or more `LayerDetailsChunk` frames followed by exactly one `StreamEnd`, all with the same `request_id` as the request. `sequence` starts at 0 and increases by 1 per chunk. The `chunk_count` of `StreamEnd` must equal the number of chunks sent. `GetLayerDetails` is a streaming request.

**P-REQ-04** `Cancel` has no response of its own. When `target_request_id` refers to a stream that has not ended, that stream must end with `StreamEnd` (status `Cancelled`); when the Server has not started handling the stream yet, it captures nothing more for it, and ends it with `StreamEnd` (status `Cancelled`, `chunk_count` 0) when its turn comes under P-REQ-06, so the responses still come in the order of the requests. The Server uses `Cancelled` only to answer a `Cancel`; when the Server itself cannot continue a stream, it ends it with `Failed` (P-REQ-05). When `target_request_id` refers to an ordinary request, a request that does not exist, or a request that has already ended, the Server must ignore the `Cancel`.

**P-REQ-05** When an ordinary request fails, the response is `Error`, with the same `request_id` as the request. When a streaming request fails, its response ends with `StreamEnd` (status `Failed`, with `error`).

**P-REQ-06** The Server handles requests one at a time, in the order received. `Cancel` is the exception: the Server must handle it while the current request is in progress, except while reading is paused under P-REQ-09. ("Except while reading is paused" since 0.5.5.)

The exception for `Cancel` relies on the Server reading all the time: while other requests wait in line, a `Cancel` is still read in, and the Server handles it on sight. Once the outstanding requests reach a certain number (P-REQ-09), the Server may pause reading, and a `Cancel` then stays in the connection like any other frame until reading resumes. Once read, it is still handled under P-REQ-04: if the stream it refers to has not ended, the stream ends with `Cancelled`; if it has, the `Cancel` is ignored. The order of the responses is unaffected and still follows the order of the requests.

**P-REQ-07** A frame whose `body` is a union member the receiver does not know fails verification, and is handled under P-FRAME-03. A peer that follows P-HELLO-04 does not send such frames.

**P-REQ-08** After the handshake completes, on receiving a frame that passes verification but should not appear (`body` absent, another `Hello`, or a message only this side should send), the Server must reply with `Error` (code `UnexpectedMessage`, `request_id` the same as that frame's) and keep the connection; the Client must close the connection.

**P-REQ-09** An outstanding request is one the Server has read in and for which it has not yet sent the last response frame (the response of an ordinary request, the `StreamEnd` of a streaming request); `Cancel` does not count. When the outstanding requests reach 64, the Server may pause reading from the connection, and must resume reading when they drop below 64; with fewer than 64 it must not pause. While paused, the Server keeps sending, and a `Cancel` from the Client is not handled until reading resumes; the stream it refers to may have ended by then, in which case the `Cancel` is ignored under P-REQ-04. For `Cancel` to take effect promptly, the Client should keep fewer than 64 requests (not counting `Cancel`) sent but without their last response frame. (Since 0.5.5.)

P-REQ-09 spares the Server from buffering requests without limit for a Client that only sends requests and never reads the replies: once the Server pauses reading, TCP flow control stops the Client from writing (backpressure is left to TCP, with no flow control of the protocol's own). 64 is the lower bound at which the Server may pause, not an upper bound the Client must stay under: a Client with more requests does not violate the protocol, and its requests are still answered in order; only `Cancel` may arrive late. Every request outstanding at the Server is one the Client is still waiting for, so a Client that follows this advice never makes the Server pause reading. A Client that cannot write must keep reading: the Server resumes reading only after it sends responses and completes requests.

## Events and app state

**P-EVT-01** Events are sent by the Server on its own initiative, with `request_id` 0. This version has one event: `AppStateChanged`.

**P-EVT-02** The Server must send the current state once right after a successful handshake, and then every time the state changes.

**P-APP-01** When the app's state is not `Active`, the Server must reply to `GetHierarchy`, `GetSubtree` and `SetAttribute` with `Error` (code `AppNotActive`), and end `GetLayerDetails` with `StreamEnd` (status `Failed`, code `AppNotActive`). `GetAppIcon` is not affected by the app's state.

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

**P-HIER-10** The response to `GetSubtree` is `Hierarchy`. The first node in `nodes` is the layer given by `root_id`, followed by all its descendants, with the order and the field rules of P-HIER-01 and 03 to 09; the first node's `parent_id` is its actual parent layer, or 0 when it is the root layer of a window. `key_window_id` is the same as in the response to `GetHierarchy`.

**P-HIER-11** When the layer given by `root_id` does not exist (P-HIER-12), the Server must reply with `Error` (code `LayerNotFound`).

**P-HIER-12** In this document, a layer that "does not exist" is one that has been released, or is no longer in any window. P-HIER-11, P-DET-02 and P-SET-03 all use this meaning. (Since 0.4; before, only P-HIER-11 stated this meaning.)

**P-HIER-13** A layer used as a `mask` is not a hierarchy node, and neither are its sublayers; its effect shows in the image of the masked layer. (Stated explicitly since 0.5.2; Servers already did so.)

`GetSubtree` refreshes part of the hierarchy: the Client replaces the subtree rooted at this layer in its model with the response. IDs do not change within a connection (P-HIER-03), so a layer that has not changed is still the same node; a new layer has a new ID, and a layer that no longer appears has been removed. The position of the subtree's root among its siblings is not in the response; when its `z_position` changes, the Client has to refresh its parent's subtree to get the new order.

## Layer details

**P-DET-01** In a stream that completes normally, each entry of the request list must correspond to exactly one `LayerDetail`; when the same layer appears in several entries, each entry gets one. A cancelled or failed stream may contain only some of them. ("Each entry" stated explicitly since 0.5.6; before, it read "each layer" and did not cover repeated entries; Servers already produced one per entry.)

**P-DET-02** When a requested layer does not exist, the corresponding `LayerDetail` has `status` `LayerNotFound`, its other fields are absent or empty (for example `attribute_groups` of length 0), and the stream continues.

**P-DET-03** When capturing fails (for example because the layer has zero size), the corresponding `LayerDetail` has `status` `CaptureFailed` and its image fields are absent; attributes may still be given.

**P-DET-04** `solo` is the rendering of the layer itself, without its sublayers. `group` is the rendering of the layer together with its whole subtree. When both are requested and the layer has no sublayers, the Server may send only `group`; the Client must then treat the absent `solo` as the same as `group`.

**P-DET-05** When `max_texture_dimension` is not 0, neither side of an image may exceed it. Where one would, the Server must scale the image down proportionally and reduce `scale` accordingly.

**P-DET-06** The Server must produce the `LayerDetail`s in the order of the request list. The total uncompressed pixel data of all images in one `LayerDetailsChunk` must not exceed 16777216 bytes (16 MiB); a single `LayerDetail` that exceeds this by itself takes a chunk of its own.

**P-DET-07** `solo` and `group` each cover exactly the layer's `bounds` rectangle: the image's top-left corner corresponds to `bounds.origin`, and the image's size in points equals `bounds.size`. Content outside `bounds` is not in the image. The image does not include the effects of the layer's own `opacity`, `hidden` and `transform`: it shows the layer at opacity 1, visible and untransformed. Sublayers in `group` are rendered with their own properties.

**P-DET-08** The uncompressed pixel data of a single image must not exceed 67108864 bytes (64 MiB). Where it would, the Server must scale the image down proportionally and reduce `scale` accordingly. This holds whatever the value of `max_texture_dimension`.

`want_solo`, `want_group`, `want_attributes` and `want_constraints` each say whether the corresponding content is wanted. A request with all four false still gets a `LayerDetail` that holds only `layer_id` and `status`.

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

**P-ATTR-06** `editable` true means the Client may modify this attribute with `SetAttribute`; `accepts_nil` true means it may be set to nil, and is meaningful only when `editable` is true. `value_kind` is the `AttributeValue` member that this attribute's value uses, and must be given even when `value` is absent; when `value` is present, `value_kind` must be the same as its member.

**P-ATTR-07** The `case_values` of an `EnumValue` has the same length as `cases` and matches it one to one: it holds the raw value of each case.

Attributes are self-describing: the Server decides which groups and attributes to give and which of them may be modified, and the Client displays what it receives. An `EnumValue` gives the current value, the names of all cases, the name of the current case and the raw value of each case.

A 0.2 Server does not send the three fields of P-ATTR-06; the Client reads false and `None`, that is, everything is read-only, with no need to check the version separately. `AttributeValueKind` has the same numbering as the type field of `AttributeValue`; FlatBuffers does not allow a union's type to be used as the type of another field, so it is defined separately, and the two are appended together from now on.

## Modifying attributes

**P-SET-01** When `SetAttribute` succeeds, the response is `SetAttributeResult`: `layer_id` is the same as the request's, and `attribute_groups` is all of this layer's attribute groups, read again after the modification took effect, by the same rules as the `attribute_groups` of `LayerDetail`.

**P-SET-02** `value` must be the member that the attribute's `value_kind` names; an absent `value` means setting the attribute to nil, which is allowed only when `accepts_nil` is true. When the value is an `EnumValue`, the Server reads only its `value`, which must be one of `case_values`; `cases` and `case_name` may be absent.

**P-SET-03** When a request is invalid, the Server must reply with `Error`, and must not change any state of the app. The error code is the first of the following that applies: `LayerNotFound` when the layer does not exist; `AttributeNotEditable` when this layer's attribute groups have no attribute with this ID, or its `editable` is false; `InvalidAttributeValue` when the request violates P-SET-02, contains a non-finite number, or is rejected by the Server's other checks.

**P-SET-04** The Server may adjust the value it writes (for example clamping opacity to 0 to 1), and the app itself may also change it afterwards. The Client must display the value in `SetAttributeResult`, and must not assume that the value written took effect as is.

**P-SET-05** The Server modifies on the main thread, must not produce implicit animations, and has the window containing the layer finish layout before replying. A later `GetSubtree`, `GetHierarchy` or `GetLayerDetails` reads the state after the modification and the layout it caused.

**P-SET-06** A modification affects only the app's current runtime state. The Server neither records nor reverts modifications; they remain after the connection closes.

`SetAttributeResult` carries the attributes of the whole layer, because changing one attribute often changes others with it (`view.alpha` and `layer.opacity`; `layer.frame` and `layer.bounds`, `layer.position`). It carries no `LayerNode`: the layout a modification causes may move many layers, and geometry is always fetched with `GetSubtree`.

After a modification, the Client works out which layers' images need updating; the protocol does not specify it. The recommended approach:

1. Update the attribute panel from `SetAttributeResult`.
2. Send `GetSubtree` for the root layer of the window that contains the target layer. The modification may cause layout of the parent and further up, and may change the drawing order of siblings; the hierarchy carries no images, so fetching one window is cheap.
3. Compare with the old nodes, and send `GetLayerDetails` again for: the target layer and its whole subtree (for example `tintColor` changes how the whole subtree renders, while their geometry stays the same); its ancestors (only `group` is needed); layers with any changed node field; new layers. Remove layers that no longer appear from the model.

Continuous modifications (for example dragging a slider): keep only one `SetAttribute` in flight for the same attribute at a time; of the new values produced before the reply arrives, keep only the latest, and send it once the reply arrives. An image stream in progress is queued ahead of the modification (P-REQ-06); `Cancel` it first if needed. `Cancel` takes effect promptly only while fewer requests are in flight than the number in P-REQ-09. Undo is done by the Client: it has the old value before modifying, so undoing is just another `SetAttribute`.

After changing an attribute that causes layout (for example compression resistance priority), the `status` of constraints (P-LAYOUT-06) may change: when step 3 of the recommended approach above requests `GetLayerDetails` again, a Client that is showing constraints includes `want_constraints`.

## Constraints

**P-LAYOUT-01** When `want_constraints` is true and the layer backs a view, the `constraints` of the `LayerDetail` must list all active constraints whose first or second item is this view or a layout guide owned by this view, and is empty when there are none. When the layer does not back a view, or `want_constraints` is false, `constraints` is absent or empty. The order is unspecified.

**P-LAYOUT-02** Constraints include those UIKit generates itself (for example those translated from an autoresizing mask, and the internal constraints of layout guides); the Server must not filter them by origin. `class_name` is the runtime class name of the constraint object, and `identifier` is its `identifier`, absent when it has none.

**P-LAYOUT-03** A constraint's `id` and a layout guide's `guide_id` must not be 0. Within a connection the same object keeps the same ID, and after the object is released its ID must not be assigned to another object (as in P-HIER-03). When the same constraint appears in the details of several layers, its `id` is the same everywhere.

**P-LAYOUT-04** When the `kind` of a `LayoutItem` is `View`, `layer_id` is the layer that backs this view; when it is `LayoutGuide`, `layer_id` is the layer that backs the view owning the guide, and `guide_id`, `class_name`, `display_class_name` and `guide_frame` are given, plus `identifier` when it is not empty; when it is `Other` (an object that is neither a view nor a layout guide), only `class_name` and `display_class_name` are given. `display_class_name` follows the same rule as for hierarchy nodes. `guide_frame` is the guide's `layoutFrame`, in the owner's coordinate space; non-finite numbers in it must be sent as 0 (as in P-HIER-05; stated explicitly since 0.5).

**P-LAYOUT-05** When a constraint has no second item, `second_item` is absent and `second_attribute` is `NotAnAttribute`. `multiplier`, `constant` and `priority` are the current values of the constraint object; non-finite numbers are sent as 0 (as in P-ATTR-05).

**P-LAYOUT-06** `status` says whether the constraint's relation holds in the layout at the time the Server takes the details: `Satisfied` when it holds, `Unsatisfied` when it does not. Both sides are computed with the geometry Auto Layout itself uses (alignment rectangles, layout margins, the `layoutFrame` of layout guides, unaffected by `transform`), and a difference of no more than half a pixel counts as holding. When the Server cannot compute it (for example for text baselines), it is `Unknown`.

**P-LAYOUT-07** `MinX`, `MinY`, `MaxX` and `MaxY` of `LayoutAttribute` (0.5) are attributes UIKit uses in constraints translated from an autoresizing mask. They are not in Apple's public `NSLayoutConstraint.Attribute`, and their values are the same as UIKit's raw values. They are the view's left, top, right and bottom edges in its superview's coordinate space. The Server must send them as they are, and must not convert them into other attributes: converting would change the second item and `constant`, contradicting the "current values" of P-LAYOUT-05. For constraints that use these attributes, `status` may be `Unknown`.

**P-LAYOUT-08** When the Server meets a raw attribute value that the protocol does not name (for example one added by a later OS), or would send a `LayoutAttribute` value that the negotiated minor version does not have (P-HELLO-04, for example `MinX` to a 0.4 Client), it must send `NotAnAttribute` instead, and give the constraint and its two items as usual. Only in these two cases may the first attribute be `NotAnAttribute`, and the second attribute as well when there is a second item; the Client displays it as an unknown attribute, and must not consider the constraint invalid because of it. Otherwise the first attribute is not `NotAnAttribute`, and the second attribute is `NotAnAttribute` if and only if there is no second item (P-LAYOUT-05). (Since 0.5.)

A view's constraints are all the active constraints that refer to it: the same constraint appears in the details of the views at both of its ends, and `id` lets the Client recognize it as the same one. Inactive constraints are in no view's `constraints` and the Server cannot find them, so the constraints given are all active. When an optional constraint (priority below 1000) loses out, or UIKit breaks a required constraint because of a conflict, `status` is `Unsatisfied` either way.

The view end of a constraint gives only the layer ID; class names and member variable names are on the hierarchy nodes. Layout guides (the safe area, `layoutMarginsGuide`, the keyboard guide, the spacers inside `UIStackView`, and so on) are not views and have no layers, so they are not hierarchy nodes; the Client converts the owner into window coordinates and adds `guide_frame` to draw a guide in the preview. The values of `LayoutAttribute` are the same as UIKit's `NSLayoutConstraint.Attribute`, plus four that UIKit does not make public (P-LAYOUT-07); `LayoutRelation` differs.

Constraints translated from an autoresizing mask usually take these shapes (for a superview 393 wide and a view with the frame 300, 700, 0, 0): a fixed margin is written as `view.minY == 700`, with no second item; a flexible margin is written from the superview's side, for example `superview.width == view.maxX + 93` for a flexible left margin; width and height are written as `view.width == 0`. Clients of 0.4 and earlier do not recognize `MinX` and the others, and the Server sends `NotAnAttribute` to them under P-LAYOUT-08.

One way to find the constraints: an active constraint is installed on the nearest common ancestor of its two ends, so walk from the view up through its superviews to the window, check the `constraints` of each, and keep those that refer to the view or to its layout guides.

A 0.3 Server does not know `want_constraints` and ignores it, and the details it returns have no `constraints`. The Client decides whether to show constraints by the negotiated version, and should not take their absence to mean "this view has no constraints".

The distance between two layers is computed by the Client after converting both into the same coordinate space under P-HIER-06; the protocol does not give it separately.

## Error codes

| Code | Meaning |
|---|---|
| `Unknown` | An unclassified error |
| `MalformedFrame` | The frame's length, file identifier or verification is invalid |
| `UnexpectedMessage` | A message that should not appear in the current state |
| `Busy` | The Server is already serving another Client |
| `AppNotActive` | The app is not active and cannot be captured |
| `Internal` | An internal Server error |
| `LayerNotFound` | The layer the request names does not exist (0.3, P-HIER-11, P-SET-03) |
| `AttributeNotEditable` | The attribute does not exist or cannot be modified (0.3, P-SET-03) |
| `InvalidAttributeValue` | The value to write is invalid (0.3, P-SET-03) |

The `message` of `Error` is an English explanation for people to read; the Client must not make decisions based on its content.

## Evolution

**P-EVO-01** Tables may only gain fields at the end. An existing field's type or name must not change, an existing field's slot must not be reused, and no field may be removed. Obsolete fields are marked `deprecated`.

**P-EVO-02** Enums and unions may only gain members at the end; the names and values of existing members must not change. A struct must not change once released. The file identifier and the root type must not change.

**P-EVO-03** A change that consists only of appends increases the minor version by 1. Any other change increases the major version by 1 and resets the minor version to 0. Any change to the schema must come with a change of version.

**P-EVO-04** A change that changes the major version must state, when it is released, its impact on Cutaway's archives and on the Servers already released. This holds both before and after 1.0. ("After 1.0" and "state its impact" since 0.5.2; before, it said only that such changes were allowed before 1.0.)

**P-EVO-05** The following must not change in any major version, so that the handshake between any two versions, and the `Error` around it (P-TRANS-03, P-FRAME-03, P-HELLO-05), can always be read: the frame format (P-FRAME-01, 02), the file identifier and the root type; the names and order of the first 10 members of `Body` (`Hello` to `Error`); the existing fields and members of `Frame`, `Hello`, `Version`, `Role`, `ClientInfo`, `AppInfo`, `DeviceKind`, `Size`, `Error` and `ErrorCode`. They may still be appended to. (Listed in full since 0.5.2; before, only `Frame`, `Hello` and `Version` were listed.)

**P-EVO-06** When an appended table field is absent (a sender of an earlier version does not write it), it must mean the behavior from before the field was appended. (Since 0.5.2.)

**P-EVO-07** A receiver that ignores an appended table field must not misread other fields because of it. A field that changes the meaning of existing fields (for example, one whose presence means colors are no longer sRGB) may be sent only when the negotiated minor version includes it, as with enum values and union members (P-HELLO-04). (Since 0.5.2.)

**P-EVO-08** A change to the normative clauses gets its version number by whether the peer is affected:
1. A change that requires no change of the peer is released as a patch version. This includes stating explicitly what both sides already do; tightening one side's requirements so that the peer still conforms to this document as before; and relaxing a constraint on one side that the peer does not rely on.
2. A change to behavior the peer may rely on can only be written as "when the negotiated minor version is at least some value", and increases the minor version by 1.
3. Any other change increases the major version by 1.

(Since 0.5.2.)

A receiver ignores table fields it does not know, so appending fields is safe, given P-EVO-06 and 07. Unknown enum values and union members are not: the former are read as the enum's first member, and the latter fail verification. So new enum values and union members may be used only when the peer's minor version includes them too (P-HELLO-04).

Archives have no negotiation: when an earlier version of Cutaway opens an archive written under a later minor version, new enum values are read as the first member (for example `Ok` of `DetailStatus`, `Active` of `AppState`) instead of causing an error. So an archive records its protocol version, and Cutaway should not read an archive of a higher minor version as if it were of its own version.

The first 10 members of `Body` are in P-EVO-05 because the type field of `Frame.body` is the member's index: if any major version moved `Hello` or `Error`, other major versions could not recognize them. `Size` is there because `AppInfo`'s `screen_size` uses it.

## An example session

The frame sequence below corresponds to the scenarios in `fixtures/`, and is for illustration only.

| Direction | `request_id` | Message | Notes |
|---|---|---|---|
| Client → Server | 0 | `Hello` | Protocol 0.5, `role` `Client` |
| Server → Client | 0 | `Hello` | Protocol 0.5, `role` `Server`, with app information |
| Server → Client | 0 | `AppStateChanged` | Current state `Active` |
| Client → Server | 1 | `GetAppIcon` | |
| Server → Client | 1 | `AppIcon` | |
| Client → Server | 2 | `GetHierarchy` | |
| Server → Client | 2 | `Hierarchy` | Nine nodes |
| Client → Server | 3 | `GetLayerDetails` | Requests three layers |
| Server → Client | 3 | `LayerDetailsChunk` | `sequence` 0 |
| Server → Client | 3 | `LayerDetailsChunk` | `sequence` 1 |
| Server → Client | 3 | `StreamEnd` | Status `Completed`, `chunk_count` 2 |
| Client → Server | 4 | `SetAttribute` | Changes `label.text` of layer 3 |
| Server → Client | 4 | `SetAttributeResult` | All attributes of layer 3 after the change |
| Client → Server | 5 | `GetSubtree` | Root layer 1 of the window, to fetch the geometry after the change |
| Server → Client | 5 | `Hierarchy` | Nine nodes |
