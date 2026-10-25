# Cutaway Protocol

The Cutaway protocol is the contract between CutawayServer (an SDK embedded in an iOS app) and Cutaway (a macOS app). The Server listens on a local port; once the Client connects, it retrieves the app's layer hierarchy, images, attributes and Auto Layout constraints by request and response, can modify attributes, and can override the app's trait environment. This document is normative: both implementations follow this document and `schema/cutaway.fbs`.

Protocol version: 1.3

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
| `GetEnvironment` | Client → Server | Gets the overrides of the app's trait environment and its current traits; the response is an `Environment` (1.2) |
| `SetEnvironment` | Client → Server | Replaces the overrides of the app's trait environment; the response is an `Environment` (1.2) |
| `Environment` | Server → Client | Response to `GetEnvironment` and `SetEnvironment` (1.2) |
| `WatchHierarchy` | Client → Server | Turns hierarchy change notifications on or off (1.3) |
| `WatchHierarchyResult` | Server → Client | Response to `WatchHierarchy` (1.3) |
| `HierarchyChanged` | Server → Client | Event: part of the hierarchy changed (1.3) |

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

**P-REQ-02** An ordinary request gets exactly one response frame, with the same `request_id` as the request. `GetAppIcon`, `GetHierarchy`, `GetSubtree`, `SetAttribute`, `GetEnvironment`, `SetEnvironment` and `WatchHierarchy` are ordinary requests. (`GetEnvironment` and `SetEnvironment` since 1.2, `WatchHierarchy` since 1.3.)

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

**P-EVT-01** Events are sent by the Server on its own initiative, with `request_id` 0. This version has two events: `AppStateChanged`, and `HierarchyChanged` (P-WATCH-02). (`HierarchyChanged` since 1.3.)

**P-EVT-02** The Server must send the current state once right after a successful handshake, and then every time the state changes.

**P-APP-01** When the app's state is not `Active`, the Server must reply to `GetHierarchy`, `GetSubtree`, `SetAttribute` and `SetEnvironment` with `Error` (code `AppNotActive`), and end `GetLayerDetails` with `StreamEnd` (status `Failed`, code `AppNotActive`). `GetAppIcon`, `GetEnvironment` and `WatchHierarchy` are not affected by the app's state. (`SetEnvironment` and `GetEnvironment` since 1.2, `WatchHierarchy` since 1.3.)

## Hierarchy changes

**P-WATCH-01** `WatchHierarchy` turns hierarchy change notifications on (`enabled` true) or off (`enabled` false) for this connection; they are off when a connection begins. Its response is `WatchHierarchyResult`, whose `enabled` is the state after the request. A request for the state already in effect changes nothing and is answered as usual. `WatchHierarchy` is not affected by the app's state (P-APP-01): notifications may be turned on while the app is not active, and the Server checks once the app is active again (P-WATCH-08). The Client sends `WatchHierarchy` only when the negotiated minor version is at least 1.3. (Since 1.3.)

**P-WATCH-02** `HierarchyChanged` is an event (P-EVT-01). The Server sends it only after it has answered a `WatchHierarchy` that turns notifications on, and not after it has answered one that turns them off; and only once it has answered a `GetHierarchy` on this connection. After it answers a successful `SetEnvironment` (one answered with `Environment`), it sends none until it has answered the next `GetHierarchy`; a rejected `SetEnvironment` changes nothing here. (Since 1.3.)

**P-WATCH-03** `roots` are the nodes whose subtrees changed. Every change the event reports lies in the subtree of one of its roots, the root itself included, and no root lies in the subtree of another; a root need not be the lowest such node. A node appearing or disappearing, moving to another parent, or changing its position among its siblings or its `z_position` is reported on its parent (on both the old and the new parent for a move); any other change of a node's own fields (P-WATCH-07) is reported on the node itself. When the node a change would be reported on is not in the baseline (P-WATCH-06), or does not exist at the time of the check (P-HIER-12), the change is reported on the nearest ancestor that is in the baseline and exists. `whole` true means the Client should get the whole hierarchy again: the Server sends it when no such ancestor exists (for example when a window appears, or the root layer of a window disappears), when the order of the windows or the key window changed, or when it cannot tell where a change lies. When `whole` is true, `roots` is empty; otherwise it is not. A root may be a virtual node. (Since 1.3.)

**P-WATCH-04** Like `AppStateChanged`, a `HierarchyChanged` may come between any two frames, also while requests are outstanding and between the chunks of a stream; it answers no request and does not take part in the order of the responses (P-REQ-06). The response to a request the Client sends after receiving a `HierarchyChanged` reads the app's state no earlier than the check that produced the event. This holds only for requests sent after the event was received, not for those already sent (for example a details stream in progress). (Since 1.3.)

**P-WATCH-05** An event is a hint. The Server may merge changes, delay them, or send `whole` when it cannot tell where they lie. The Client must not rely on receiving an event for every change; getting the hierarchy again by request always works. (Since 1.3.)

**P-WATCH-06** The Server finds changes by checking the hierarchy against a baseline. For each node, the baseline is the state of it the Server last told the Client on this connection: in the response to a `GetHierarchy` or `GetSubtree` that listed it, or, when the node lies in the subtree of a root of a `HierarchyChanged` (in any subtree, when `whole` is true), at the check that produced that event; P-WATCH-09 may also count a state as told. A node that differs from its baseline has changed, and a node with no baseline is new. So a change made while notifications are off is reported in the first check after they are turned on, and the same change is not reported again whether or not the Client gets the hierarchy. (Since 1.3.)

**P-WATCH-07** The changes the Server reports include at least: a layer appearing or disappearing, moving to another parent or changing its position among its siblings, and a change of a layer's `bounds`, `position`, `anchor_point`, `transform`, `z_position`, `hidden`, `opacity` or `masks_to_bounds`. Changes of other fields of `LayerNode` may be reported. When only what a layer draws changed, and none of the above, the Server reports it on a best-effort basis, without guarantee. Changes of virtual nodes are not guaranteed to be reported either. (Since 1.3.)

**P-WATCH-08** Two `HierarchyChanged` on one connection are at least 1 second apart; the Server merges continuous changes, such as those of an animation or of scrolling. The Server does not check while the app is not `Active`. Once notifications are turned on, and when the app becomes `Active` again while they are on, the Server checks once without waiting for activity of the app's own, provided P-WATCH-02 lets it send events at that point. (Since 1.3.)

**P-WATCH-09** The Client must not rely on events to learn of the changes its own `SetAttribute` and `SetEnvironment` bring. After a successful `SetEnvironment`, P-WATCH-02 applies. For `SetAttribute`, the Server tries not to send `HierarchyChanged` for the changes it brings: it may count the state of the window containing the layer (for a virtual node, of its nearest layer ancestor) as told to the Client, from the modification until the check after continuous modifications stop, so changes the app itself makes in that window during that time may go unreported; and the Client may still receive an event for a change it made. (Since 1.3.)

The Client turns notifications on and off by request rather than in the handshake, so that the person can switch them at any time. A 1.2 Server does not know `WatchHierarchy`, and with it the Client has no automatic refresh. When the Client turns notifications off, events the Server sent before answering may still arrive ahead of the answer, and the Client handles them as usual until the answer arrives.

The recommended handling of an event, which the protocol does not specify: for each root, send `GetSubtree`; on `LayerNotFound`, get the root's parent instead, and failing that the whole hierarchy; on `whole`, send `GetHierarchy`. Then compare with the old nodes as after a modification, and get the images again for the roots' subtrees and the `group` of their ancestors. These requests carry the digests of the images the Client holds (P-DET-11), so the images that did not change come back as unchanged images (P-IMG-05), and getting a whole subtree again costs little; this is why the digests and the notifications came in the same version.

