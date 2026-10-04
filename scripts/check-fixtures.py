#!/usr/bin/env python3
"""Checks that the fixture sources obey the protocol clauses a schema cannot express.

Usage: check-fixtures.py <fixtures/src>

The hierarchy's order and its view controller and member reference fields
(P-HIER-01, 03, 07 to 09). Per scenario: request ids, stream sequencing and chunk counts (P-REQ-01, 03),
one detail per requested layer (P-DET-01), what each detail contains against
what was asked (P-DET-02 to 04), and every image's size and data (P-DET-07,
P-IMG-01, 02). Every attribute's editing fields (P-ATTR-06, 07). Each plain
request gets one response with its request id (P-REQ-02); a subtree is the
hierarchy's subtree under the asked root (P-HIER-10, 11); and the answer to
each SetAttribute is the one P-SET-01 to 03 call for, judged by the
attributes the fixtures give for that layer.
"""

import glob
import json
import os
import subprocess
import sys

problems = []


def problem(where, text):
    problems.append("%s: %s" % (where, text))


def decompress(data):
    result = subprocess.run(["compression_tool", "-decode", "-a", "lzfse"], input=bytes(data), capture_output=True)
    return result.stdout if result.returncode == 0 else None


def check_image(where, image, bounds):
    width, height = image.get("pixel_width", 0), image.get("pixel_height", 0)
    row, scale = image.get("bytes_per_row", 0), image.get("scale", 0)
    if row < width * 4:
        problem(where, "bytes_per_row %d is less than pixel_width x 4 (P-IMG-02)" % row)
    raw = decompress(image.get("data", []))
    if raw is None:
        problem(where, "data is not valid LZFSE (P-IMG-01)")
    elif len(raw) != row * height:
        problem(where, "data decompresses to %d bytes, expected %d (P-IMG-01)" % (len(raw), row * height))
    if bounds is not None and scale:
        size = bounds["size"]
        if abs(width / scale - size["width"]) > 0.5 or abs(height / scale - size["height"]) > 0.5:
            problem(where, "image is %gx%g pt but the layer's bounds are %gx%g (P-DET-07)"
                    % (width / scale, height / scale, size["width"], size["height"]))


PLAIN_RESPONSES = {
    "GetAppIcon": "AppIcon",
    "GetHierarchy": "Hierarchy",
    "GetSubtree": "Hierarchy",
    "SetAttribute": "SetAttributeResult",
}


def check_nodes(where, listed, first_parent=None):
    """Checks a pre-order node list. The first node's parent may lie outside the list when first_parent is set."""
    seen = set()
    for index, node in enumerate(listed):
        parent = node.get("parent_id", 0)
        if node.get("id", 0) == 0:
            problem(where, "a node has id 0 (P-HIER-03)")
        outside = index == 0 and first_parent is not None
        if outside and parent != first_parent:
            problem(where, "the subtree's root has parent %d, expected %d (P-HIER-10)" % (parent, first_parent))
        if not outside and parent != 0 and parent not in seen:
            problem(where, "node %d appears before its parent %d (P-HIER-01)" % (node.get("id", 0), parent))
        spot = "%s node %d" % (where, node.get("id", 0))
        controller = ("view_controller_class_name" in node, "view_controller_display_class_name" in node)
        if controller[0] != controller[1]:
            problem(spot, "view controller names must be given together (P-HIER-07)")
        if any(controller) and "view_class_name" not in node:
            problem(spot, "only a layer that backs a view can back a view controller's root view (P-HIER-07)")
        references = node.get("member_references", [])
        if references and parent == 0:
            problem(spot, "a root layer has no ancestors to hold it (P-HIER-08)")
        for reference in references:
            if not all(reference.get(key) for key in ("owner_class_name", "owner_display_class_name", "name")):
                problem(spot, "a member reference needs both class names and a name (P-HIER-09)")
        seen.add(node.get("id", 0))


def check_attributes(where, groups):
    for group in groups:
        for attribute in group.get("attributes", []):
            spot = "%s attribute %s" % (where, attribute.get("id"))
            kind = attribute.get("value_kind", "None")
            if kind == "None":
                problem(spot, "value_kind must be given, also when the value is nil (P-ATTR-06)")
            elif "value_type" in attribute and attribute["value_type"] != kind:
                problem(spot, "value_kind %s does not match the value's %s (P-ATTR-06)" % (kind, attribute["value_type"]))
            if attribute.get("value_type") == "EnumValue":
                value = attribute.get("value", {})
                cases, values = value.get("cases", []), value.get("case_values", [])
                if len(values) != len(cases):
                    problem(spot, "case_values has %d entries for %d cases (P-ATTR-07)" % (len(values), len(cases)))
                elif value.get("value", 0) not in values or cases[values.index(value.get("value", 0))] != value.get("case_name"):
                    problem(spot, "value and case_name do not name the same case (P-ATTR-07)")


