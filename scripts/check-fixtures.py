#!/usr/bin/env python3
"""Checks that the fixture sources obey the protocol clauses a schema cannot express.

Usage: check-fixtures.py <fixtures/src>

The hierarchy's order and its view controller and member reference fields
(P-HIER-01, 03, 07 to 09). Per scenario: request ids, stream sequencing and chunk counts (P-REQ-01, 03),
one detail per requested layer (P-DET-01), what each detail contains against
what was asked (P-DET-02 to 04), and every image's size and data (P-DET-07,
P-IMG-01, 02).
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


def main():
    root = sys.argv[1]
    scenarios = {}
    for path in sorted(glob.glob(os.path.join(root, "*", "*.json"))):
        scenario, name = path.split(os.sep)[-2:]
        scenarios.setdefault(scenario, []).append((name, json.load(open(path, encoding="utf-8"))))

    nodes = {}
    for name, frame in scenarios.get("hierarchy", []):
        if frame.get("body_type") == "Hierarchy":
            listed = frame["body"].get("nodes", [])
            seen = set()
            for node in listed:
                parent = node.get("parent_id", 0)
                if node.get("id", 0) == 0:
                    problem("hierarchy/" + name, "a node has id 0 (P-HIER-03)")
                if parent != 0 and parent not in seen:
                    problem("hierarchy/" + name, "node %d appears before its parent %d (P-HIER-01)" % (node["id"], parent))
                spot = "hierarchy/%s node %d" % (name, node.get("id", 0))
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
                seen.add(node["id"])
                nodes[node["id"]] = node
    children = {}
    for node in nodes.values():
        children.setdefault(node.get("parent_id", 0), []).append(node["id"])

    for scenario, frames in sorted(scenarios.items()):
        last_id, requests, streams = 0, {}, {}
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
