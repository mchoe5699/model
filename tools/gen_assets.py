"""Builds the 3D HT-100 door camera: OBJ mesh + MTL, textures, block/item models and blockstates.

Run from the repository root:  python3 tools/gen_assets.py   (needs Pillow + numpy)

All dimensions are in model pixels (1 block = 16 px), measured from the front/side photos
(front photo scale: 49.4 photo px = 1 model px).
Authoring frame (see meshlib): u = from viewer's left, w = up, d = out from the wall.
The device occupies u 0..10, w 0..13.2 and sits on the wall (d = 0) facing north.
"""
import json
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

import meshlib as ml
from meshlib import Mesh, rounded_rect, filleted_solid, recess, cylinder_ring, annulus, dome

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ASSETS = os.path.join(ROOT, "src/main/resources/assets/qwertys_model")
TEX = os.path.join(ASSETS, "textures/block")
MODELS = os.path.join(ASSETS, "models/block")
ITEMS = os.path.join(ASSETS, "models/item")
STATES = os.path.join(ASSETS, "blockstates")
MODID = "qwertys_model"

# Real size: 0.2 block tall (3.2 px); width follows the photo ratio (10 : 13.2 -> 2.42 px).
# Depth: the side photos give tray + cover ~ 23 % of the height, so depth is compressed by 12 %.
SCALE = 3.2 / 13.2            # authoring px -> block px
DEPTH_SCALE = SCALE * 0.88
CENTER_X, CENTER_Y = 8.0, 8.0  # centred on the wall face
WALL_Z = 16.0

DEV_W, DEV_H, DEV_D = 10.0, 13.2, 4.0

# ------------------------------------------------------------------ dimensions (px)
BASE = dict(u0=0.0, w0=0.0, u1=10.0, w1=13.2, r=0.4, d0=0.0, d1=2.1, fillet=0.14)
COVER = dict(u0=0.12, w0=0.12, u1=9.88, w1=13.08, r=0.55, d0=1.6, d1=3.4, fillet=0.4)

# camera hood: a wedge – nearly flush at the top, standing proud at its curved lower edge
HOOD = dict(u0=1.05, w0=4.9, u1=9.0, w1=13.0, r_bottom=0.95, r_top=0.32,
            d0=COVER["d1"], thick=0.6, fillet=0.27, top_scale=0.35)

WINDOW = dict(u0=2.75, w0=6.6, u1=7.3, w1=11.2, r=0.22, frame=3.52)
GLASS = dict(u0=3.05, w0=6.9, u1=7.0, w1=10.9, r=0.14, floor=3.44)
IR_STRIP = (3.4, 8.8, 6.66, 10.7)            # u0, w0, u1, w1 (tinted window over the IR LEDs)
IR_LEDS = [(3.4 + (6.66 - 3.4) * (k + 0.5) / 4, 9.75) for k in range(4)]
LENS = dict(u=5.04, w=7.71, r_bezel=1.0, r_barrel=0.8, r_glass=0.58)

GRILLE = dict(u0=1.26, u1=5.4, slots=[13.2 - (9.15 + k * 0.53) for k in range(6)], h=0.18, depth=0.34)
POCKET = dict(u0=6.17, w0=1.2, u1=9.1, w1=4.25, r=0.32, depth=0.26)
BUTTON = dict(inset=0.13, r=0.22, proud=0.07, fillet=0.1)
LED = dict(u0=7.345, w0=3.77, u1=7.875, w1=3.97)
MICS = [(9.1, 13.2 - 1.62, 9.45, 13.2 - 1.48), (9.1, 13.2 - 1.94, 9.45, 13.2 - 1.80)]
TAB = dict(cu=5.14, half=0.52, top=1.12, bottom=-0.07, d0=3.4, d1=3.53, under_d0=2.25)
DECAL = dict(u0=2.7, w0=11.48, u1=7.25, w1=12.42)
SNAP_SLOTS = [(9.5, 10.3), (2.7, 3.5)]        # w ranges of the snap slots on both base sides


def hood_scale(w):
    t = (HOOD["w1"] - w) / (HOOD["w1"] - HOOD["w0"])
    t = min(max(t, 0.0), 1.0)
    return HOOD["top_scale"] + (1 - HOOD["top_scale"]) * t


def hood_front(w):
    return HOOD["d0"] + HOOD["thick"] * hood_scale(w)


def hood_radii():
    return [HOOD["r_bottom"], HOOD["r_bottom"], HOOD["r_top"], HOOD["r_top"]]


# ------------------------------------------------------------------ geometry

def box(m, mat, u0, u1, w0, w1, d0, d1, skip=()):
    P = lambda a, b, c: (a, b, c)
    faces = {
        "-u": ([P(u0, w0, d0), P(u0, w0, d1), P(u0, w1, d1), P(u0, w1, d0)], (-1, 0, 0)),
        "+u": ([P(u1, w0, d0), P(u1, w1, d0), P(u1, w1, d1), P(u1, w0, d1)], (1, 0, 0)),
        "-w": ([P(u0, w0, d0), P(u1, w0, d0), P(u1, w0, d1), P(u0, w0, d1)], (0, -1, 0)),
        "+w": ([P(u0, w1, d0), P(u0, w1, d1), P(u1, w1, d1), P(u1, w1, d0)], (0, 1, 0)),
        "-d": ([P(u0, w0, d0), P(u0, w1, d0), P(u1, w1, d0), P(u1, w0, d0)], (0, 0, -1)),
        "+d": ([P(u0, w0, d1), P(u1, w0, d1), P(u1, w1, d1), P(u0, w1, d1)], (0, 0, 1)),
    }
    for k, (pts, n) in faces.items():
        if k not in skip:
            m.face(mat, pts, n)