def attribute_frames(scenarios):
    """Yields (where, layer id, attribute groups) for every attribute list a Server sends."""
    for scenario, frames in sorted(scenarios.items()):
        for name, frame in frames:
            where, body = "%s/%s" % (scenario, name), frame.get("body", {})
            if frame.get("body_type") == "LayerDetailsChunk":
                for detail in body.get("details", []):
                    if "attribute_groups" in detail:
                        yield where, detail.get("layer_id"), detail["attribute_groups"]
            elif frame.get("body_type") == "SetAttributeResult":
                yield where, body.get("layer_id"), body.get("attribute_groups", [])


def expected_set_error(body, nodes, attributes):
    """The error code P-SET-03 calls for, or None when the SetAttribute must succeed."""
    layer, attribute_id = body.get("layer_id", 0), body.get("attribute_id")
    if layer not in nodes:
        return "LayerNotFound"
    known = attributes.get((layer, attribute_id))
    if known is None or not known.get("editable", False):
        return "AttributeNotEditable"
    kind = body.get("value_type")
    if kind is None:
        return None if known.get("accepts_nil", False) else "InvalidAttributeValue"
    if kind != known.get("value_kind"):
        return "InvalidAttributeValue"
    if kind == "EnumValue" and body.get("value", {}).get("value", 0) not in known.get("value", {}).get("case_values", []):
        return "InvalidAttributeValue"
    return None


