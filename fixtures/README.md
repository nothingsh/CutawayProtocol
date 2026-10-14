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

`scripts/verify.sh` regenerates them and compares the result with `bin/`, failing on any difference; it also uses `scripts/check-fixtures.py` to check the fixtures against the clauses the schema cannot express (sequence numbers, chunk counts, how responses match requests, image sizes, the attributes' editing fields, the content of subtrees, the reply each modification request should get, the structure of constraints, the addresses, class origins, base classes and view controller visibility of nodes, attributes' sections, limits, units and system color names, each layer's paired attributes, clusters and inactive causes, and the origins of constraints and kinds of layout guides). Do not edit the files under `bin/` by hand.

## Scenarios

| Scenario | Content | Clauses verified |
|---|---|---|
| `handshake` | A successful handshake at 1.1, after which the Server sends the current state | P-HELLO-01, 02; P-EVT-01, 02 |
| `handshake-version-mismatch` | A 1.0 Client connects to a Server still at 0.5; the Server still replies with its own `Hello` (0.5), then closes the connection | P-HELLO-02, 03 |
| `busy` | The only frame received when connecting to a Server that already has a Client | P-TRANS-03 |
| `app-icon` | Getting the app icon | P-REQ-02; P-ICON-01; P-IMG-01 |
| `hierarchy` | A hierarchy of one window and nine nodes, with view controllers, member variables, addresses, class origins, base classes and view controller visibility | P-HIER-01 to 04, 06 to 09, 14, 16 to 18 |
| `layer-details` | Details of three layers in two chunks, ending normally; attributes carry editing fields, sections, limits, clusters, units, inactive causes, a system color name and the groups' class names | P-REQ-03; P-DET-01, 02, 04, 07; P-ATTR-01, 02, 06 to 16 |
| `layer-details-edge` | An omitted solo, an image with row padding and the attributes of a layer that backs no view, a failed capture with attributes, a request that wants nothing | P-DET-03, 04; P-IMG-02; P-ATTR-11 |
| `layer-details-cancelled` | A details stream cancelled after its first chunk | P-REQ-01, 04, 06 |
| `app-not-active` | Requesting the hierarchy after the app goes to the background | P-APP-01; P-REQ-05 |
| `layer-details-failed` | The app leaves the active state while a details stream is in progress | P-APP-01; P-EVT-02; P-REQ-05 |
| `set-attribute` | Changing text, an enum, a color (from nil to a color and back to nil) and `view.alpha`, each reply holding the whole layer's attributes; layer 4's `corners` cluster spans two groups | P-REQ-02; P-ATTR-06, 07, 11, 12; P-SET-01, 02 |
| `set-attribute-rejected` | A layer that does not exist, a read-only attribute, the wrong member, nil for an attribute that does not accept nil, two values outside the limits, the layer attribute of a pair on a layer that backs a view | P-SET-03, 07; P-ATTR-11; P-REQ-05 |
| `subtree` | Getting the subtree of node 4, with its addresses, origins and base classes; getting a layer that does not exist | P-HIER-10, 11, 14, 16, 17 |
| `layout-constraints` | Five layers, constraints only: constraints to views and to the safe area, without a second item, an optional constraint that does not hold, the same constraint in two places, constraints UIKit generates (using `MinY` and `MaxX`, with the superview as first item), a layer that does not back a view, a layer that does not exist; each constraint's origin and the guide's kind | P-DET-02; P-LAYOUT-01 to 07, 09 |

Clauses no fixture covers: in P-HIER-01, the ordering of siblings with different `zPosition` (it is already done on the wire; a fixture can only give the result, not the `sublayers` before sorting); P-HIER-05 and P-ATTR-05 (non-finite numbers sent as 0); P-HELLO-04 (a handshake with different minor versions); P-IMG-03 (`scale` is nominal); P-DET-05 and P-DET-08 (scaling down oversized images); P-DET-06 (the chunk size limit); P-FRAME-03 (malformed frames); P-HELLO-05, 06, 07 and P-REQ-08; the "change no state" part of P-SET-03; P-SET-04 (the Server adjusting the value written); P-HIER-15 and the Client's side of P-SET-07; the replacement of a section the Client's version does not have in P-ATTR-08; P-SET-05 (layout, no animations); P-SET-06; the "no filtering" of P-LAYOUT-02; the judgement of P-LAYOUT-06 (a fixture can only give the result); non-finite numbers in `guide_frame` in P-LAYOUT-04; P-LAYOUT-08 (sending `NotAnAttribute` instead; the fixtures represent a Client at the same minor version as the Server); the handling of layers moved out of their window in P-HIER-12; the replacement of a unit, a base class or a guide kind the Client's version does not have in P-ATTR-14, P-HIER-17 and P-LAYOUT-04; how the Server judges P-HIER-16 to 18, P-ATTR-15 and P-LAYOUT-09 (a fixture can only give the result), including `NotShown`, transitions and `UIHostingView`. These rely on each side's own tests.

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

### Addresses (1.1)

Every node has `layer_address` 0x600003B4C000 + 0x40 × (ID − 1); a node that backs a view has `view_address` 0x103806800 + 0x200 × ID; node 2 has `view_controller_address` 0x103007A00 (P-HIER-14). The JSON sources write them in decimal. Node 5 and node 8 do not back a view, so they have no `view_address`. The `subtree` scenario gives nodes 4 and 5 the same addresses.

### Origins, base classes and visibility (1.1)

Every node has `layer_class_origin` `System`; every node that backs a view has `view_class_origin` `System`, except node 4, whose `Demo.CardView` is `App`. Node 2's view controller `Demo.HomeViewController` has `view_controller_class_origin` `App` and `view_controller_visibility` `Shown` (P-HIER-16, 18). `view_base_class_name` is `UIWindow` for node 1, `UILabel` for nodes 3 and 7 and `UIScrollView` for node 6; nodes 2, 4 and 9 are plain `UIView`s, whose chain holds no class of the table. Node 5 has `layer_base_class_name` `CAShapeLayer`; the other layers' classes are not in the table (P-HIER-17). The `subtree` scenario gives nodes 4 and 5 the same fields.

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

Layer 3 (a `UILabel`) has three groups with 19 attributes in all, covering all 11 members of `AttributeValue` and one attribute whose value is nil (`layer.backgroundColor`):

| Group | `class_name` | Attributes | Value types |
|---|---|---|---|
| `layer` | `CALayer` | 9 | `RectValue` (`frame`, `bounds`), `PointValue`, `DoubleValue` (`shadowOpacity`, `borderWidth`), `SizeValue`, nil, `ColorValue`, `TransformValue` |
| `label` | `UILabel` | 4 | `StringValue`, `DoubleValue` (`fontSize`), `IntValue`, `EnumValue` |
| `view` | `UIView` | 6 | `IntValue` (`tag`), `BoolValue` (`isHidden`, `isUserInteractionEnabled`), `DoubleValue` (`alpha`), `ColorValue` (`tintColor`), `InsetsValue` |

Layer 3 backs a view, so it has `view.isHidden` and `view.alpha` and not `layer.hidden` and `layer.opacity` (P-ATTR-11).

Layer 4 has both a `solo` and a `group` image, and no attributes were requested. Layer 99 does not exist; its `status` is `LayerNotFound`.

## The `layer-details-edge` scenario

| Layer | Request | Response | Notes |
|---|---|---|---|
| 3 | solo and group | group only | Layer 3 has no sublayers, so the Server omitted solo; the Client treats it as the same as group (P-DET-04) |
| 8 | group and attributes | group, with row padding; `layer.hidden` and `layer.opacity` | P-IMG-02; layer 8 backs no view, so it has the layer's attribute of each pair (P-ATTR-11) |
| 9 | group and attributes | `CaptureFailed`, no images, with attributes | A layer of zero size (P-DET-03) |
| 7 | nothing | only `layer_id` and `status` | |

## Editing fields (0.3)

Every attribute in `layer-details` and `layer-details-edge` carries `editable`, `accepts_nil` and `value_kind`. Which attributes are editable is decided by the Server's list of attributes; the values in the fixtures are only an example:

- `layer.frame` is read-only (it is computed from `bounds`, `position`, `anchorPoint` and `transform`); all others are editable.
- `layer.backgroundColor`, `layer.borderColor`, `label.text` and `view.tintColor` may be set to nil.
- Titles follow the convention of 1.1 (Hidden, Opacity, Background, Tint, Lines); the IDs are unchanged.
- `layer.backgroundColor`, whose value is nil, still carries `value_kind` (`ColorValue`).
- The `case_values` of `label.textAlignment` are 0 to 4, matching `cases` one to one.

## Sections and limits (1.1)

Every attribute in `layer-details`, `layer-details-edge` and `set-attribute` carries a `section` (P-ATTR-08): `view.tag` is `Identity`; `layer.frame`, `layer.bounds`, `layer.position`, `layer.transform` and `view.layoutMargins` are `Layout`; the attributes of the `label` group are `Content`; `view.isUserInteractionEnabled` is `Behavior`; all others are `Appearance`. No fixture uses `General`. As with editing fields, the assignment is the Server's; the fixtures are only an example.

| Attribute | `limits` (P-ATTR-09, 10) |
|---|---|
| `layer.bounds` | Four entries, one per component: x and y free, width and height at least 0 |
| `layer.opacity`, `view.alpha`, `layer.shadowOpacity` | One entry: 0 to 1 |
| `layer.cornerRadius`, `layer.borderWidth`, `label.numberOfLines` | One entry: at least 0 |
| `label.fontSize` | One entry: greater than 0 (`minimum_exclusive`) |

No other attribute has limits: colors, booleans, strings and enums never do, and `layer.frame` is read-only.

## Clusters, units, inactive causes and system colors (1.1)

| Layer | `cluster` | Attributes by `slot` |
|---|---|---|
| 3 | `geometry` | `frame` `layer.frame`, `bounds` `layer.bounds`, `position` `layer.position`, `transform` `layer.transform` |
| 3 | `shadow` | `opacity` `layer.shadowOpacity`, `offset` `layer.shadowOffset` |
| 3 | `border` | `width` `layer.borderWidth`, `color` `layer.borderColor` |
| 3 | `font` | `size` `label.fontSize` (no `name`: every slot is optional) |
| 3 | `lines` | `count` `label.numberOfLines` |
| 3 | `visibility` | `hidden` `view.isHidden`, `opacity` `view.alpha` |
| 4 | `corners` | `radius` `layer.cornerRadius`, `clip` `view.clipsToBounds`: one cluster across two groups |
| 4 | `visibility` | `opacity` `view.alpha` |
| 8 | `visibility` | `hidden` `layer.hidden`, `opacity` `layer.opacity` |
| 9 | `geometry`, `visibility` | `frame` `layer.frame`; `hidden` `view.isHidden` |

`unit` (P-ATTR-14) is `Fraction` for `view.alpha`, `layer.opacity` and `layer.shadowOpacity`, `Points` for the other lengths (`frame`, `bounds`, `position`, `shadowOffset`, `borderWidth`, `cornerRadius`, `fontSize`, `layoutMargins`), and `Unspecified` for the rest, including `layer.transform`.

On layer 3, `layer.borderWidth` and `layer.shadowOpacity` are 0, so `layer.borderColor` has `inactive_cause` `layer.borderWidth` and `layer.shadowOffset` has `layer.shadowOpacity` (P-ATTR-13). Layer 3's `view.tintColor` is `systemBlue`, (0, 0.47843137, 1, 1) in sRGB, with `system_name` `systemBlue` (P-ATTR-15); `layer.borderColor` is a `CGColor` and has none.

## The `set-attribute` scenario

| Request | Layer | Attribute | Value written | Change in the reply |
|---|---|---|---|---|
| 1 | 3 | `label.text` | `"Welcome back"` | The text changed; the rest is the same as layer 3's attributes in `layer-details` |
| 2 | 3 | `label.textAlignment` | An `EnumValue` with only `value` 2 | The case becomes `right` |
| 3 | 4 | `layer.backgroundColor` | From nil to (0.2, 0.4, 0.8, 1) | |
| 4 | 4 | `view.alpha` | 0.5 | |
| 5 | 4 | `layer.backgroundColor` | No `value`, that is, set to nil | The background color is back to nil; `value_kind` is still `ColorValue` |

Layer 4's attributes appear only in this scenario: the `layer` group has `layer.cornerRadius` and `layer.backgroundColor`, and the `view` group has `view.alpha`, `view.clipsToBounds` and `view.tintColor`, whose value is nil. Layer 4 backs a view, so it has no `layer.opacity` (P-ATTR-11); before 1.1 this scenario showed `layer.opacity` changing with `view.alpha`.

## The `set-attribute-rejected` scenario

| Request | Layer | Attribute | Value written | Error code |
|---|---|---|---|---|
| 1 | 99 | `label.text` | `"Hi"` | `LayerNotFound` |
| 2 | 3 | `layer.frame` | A rectangle | `AttributeNotEditable` |
| 3 | 3 | `view.alpha` | `StringValue` | `InvalidAttributeValue` |
| 4 | 3 | `label.numberOfLines` | No `value` (nil) | `InvalidAttributeValue` |
| 5 | 3 | `view.alpha` | 1.5, above its limit of 1 | `InvalidAttributeValue` (P-SET-07) |
| 6 | 3 | `layer.bounds` | −20, 0, −20, 24: x is free, width is below its limit of 0 | `InvalidAttributeValue` (P-SET-07) |
| 7 | 3 | `layer.opacity` | 0.5: layer 3 backs a view, so its groups have `view.alpha` instead | `AttributeNotEditable` (P-ATTR-11, P-SET-03) |

## The `subtree` scenario

Getting the subtree of node 4 replies with nodes 4 and 5, exactly as in the `hierarchy` scenario; node 4's `parent_id` is still 2, and `key_window_id` is 1. Getting layer 99, which does not exist, replies with `LayerNotFound`.

## The `layout-constraints` scenario (0.4; constraints 8 to 11 changed to the shapes UIKit actually uses in 0.5)

One `GetLayerDetails` requests layers 3, 4, 9, 8 and 99, each for constraints only (`want_constraints`), in one chunk. The layers are the nodes of the `hierarchy` scenario. Constraints are written as "first item.attribute relation second item.attribute × multiplier + constant", where the numbers are layer IDs:

| ID | Constraint | Priority | `status` | Appears in | Notable |
|---|---|---|---|---|---|
| 1 | `3.centerX == 2.centerX` | 1000 | `Satisfied` | 3 | |
| 2 | `3.top == 2.safeAreaLayoutGuide.top + 49` | 1000 | `Satisfied` | 3 | The second item is a layout guide: `guide_id` 1, `UILayoutGuide`, `identifier` `UIViewSafeAreaLayoutGuide`, `guide_frame` 0, 59, 393, 759 |
| 3 | `3.width == 240` | 250 | `Unsatisfied` | 3 | No second item; has `identifier` `titleLabel.preferredWidth`; layer 3 is actually 200 wide |
| 4 | `4.top == 3.bottom + 78` | 1000 | `Satisfied` | 3, 4 | Exactly the same in both places; layer 4 is rotated 30°, and by the untransformed geometry its top is 300 − 90 = 210, which equals 132 + 78 |
| 5 | `4.width == 300` | 1000 | `Satisfied` | 4 | No second item |
| 6 | `4.height == 180` | 1000 | `Satisfied` | 4 | No second item |
| 7 | `4.centerX == 2.centerX` | 1000 | `Satisfied` | 4 | |
| 8 to 11 | `2.width == 9.maxX + 93`, `9.width == 0`, `9.minY == 700`, `9.height == 0` | 1000 | `Satisfied` | 9 | `class_name` is `NSAutoresizingMaskLayoutConstraint` (P-LAYOUT-02); they use attributes UIKit does not make public (P-LAYOUT-07, 0.5): the left margin is flexible and written from the superview's side, 393 = 300 + 93; the top margin is fixed, with no second item |

All multipliers are 1. The `class_name` of constraints 1 to 7 is `NSLayoutConstraint`, and their `origin` is `App`; constraints 8 to 11 are `System` (P-LAYOUT-09). The safe area guide has `guide_kind` `SafeArea` (P-LAYOUT-04). Layer 8 does not back a view, so its details have no `constraints`; layer 99 does not exist, and its `status` is `LayerNotFound`.