def build_mesh():
    m = Mesh()

    # 1. wall base / back tray
    b = BASE
    filleted_solid(m, "base", lambda i: rounded_rect(b["u0"], b["w0"], b["u1"], b["w1"], [b["r"]] * 4, 8, i),
                   b["d0"], b["d1"], b["fillet"], 3)
    # snap slots on both sides of the tray with the cover's clip showing inside
    for (s0, s1) in SNAP_SLOTS:
        for side, uu in ((-1, b["u0"]), (1, b["u1"])):
            off = 0.004 * side
            m.face("slot", [(uu + off, s0, 0.9), (uu + off, s1, 0.9), (uu + off, s1, 1.6), (uu + off, s0, 1.6)],
                   (side, 0, 0))
            cu0, cu1 = (uu - 0.002, uu + 0.06) if side > 0 else (uu - 0.06, uu + 0.002)
            box(m, "body", cu0, cu1, s0 + 0.08, s1 - 0.08, 0.97, 1.53, skip=("-u",) if side > 0 else ("+u",))

    # 2. front cover with heavily rounded front edge, cut-outs for grille, button pocket, mics
    c = COVER
    holes = []
    for wc in GRILLE["slots"]:
        hh = GRILLE["h"] / 2
        holes.append(dict(loop=rounded_rect(GRILLE["u0"], wc - hh, GRILLE["u1"], wc + hh, [hh * 0.98] * 4, 5),
                          depth=GRILLE["depth"], mat="slot"))
    p = POCKET
    holes.append(dict(loop=rounded_rect(p["u0"], p["w0"], p["u1"], p["w1"], [p["r"]] * 4, 6),
                      depth=p["depth"], mat="slot"))
    for (a0, b0, a1, b1) in MICS:
        r = (b1 - b0) / 2 * 0.98
        holes.append(dict(loop=rounded_rect(a0, b0, a1, b1, [r] * 4, 4), depth=0.22, mat="slot"))
    filleted_solid(m, "body", lambda i: rounded_rect(c["u0"], c["w0"], c["u1"], c["w1"], [c["r"]] * 4, 10, i),
                   c["d0"], c["d1"], c["fillet"], 6, holes=holes, back_cap=False)

    # 3. camera hood (wedge) with the window opening
    h = HOOD
    win = WINDOW
    win_loop = rounded_rect(win["u0"], win["w0"], win["u1"], win["w1"], [win["r"]] * 4, 5)
    hood = Mesh()
    filleted_solid(hood, "body", lambda i: rounded_rect(h["u0"], h["w0"], h["u1"], h["w1"], hood_radii(), 12, i),
                   h["d0"] - 0.5, h["d0"] + h["thick"], h["fillet"], 5, back_cap=False,
                   holes=[dict(loop=win_loop, depth=0.0, mat="window_wall")])
    hood.faces = [f for f in hood.faces if f["mat"] != "window_wall"]
    for f in hood.faces:
        f["pts"] = [(q[0], q[1], h["d0"] + (q[2] - h["d0"]) * hood_scale(q[1]) if q[2] > h["d0"] else q[2])
                    for q in f["pts"]]
    m.faces += hood.faces
    # window walls: from the slanted hood face down to the grey frame
    top = [(q[0], q[1], hood_front(q[1])) for q in win_loop]
    bot = [(q[0], q[1], win["frame"]) for q in win_loop]
    wcu, wcw = (win["u0"] + win["u1"]) / 2, (win["w0"] + win["w1"]) / 2
    m.strip("window_wall", top, bot, None, outward_fn=lambda cc: (wcu - cc[0], wcw - cc[1], 0.0))
    # grey window frame with the glass set a step deeper
    g = GLASS
    glass_loop = rounded_rect(g["u0"], g["w0"], g["u1"], g["w1"], [g["r"]] * 4, 4)
    m.cap("insert", win_loop, win["frame"], +1, [glass_loop],
          uv=("rect", win["u0"], win["w0"], win["u1"], win["w1"]))
    recess(m, glass_loop, win["frame"], g["floor"], "window_wall", "glass",
           floor_uv=("rect", g["u0"], g["w0"], g["u1"], g["w1"]))

    # 4. IR LEDs under the tinted strip
    for (lu, lw) in IR_LEDS:
        dome(m, "ir_led", lu, lw, 0.2, g["floor"], 0.06, seg=12, rings=2,
             uv=("rect", lu - 0.2, lw - 0.2, lu + 0.2, lw + 0.2))

    # 5. lens: metal bezel, black barrel step, coated glass dome
    L = LENS
    fl = g["floor"]
    bezel_uv = ("rect", L["u"] - L["r_bezel"], L["w"] - L["r_bezel"], L["u"] + L["r_bezel"], L["w"] + L["r_bezel"])
    cylinder_ring(m, "lens_bezel", L["u"], L["w"], L["r_bezel"], fl, fl + 0.17, seg=32, uv=bezel_uv)
    annulus(m, "lens_bezel", L["u"], L["w"], L["r_barrel"], L["r_bezel"], fl + 0.17, seg=32, uv=bezel_uv)
    cylinder_ring(m, "lens_ring", L["u"], L["w"], L["r_barrel"], fl + 0.17, fl + 0.12, seg=32, inward=True)
    annulus(m, "lens_ring", L["u"], L["w"], L["r_glass"], L["r_barrel"], fl + 0.12, seg=32, uv=bezel_uv)
    cylinder_ring(m, "lens_ring", L["u"], L["w"], L["r_glass"], fl + 0.12, fl + 0.07, seg=32, inward=True)
    lens_uv = ("rect", L["u"] - L["r_glass"], L["w"] - L["r_glass"], L["u"] + L["r_glass"], L["w"] + L["r_glass"])
    dome(m, "lens_glass", L["u"], L["w"], L["r_glass"], fl + 0.07, 0.09, seg=32, rings=4, uv=lens_uv)

    # 6. call button in its pocket, with a recessed LED light pipe
    bi = BUTTON["inset"]
    bu0, bw0, bu1, bw1 = p["u0"] + bi, p["w0"] + bi, p["u1"] - bi, p["w1"] - bi
    led_r = (LED["w1"] - LED["w0"]) / 2 * 0.98
    led_loop = rounded_rect(LED["u0"], LED["w0"], LED["u1"], LED["w1"], [led_r] * 4, 4)
    start = len(m.faces)
    filleted_solid(m, "body", lambda i: rounded_rect(bu0, bw0, bu1, bw1, [BUTTON["r"]] * 4, 6, i),
                   c["d1"] - p["depth"], c["d1"] + BUTTON["proud"], BUTTON["fillet"], 3,
                   back_cap=False, front_mat="button",
                   holes=[dict(loop=led_loop, depth=0.035, mat="slot", floor_mat="led",
                               floor_uv=("rect", LED["u0"], LED["w0"], LED["u1"], LED["w1"]))])
    for f in m.faces[start:]:
        if f["mat"] == "button":
            f["uv"] = ("rect", bu0, bw0, bu1, bw1)

    # 7. bottom latch: front plate with a round top + the strip that wraps under the edge
    t = TAB
    outline = [(t["cu"] - t["half"], t["bottom"]), (t["cu"] + t["half"], t["bottom"])]
    outline += [(t["cu"] + t["half"] * math.cos(math.radians(a)), t["top"] - t["half"] + t["half"] * math.sin(math.radians(a)))
                for a in range(0, 181, 10)]
    filleted_solid(m, "tab", lambda i: _offset(outline, i), t["d0"], t["d1"], 0.045, 2)
    yb = t["bottom"] - 0.06
    under = [(t["cu"] - t["half"], yb, t["under_d0"]), (t["cu"] + t["half"], yb, t["under_d0"]),
             (t["cu"] + t["half"], yb, t["d1"]), (t["cu"] - t["half"], yb, t["d1"])]
    m.face("tab", under, (0, -1, 0))
    m.face("tab", [(q[0], COVER["w0"] + 0.01, q[2]) for q in under], (0, 1, 0))
    for side in (-1, 1):
        uu = t["cu"] + side * t["half"]
        m.face("tab", [(uu, yb, t["under_d0"]), (uu, COVER["w0"] + 0.01, t["under_d0"]),
                       (uu, COVER["w0"] + 0.01, t["d0"]), (uu, yb, t["d0"])], (side, 0, 0))
    m.face("tab", [(t["cu"] - t["half"], yb, t["under_d0"]), (t["cu"] + t["half"], yb, t["under_d0"]),
                   (t["cu"] + t["half"], COVER["w0"] + 0.01, t["under_d0"]),
                   (t["cu"] - t["half"], COVER["w0"] + 0.01, t["under_d0"])], (0, 0, -1))

    # 8. printed logo / model name, following the slanted hood face
    dc = DECAL
    quad = [(dc["u0"], dc["w0"]), (dc["u1"], dc["w0"]), (dc["u1"], dc["w1"]), (dc["u0"], dc["w1"])]
    m.face("decal", [(q[0], q[1], hood_front(q[1]) + 0.012) for q in quad], (0, 0, 1),
           uv=("rect", dc["u0"], dc["w0"], dc["u1"], dc["w1"]))
    return m


