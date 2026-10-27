"""Convert pinned CC0 MakeHuman data to a clothed, compact local athlete mesh.

No MakeHuman program code is imported. Source assets and license hashes are
recorded separately; run from the repository root after acquiring those assets.
"""
import hashlib
import json
import math
from pathlib import Path

SOURCE = Path("out/reference-assets")
DEST = Path("web/assets/athlete")


def build():
    provenance = DEST / "provenance.json"
    if provenance.exists():
        pinned = json.loads(provenance.read_text())
        for name, expected in pinned["files"].items():
            if hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Pinned source hash mismatch: {name}")
    vertices, groups, group = [], {}, ""
    for line in (SOURCE / "base.obj").read_text().splitlines():
        if line.startswith("v "):
            vertices.append(list(map(float, line.split()[1:4])))
        elif line.startswith("g "):
            group = line[2:]
        elif line.startswith("f "):
            groups.setdefault(group, []).append([int(p.split("/")[0]) - 1 for p in line.split()[1:]])
    for line in (SOURCE / "athlete.target").read_text().splitlines():
        if line and not line.startswith("#"):
            index, *delta = line.split()
            for axis in range(3):
                vertices[int(index)][axis] += float(delta[axis]) * 0.75
    rig = json.loads((SOURCE / "rig.json").read_text())
    weights = json.loads((SOURCE / "weights.json").read_text())["weights"]
    body_indices = sorted({i for face in groups["body"] for i in face})
    ground = min(vertices[i][1] for i in body_indices)
    scale = 1.85 / (max(vertices[i][1] for i in body_indices) - ground)
    def point(v):
        return [round(v[0] * scale, 6), round((v[1] - ground) * scale, 6), round(v[2] * scale, 6)]
    keep = {"root", "spine05", "spine03", "spine01", "neck01", "head"}
    for side in ("L", "R"):
        keep.update(f"{bone}.{side}" for bone in ("pelvis", "shoulder01", "upperarm01", "lowerarm01", "wrist", "upperleg01", "lowerleg01", "foot"))
    names = sorted(keep)
    def retained(name):
        while name not in keep:
            name = rig["bones"][name]["parent"]
        return name
    bones = []
    for name in names:
        bone = rig["bones"][name]
        joint = rig["joints"][bone["head"]]
        head = [sum(vertices[i][axis] for i in joint) / len(joint) for axis in range(3)]
        parent = retained(bone["parent"]) if bone["parent"] else None
        bones.append({"name": name, "parent": names.index(parent) if parent else -1, "head": point(head)})
    by_vertex = {}
    for name, values in weights.items():
        index = names.index(retained(name))
        for vertex, weight in values:
            values_ = by_vertex.setdefault(vertex, {})
            values_[index] = values_.get(index, 0) + weight
    positions, skin_indices, skin_weights, regions = [], [], [], []
    for index in body_indices:
        p = point(vertices[index]); x, y, z = p
        influences = sorted(by_vertex.get(index, {names.index("root"): 1}).items(), key=lambda item: -item[1])[:4]
        dominant = names[influences[0][0]]
        arm = "arm" in dominant or "wrist" in dominant
        region = 0
        if 0.94 < y < 1.53 and not arm:
            region = 1
        elif "upperarm" in dominant:
            shoulder = bones[names.index("upperarm01." + dominant[-1])]["head"]
            if sum((p[a] - shoulder[a]) ** 2 for a in range(3)) < 0.17 ** 2:
                region = 1
        elif 0.67 < y <= 0.94 and not arm:
            region = 2
        elif 0.13 < y < 0.37:
            region = 3
        elif y <= 0.13:
            region = 4
        # Garments have their own silhouette instead of painted bare anatomy.
        if region in (1, 2):
            p[0] *= 1.07; p[2] *= 1.12
        positions.extend(p); regions.append(region)
        total = sum(w for _, w in influences)
        skin_indices.extend([i for i, _ in influences] + [0] * (4 - len(influences)))
        skin_weights.extend([round(w / total, 6) for _, w in influences] + [0] * (4 - len(influences)))
    remap = {old: new for new, old in enumerate(body_indices)}
    indices = []
    for face in groups["body"]:
        for i in range(1, len(face) - 1):
            indices.extend(remap[v] for v in (face[0], face[i], face[i + 1]))
    # Facial detail is part of the skinned mesh, avoiding 110 separate eye/hair draws.
    def sphere(center, radius, region, max_theta=math.pi):
        start = len(positions) // 3
        for row in range(9):
            theta = row / 8 * max_theta
            for col in range(13):
                phi = col / 12 * math.pi * 2
                positions.extend([round(center[0] + radius[0] * math.sin(theta) * math.cos(phi), 6),
                                  round(center[1] + radius[1] * math.cos(theta), 6),
                                  round(center[2] + radius[2] * math.sin(theta) * math.sin(phi), 6)])
                regions.append(region); skin_indices.extend([names.index("head"), 0, 0, 0]); skin_weights.extend([1, 0, 0, 0])
        for row in range(8):
            for col in range(12):
                a = start + row * 13 + col; b = a + 13
                indices.extend([a, a + 1, b, a + 1, b + 1, b])
    sphere([0, 1.752, 0.016], [0.095, 0.112, 0.105], 5, math.pi * 0.53)
    eyes = [point([sum(vertices[i][a] for i in rig["joints"][rig["bones"]["eye." + side]["head"]]) /
                   len(rig["joints"][rig["bones"]["eye." + side]["head"]]) for a in range(3)]) for side in ("L", "R")]
    for eye in eyes:
        sphere(eye, [0.0105, 0.0105, 0.0105], 6)
        sphere([eye[0], eye[1], eye[2] + 0.008], [0.0045, 0.0045, 0.0045], 7)
    model = {"version": 1, "height": 1.85, "positions": positions, "indices": indices,
             "skinIndices": skin_indices, "skinWeights": skin_weights, "regions": regions, "bones": bones,
             "eyes": eyes}
    DEST.mkdir(parents=True, exist_ok=True)
    output = DEST / "athlete.json"
    output.write_text(json.dumps(model, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    (DEST / "CC0.txt").write_bytes((SOURCE / "CC0.txt").read_bytes())
    metadata = {"source": "https://github.com/makehumancommunity/makehuman", "commit": "a8bc2d54ff0ac92e78ff71431b1023eda42bf482",
                "license": "CC0-1.0", "vertices": len(positions) // 3, "triangles": len(indices) // 3, "bones": len(bones),
                "files": {name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest()
                          for name in ("base.obj", "athlete.target", "rig.json", "weights.json", "CC0.txt")},
                "athleteSHA256": hashlib.sha256(output.read_bytes()).hexdigest()}
    (DEST / "provenance.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8", newline="\n")
    print({k: metadata[k] for k in ("vertices", "triangles", "bones", "athleteSHA256")})


if __name__ == "__main__":
    build()