The baseline is pieced together from responses given at different times rather than taken at one moment: a `GetSubtree` renews only the nodes in its subtree. A Server can keep, for each node, a signature of its own fields, of its list of children (their IDs and `z_position`) and of its whole subtree, and compare from the root of each window down, skipping a subtree whose signature is unchanged; a change of the list of children is then reported on the parent, and a node new in this check is not in the baseline, so a change below it is reported higher up.

Core Animation applies animations to the presentation layer and sets the model value at once, and the Server reads model values (P-HIER-05), so an animation produces one change, not one per frame. Scrolling is not an animation: a scroll view's `bounds.origin` changes on every frame, so while scrolling the Client receives one event a second, with the scroll view as its root; cells that table and collection views reuse while scrolling change the scroll view's children, and are reported on it too, without other roots. An app that changes model values on every frame (for example a scene driven by `CADisplayLink`) likewise produces one event a second, rooted at that scene's layer. The Client may choose not to follow events in these cases.

Redrawing usually draws into the layer's existing backing store, so what a layer draws can change without any field the Server reads changing: for example, an image view given another image of the same size is usually reported, while a label given other text of the same size usually is not. A Server need not ask the host app for its virtual nodes while checking, which would call into the host app at times it does not expect; a change of virtual nodes is then brought along when the subtree of their nearest layer ancestor is got again.

P-WATCH-09 covers only what the modification itself brings, including the layout of P-SET-05 and the app's response that P-ENV-02 waits for. What the app does later in response, for example a reload it schedules on the main thread from a property observer, is reported as any other change, except that for `SetAttribute` it may fall within the time the Server counts as told. After `SetEnvironment` the Client gets the whole hierarchy again (see Environment), and events resume after that.

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

**P-HIER-10** The response to `GetSubtree` is `Hierarchy`. The first node in `nodes` is the node given by `root_id`, followed by all its descendants, virtual nodes included, with the order and the field rules of P-HIER-01, 03 to 09 and 14 to 23; the first node's `parent_id` is its actual parent node, or 0 when it is the root layer of a window. `key_window_id` is the same as in the response to `GetHierarchy`. ("Node" and virtual nodes since 1.2; before, it read "layer" and "parent layer".)

**P-HIER-11** When the layer given by `root_id` does not exist (P-HIER-12), the Server must reply with `Error` (code `LayerNotFound`).

**P-HIER-12** In this document, a layer that "does not exist" is one that has been released, or is no longer in any window. P-HIER-11, P-DET-02 and P-SET-03 all use this meaning. (Since 0.4; before, only P-HIER-11 stated this meaning.)

**P-HIER-13** A layer used as a `mask` is not a hierarchy node, and neither are its sublayers; its effect shows in the image of the masked layer. (Stated explicitly since 0.5.2; Servers already did so.)

**P-HIER-14** `layer_address` is the address of the layer object in the app's process at the time the hierarchy was captured, and must be given, except for a virtual node (P-HIER-20). `view_address` is the address of the view the layer backs, given exactly when `view_class_name` is (P-HIER-04); `view_controller_address` is the address of the view controller, given exactly when `view_controller_class_name` is (P-HIER-07). 0 means absent. The Server takes the addresses of the objects it already reads for the node, and must not retain or load anything to get them. (Since 1.1; the exception for virtual nodes since 1.2.)

**P-HIER-15** Addresses are for display only. Once an object is released its address may belong to another object, so an address is not an identity: the layer ID (P-HIER-03) remains the only one, and the Client must not use an address to identify a layer or to match nodes between captures. (Since 1.1.)

**P-HIER-16** `layer_class_origin`, `view_class_origin` and `view_controller_class_origin` say where the classes named by `class_name`, `view_class_name` and `view_controller_class_name` come from. `App` means that the executable image defining the class lies inside the `.app` bundle that contains the host process (when the host is an app extension, the app that contains the extension): the main executable, or a framework or plug-in in that bundle, including the third-party libraries the app links. `System` means any other image, such as the system's frameworks and runtime. The Server judges by the image the class lies in, not by its name; a class created at runtime, with no image of its own (for example a KVO subclass), takes the origin of the nearest superclass that has one. Each is given exactly when its class name is, and is then never `Unknown`; `Unknown` means absent. (Since 1.1.)

**P-HIER-17** `layer_base_class_name` is the nearest known class of the layer: walking up from the layer's class through its superclasses, the runtime name of the first class in the layer table below. `view_base_class_name` is the same for the view the layer backs, with the view table, and is absent when the layer backs no view. Either is absent when no class in the chain is in its table. One entry is not a runtime class name: `UIHostingView` stands for a view SwiftUI uses to host SwiftUI content in UIKit (for example the root view of a `UIHostingController`, or the content view of a `UIHostingConfiguration`), and the Server gives it when such a view's class is the first match in the chain. The tables are part of the protocol and are only appended to. The Server uses only the entries the negotiated minor version has, and the Client treats a name it does not know as absent. (Since 1.1.)

| Table | Classes |
|---|---|
| Views | `UIWindow`, `UILabel`, `UITextField`, `UITextView`, `UISegmentedControl`, `UIPageControl`, `UIStepper`, `UIDatePicker`, `UIPickerView`, `UIButton`, `UISwitch`, `UISlider`, `UIControl`, `UIImageView`, `UITableViewCell`, `UICollectionViewCell`, `UICollectionReusableView`, `UITableViewHeaderFooterView`, `UICollectionView`, `UITableView`, `UIScrollView`, `UINavigationBar`, `UITabBar`, `UIToolbar`, `UISearchBar`, `WKWebView`, `MKMapView`, `UIActivityIndicatorView`, `UIProgressView`, `UIStackView`, `UIVisualEffectView`, `UIHostingView` |
| Layers | `CAShapeLayer`, `CAGradientLayer`, `CATextLayer` |

**P-HIER-18** `view_controller_visibility` is given exactly when `view_controller_class_name` is, and is then never `Unknown`; `Unknown` means absent. It is `Shown` when all of the following hold, and `NotShown` otherwise: the view controller's view is in a window; each of its ancestor view controllers is shown by this rule; when its parent is a `UIPageViewController`, it is one of the current pages; when its parent is a `UISplitViewController`, the column it is in is showing. Under any other parent (navigation and tab bar controllers and the app's own containers included), a child whose view is in a window counts as shown. While a transition is in progress, either value may be given. (Since 1.1.)

**P-HIER-19** A node whose `node_kind` is `Virtual` is a virtual node: a part of the interface that the host app draws itself and describes to the Server (for example one bar of a chart view), not a layer. Its `parent_id` is a layer or another virtual node, and the children of a virtual node are virtual nodes only. Its `id` is in the same space as layer IDs and follows P-HIER-03, where the same object means the same identity under the same nearest layer ancestor: within a connection, virtual nodes with the same nearest layer ancestor and the same identity given by the host app keep the same ID, also when their virtual parent changes, and an ID is never given to another identity. Among the virtual nodes under one layer, an identity appears at most once; when the host app gives one more than once, the Server sends only the first, and leaves out the others with their subtrees. (Since 1.2.)