def _offset(outline, d):
    if d == 0:
        return list(outline)
    cu = sum(q[0] for q in outline) / len(outline)
    cw = sum(q[1] for q in outline) / len(outline)
    out = []
    for q in outline:
        vx, vy = cu - q[0], cw - q[1]
        l = math.hypot(vx, vy) or 1
        out.append((q[0] + vx / l * d, q[1] + vy / l * d))
    return out


# ------------------------------------------------------------------ UVs + OBJ export

SIDE_SPLIT = ("body", "base")   # these get a separate *_side material for faces not facing front


def classify(f, n):
    au, aw, ad = (abs(x) for x in n)
    front = ad >= au and ad >= aw
    mat = f["mat"]
    if mat in SIDE_SPLIT and not front and f["uv"] is None:
        mat = mat + "_side"
    return mat


def face_uv(f, mat, p, n):
    mode = f["uv"]
    if mode and mode[0] == "rect":
        _, u0, w0, u1, w1 = mode
        return ((p[0] - u0) / (u1 - u0), (p[1] - w0) / (w1 - w0))
    au, aw, ad = (abs(x) for x in n)
    if mat.endswith("_side"):
        if au >= aw:   # left/right walls: left half of the texture (left wall, right wall)
            return ((0.0 if n[0] < 0 else 0.25) + p[2] / DEV_D * 0.25, p[1] / DEV_H)
        # top/bottom walls: right half (bottom = lower quarter... top = upper)
        return (0.5 + p[0] / DEV_W * 0.5, (0.5 if n[1] > 0 else 0.0) + p[2] / DEV_D * 0.5)
    if ad >= au and ad >= aw:
        return (p[0] / DEV_W, p[1] / DEV_H)
    if au >= aw:
        return (p[2] / DEV_D, p[1] / DEV_H)
    return (p[0] / DEV_W, p[2] / DEV_D)


def to_block(p):
    x = CENTER_X - (p[0] - DEV_W / 2) * SCALE
    y = CENTER_Y + (p[1] - DEV_H / 2) * SCALE
    z = WALL_Z - p[2] * DEPTH_SCALE
    return (x / 16.0, y / 16.0, z / 16.0)


def to_block_normal(n):
    # normals transform with the inverse scale (non-uniform depth scale)
    x, y, z = -n[0] / SCALE, n[1] / SCALE, -n[2] / DEPTH_SCALE
    l = math.sqrt(x * x + y * y + z * z)
    return (x / l, y / l, z / l)


