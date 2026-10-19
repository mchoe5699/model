"""Software renderer for the generated OBJ (textured, z-buffered) – used to check the model
without launching Minecraft.   python3 tools/preview.py <model json name> <out.png>"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RES = os.path.join(ROOT, "src/main/resources/assets")


def rl_path(rl, kind):
    ns, path = rl.split(":")
    return os.path.join(RES, ns, path) if kind == "raw" else os.path.join(RES, ns, "textures", path + ".png")


def load(model_name):
    mj = json.load(open(os.path.join(RES, "qwertys_model/models/block", model_name + ".json")))
    obj = rl_path(mj["model"], "raw")
    v, vt, faces, mat = [], [], [], None
    mtl = {}
    for line in open(obj):
        p = line.split()
        if not p:
            continue
        if p[0] == "mtllib":
            for l2 in open(rl_path(p[1], "raw")):
                q = l2.split()
                if q and q[0] == "newmtl":
                    cur = q[1]
                if q and q[0] == "map_Kd":
                    mtl[cur] = q[1]
        elif p[0] == "v":
            v.append(tuple(map(float, p[1:4])))
        elif p[0] == "vt":
            vt.append(tuple(map(float, p[1:3])))
        elif p[0] == "usemtl":
            mat = p[1]
        elif p[0] == "f":
            idx = [tuple(int(x) - 1 for x in t.split("/")[:2]) for t in p[1:]]
            faces.append((mat, idx))
    tex = {}
    for m, ref in mtl.items():
        rl = mj["textures"][ref[1:]]
        tex[m] = np.asarray(Image.open(rl_path(rl, "tex")).convert("RGBA"), dtype=np.float32)
    return np.array(v), np.array(vt), faces, tex, mj.get("flip_v", False)


def render(model_name, yaw, pitch, size=700, zoom=1.0):
    v, vt, faces, tex, flip = load(model_name)
    c = (v.min(0) + v.max(0)) / 2
    ext = float((v.max(0) - v.min(0)).max())
    ry, rx = math.radians(yaw), math.radians(pitch)
    Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
    Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
    R = Rx @ Ry
    # camera looks along +z toward the device front (device faces -z / north)
    P = (v - c) @ R.T
    scale = size * 0.8 / ext * zoom
    sx = size / 2 - P[:, 0] * scale        # mirror x so north face reads correctly
    sy = size / 2 - P[:, 1] * scale
    depth = P[:, 2]
    img = np.full((size, size, 3), 235.0)
    zb = np.full((size, size), np.inf)
    light = np.array([0.35, 0.6, -0.72]); light /= np.linalg.norm(light)
    for mat, idx in faces:
        tris = [idx] if len(idx) == 3 else [[idx[0], idx[1], idx[2]], [idx[0], idx[2], idx[3]]]
        T = tex[mat]
        th, tw = T.shape[:2]
        for tri in tris:
            vi = [a for a, _ in tri]
            ti = [b for _, b in tri]
            p0, p1, p2 = (np.array([sx[i], sy[i]]) for i in vi)
            w3 = v[vi]
            n = np.cross(w3[1] - w3[0], w3[2] - w3[0])
            nl = np.linalg.norm(n)
            if nl < 1e-12:
                continue
            n /= nl
            nv = R @ n
            if nv[2] >= 0:      # back-face (normal pointing away from camera at -z)
                continue
            shade = 0.55 + 0.45 * max(0.0, float(np.dot(n, -light)))
            minx, maxx = int(max(0, min(p0[0], p1[0], p2[0]))), int(min(size - 1, max(p0[0], p1[0], p2[0]) + 1))
            miny, maxy = int(max(0, min(p0[1], p1[1], p2[1]))), int(min(size - 1, max(p0[1], p1[1], p2[1]) + 1))
            if minx > maxx or miny > maxy:
                continue
            xs, ys = np.meshgrid(np.arange(minx, maxx + 1) + 0.5, np.arange(miny, maxy + 1) + 0.5)
            d = (p1[1] - p2[1]) * (p0[0] - p2[0]) + (p2[0] - p1[0]) * (p0[1] - p2[1])
            if abs(d) < 1e-12:
                continue
            a = ((p1[1] - p2[1]) * (xs - p2[0]) + (p2[0] - p1[0]) * (ys - p2[1])) / d
            b = ((p2[1] - p0[1]) * (xs - p2[0]) + (p0[0] - p2[0]) * (ys - p2[1])) / d
            g = 1 - a - b
            mask = (a >= -1e-4) & (b >= -1e-4) & (g >= -1e-4)
            if not mask.any():
                continue
            z = a * depth[vi[0]] + b * depth[vi[1]] + g * depth[vi[2]]
            uv = [vt[i] for i in ti]
            u = a * uv[0][0] + b * uv[1][0] + g * uv[2][0]
            vv = a * uv[0][1] + b * uv[1][1] + g * uv[2][1]
            if flip:
                vv = 1 - vv
            tx = np.clip((u * tw).astype(int), 0, tw - 1)
            ty = np.clip((vv * th).astype(int), 0, th - 1)
            col = T[ty, tx]
            mask &= col[..., 3] > 127
            yy, xx = np.nonzero(mask)
            yy_full, xx_full = yy + miny, xx + minx
            zz = z[yy, xx] - 1e-6 * (mat == "decal")
            closer = zz < zb[yy_full, xx_full]
            yy_full, xx_full, yy, xx, zz = yy_full[closer], xx_full[closer], yy[closer], xx[closer], zz[closer]
            zb[yy_full, xx_full] = zz
            img[yy_full, xx_full] = col[yy, xx, :3] * shade
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


if __name__ == "__main__":
    name = sys.argv[1]
    out = sys.argv[2]
    views = [(0, 0, 1.0), (35, -18, 1.0), (-55, -12, 1.0), (88, 0, 1.0), (25, 60, 1.0), (30, -15, 2.6)]
    ims = [render(name, y, p, 520, z) for y, p, z in views]
    sheet = Image.new("RGB", (520 * 3, 520 * 2), "white")
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % 3) * 520, (i // 3) * 520))
    sheet.save(out)