**P-HIER-20** For a virtual node, `class_name` and `display_class_name` are the type name the host app gives, and `layer_class_origin` is `App`; `name` is a short label the host app gives, and is absent when it gives none; only virtual nodes have `name`. Its geometry follows P-HIER-05 and 06 in its parent's coordinate space: for the rectangle the host app gives, `bounds` has origin 0 and the rectangle's size, and `position` is the rectangle's center; `anchor_point` is (0.5, 0.5), `transform` is the identity unless the host app gives one, `z_position` is 0, and `masks_to_bounds` is false. `hidden` and `opacity` are as the host app gives them, visible and 1 when it gives nothing. The fields of the view, the view controller, member references, addresses and base classes are absent. (Since 1.2.)

**P-HIER-21** Among the children of a layer, its virtual children come first, in the order the host app gives, followed by its sublayers in the order of P-HIER-01: they are drawn as part of the layer's own content, behind all its sublayers. Among the children of a virtual node, they are in the order the host app gives. (Since 1.2.)

**P-HIER-22** The Server sends virtual nodes only when the negotiated minor version is at least 1.2 (P-HELLO-04). `root_id` of `GetSubtree` may be a virtual node, and the subtree of a layer includes the virtual nodes below it. A virtual node "does not exist" (P-HIER-12) when the host app no longer gives it at the time the Server handles the request, or when its nearest layer ancestor does not exist. (Since 1.2.)

**P-HIER-23** `collapsed_by_default` true means the host app would like the Client to show this node collapsed at first (for example the inside of one of its own complex controls). It is a hint: the Client may ignore it, and always lets the person expand the node. It may be given on layers and virtual nodes alike. (Since 1.2.)

Addresses let the person debugging match a node with what the debugger and the app's logs print (for example `po 0x…` in LLDB); the layer ID means nothing outside Cutaway. A 1.0 Server does not send them, and the Client reads 0, that is, absent. An address also reveals where the app's heap lies; the Server listens on loopback only (P-TRANS-01), so it is visible only to the Client on the same machine or connected over USB.

The origins and base classes let the Client tell the app's own classes from the system's, and pick an icon for a node, without guessing from class names; a third-party library counts as the app's: linked statically it is in the main executable, linked dynamically it is in the bundle, so the rule gives the same answer either way. A 1.0 Server does not send them, and the Client reads `Unknown` and absent, and can then fall back to its own guess. Because a later table may add a class between an existing entry and a subclass (for example `UIDatePicker` below `UIControl`), sending a newer entry to an older Client would lose the entry it knows; so the Server answers by the negotiated table.

UIKit removes from the window the view of a controller covered by a full-screen presentation, as well as the pages below the top of a navigation stack and the tabs that are not selected, so "in a window" covers them; a controller under a presentation that leaves it in the window (for example `.overFullScreen`) counts as shown. The Server reads no `presentationController` for this, since reading it creates one. What appears during a transition cannot be judged with public API, and a hierarchy is in any case a snapshot of one moment.

Virtual nodes let the Client select and inspect what the host app draws inside one layer: the bars of a chart, the rows of a list it draws itself, the nodes of a game scene. Their appearance stays in their nearest layer ancestor's images (P-DET-09), so in 3D the Client can only outline them. Real sublayers are never placed under a virtual node: a sublayer's `position` is in its actual parent layer's coordinate space (P-HIER-06), and the chain of coordinate spaces would break. A host app usually gives a virtual node's identity as a hashable key rather than an object, since what it draws is often a value; how it does so is the Server's interface, not the protocol. Whether a virtual node exists is decided when each request is handled, as for layers: the Server asks the host app again rather than keeping what it gave earlier. When the host app gives the same node collapsed for a class, the Server may give it on instances of the class's subclasses too; that is the Server's interface as well.

`GetSubtree` refreshes part of the hierarchy: the Client replaces the subtree rooted at this layer in its model with the response. IDs do not change within a connection (P-HIER-03), so a layer that has not changed is still the same node; a new layer has a new ID, and a layer that no longer appears has been removed. The position of the subtree's root among its siblings is not in the response; when its `z_position` changes, the Client has to refresh its parent's subtree to get the new order.

## Layer details

**P-DET-01** In a stream that completes normally, each entry of the request list must correspond to exactly one `LayerDetail`; when the same layer appears in several entries, each entry gets one. A cancelled or failed stream may contain only some of them. ("Each entry" stated explicitly since 0.5.6; before, it read "each layer" and did not cover repeated entries; Servers already produced one per entry.)

**P-DET-02** When a requested layer does not exist, the corresponding `LayerDetail` has `status` `LayerNotFound`, its other fields are absent or empty (for example `attribute_groups` of length 0), and the stream continues.

**P-DET-03** When capturing fails (for example because the layer has zero size), the corresponding `LayerDetail` has `status` `CaptureFailed` and its image fields are absent; attributes may still be given.

**P-DET-04** `solo` is the rendering of the layer itself, without its sublayers. `group` is the rendering of the layer together with its whole subtree. When both are requested and the layer has no sublayers, the Server may send only `group`; the Client must then treat the absent `solo` as the same as `group`.

**P-DET-05** When `max_texture_dimension` is not 0, neither side of an image may exceed it. Where one would, the Server must scale the image down proportionally and reduce `scale` accordingly.

**P-DET-06** The Server must produce the `LayerDetail`s in the order of the request list. The total uncompressed pixel data of all images in one `LayerDetailsChunk` must not exceed 16777216 bytes (16 MiB); a single `LayerDetail` that exceeds this by itself takes a chunk of its own. An unchanged image (P-IMG-05) has no pixel data and counts as none. (The last sentence since 1.3.)

**P-DET-07** `solo` and `group` each cover exactly the layer's `bounds` rectangle: the image's top-left corner corresponds to `bounds.origin`, and the image's size in points equals `bounds.size`. Content outside `bounds` is not in the image. The image does not include the effects of the layer's own `opacity`, `hidden` and `transform`: it shows the layer at opacity 1, visible and untransformed. Sublayers in `group` are rendered with their own properties.

**P-DET-08** The uncompressed pixel data of a single image must not exceed 67108864 bytes (64 MiB). Where it would, the Server must scale the image down proportionally and reduce `scale` accordingly. This holds whatever the value of `max_texture_dimension`.

**P-DET-09** For a virtual node that exists, `status` is `Ok` (unless P-DET-10 applies), and neither `solo` nor `group` is given even when requested: its appearance is part of the images of its nearest layer ancestor. The Client must not take their absence for a failed capture. `constraints` is absent or empty, and `attribute_groups` holds only groups from the host app (P-ATTR-19). (Since 1.2.)

**P-DET-10** `capture_excluded` true means the host app excludes this node and its subtree from images. It is given on the layer the host app excluded and on every node of its subtree, virtual nodes included; a host app cannot exclude a virtual node alone, since its appearance is drawn by its layer ancestor, so a virtual node has it only below an excluded layer. For such a node that exists, `status` is `Excluded`, also when no image was requested, and neither `solo` nor `group` is given; attributes and constraints are given as usual. In the images of every other layer, excluded layers are left out as if they were hidden. The Server may hide them while it captures, as long as the app's state after capturing is the same as before. When the negotiated minor version is 1.1, the Server still excludes them, and the `status` of such a node is `CaptureFailed` when `solo` or `group` was requested and `Ok` otherwise. (Since 1.2.)

**P-DET-11** `known_solo_digest` and `known_group_digest` are the `digest` (P-IMG-04) of the `solo` and the `group` the Client holds for this layer, byte for byte as the Server sent them on this connection. The Client gives a digest only for an image it holds. The Server ignores a digest for an image that is not requested (`want_solo` or `want_group` false). A digest means something only on the connection it was sent on. (Since 1.3.)