def export_obj(mesh, obj_path, mtl_rl):
    v, vt, vn = [], [], []
    by_mat = {}
    for f in mesh.faces:
        n = ml.newell(f["pts"])
        if n is None:
            continue
        by_mat.setdefault(classify(f, n), []).append((f, n))
    out = ["# HT-100 door camera - generated by tools/gen_assets.py", f"mtllib {mtl_rl}"]
    lines = []
    for mat, faces in by_mat.items():
        lines.append(f"usemtl {mat}")
        for f, n in faces:
            pts = f["pts"]
            polys = [pts] if len(pts) <= 4 else [[pts[0], pts[i], pts[i + 1]] for i in range(1, len(pts) - 1)]
            for poly in polys:
                vn.append(to_block_normal(n))
                ni = len(vn)
                idx = []
                for q in poly:
                    v.append(to_block(q))
                    vt.append(face_uv(f, mat, q, n))
                    idx.append(f"{len(v)}/{len(vt)}/{ni}")
                lines.append("f " + " ".join(idx))
    out += [f"v {a:.6f} {b:.6f} {c:.6f}" for a, b, c in v]
    out += [f"vt {a:.6f} {b:.6f}" for a, b in vt]
    out += [f"vn {a:.5f} {b:.5f} {c:.5f}" for a, b, c in vn]
    out += lines
    with open(obj_path, "w") as fh:
        fh.write("\n".join(out) + "\n")
    return len(v), sum(len(x) for x in by_mat.values()), sorted(by_mat)


MATERIALS = ["base", "base_side", "body", "body_side", "slot", "window_wall", "insert", "glass", "ir_led",
             "lens_bezel", "lens_ring", "lens_glass", "button", "led", "tab", "decal"]


def export_mtl(path):
    out = []
    for mname in MATERIALS:
        out += [f"newmtl {mname}", "Ka 1.0 1.0 1.0", "Kd 1.0 1.0 1.0", "Ks 0.0 0.0 0.0", "d 1.0",
                f"map_Kd #{mname}", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(out))


# ------------------------------------------------------------------ texture helpers (numpy, float RGB 0..1)

PAL = {
    "clean": dict(body=(0.886, 0.866, 0.784), base=(0.850, 0.843, 0.796), button=(0.900, 0.884, 0.812),
                  ir=(0.13, 0.11, 0.30), insert=(0.40, 0.42, 0.395), text=(0.25, 0.31, 0.42)),
    "aged": dict(body=(0.845, 0.807, 0.672), base=(0.828, 0.818, 0.760), button=(0.868, 0.838, 0.722),
                 ir=(0.16, 0.34, 0.80), insert=(0.37, 0.40, 0.36), text=(0.25, 0.30, 0.41)),
}