def main():
    root = sys.argv[1]
    scenarios = {}
    for path in sorted(glob.glob(os.path.join(root, "*", "*.json"))):
        scenario, name = path.split(os.sep)[-2:]
        scenarios.setdefault(scenario, []).append((name, json.load(open(path, encoding="utf-8"))))

    nodes, order, key_window = {}, [], 0
    for name, frame in scenarios.get("hierarchy", []):
        if frame.get("body_type") == "Hierarchy":
            listed = frame["body"].get("nodes", [])
            check_nodes("hierarchy/" + name, listed)
            nodes.update((node["id"], node) for node in listed)
            order = [node["id"] for node in listed]
            key_window = frame["body"].get("key_window_id", 0)
    children = {}
    for node in nodes.values():
        children.setdefault(node.get("parent_id", 0), []).append(node["id"])

    attributes, flags = {}, {}
    for where, layer, groups in attribute_frames(scenarios):
        check_attributes(where, groups)
        for group in groups:
            for attribute in group.get("attributes", []):
                key = (layer, attribute.get("id"))
                attributes.setdefault(key, attribute)
                marks = tuple(attribute.get(field) for field in ("editable", "accepts_nil", "value_kind"))
                if flags.setdefault(key, marks) != marks:
                    problem(where, "layer %s attribute %s changes its editing fields between fixtures" % key)

    for scenario, frames in sorted(scenarios.items()):
        last_id, requests, streams, plain = 0, {}, {}, {}
        for name, frame in frames:
            where = "%s/%s" % (scenario, name)
            direction = name.split("-")[1]
            request_id, kind, body = frame.get("request_id", 0), frame.get("body_type"), frame.get("body", {})
            if direction == "c2s":
                if kind != "Hello":
                    if request_id <= last_id:
                        problem(where, "request_id %d does not increase (P-REQ-01)" % request_id)
                    last_id = request_id
                elif request_id != 0:
                    problem(where, "Hello must use request_id 0 (P-HELLO-01)")
                if kind == "GetLayerDetails":
                    requests[request_id] = body.get("requests", [])
                    streams[request_id] = {"chunks": 0, "seen": [], "ended": None}
                if kind in PLAIN_RESPONSES:
                    plain[request_id] = (kind, body)
            elif kind in PLAIN_RESPONSES.values() or (kind == "Error" and request_id in plain):
                if request_id not in plain:
                    problem(where, "%s answers no pending request %d (P-REQ-02)" % (kind, request_id))
                    continue
                asked, question = plain.pop(request_id)
                if kind not in (PLAIN_RESPONSES[asked], "Error"):
                    problem(where, "%s answers a %s (P-REQ-02)" % (kind, asked))
                    continue
                if asked == "GetSubtree":
                    root = question.get("root_id", 0)
                    wanted = None if root in nodes else "LayerNotFound"
                    if kind == "Hierarchy" and wanted is None:
                        listed = body.get("nodes", [])
                        inside = set()
                        for layer in order:
                            if layer == root or nodes[layer].get("parent_id", 0) in inside:
                                inside.add(layer)
                        expected = [layer for layer in order if layer in inside]
                        if [node.get("id") for node in listed] != expected:
                            problem(where, "subtree of %d must list %s (P-HIER-10)" % (root, expected))
                        check_nodes(where, listed, nodes[root].get("parent_id", 0))
                        if body.get("key_window_id", 0) != key_window:
                            problem(where, "key_window_id differs from the hierarchy's (P-HIER-10)")
                elif asked == "SetAttribute":
                    wanted = expected_set_error(question, nodes, attributes)
                    if kind == "SetAttributeResult" and wanted is None:
                        if body.get("layer_id") != question.get("layer_id"):
                            problem(where, "layer_id differs from the request's (P-SET-01)")
                        ids = [a.get("id") for g in body.get("attribute_groups", []) for a in g.get("attributes", [])]
                        if question.get("attribute_id") not in ids:
                            problem(where, "the result must hold the attribute that was set (P-SET-01)")
                if asked in ("GetSubtree", "SetAttribute"):
                    got = body.get("code", "Unknown") if kind == "Error" else None
                    if got != wanted:
                        problem(where, "answered with %s, the protocol calls for %s (P-HIER-11, P-SET-03)"
                                % (got or kind, wanted or PLAIN_RESPONSES[asked]))
            elif kind in ("Hello", "AppStateChanged"):
                if request_id != 0:
                    problem(where, "%s must use request_id 0" % kind)
            elif kind == "LayerDetailsChunk":
                stream = streams.get(request_id)
                if stream is None:
                    problem(where, "chunk for an unknown request %d" % request_id)
                    continue
                if body.get("sequence", 0) != stream["chunks"]:
                    problem(where, "sequence %d, expected %d (P-REQ-03)" % (body.get("sequence", 0), stream["chunks"]))
                stream["chunks"] += 1
                wanted = {r["layer_id"]: r for r in requests[request_id]}
                for detail in body.get("details", []):
                    layer, status = detail.get("layer_id"), detail.get("status", "Ok")
                    stream["seen"].append(layer)
                    spot = "%s layer %s" % (where, layer)
                    ask = wanted.get(layer)
                    if ask is None:
                        problem(spot, "was not requested")
                        continue
                    if status == "LayerNotFound" and (set(detail) - {"layer_id", "status"}):
                        problem(spot, "LayerNotFound must carry nothing else (P-DET-02)")
                    if status == "CaptureFailed" and ("solo" in detail or "group" in detail):
                        problem(spot, "CaptureFailed must not carry images (P-DET-03)")
                    if status == "Ok":
                        leaf = not children.get(layer)
                        if ask.get("want_group", False) != ("group" in detail):
                            problem(spot, "group image presence does not match the request")
                        if "solo" in detail and not ask.get("want_solo", False):
                            problem(spot, "solo image was not requested")
                        if ask.get("want_solo", False) and "solo" not in detail and not (leaf and "group" in detail):
                            problem(spot, "solo may be omitted only for a layer without sublayers, with group present (P-DET-04)")
                        if ask.get("want_attributes", False) != ("attribute_groups" in detail):
                            problem(spot, "attribute presence does not match the request")
                    if status != "LayerNotFound" and "attribute_groups" in detail and not ask.get("want_attributes", False):
                        problem(spot, "attributes were not requested")
                    for key in ("solo", "group"):
                        if key in detail:
                            check_image("%s %s" % (spot, key), detail[key], nodes.get(layer, {}).get("bounds"))
            elif kind == "StreamEnd":
                stream = streams.get(request_id)
                if stream is None:
                    problem(where, "StreamEnd for an unknown request %d" % request_id)
                    continue
                stream["ended"] = body.get("status", "Completed")
                if body.get("chunk_count", 0) != stream["chunks"]:
                    problem(where, "chunk_count %d, but %d chunk(s) were sent (P-REQ-03)" % (body.get("chunk_count", 0), stream["chunks"]))
                if stream["ended"] == "Failed" and "error" not in body:
                    problem(where, "a failed stream must carry an error (P-REQ-05)")
                if stream["ended"] == "Completed":
                    asked = [r["layer_id"] for r in requests[request_id]]
                    if sorted(stream["seen"]) != sorted(asked):
                        problem(where, "a completed stream must hold each requested layer once: asked %s, got %s (P-DET-01)" % (asked, stream["seen"]))
                    elif stream["seen"] != asked:
                        problem(where, "details must follow the request order (P-DET-06)")
            elif kind == "AppIcon" and "image" in body:
                check_image(where, body["image"], None)
        for request_id, (asked, _) in plain.items():
            problem(scenario, "%s %d is never answered (P-REQ-02)" % (asked, request_id))
        for request_id, stream in streams.items():
            if stream["ended"] is None:
                problem(scenario, "stream %d never ends (P-REQ-03)" % request_id)

    if problems:
        print("check-fixtures: %d problem(s):" % len(problems))
        for text in problems:
            print("  - " + text)
        sys.exit(1)
    print("check-fixtures: %d scenario(s) ok" % len(scenarios))


if __name__ == "__main__":
    main()