`want_solo`, `want_group`, `want_attributes` and `want_constraints` each say whether the corresponding content is wanted. A request with all four false still gets a `LayerDetail` that holds only `layer_id` and `status`.

A host app excludes a view whose content is sensitive, or slow or impossible to capture (for example video or a map). The flag on every node lets the Client avoid requesting images it will not get, also after a `GetSubtree` of a node inside the subtree; `Excluded` tells it why when it does. Exclusion applies to the layers in the subtree: content the app copies elsewhere (for example a snapshot view, or a portal) is captured where it is shown.

What P-DET-07 means: the Client pins the image to the four corners of the layer's `bounds`, and then applies the layer's transform and opacity itself. P-DET-08 ensures that a `LayerDetail` with two images does not exceed the limit of a single frame.

## Images

**P-IMG-01** Encoding `Bgra8PremultipliedLzfse`: pixels are BGRA with 8 bits per channel, premultiplied alpha, in the sRGB color space, in rows from top to bottom. `data` is the LZFSE compression of `bytes_per_row × pixel_height` bytes. An unchanged image (P-IMG-05) has no `data`. (The last sentence since 1.3.)

**P-IMG-02** `bytes_per_row` must be at least `pixel_width × 4`. The bytes of each row beyond `pixel_width × 4` are padding, with unspecified content.

**P-IMG-03** `scale` is nominal: the number of pixels per point. Pixel sizes are rounded, so `pixel_width / scale` and `pixel_height / scale` may differ from the layer's `bounds.size` by up to one pixel, plus the rounding from representing `scale` as a `float`. The Client must pin the image to `bounds` as P-DET-07 says, and must not derive the layer's size from `scale`.

**P-IMG-04** When the negotiated minor version is at least 1.3, every `solo` and `group` in a `LayerDetail` must carry a `digest` of 1 to 32 bytes; otherwise the Server may leave it out, and the image of `AppIcon` may always leave it out. A digest is opaque to the Client: the Client keeps it and sends it back as it is, and neither interprets nor computes it. Two images with the same `digest` on one connection must have the same `encoding`, `pixel_width`, `pixel_height` and `scale`, and the same pixels, not counting the padding of P-IMG-02, whichever layers and kinds of image they belong to. The algorithm is the Server's own and does not change within a connection. The digest is that of the image actually sent, after any scaling down under P-DET-05 and 08. (Since 1.3.)

**P-IMG-05** When an entry of the request gives `known_solo_digest` (or `known_group_digest`), and the `solo` (or `group`) the Server is about to send for it has the same `digest`, the Server may send an unchanged image instead: `unchanged` true, `digest` the same as the request's, no `data`, and every other field at its default. The Server may also always send the full image. The Server sends an unchanged image only when the negotiated minor version is at least 1.3, since it changes what an absent `data` means (P-EVO-07). (Since 1.3.)

**P-IMG-06** On receiving an unchanged image, the Client uses the image it holds. When it no longer holds that image, or the `digest` differs from the one it gave, it treats the image as not received. When the Server sends only `group` for a layer without sublayers (P-DET-04), an unchanged `group` stands for the absent `solo` as well. (Since 1.3.)

A refresh usually finds most layers drawn exactly as before. The Server still renders every image it is asked for, but when the Client already holds the same one it sends an unchanged image instead, which saves the compression, the transfer, and the Client's decompression and texture upload. A request compares a layer's image only with the image of the same kind the Client holds for that layer: the Client keeps no cache by digest, and the Server remembers nothing of what it sent. P-IMG-04 still holds across the whole connection because of P-DET-04: the Client holds a leaf's `group` as its `solo` too, so a later `known_solo_digest` may be the digest of a `group`, compared with a `solo` once the layer has sublayers.

A suggested algorithm: SHA-256 over `pixel_width` and `pixel_height` (4 bytes each, little-endian), `scale` (the 4 bytes of the `float`, little-endian) and `encoding` (1 byte), followed by the first `pixel_width × 4` bytes of each row of the decompressed pixels, keeping the first 16 bytes of the result. CryptoKit has SHA-256 from iOS 13, and comparing before compressing spares the compression as well. The chance that two different images share 16 bytes of SHA-256 is negligible; a checksum such as CRC does not meet P-IMG-04. The digests in the fixtures are computed this way. Like layer IDs (P-HIER-03), digests hold only within a connection: a Client drops every digest it holds when it reconnects.

## Attributes

**P-ATTR-01** The `id` of an `AttributeGroup` and the `id` of an `Attribute` are stable identifiers: once released, the meaning of an ID must not change. `title` is for display only, and may change between versions.

**P-ATTR-02** An absent `value` in an `Attribute` means the attribute's value is nil.

**P-ATTR-03** The Client must not rely on a fixed list of attributes: it must be able to display a group or an attribute of any `id` from its `title` and `value`. The Server may use only the `AttributeValue` members that exist in the negotiated minor version; when a value cannot be expressed with those members, the Server sends a text description of it as a `StringValue`.

**P-ATTR-04** The components of a `ColorValue` are in the sRGB color space (as in P-IMG-01) and range from 0 to 1, with alpha not premultiplied. The Server clamps colors outside the sRGB gamut into this range.

**P-ATTR-05** Non-finite numbers (NaN, positive and negative infinity) in attribute values must be sent as 0, as P-HIER-05 requires for geometry fields.

**P-ATTR-06** `editable` true means the Client may modify this attribute with `SetAttribute`; `accepts_nil` true means it may be set to nil, and is meaningful only when `editable` is true. `value_kind` is the `AttributeValue` member that this attribute's value uses, and must be given even when `value` is absent; when `value` is present, `value_kind` must be the same as its member.

**P-ATTR-07** The `case_values` of an `EnumValue` has the same length as `cases` and matches it one to one: it holds the raw value of each case.

**P-ATTR-08** `section` names the part of an inspector an attribute belongs on: `Identity` for what identifies the object (for example `view.tag`); `Layout` for its geometry and Auto Layout; `Content` for what is particular to the concrete type of the view (for example a label's text, a scroll view's offset, a stack view's arrangement); `Appearance` for how it looks (for example visibility, colors, corners, borders and shadows); `Behavior` for how it responds to interaction (for example `view.isUserInteractionEnabled`); `Accessibility` for what it gives assistive technologies (for example `view.accessibilityLabel`); `General` for an attribute in none of these. It is a hint: the Client must still display every attribute (P-ATTR-03), and must display `Unspecified` and values it does not know as `General`. The Server must not send a section that the negotiated minor version does not have (P-HELLO-04); it sends `Unspecified` instead. (Since 1.1; `Accessibility` since 1.2.)

**P-ATTR-09** `limits` states the values `SetAttribute` accepts for an attribute, one numeric component at a time. It is given only for an attribute whose `editable` is true and whose `value_kind` is `IntValue`, `DoubleValue`, `PointValue`, `SizeValue`, `RectValue`, `InsetsValue` or `TransformValue`; for any other attribute it is absent or empty, and the Client ignores it. It follows `value_kind`, and holds also when `value` is absent. Absent or empty means the Server states no limits. One entry applies to every component of the value. Otherwise there is exactly one entry per component, in the order of the fields: `PointValue` x, y; `SizeValue` width, height; `RectValue` origin x, origin y, width, height; `InsetsValue` top, left, bottom, right; `TransformValue` m11 to m44. The Client must treat `limits` with any other number of entries as absent. (Since 1.1.)

**P-ATTR-10** In a `NumberLimit`, when `has_minimum` is true a component must be at least `minimum`, or greater than it when `minimum_exclusive` is true; when `has_maximum` is true it must be at most `maximum`, or less than it when `maximum_exclusive` is true. A side whose `has_` field is false is unbounded, and its other two fields are left at their defaults; an entry with neither bound leaves that component free. Bounds are finite numbers; when both are given, `minimum` is at most `maximum`, and some value lies between them. For `IntValue` the bounds are integers, and the value is compared as a double. (Since 1.1.)

**P-ATTR-11** Some properties of a view are stored in the layer that backs it, so a view attribute and a layer attribute can be closely related, and most of the time read and write the same state. Of each pair in the table below, one layer's attribute groups must not contain both: when the layer backs a view, the Server gives the view's attribute; otherwise it gives the layer's. The table is part of the protocol and is only appended to. (Since 1.1.)

| View attribute | Layer attribute |
|---|---|
| `view.isHidden` | `layer.hidden` |
| `view.alpha` | `layer.opacity` |
| `view.clipsToBounds` | `layer.masksToBounds` |
| `view.backgroundColor` | `layer.backgroundColor` |

For `view.backgroundColor` the two need not read the same: some views keep their background apart from their layer's (a `UILabel` draws it into its contents and leaves the layer's nil). On most such views the view's attribute is the one that is displayed, which is why it is the one given.