def fbm(size, seed, octaves=5, base=4):
    """smooth value noise in 0..1"""
    rng = np.random.default_rng(seed)
    out = np.zeros((size, size))
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        n = base * (2 ** o)
        g = rng.random((n + 1, n + 1))
        img = Image.fromarray((g * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
        out += np.asarray(img, dtype=np.float64) / 255 * amp
        tot += amp
        amp *= 0.5
    return out / tot


def grain(size, seed, amp):
    rng = np.random.default_rng(seed)
    return 1 + (rng.random((size, size)) - 0.5) * 2 * amp


def solid(size, col):
    return np.ones((size, size, 3)) * np.array(col)


def to_img(arr):
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "RGB").convert("RGBA")


def mask_from(draw_fn, size, blur=0.0):
    im = Image.new("L", (size, size), 0)
    draw_fn(ImageDraw.Draw(im))
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(im, dtype=np.float64) / 255


def lerp(a, b, t):
    t = t[..., None] if np.ndim(t) == 2 else t
    return a * (1 - t) + b * t


def F(u, w, size):
    """device front coordinate -> pixel in a front-mapped texture"""
    return (u / DEV_W * size, (1 - w / DEV_H) * size)


def poly_px(loop, size):
    return [F(q[0], q[1], size) for q in loop]


# ------------------------------------------------------------------ textures

def body_front_tex(pal, aged, S=512):
    p = PAL[pal]
    col = solid(S, p["body"])
    # low-frequency tone variation + fine moulding grain
    col *= (0.975 + 0.05 * fbm(S, 3))[..., None]
    col *= grain(S, 4, 0.012)[..., None]

    hood_loop = rounded_rect(HOOD["u0"], HOOD["w0"], HOOD["u1"], HOOD["w1"], hood_radii(), 12)
    hood = mask_from(lambda d: d.polygon(poly_px(hood_loop, S), fill=255), S)
    # soft contact shadow cast by the hood onto the cover (light from above)
    shifted = [F(q[0], q[1] - 0.22, S) for q in hood_loop]
    shadow = mask_from(lambda d: d.polygon(shifted, fill=255), S, blur=S * 0.012)
    shadow = np.clip(shadow - hood, 0, 1)
    col *= (1 - 0.30 * shadow)[..., None]
    # hood face: slightly darker toward its lower lip (face tilts down), thin highlight on the top lip
    ww = np.linspace(DEV_H, 0, S)[:, None] * np.ones((1, S))
    tilt = np.clip((HOOD["w1"] - ww) / (HOOD["w1"] - HOOD["w0"]), 0, 1)
    col *= (1 - hood * 0.06 * tilt)[..., None]

    # ambient occlusion rims around every cut-out
    def ring(loop, width, strength, blur):
        pts = poly_px(loop, S)
        m = mask_from(lambda d: d.line(pts + [pts[0]], fill=255, width=int(width)), S, blur=blur)
        return m * strength
    ao = np.zeros((S, S))
    for wc in GRILLE["slots"]:
        hh = GRILLE["h"] / 2
        ao += ring(rounded_rect(GRILLE["u0"], wc - hh, GRILLE["u1"], wc + hh, [hh * 0.98] * 4, 5), 4, 0.18, 2)
    ao += ring(rounded_rect(POCKET["u0"], POCKET["w0"], POCKET["u1"], POCKET["w1"], [POCKET["r"]] * 4, 6), 5, 0.22, 3)
    ao += ring(rounded_rect(WINDOW["u0"], WINDOW["w0"], WINDOW["u1"], WINDOW["w1"], [WINDOW["r"]] * 4, 5), 4, 0.2, 2.5)
    for (a0, b0, a1, b1) in MICS:
        ao += ring(rounded_rect(a0, b0, a1, b1, [(b1 - b0) / 2 * 0.98] * 4, 4), 3, 0.2, 1.5)
    col *= (1 - np.clip(ao, 0, 0.45))[..., None]

    # darker band where the front edge rolls over (fillet area), lighter crest just inside it
    uu = np.linspace(0, DEV_W, S)[None, :] * np.ones((S, 1))
    edge = np.minimum.reduce([uu - COVER["u0"], COVER["u1"] - uu, ww - COVER["w0"], COVER["w1"] - ww])
    roll = np.clip(1 - edge / COVER["fillet"], 0, 1)
    col *= (1 - 0.16 * roll ** 1.6)[..., None]
    crest = np.exp(-((edge - COVER["fillet"] * 1.15) / 0.06) ** 2) * (1 - hood)
    col = col * (1 + 0.04 * crest)[..., None]

    if aged:
        col = age_front(col, S, hood)
    return to_img(col)


def age_front(col, S, hood):
    rnd = random.Random(77)
    uu = np.linspace(0, DEV_W, S)[None, :] * np.ones((S, 1))
    ww = np.linspace(DEV_H, 0, S)[:, None] * np.ones((1, S))
    # UV yellowing, stronger low and toward the left (sun side), plus blotchy grime
    yellow = 0.5 + 0.5 * fbm(S, 21, 4, 3)
    col = lerp(col, col * np.array([0.97, 0.93, 0.80]), yellow * 0.6)
    grime = fbm(S, 22, 5, 6)
    weight = np.clip(0.25 + 0.45 * (1 - ww / DEV_H) + 0.25 * (1 - uu / DEV_W), 0, 1)
    col = lerp(col, col * np.array([0.78, 0.74, 0.64]), np.clip((grime - 0.45) * 2.2, 0, 1) * weight * 0.7)
    # finger grime around the call button
    fx, fy = F((POCKET["u0"] + POCKET["u1"]) / 2, (POCKET["w0"] + POCKET["w1"]) / 2, S)
    yy, xx = np.mgrid[0:S, 0:S]
    fg = np.exp(-(((xx - fx) / (S * 0.10)) ** 2 + ((yy - fy) / (S * 0.09)) ** 2))
    col = lerp(col, col * np.array([0.82, 0.78, 0.68]), fg * 0.35)

    img = to_img(col)
    d = ImageDraw.Draw(img, "RGBA")
    # yellowed tape residue under the window (photo: torn rectangle, darker rim)
    tl = F(4.39, 6.74, S); br = F(7.83, 5.02, S)
    pts = []
    for k in range(18):
        t = k / 17
        pts.append((tl[0] + (br[0] - tl[0]) * t, tl[1] + rnd.uniform(-3, 3)))
    for k in range(10):
        t = k / 9
        pts.append((br[0] + rnd.uniform(-3, 2), tl[1] + (br[1] - tl[1]) * t))
    for k in range(18):
        t = k / 17
        pts.append((br[0] - (br[0] - tl[0]) * t, br[1] + rnd.uniform(-4, 2)))
    for k in range(10):
        t = k / 9
        pts.append((tl[0] + rnd.uniform(-2, 3), br[1] - (br[1] - tl[1]) * t))
    d.polygon(pts, fill=(205, 180, 110, 70), outline=(150, 128, 70, 120))
    # black scuffs (bottom-left of cover, left edge, right edge)
    for (u0, w0, u1, w1, n) in [(1.2, 0.6, 3.0, 1.5, 14), (0.15, 6.5, 0.6, 8.7, 8), (9.55, 8.0, 9.85, 9.9, 8),
                                (0.4, 3.0, 1.2, 4.2, 6)]:
        for _ in range(n):
            x0, y0 = F(rnd.uniform(u0, u1), rnd.uniform(w0, w1), S)
            d.line([(x0, y0), (x0 + rnd.uniform(-10, 10), y0 + rnd.uniform(-6, 6))],
                   fill=(55, 50, 42, rnd.randint(90, 170)), width=rnd.choice([1, 2, 2, 3]))
    # white wall-paint smears on the left edge and top-left corner
    for (u0, w0, u1, w1, n) in [(0.1, 6.6, 0.9, 9.4, 16), (0.1, 11.8, 1.6, 13.0, 12), (8.8, 12.4, 9.8, 13.0, 6)]:
        for _ in range(n):
            x0, y0 = F(rnd.uniform(u0, u1), rnd.uniform(w0, w1), S)
            r = rnd.uniform(1.5, 5)
            d.ellipse((x0 - r, y0 - r * 0.6, x0 + r, y0 + r * 0.6), fill=(246, 245, 238, rnd.randint(150, 230)))
    # fine light scratches
    for _ in range(70):
        x0, y0 = rnd.uniform(0, S), rnd.uniform(0, S)
        a = rnd.uniform(0, math.pi)
        L = rnd.uniform(6, 30)
        d.line([(x0, y0), (x0 + L * math.cos(a), y0 + L * math.sin(a))], fill=(240, 235, 215, 70), width=1)
    # dirt collected below the speaker slots
    for wc in GRILLE["slots"]:
        x0, y0 = F(GRILLE["u0"], wc - GRILLE["h"] / 2, S)
        x1, _ = F(GRILLE["u1"], wc, S)
        d.line([(x0 + 4, y0 + 2), (x1 - 4, y0 + 2)], fill=(90, 80, 60, 70), width=2)
    return np.asarray(img.convert("RGB"), dtype=np.float64) / 255


def side_tex(col_rgb, aged, base=False, S=512):
    col = solid(S, col_rgb)
    col *= (0.975 + 0.05 * fbm(S, 31 if base else 32))[..., None]
    col *= grain(S, 33, 0.012)[..., None]
    # sides face away from the light a bit: gentle gradient (lighter near the front edge)
    dd = np.zeros((S, S))
    xs = np.arange(S)
    # left half: two side walls, d grows to the right inside each quarter
    q = (xs % (S // 4)) / (S // 4)
    dd[:, : S // 2] = q[: S // 2][None, :]
    col *= (0.93 + 0.07 * dd)[..., None]
    if not aged:
        return to_img(col)
    col = lerp(col, col * np.array([0.96, 0.92, 0.80]), 0.5 * fbm(S, 34, 4, 3))
    img = to_img(col)
    d = ImageDraw.Draw(img, "RGBA")
    rnd = random.Random(35 if base else 36)

    def side_px(left, dd_, w):     # side-wall coordinate -> pixel
        u = (0.0 if left else 0.25) + dd_ / DEV_D * 0.25
        return (u * S, (1 - w / DEV_H) * S)

    if base:
        # white paint chips concentrated along the front rim of the tray and the top-left corner
        for _ in range(140):
            left = rnd.random() < 0.65
            w = rnd.uniform(0, DEV_H)
            dd_ = BASE["d1"] - abs(rnd.gauss(0, 0.35))
            if left and rnd.random() < 0.4:
                w = rnd.uniform(10.5, 13.2)
            x, y = side_px(left, max(dd_, 0), w)
            r = rnd.uniform(1, 4)
            d.ellipse((x - r * 0.6, y - r, x + r * 0.6, y + r), fill=(248, 248, 244, 235))
        # paper label stuck on the left side of the tray (photo 1)
        x0, y0 = side_px(True, 0.25, 6.2)
        x1, y1 = side_px(True, 1.95, 1.4)
        d.rectangle((x0, y0, x1, y1), fill=(238, 236, 226, 255), outline=(200, 196, 182, 255))
        for k in range(7):
            yy = y0 + 12 + k * (y1 - y0 - 20) / 7
            d.line([(x0 + 6, yy), (x0 + 6 + rnd.uniform(12, x1 - x0 - 14), yy + rnd.uniform(-2, 2))],
                   fill=(40, 40, 50, 200), width=2)
        for _ in range(20):
            x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
            d.point((x, y), fill=(30, 30, 30, 255))
    else:
        for _ in range(30):
            left = rnd.random() < 0.7
            x, y = side_px(left, rnd.uniform(1.6, 3.4), rnd.uniform(0, DEV_H))
            d.line([(x, y), (x + rnd.uniform(-4, 4), y + rnd.uniform(-10, 10))], fill=(60, 54, 44, 120), width=2)
    return img


def base_front_tex(pal, aged, S=256):
    col = solid(S, PAL[pal]["base"])
    col *= (0.98 + 0.04 * fbm(S, 41))[..., None]
    col *= grain(S, 42, 0.01)[..., None]
    img = to_img(col)
    if aged:
        d = ImageDraw.Draw(img, "RGBA")
        rnd = random.Random(43)
        for _ in range(60):
            u = rnd.choice([rnd.uniform(0, 0.4), rnd.uniform(9.6, 10)]) if rnd.random() < 0.7 else rnd.uniform(0, 10)
            w = rnd.uniform(0, 13.2) if rnd.random() < 0.6 else rnd.choice([rnd.uniform(0, 0.4), rnd.uniform(12.8, 13.2)])
            x, y = F(u, w, S)
            r = rnd.uniform(0.8, 2.5)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(248, 248, 244, 240))
    return img


def window_frame_tex(pal, S=128):
    col = solid(S, PAL[pal]["insert"])
    col *= grain(S, 51, 0.02)[..., None]
    yy = np.linspace(0, 1, S)[:, None] * np.ones((1, S))
    col *= (1.05 - 0.1 * yy)[..., None]          # light falls from the top of the opening
    return to_img(col)


def glass_tex(pal, ir_on, aged, S=256):
    p = PAL[pal]
    g = GLASS
    col = solid(S, (0.13, 0.14, 0.15))
    col *= (0.9 + 0.2 * fbm(S, 61, 3, 2))[..., None]
    img = to_img(col)
    d = ImageDraw.Draw(img, "RGBA")

    def px(u, w):
        return ((u - g["u0"]) / (g["u1"] - g["u0"]) * S, (1 - (w - g["w0"]) / (g["w1"] - g["w0"])) * S)

    a = px(IR_STRIP[0], IR_STRIP[3]); b = px(IR_STRIP[2], IR_STRIP[1])
    strip_col = (100, 16, 26) if ir_on else tuple(int(x * 255) for x in p["ir"])
    d.rectangle((a[0], a[1], b[0], b[1]), fill=strip_col + (255,))
    # tint window: lighter at its top edge
    grad = Image.new("L", (S, S), 0)
    gd = ImageDraw.Draw(grad)
    hgt = int(b[1] - a[1])
    for k in range(hgt):
        gd.line([(a[0], a[1] + k), (b[0], a[1] + k)], fill=int(40 * (1 - k / hgt)))
    img = Image.composite(Image.new("RGBA", (S, S), (255, 255, 255, 255)), img, grad)
    if ir_on:
        glow = Image.new("L", (S, S), 0)
        gl = ImageDraw.Draw(glow)
        for (lu, lw) in IR_LEDS:
            cx, cy = px(lu, lw)
            gl.ellipse((cx - 16, cy - 13, cx + 16, cy + 13), fill=150)
        glow = glow.filter(ImageFilter.GaussianBlur(6))
        img = Image.composite(Image.new("RGBA", (S, S), (255, 70, 60, 255)), img, glow)
    # glossy diagonal reflection across the whole glass
    refl = Image.new("L", (S, S), 0)
    rd = ImageDraw.Draw(refl)
    rd.polygon([(S * 0.05, 0), (S * 0.32, 0), (S * 0.02, S * 0.55), (0, S * 0.55)], fill=60)
    rd.polygon([(S * 0.40, 0), (S * 0.47, 0), (S * 0.10, S * 0.7), (S * 0.05, S * 0.7)], fill=35)
    refl = refl.filter(ImageFilter.GaussianBlur(3))
    img = Image.composite(Image.new("RGBA", (S, S), (255, 255, 255, 255)), img, refl)
    if aged:   # peeling protective film edge
        d = ImageDraw.Draw(img, "RGBA")
        film = [px(3.15, 10.85), px(3.55, 9.0), px(3.25, 7.3), px(4.6, 7.0), px(6.3, 7.05), px(6.9, 8.2),
                px(6.45, 9.6), px(6.95, 10.85)]
        d.line(film, fill=(205, 215, 222, 210), width=3)
        d.polygon(film[:4] + [px(3.15, 7.0)], fill=(220, 225, 230, 40))
    return img


def ir_led_tex(lit, S=32):
    img = Image.new("RGBA", (S, S), (50, 14, 18, 255) if not lit else (255, 70, 60, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((6, 5, 14, 12), fill=(255, 220, 220, 255) if lit else (140, 90, 95, 255))
    return img


def lens_bezel_tex(S=128):
    yy, xx = np.mgrid[0:S, 0:S]
    c = (S - 1) / 2
    r = np.hypot(xx - c, yy - c) / c
    ang = np.arctan2(yy - c, xx - c)
    # brushed metal ring: radial falloff + angular sheen
    metal = 0.55 + 0.25 * np.cos(ang * 2 + 0.6) + 0.08 * np.cos(r * 60)
    col = np.stack([metal * 0.92, metal * 0.94, metal * 0.98], -1)
    inner = r < LENS["r_barrel"] / LENS["r_bezel"]
    col[inner] = np.array([0.08, 0.08, 0.09])
    return to_img(col)


def lens_glass_tex(S=64):
    yy, xx = np.mgrid[0:S, 0:S]
    c = (S - 1) / 2
    r = np.hypot(xx - c, yy - c) / c
    col = np.zeros((S, S, 3))
    col[...] = np.array([0.05, 0.06, 0.08])
    # anti-reflection coating: purple/green rings
    col += (np.exp(-((r - 0.75) / 0.08) ** 2))[..., None] * np.array([0.25, 0.10, 0.35])
    col += (np.exp(-((r - 0.45) / 0.06) ** 2))[..., None] * np.array([0.05, 0.22, 0.12])
    # pupil
    col[r < 0.25] = np.array([0.02, 0.02, 0.03])
    img = to_img(col)
    d = ImageDraw.Draw(img)
    d.ellipse((S * 0.25, S * 0.2, S * 0.42, S * 0.36), fill=(225, 230, 240, 255))
    d.ellipse((S * 0.58, S * 0.6, S * 0.64, S * 0.66), fill=(150, 160, 180, 255))
    return img


def button_tex(pal, aged, S=128):
    col = solid(S, PAL[pal]["button"])
    col *= grain(S, 71, 0.01)[..., None]
    yy, xx = np.mgrid[0:S, 0:S] / (S - 1)
    # very slightly dished face: darker toward the middle-bottom, light at the top edge
    dish = np.exp(-(((xx - 0.5) / 0.45) ** 2 + ((yy - 0.55) / 0.5) ** 2))
    col *= (1.02 - 0.05 * dish)[..., None]
    col *= (1 + 0.04 * np.clip(1 - yy / 0.08, 0, 1))[..., None]
    if aged:
        thumb = np.exp(-(((xx - 0.5) / 0.28) ** 2 + ((yy - 0.6) / 0.3) ** 2))
        col = lerp(col, col * np.array([0.80, 0.76, 0.66]), thumb * 0.55)
    return to_img(col)


def led_tex(lit, S=32):
    if lit:
        img = Image.new("RGBA", (S, S), (255, 120, 30, 255))
        ImageDraw.Draw(img).ellipse((6, 4, S - 7, S // 2), fill=(255, 225, 160, 255))
    else:
        img = Image.new("RGBA", (S, S), (70, 40, 26, 255))
        ImageDraw.Draw(img).ellipse((6, 4, S - 7, S // 2), fill=(120, 80, 60, 255))
    return img


def tab_tex(S=32):
    col = solid(S, (0.76, 0.77, 0.78))
    col *= grain(S, 81, 0.02)[..., None]
    return to_img(col)


def flat(col, S=16, amp=0.03, seed=1):
    return to_img(solid(S, col) * grain(S, seed, amp)[..., None])


def decal_tex(pal, aged):
    p = PAL[pal]
    W, H = 512, 512
    img = Image.new("RGBA", (W, 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = tuple(int(x * 255) for x in p["text"]) + (255 if not aged else 225,)
    hx, hy, hs = 14, 12, 72
    d.line([(hx, hy + hs * 0.5), (hx + hs * 0.5, hy + 4), (hx + hs, hy + hs * 0.5)], fill=col, width=7)
    d.rectangle((hx + hs * 0.18, hy + hs * 0.5, hx + hs * 0.82, hy + hs * 0.95), outline=col, width=6)
    d.rectangle((hx + hs * 0.42, hy + hs * 0.66, hx + hs * 0.58, hy + hs * 0.95), fill=col)
    try:
        big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)
        small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except OSError:
        big = small = ImageFont.load_default()
    d.text((112, 2), "HT-100", font=big, fill=col)
    d.text((112, 58), "DOOR CAMERA", font=small, fill=col)
    if aged:   # worn print: knock a few pixels out
        rnd = random.Random(91)
        px = img.load()
        for _ in range(1800):
            x, y = rnd.randrange(W), rnd.randrange(100)
            px[x, y] = (0, 0, 0, 0)
    return img.resize((W, H), Image.LANCZOS)


# ------------------------------------------------------------------ writers

def opaque(img):
    img = img.convert("RGBA")
    img.putalpha(255)
    return img


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _display():
    """Item transforms: enlarge the 0.2-block model and cancel its offset toward the wall,
    so it sits centred in the slot / hand.  MC applies translate -> rotateXYZ -> scale."""
    zc = (WALL_Z - (3.4 + HOOD["thick"]) * DEPTH_SCALE / 2) - 8.0     # model centre offset (px) from block centre
    def make(rot, s, extra=(0, 0, 0)):
        rx, ry, rz = (math.radians(a) for a in rot)
        Rx = np.array([[1, 0, 0], [0, math.cos(rx), -math.sin(rx)], [0, math.sin(rx), math.cos(rx)]])
        Ry = np.array([[math.cos(ry), 0, math.sin(ry)], [0, 1, 0], [-math.sin(ry), 0, math.cos(ry)]])
        Rz = np.array([[math.cos(rz), -math.sin(rz), 0], [math.sin(rz), math.cos(rz), 0], [0, 0, 1]])
        off = Rx @ Ry @ Rz @ np.array([0.0, 0.0, zc * s])
        tr = [round(float(-off[i] + extra[i]), 3) for i in range(3)]
        return {"rotation": list(rot), "translation": tr, "scale": [s, s, s]}
    return {
        "gui": make((15, 200, 0), 3.6),
        "fixed": make((0, 180, 0), 3.0),
        "ground": make((0, 0, 0), 1.6, (0, 2, 0)),
        "head": make((0, 180, 0), 2.0, (0, 6, 0)),
        "thirdperson_righthand": make((10, 200, 0), 1.6, (0, 2, 1)),
        "thirdperson_lefthand": make((10, 200, 0), 1.6, (0, 2, 1)),
        "firstperson_righthand": make((0, 200, 0), 1.8, (1, 3, 0)),
        "firstperson_lefthand": make((0, 200, 0), 1.8, (1, 3, 0)),
    }


DISPLAY = _display()


def save(img, name, keep_alpha=False):
    (img if keep_alpha else opaque(img)).save(os.path.join(TEX, name + ".png"))


def main():
    for dd in (TEX, MODELS, ITEMS, STATES):
        os.makedirs(dd, exist_ok=True)
    for dd in (TEX, MODELS):
        for fn in os.listdir(dd):
            if fn.startswith(("ht100_door_camera", "door_camera")):
                os.remove(os.path.join(dd, fn))

    mesh = build_mesh()
    obj_name = "ht100_door_camera"
    mtl_rl = f"{MODID}:models/block/{obj_name}.mtl"
    nv, nf, mats = export_obj(mesh, os.path.join(MODELS, obj_name + ".obj"), mtl_rl)
    assert set(mats) <= set(MATERIALS), mats
    export_mtl(os.path.join(MODELS, obj_name + ".mtl"))
    print(f"mesh: {nf} faces, {nv} vertices, materials: {', '.join(mats)}")

    pre = "ht100_door_camera"
    save(flat((0.07, 0.07, 0.065)), f"{pre}_slot")
    save(flat((0.24, 0.25, 0.24)), f"{pre}_window_wall")
    save(flat((0.09, 0.09, 0.10), amp=0.05), f"{pre}_lens_ring")
    save(lens_bezel_tex(), f"{pre}_lens_bezel")
    save(lens_glass_tex(), f"{pre}_lens_glass")
    save(tab_tex(), f"{pre}_tab")
    for lit in (False, True):
        save(ir_led_tex(lit), f"{pre}_ir_led{'_on' if lit else ''}")
        save(led_tex(lit), f"{pre}_led{'_on' if lit else ''}")

    blocks = {"ht100_door_camera": "clean", "ht100_door_camera_aged": "aged"}
    rot = {"north": 0, "east": 90, "south": 180, "west": 270}
    for block, pal in blocks.items():
        aged = pal == "aged"
        t = lambda name: f"{MODID}:block/{name}"
        save(body_front_tex(pal, aged), f"{block}_body")
        save(side_tex(PAL[pal]["body"], aged, base=False), f"{block}_body_side")
        save(base_front_tex(pal, aged), f"{block}_base")
        save(side_tex(PAL[pal]["base"], aged, base=True), f"{block}_base_side")
        save(window_frame_tex(pal), f"{block}_insert")
        save(button_tex(pal, aged), f"{block}_button")
        save(decal_tex(pal, aged), f"{block}_decal", keep_alpha=True)
        for ir in (False, True):
            save(glass_tex(pal, ir, aged), f"{block}_glass{'_ir' if ir else ''}")
        for ir in (False, True):
            for call in (False, True):
                suffix = ("_ir" if ir else "") + ("_call" if call else "")
                write_json(os.path.join(MODELS, f"{block}{suffix}.json"), {
                    "loader": "forge:obj",
                    "model": f"{MODID}:models/block/{obj_name}.obj",
                    "flip_v": True,
                    "shade_quads": True,
                    "emissive_ambient": True,
                    "automatic_culling": True,
                    "render_type": "minecraft:cutout",
                    "ambientocclusion": False,
                    "textures": {
                        "particle": t(f"{block}_body"),
                        "base": t(f"{block}_base"),
                        "base_side": t(f"{block}_base_side"),
                        "body": t(f"{block}_body"),
                        "body_side": t(f"{block}_body_side"),
                        "slot": t(f"{pre}_slot"),
                        "window_wall": t(f"{pre}_window_wall"),
                        "insert": t(f"{block}_insert"),
                        "glass": t(f"{block}_glass{'_ir' if ir else ''}"),
                        "ir_led": t(f"{pre}_ir_led{'_on' if ir else ''}"),
                        "lens_bezel": t(f"{pre}_lens_bezel"),
                        "lens_ring": t(f"{pre}_lens_ring"),
                        "lens_glass": t(f"{pre}_lens_glass"),
                        "button": t(f"{block}_button"),
                        "led": t(f"{pre}_led{'_on' if call else ''}"),
                        "tab": t(f"{pre}_tab"),
                        "decal": t(f"{block}_decal"),
                    },
                    "display": DISPLAY,
                })
        variants = {}
        for facing, y in rot.items():
            for call in (0, 1, 2):
                for lit in (False, True):
                    suffix = ("_ir" if lit else "") + ("_call" if call > 0 else "")
                    v = {"model": f"{MODID}:block/{block}{suffix}"}
                    if y:
                        v["y"] = y
                    variants[f"call={call},facing={facing},lit={str(lit).lower()}"] = v
        write_json(os.path.join(STATES, block + ".json"), {"variants": variants})
        write_json(os.path.join(ITEMS, block + ".json"), {"parent": f"{MODID}:block/{block}"})


if __name__ == "__main__":
    main()