**P-ATTR-12** `cluster` gathers attributes of one layer that the Client may show together as one compound row, and `slot` names the part each plays in it; `slot` is given exactly when `cluster` is. Both are taken from the table below, which is part of the protocol and is only appended to. Among one layer's attributes, the same `slot` of the same `cluster` appears at most once, and all attributes of one cluster have the same `section`. A cluster may span groups. Every slot is optional: a layer may give only some of a cluster's slots, and the Client decides how to show such a cluster (as a compound row, or attribute by attribute). The Client shows the attributes of a cluster it does not know attribute by attribute, and so too an attribute whose slot it does not know in a cluster it knows. Either way every attribute is displayed (P-ATTR-03). The Server uses only the clusters and slots that the negotiated minor version's table has; it sends any other attribute without `cluster` and `slot`. (Since 1.1; unknown slots and the negotiated table since 1.2.)

| `cluster` | `slot`s | For example |
|---|---|---|
| `visibility` | `hidden`, `opacity` | `view.isHidden`, `view.alpha` |
| `corners` | `radius`, `clip` | `layer.cornerRadius`, `view.clipsToBounds` |
| `border` | `width`, `color` | `layer.borderWidth`, `layer.borderColor` |
| `shadow` | `color`, `opacity`, `radius`, `offset` | `layer.shadowColor` and so on |
| `geometry` | `frame`, `bounds`, `position`, `anchor`, `zPosition`, `transform` | `layer.frame` and so on |
| `sizing` | `hugging.horizontal`, `hugging.vertical`, `compression.horizontal`, `compression.vertical`, `intrinsic.width`, `intrinsic.height` | content hugging and compression resistance priorities, intrinsic content size |
| `autoLayout` | `autoresizing`, `ambiguous` | `view.translatesAutoresizingMaskIntoConstraints`, `view.hasAmbiguousLayout` |
| `font` | `name`, `size`; 1.2: `textStyle`, `scalable` | `label.fontName`, `label.fontSize`; the font's text style, `label.adjustsFontForContentSizeCategory` |
| `lines` | `count`, `lineBreak`; 1.2: `drawn`, `truncated` | `label.numberOfLines`, `label.lineBreakMode`; the number of lines actually drawn, whether the text is truncated |
| `state` | `enabled`, `selected`, `highlighted` | `control.isEnabled` and so on |
| `scrolling` | `enabled`, `paging` | `scrollView.isScrollEnabled`, `scrollView.isPagingEnabled` |
| `image` (1.2) | `name`, `size`, `scale`, `renderingMode`, `symbolConfiguration` | an image view's image: its name or symbol name, size, scale, rendering mode and symbol configuration |
| `indexPath` (1.2) | `section`, `item` | a cell's index path; for a table view, `item` is the row |
| `listCounts` (1.2) | `sections`, `items` | the number of sections of a table or collection view, and of items in all its sections together |

**P-ATTR-13** When `inactive_cause` is given, the attribute has no effect on what is displayed right now, because of the current value of the attribute of the same layer whose ID it gives; that attribute must be in the same layer's attribute groups. It is a hint: the attribute can still be read, and still be modified when `editable` is true. When a layer gives both attributes of a row below and the condition holds, the Server must give `inactive_cause` as the row says; it may give it in other cases too. (Since 1.1.)

| Attribute | No effect while | `inactive_cause` |
|---|---|---|
| `layer.borderColor` | `layer.borderWidth` is 0 | `layer.borderWidth` |
| `layer.shadowColor`, `layer.shadowRadius`, `layer.shadowOffset` | `layer.shadowOpacity` is 0 | `layer.shadowOpacity` |

**P-ATTR-14** `unit` says how to read the numbers of an attribute's value: `Points` for lengths in points; `Fraction` for a proportion where 1 is the whole (for example opacity), which the Client may show and take as a percentage, while the value on the wire and its `limits` stay proportions; `Unspecified` for anything else, shown as plain numbers. It applies to every component of the value. Only an attribute whose `value_kind` is `IntValue`, `DoubleValue`, `PointValue`, `SizeValue`, `RectValue` or `InsetsValue` may have a unit other than `Unspecified`. The Server must not send a unit that the negotiated minor version does not have; it sends `Unspecified` instead. (Since 1.1.)

**P-ATTR-15** The `system_name` of a `ColorValue` is given when the Server recognizes the color as one of UIKit's system colors: the attribute's value is a `UIColor`, and that object is the color one of `UIColor`'s class properties returns (for example `systemBlue`, `label`, `secondarySystemBackground`). `system_name` is the name of that property. It must not be found by comparing components, and is never given for an attribute whose value is a `CGColor` (for example `layer.borderColor`). When given, it must be correct; when absent, the color may still be a system color the Server did not recognize. `value` is given as P-ATTR-04 says either way. (Since 1.1.)

**P-ATTR-16** The `class_name` of an `AttributeGroup` must be given: it is the runtime name of the class that declares the group's properties (for example `CALayer` for `layer`, `UIView` for `view`, `UILabel` for `label`), not the runtime class of the object, so the `label` group of an instance of a subclass of `UILabel` still has `UILabel`. (Since 1.1.)

**P-ATTR-17** The `light` and `dark` of a `ColorValue` are the attribute's value resolved with the trait collection the Server resolves `value` with, with only the appearance changed to light and to dark, each converted as P-ATTR-04 says. They are given together, and only when they differ: when, with each component rounded to 8 bits, at least one component of one differs from the other's. Otherwise both are absent, as they always are for a `CGColor` (for example `layer.borderColor`). `value` is still the value under the current traits, with the overrides of P-ENV-02 in effect. (Since 1.2.)

**P-ATTR-18** A `LayerReferenceValue` refers to the objects an attribute holds, one entry of `references` per object, in the order the property holds them; it is empty when the property holds none. For a view, `layer_id` is the layer that backs it; for a view controller, the layer that backs its root view. Either is given only when that layer exists (P-HIER-12), and is 0 otherwise; for a view controller whose view is not loaded, and for any other object, it is 0. The Server must not load a view controller's view for this (as in P-HIER-07). `class_name` and `display_class_name` must be given, and name the object itself (for a view controller, the controller's class), by the same rules as for hierarchy nodes. An attribute whose `value_kind` is `LayerReferenceValue` is read-only: its `editable` is false. (Since 1.2.)

**P-ATTR-19** An `AttributeGroup` whose `from_app` is true comes from the host app rather than the Server's own list. Its `id`, and the `id` of each of its attributes, begin with `app.`; the Server's own groups and attributes never do. The obligations of P-ATTR-01 to 18 are still the Server's for what it sends: before sending such a group, it checks that the IDs are unique among the layer's attributes, that `limits` follow P-ATTR-09 and 10, that clusters and slots come from the table with each slot once and one section per cluster (P-ATTR-12), that `inactive_cause` names an attribute of the same layer (P-ATTR-13), and that `unit` is allowed for the `value_kind` (P-ATTR-14); and it works out `system_name`, `light`, `dark` and `name` itself (P-ATTR-15, 17, 20). It leaves out a field, an attribute or the whole group that does not pass, rather than send content that breaks these clauses. What the Server cannot check is the host app's: that IDs keep their meaning (P-ATTR-01), that an attribute named by `inactive_cause` really has no effect (P-ATTR-13), and that a value written takes effect. The `class_name` of such a group (P-ATTR-16) is the type name the host app gives for it; on a virtual node, when the host app gives none, it is the virtual node's `class_name`. The Server sends these groups whatever the negotiated minor version; a value that needs a member the negotiated minor version does not have is sent as text (P-ATTR-03). (Since 1.2.)

**P-ATTR-20** The host app may register named colors with the Server. The `name` of a `ColorValue` is the name of a registered color equal to the value: the Server resolves the registered color with the same trait collection and by the same rules as `value`, `light` and `dark` (P-ATTR-04, 17), and the two are equal when, with each component rounded to 8 bits, the `value`s are equal, and `light` and `dark` are either absent on both sides or present and equal on both. When several registered colors are equal, it is the first registered. For an attribute whose value is a `CGColor`, the trait collection is that of the view the layer backs, or of its nearest ancestor layer that backs a view. When given, `name` must be correct. (Since 1.2.)

Attributes are self-describing: the Server decides which groups and attributes to give and which of them may be modified, and the Client displays what it receives. An `EnumValue` gives the current value, the names of all cases, the name of the current case and the raw value of each case.

A 0.2 Server does not send the three fields of P-ATTR-06; the Client reads false and `None`, that is, everything is read-only, with no need to check the version separately. `AttributeValueKind` has the same numbering as the type field of `AttributeValue`; FlatBuffers does not allow a union's type to be used as the type of another field, so it is defined separately, and the two are appended together from now on.

A 1.0 Server does not send `section` or `limits`; the Client reads `Unspecified` and no limits, and shows every attribute as `General`. Where `General` goes in an inspector is the Client's choice. A later version may append narrower sections; an attribute that fits none of them stays in `General`.

`title` is a short name for a person, in title case, without the "is" of a Boolean property (Hidden, not Is Hidden); the ID says which property it is. Titles are the Server's, and may change between versions (P-ATTR-01).

A 1.0 Server does not follow P-ATTR-11 to 16: it may give both attributes of a pair, and sends none of their fields; the Client reads no clusters, no inactive causes, `Unspecified` units, no system color names and no class names, and shows attributes one by one as before. Under P-ATTR-11 the attribute left out is not in the layer's groups, so a `SetAttribute` for it is answered with `AttributeNotEditable` (P-SET-03); the `hidden`, `opacity` and `masks_to_bounds` of `LayerNode` are unaffected. Which attribute has which section, cluster and unit is set by the Server's list of attributes, like titles; the protocol fixes only their meaning. The text that tells a person why an attribute has no effect is composed by the Client from the two attributes' titles. `system_name` is not named `name` so that a later version can give the names of an app's own colors without changing its meaning.

Dynamic colors are those that resolve differently in light and dark, such as most system colors and colors from an asset catalog with a dark variant. P-ATTR-17 compares the two resolved values rather than asking whether the color is dynamic, since a color built with a provider may resolve the same in both. High contrast variants are not given.

A `LayerReferenceValue` lets the Client offer a way to the objects an attribute names: a stack view's arranged subviews, a table view's data source and delegate (often a view controller). An entry whose `layer_id` is 0, or names a layer the Client does not have in its hierarchy, is shown by its class name alone. Under P-ATTR-03, a Server whose negotiated minor version is 1.1 sends such an attribute as a `StringValue` describing the objects, with `value_kind` `StringValue`.

A 1.1 Server gives no `light`, `dark` or references and no `Accessibility` section, and only the clusters and slots of 1.1; the Client reads them as absent. Because a table field reaches every peer (P-HELLO-04), a cluster or slot added later would otherwise reach a Client that knows the cluster but not the slot, which is why the Server answers by the negotiated table.

Unlike `system_name`, `name` is found by comparing values, so an attribute whose value is a `CGColor` (for example `layer.borderColor`) may have one too; it says that the value equals the color the app calls by that name, not that the value came from it. Comparing `light` and `dark` keeps a fixed color from being named after a dynamic color it equals in one appearance only, and the other way round; a `CGColor` has no `light` or `dark`, so it is named only after a registered color that does not change with the appearance.

The host app's groups use the same clauses as the Server's own, so a Client handles them like any other (P-ATTR-03); `from_app` lets it place them apart. The prefix `app.` keeps their IDs from meeting IDs a later Server adds to its own list; the Client must not judge by the prefix. When the host app refuses a value written to one of its attributes, the Server answers `InvalidAttributeValue`, as a check of its own (P-SET-03). The host app writes after the Server's checks, so when its write fails partway, what P-SET-03 requires of the app's state is in the host app's hands. A 1.1 Server gives no `from_app` and no `name`; the Client reads false and absent.

Limits cover numbers only. `BoolValue`, `StringValue` and `EnumValue` have none (an `EnumValue` is limited by its `case_values`), and neither has `ColorValue`: its components are always 0 to 1 (P-ATTR-04).

## Modifying attributes

**P-SET-01** When `SetAttribute` succeeds, the response is `SetAttributeResult`: `layer_id` is the same as the request's, and `attribute_groups` is all of this layer's attribute groups, read again after the modification took effect, by the same rules as the `attribute_groups` of `LayerDetail`.

**P-SET-02** `value` must be the member that the attribute's `value_kind` names; an absent `value` means setting the attribute to nil, which is allowed only when `accepts_nil` is true. When the value is an `EnumValue`, the Server reads only its `value`, which must be one of `case_values`; `cases` and `case_name` may be absent. When the value is a `ColorValue`, the Server reads only its `value` and ignores `system_name` (since 1.1), `light`, `dark` and `name` (since 1.2).

**P-SET-03** When a request is invalid, the Server must reply with `Error`, and must not change any state of the app. The error code is the first of the following that applies: `LayerNotFound` when the layer does not exist; `AttributeNotEditable` when this layer's attribute groups have no attribute with this ID, or its `editable` is false; `InvalidAttributeValue` when the request violates P-SET-02, contains a non-finite number, or is rejected by the Server's other checks.

**P-SET-04** The Server may adjust the value it writes (for example clamping a color's components into 0 to 1, P-ATTR-04), and the app itself may also change it afterwards. The Client must display the value in `SetAttributeResult`, and must not assume that the value written took effect as is.

**P-SET-05** The Server modifies on the main thread, must not produce implicit animations, and has the window containing the layer finish layout before replying. A later `GetSubtree`, `GetHierarchy` or `GetLayerDetails` reads the state after the modification and the layout it caused. For a virtual node, the window is that of its nearest layer ancestor, and that layer must also have redrawn before the reply, so that its images show the modification. (Virtual nodes since 1.2.)

**P-SET-06** A modification affects only the app's current runtime state. The Server neither records nor reverts modifications; they remain after the connection closes.

**P-SET-07** The Client must not send a value with a component outside the limits (P-ATTR-09, 10) of that attribute in the attribute groups it last received for the layer. The Server must reject a value with a component outside the limits the attribute has as it reads now, with `InvalidAttributeValue` (P-SET-03). Limits are necessary, not sufficient: a value within them may still be rejected by the Server's other checks, or adjusted (P-SET-04); and absent limits do not mean that every value is accepted. (Since 1.1.)

Limits are what the Server accepts, not what the attribute can hold: the app may have set a value outside them itself (for example a negative width in `layer.bounds`). Such a value is displayed as it is, and a modification that keeps it is rejected like any other value outside the limits; the Client should tell the person which component is out of range rather than send it. Undoing to an old value that lies outside the limits the attribute has now is not sent either. A Server that used to clamp a number into a range rejects the values outside it once it states that range as limits; a 1.0 Client receives no limits and learns of this only from the `InvalidAttributeValue`.

`SetAttributeResult` carries the attributes of the whole layer, because changing one attribute often changes others with it (`layer.frame` with `layer.bounds` and `layer.position`; `layer.borderWidth` with the `inactive_cause` of `layer.borderColor`). It carries no `LayerNode`: the layout a modification causes may move many layers, and geometry is always fetched with `GetSubtree`.

After a modification, the Client works out which layers' images need updating; the protocol does not specify it. The recommended approach:

1. Update the attribute panel from `SetAttributeResult`.
2. Send `GetSubtree` for the root layer of the window that contains the target layer. The modification may cause layout of the parent and further up, and may change the drawing order of siblings; the hierarchy carries no images, so fetching one window is cheap.
3. Compare with the old nodes, and send `GetLayerDetails` again for: the target layer and its whole subtree (for example `tintColor` changes how the whole subtree renders, while their geometry stays the same); its ancestors (only `group` is needed); layers with any changed node field; new layers. Remove layers that no longer appear from the model. When the target is a virtual node, its images are those of its nearest layer ancestor, so start from that layer.

Continuous modifications (for example dragging a slider): keep only one `SetAttribute` in flight for the same attribute at a time; of the new values produced before the reply arrives, keep only the latest, and send it once the reply arrives. An image stream in progress is queued ahead of the modification (P-REQ-06); `Cancel` it first if needed. `Cancel` takes effect promptly only while fewer requests are in flight than the number in P-REQ-09. Undo is done by the Client: it has the old value before modifying, so undoing is just another `SetAttribute`.

After changing an attribute that causes layout (for example compression resistance priority), the `status` of constraints (P-LAYOUT-06) may change: when step 3 of the recommended approach above requests `GetLayerDetails` again, a Client that is showing constraints includes `want_constraints`.

## Constraints

**P-LAYOUT-01** When `want_constraints` is true and the layer backs a view, the `constraints` of the `LayerDetail` must list all active constraints whose first or second item is this view or a layout guide owned by this view, and is empty when there are none. When the layer does not back a view, or `want_constraints` is false, `constraints` is absent or empty. The order is unspecified.

**P-LAYOUT-02** Constraints include those UIKit generates itself (for example those translated from an autoresizing mask, and the internal constraints of layout guides); the Server must not filter them by origin. `class_name` is the runtime class name of the constraint object, and `identifier` is its `identifier`, absent when it has none.

**P-LAYOUT-03** A constraint's `id` and a layout guide's `guide_id` must not be 0. Within a connection the same object keeps the same ID, and after the object is released its ID must not be assigned to another object (as in P-HIER-03). When the same constraint appears in the details of several layers, its `id` is the same everywhere.

**P-LAYOUT-04** When the `kind` of a `LayoutItem` is `View`, `layer_id` is the layer that backs this view; when it is `LayoutGuide`, `layer_id` is the layer that backs the view owning the guide, and `guide_id`, `class_name`, `display_class_name` and `guide_frame` are given, plus `identifier` when it is not empty; when it is `Other` (an object that is neither a view nor a layout guide), only `class_name` and `display_class_name` are given. `display_class_name` follows the same rule as for hierarchy nodes. `guide_frame` is the guide's `layoutFrame`, in the owner's coordinate space; non-finite numbers in it must be sent as 0 (as in P-HIER-05; stated explicitly since 0.5). For a `LayoutGuide`, `guide_kind` must also be given: `SafeArea`, `LayoutMargins`, `ReadableContent` or `Keyboard` when the guide is the owner's `safeAreaLayoutGuide`, `layoutMarginsGuide`, `readableContentGuide` or `keyboardLayoutGuide`, and `Other` for any other guide; it is never `Unknown`, which means absent, and is absent for the other kinds. The Server identifies a guide by its own class and `identifier`, and must not read those properties of the owner to compare, since each creates its guide, and constraints with it, the first time it is read. It must not send a kind that the negotiated minor version does not have; it sends `Other` instead. (`guide_kind` since 1.1.)

**P-LAYOUT-05** When a constraint has no second item, `second_item` is absent and `second_attribute` is `NotAnAttribute`. `multiplier`, `constant` and `priority` are the current values of the constraint object; non-finite numbers are sent as 0 (as in P-ATTR-05).

**P-LAYOUT-06** `status` says whether the constraint's relation holds in the layout at the time the Server takes the details: `Satisfied` when it holds, `Unsatisfied` when it does not. Both sides are computed with the geometry Auto Layout itself uses (alignment rectangles, layout margins, the `layoutFrame` of layout guides, unaffected by `transform`), and a difference of no more than half a pixel counts as holding. When the Server cannot compute it (for example for text baselines), it is `Unknown`.

**P-LAYOUT-07** `MinX`, `MinY`, `MaxX` and `MaxY` of `LayoutAttribute` (0.5) are attributes UIKit uses in constraints translated from an autoresizing mask. They are not in Apple's public `NSLayoutConstraint.Attribute`, and their values are the same as UIKit's raw values. They are the view's left, top, right and bottom edges in its superview's coordinate space. The Server must send them as they are, and must not convert them into other attributes: converting would change the second item and `constant`, contradicting the "current values" of P-LAYOUT-05. For constraints that use these attributes, `status` may be `Unknown`.

**P-LAYOUT-08** When the Server meets a raw attribute value that the protocol does not name (for example one added by a later OS), or would send a `LayoutAttribute` value that the negotiated minor version does not have (P-HELLO-04, for example `MinX` to a 0.4 Client), it must send `NotAnAttribute` instead, and give the constraint and its two items as usual. Only in these two cases may the first attribute be `NotAnAttribute`, and the second attribute as well when there is a second item; the Client displays it as an unknown attribute, and must not consider the constraint invalid because of it. Otherwise the first attribute is not `NotAnAttribute`, and the second attribute is `NotAnAttribute` if and only if there is no second item (P-LAYOUT-05). (Since 0.5.)

**P-LAYOUT-09** `origin` must be given, and is never `Unknown`, which means absent. It is `System` when the Server recognizes the constraint as one UIKit created itself: its class is one UIKit uses for the constraints it generates (for example `NSAutoresizingMaskLayoutConstraint`, `NSContentSizeLayoutConstraint`), or its `identifier` begins with a prefix UIKit gives its own constraints (for example `UISV-`, `UIView-Encapsulated-Layout-`, `_UITemporaryLayout`). Otherwise it is `App`. It is a hint: a constraint UIKit creates through the public API without an `identifier` (for example inside one of its own controls) may be `App`, so the constraints marked `System` are a lower bound of those UIKit created. P-LAYOUT-02 still holds: the Server does not filter constraints by origin. (Since 1.1.)

A view's constraints are all the active constraints that refer to it: the same constraint appears in the details of the views at both of its ends, and `id` lets the Client recognize it as the same one. Inactive constraints are in no view's `constraints` and the Server cannot find them, so the constraints given are all active. When an optional constraint (priority below 1000) loses out, or UIKit breaks a required constraint because of a conflict, `status` is `Unsatisfied` either way.

The view end of a constraint gives only the layer ID; class names and member variable names are on the hierarchy nodes. Layout guides (the safe area, `layoutMarginsGuide`, the keyboard guide, the spacers inside `UIStackView`, and so on) are not views and have no layers, so they are not hierarchy nodes; the Client converts the owner into window coordinates and adds `guide_frame` to draw a guide in the preview. The values of `LayoutAttribute` are the same as UIKit's `NSLayoutConstraint.Attribute`, plus four that UIKit does not make public (P-LAYOUT-07); `LayoutRelation` differs.

Constraints translated from an autoresizing mask usually take these shapes (for a superview 393 wide and a view with the frame 300, 700, 0, 0): a fixed margin is written as `view.minY == 700`, with no second item; a flexible margin is written from the superview's side, for example `superview.width == view.maxX + 93` for a flexible left margin; width and height are written as `view.width == 0`. Clients of 0.4 and earlier do not recognize `MinX` and the others, and the Server sends `NotAnAttribute` to them under P-LAYOUT-08.

One way to find the constraints: an active constraint is installed on the nearest common ancestor of its two ends, so walk from the view up through its superviews to the window, check the `constraints` of each, and keep those that refer to the view or to its layout guides.

The class of a constraint does not say who created it: a constraint the app creates with layout anchors has a private UIKit class, so P-LAYOUT-09 judges by the classes and prefixes UIKit uses for its own constraints. The classes and prefixes in it are examples, not a closed list: UIKit's internal conventions change, and the Server follows them without a change of the protocol. Likewise the kind of a layout guide is recognized from UIKit's conventions; a 1.0 Server does not send `guide_kind` or `origin`, and the Client reads `Unknown` and can then fall back to its own guess.

A 0.3 Server does not know `want_constraints` and ignores it, and the details it returns have no `constraints`. The Client decides whether to show constraints by the negotiated version, and should not take their absence to mean "this view has no constraints".

The distance between two layers is computed by the Client after converting both into the same coordinate space under P-HIER-06; the protocol does not give it separately.

## Environment

**P-ENV-01** The response to `GetEnvironment` and to `SetEnvironment` is `Environment`. `overrides` holds what the Client has set on this connection, with `Unspecified` for a trait it has not overridden. `current` holds the effective traits of the key window, or of the first window when there is no key window, with the overrides in effect; it is `Unspecified` only for a trait the Server cannot read. `overridable` lists the kinds of trait this Server can override on this device, each at most once. An absent `overrides` or `current` means every trait in it is `Unspecified`. (Since 1.2.)

**P-ENV-02** `SetEnvironment` replaces all of this connection's overrides with its `overrides`: a trait that is `Unspecified` there is no longer overridden and goes back to the app's own value, and an absent `overrides` removes them all. The overrides apply to every window of the app, including windows that appear later, and take precedence over the values the app sets on its windows and window scenes itself (for example a window's `overrideUserInterfaceStyle`). The Server applies them on the main thread and must not produce implicit animations. Before replying, it lets the app respond to the changed traits: it returns to the main run loop and lets it complete at least two turns, so that work the app scheduled on the main thread in response (for example with `DispatchQueue.main.async`, or through a notification posted from there) has run; then it has the windows finish layout, as in P-SET-05, and commits the resulting changes, so that what is captured for a later request shows them. `current` in the reply is read after this. What the app does later still, for example after a delay, at the end of an animation or on a network response, is not waited for. (Since 1.2.)

**P-ENV-03** Overrides last only as long as the connection. When the connection closes, for any reason, the Server must remove every override and restore the values of the app's own that it replaced to apply them. What the app did in response to the changed traits is the app's, and is not undone. This differs from P-SET-06: a modified attribute remains after the connection closes; an override does not. (Since 1.2.)

**P-ENV-04** When `overrides` gives a value other than `Unspecified` for a kind that is not in `overridable`, or a value the Server does not know, the Server must reply with `Error` (code `NotSupported`), and must not change any override. When the app is not active, P-APP-01 applies first. (Since 1.2.)

**P-ENV-05** Overrides that the app's view controllers and views set themselves (for example a view controller's `overrideUserInterfaceStyle`) still take precedence under UIKit's rules, and the part of the interface below them does not change. The Server must not change them. (Since 1.2.)

On iOS 17 and later a Server can override all five kinds with `traitOverrides`; before iOS 17 only the appearance can be overridden for a window, so `overridable` lists only `UserInterfaceStyle`. The Server lists a kind only when overriding it takes effect. Overriding the content size category changes only content that takes its font from the trait environment (with `adjustsFontForContentSizeCategory`, or a preferred font obtained for a trait collection); a font the app obtains without one reads the app's global setting and does not change. Overriding the layout direction does not change what the app reads from `UIApplication.userInterfaceLayoutDirection`, nor views whose `semanticContentAttribute` forces a direction. These are known differences from changing the device's settings. Size classes may be combined freely; some system containers lay themselves out differently under a size class the device does not normally have.

Returning to the main run loop means continuing from work the Server itself schedules on the main queue, not running the run loop from inside the Server's handling of the request: a nested run loop would also run the Server's own input, and could start the next request before this one is answered (P-REQ-06). Committing the changes means, for example, `CATransaction.flush()`. A Server may wait more turns, up to a limit of its own; keeping the whole wait to a fraction of a second keeps `SetEnvironment` responsive.

`current` describes one window. On iPad, windows in different scenes may have different size classes, and a view controller may override traits for its own part of the interface (P-ENV-05), so what a given layer shows may differ from `current`.

After `SetEnvironment`, the app may rebuild parts of its interface in response, so layer IDs may change throughout: the Client gets the whole hierarchy again with `GetHierarchy` rather than one window's `GetSubtree`, and then the images it needs. Colors held as `CGColor` (for example `layer.borderColor`) follow a change of appearance only if the app updates them itself. There is no event for the app changing its own environment (for example the person switching the device to dark mode); the Client reads `Environment` again when it refreshes. If the app sets one of the overridden values itself while the override is in effect, which value remains after the connection closes is up to the Server.

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
| `InvalidAttributeValue` | The value to write is invalid (0.3, P-SET-03), or outside the attribute's limits (1.1, P-SET-07) |
| `NotSupported` | The Server cannot apply an override the request asks for (1.2, P-ENV-04) |

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
| Server → Client | 2 | `Hierarchy` | Fourteen nodes |
| Client → Server | 3 | `GetLayerDetails` | Requests three layers |
| Server → Client | 3 | `LayerDetailsChunk` | `sequence` 0 |
| Server → Client | 3 | `LayerDetailsChunk` | `sequence` 1 |
| Server → Client | 3 | `StreamEnd` | Status `Completed`, `chunk_count` 2 |
| Client → Server | 4 | `SetAttribute` | Changes `label.text` of layer 3 |
| Server → Client | 4 | `SetAttributeResult` | All attributes of layer 3 after the change |
| Client → Server | 5 | `GetSubtree` | Root layer 1 of the window, to fetch the geometry after the change |
| Server → Client | 5 | `Hierarchy` | Fourteen nodes |
