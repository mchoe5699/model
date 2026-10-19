"""Builds the 3D HT-100 door camera: OBJ mesh + MTL, textures, block/item models and blockstates.

Run from the repository root:  python3 tools/gen_assets.py   (needs Pillow)

All dimensions are in model pixels (1 block = 16 px) and were measured from front/side photos.
Authoring frame (see meshlib): u = from viewer's left, w = up, d = out from the wall.
The device occupies u 0..10, w 0..13.2 and sits on the wall (d = 0) facing north.
"""
import json
import math
import os
import random

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

# block-space placement of the authoring frame
U_ORIGIN_X = 13.0     # x = 13 - u
W_ORIGIN_Y = 1.4      # y = 1.4 + w
WALL_Z = 16.0         # z = 16 - d

DEV_W, DEV_H = 10.0, 13.2

# ------------------------------------------------------------------ dimensions (px)
BASE = dict(u0=0.0, w0=0.0, u1=10.0, w1=13.2, r=0.4, d0=0.0, d1=2.1, fillet=0.12)
COVER = dict(u0=0.12, w0=0.12, u1=9.88, w1=13.08, r=0.55, d0=1.6, d1=3.4, fillet=0.38)

# camera hood: a wedge – nearly flush at the top, standing proud at its curved lower edge
HOOD = dict(u0=1.05, w0=4.9, u1=9.0, w1=13.02, r_bottom=0.95, r_top=0.32,
            d0=COVER["d1"], thick=0.5, fillet=0.26, top_scale=0.28)

WINDOW = dict(u0=2.75, w0=6.6, u1=7.3, w1=11.2, r=0.22, floor=3.43)
IR_STRIP = (3.4, 8.8, 6.66, 10.7)     # u0, w0, u1, w1 (on the window insert)
LENS = dict(u=5.04, w=7.71, r_ring=0.98, r_glass=0.6)

GRILLE = dict(u0=1.26, u1=5.4, slots=[13.2 - (9.15 + k * 0.53) for k in range(6)], h=0.18, depth=0.26)
POCKET = dict(u0=6.17, w0=1.2, u1=9.1, w1=4.25, r=0.32, depth=0.24)
BUTTON = dict(inset=0.13, r=0.2, proud=0.07, fillet=0.13)
MICS = [(9.1, 13.2 - 1.62, 9.45, 13.2 - 1.48), (9.1, 13.2 - 1.94, 9.45, 13.2 - 1.80)]
TAB = dict(cu=5.14, half=0.52, top=1.12, bottom=-0.07, d0=3.4, d1=3.53, under_d0=2.25)
DECAL = dict(u0=2.7, w0=11.48, u1=7.25, w1=12.42)


def hood_scale(w):
    t = (HOOD["w1"] - w) / (HOOD["w1"] - HOOD["w0"])
    t = min(max(t, 0.0), 1.0)
    return HOOD["top_scale"] + (1 - HOOD["top_scale"]) * t


def hood_front(w):
    return HOOD["d0"] + HOOD["thick"] * hood_scale(w)


# ------------------------------------------------------------------ geometry

def build_mesh():
    m = Mesh()

    # 1. wall base / back tray (straight-sided, lightly rounded corners)
    b = BASE
    filleted_solid(m, "base", lambda i: rounded_rect(b["u0"], b["w0"], b["u1"], b["w1"], [b["r"]] * 4, 6, i),
                   b["d0"], b["d1"], b["fillet"], 3)

    # 2. front cover with heavily rounded front edge, cut-outs for grille, button pocket, mic
    c = COVER
    holes = []
    for wc in GRILLE["slots"]:
        hh = GRILLE["h"] / 2
        holes.append(dict(loop=rounded_rect(GRILLE["u0"], wc - hh, GRILLE["u1"], wc + hh, [hh * 0.98] * 4, 4),
                          depth=GRILLE["depth"], mat="slot"))
    p = POCKET
    holes.append(dict(loop=rounded_rect(p["u0"], p["w0"], p["u1"], p["w1"], [p["r"]] * 4, 5),
                      depth=p["depth"], mat="slot"))
    for (a0, b0, a1, b1) in MICS:
        r = (b1 - b0) / 2 * 0.98
        holes.append(dict(loop=rounded_rect(a0, b0, a1, b1, [r] * 4, 3), depth=0.2, mat="slot"))
    filleted_solid(m, "body", lambda i: rounded_rect(c["u0"], c["w0"], c["u1"], c["w1"], [c["r"]] * 4, 7, i),
                   c["d0"], c["d1"], c["fillet"], 5, holes=holes, back_cap=False)

    # 3. camera hood (wedge) with the window opening
    h = HOOD
    radii = [h["r_bottom"], h["r_bottom"], h["r_top"], h["r_top"]]
    win = WINDOW
    win_loop = rounded_rect(win["u0"], win["w0"], win["u1"], win["w1"], [win["r"]] * 4, 4)
    hood = Mesh()
    filleted_solid(hood, "body", lambda i: rounded_rect(h["u0"], h["w0"], h["u1"], h["w1"], radii, 8, i),
                   h["d0"] - 0.5, h["d0"] + h["thick"], h["fillet"], 4, back_cap=False,
                   holes=[dict(loop=win_loop, depth=0.0, mat="window_wall")])
    # replace the zero-depth recess by a proper one after the wedge transform:
    hood.faces = [f for f in hood.faces if f["mat"] != "window_wall"]
    for f in hood.faces:
        f["pts"] = [(p[0], p[1], h["d0"] + (p[2] - h["d0"]) * hood_scale(p[1]) if p[2] > h["d0"] else p[2])
                    for p in f["pts"]]
    m.faces += hood.faces
    # window walls from the slanted hood face down to the insert
    top = [(p[0], p[1], hood_front(p[1])) for p in win_loop]
    bot = [(p[0], p[1], win["floor"]) for p in win_loop]
    wcu = (win["u0"] + win["u1"]) / 2
    wcw = (win["w0"] + win["w1"]) / 2
    m.strip("window_wall", top, bot, None, outward_fn=lambda cc: (wcu - cc[0], wcw - cc[1], 0.0))
    m.cap("insert", win_loop, win["floor"], +1, (), uv=("rect", win["u0"], win["w0"], win["u1"], win["w1"]))

    # 4. lens: barrel, bezel ring, recessed glass dome
    L = LENS
    fl = win["floor"]
    cylinder_ring(m, "lens_ring", L["u"], L["w"], L["r_ring"], fl, fl + 0.16)
    annulus(m, "lens_ring", L["u"], L["w"], L["r_glass"], L["r_ring"], fl + 0.16)
    cylinder_ring(m, "lens_ring", L["u"], L["w"], L["r_glass"], fl + 0.16, fl + 0.1, inward=True)
    lens_uv = ("rect", L["u"] - L["r_glass"], L["w"] - L["r_glass"], L["u"] + L["r_glass"], L["w"] + L["r_glass"])
    dome(m, "lens_glass", L["u"], L["w"], L["r_glass"], fl + 0.1, 0.08, uv=lens_uv)

    # 5. call button sitting in its pocket
    bi = BUTTON["inset"]
    bu0, bw0, bu1, bw1 = p["u0"] + bi, p["w0"] + bi, p["u1"] - bi, p["w1"] - bi
    filleted_solid(m, "body", lambda i: rounded_rect(bu0, bw0, bu1, bw1, [BUTTON["r"]] * 4, 5, i),
                   c["d1"] - p["depth"], c["d1"] + BUTTON["proud"], BUTTON["fillet"], 3,
                   back_cap=False, front_mat="button")
    for f in m.faces:
        if f["mat"] == "button":
            f["uv"] = ("rect", bu0, bw0, bu1, bw1)

    # 6. bottom latch: front plate with a round top + the strip that wraps under the edge
    t = TAB
    outline = [(t["cu"] - t["half"], t["bottom"]), (t["cu"] + t["half"], t["bottom"])]
    arc = [(t["cu"] + t["half"] * math.cos(math.radians(a)), t["top"] - t["half"] + t["half"] * math.sin(math.radians(a)))
           for a in range(0, 181, 15)]
    outline += arc
    filleted_solid(m, "tab", lambda i: _offset(outline, i), t["d0"], t["d1"], 0.04, 1)
    under = [(t["cu"] - t["half"], t["bottom"] - 0.06, t["under_d0"]), (t["cu"] + t["half"], t["bottom"] - 0.06, t["under_d0"]),
             (t["cu"] + t["half"], t["bottom"] - 0.06, t["d1"]), (t["cu"] - t["half"], t["bottom"] - 0.06, t["d1"])]
    m.face("tab", under, (0, -1, 0))
    under_top = [(q[0], COVER["w0"] + 0.01, q[2]) for q in under]
    m.face("tab", under_top, (0, 1, 0))
    for side in (-1, 1):
        uu = t["cu"] + side * t["half"]
        m.face("tab", [(uu, t["bottom"] - 0.06, t["under_d0"]), (uu, COVER["w0"] + 0.01, t["under_d0"]),
                       (uu, COVER["w0"] + 0.01, t["d0"]), (uu, t["bottom"] - 0.06, t["d0"])], (side, 0, 0))

    # 7. printed logo / model name decal, following the slanted hood face
    dc = DECAL
    quad = [(dc["u0"], dc["w0"]), (dc["u1"], dc["w0"]), (dc["u1"], dc["w1"]), (dc["u0"], dc["w1"])]
    m.face("decal", [(q[0], q[1], hood_front(q[1]) + 0.012) for q in quad], (0, 0, 1),
           uv=("rect", dc["u0"], dc["w0"], dc["u1"], dc["w1"]))
    return m


def _inside(pts, win):
    cu = sum(p[0] for p in pts) / len(pts)
    cw = sum(p[1] for p in pts) / len(pts)
    return win["u0"] < cu < win["u1"] and win["w0"] < cw < win["w1"]


def _offset(outline, d):
    """inset a convex outline by d (simple vertex-normal offset)"""
    if d == 0:
        return list(outline)
    cu = sum(p[0] for p in outline) / len(outline)
    cw = sum(p[1] for p in outline) / len(outline)
    out = []
    for p in outline:
        vx, vy = cu - p[0], cw - p[1]
        l = math.hypot(vx, vy) or 1
        out.append((p[0] + vx / l * d, p[1] + vy / l * d))
    return out


# ------------------------------------------------------------------ UVs + OBJ export

def face_uv(f, p, normal):
    mode = f["uv"]
    if mode and mode[0] == "rect":
        _, u0, w0, u1, w1 = mode
        return ((p[0] - u0) / (u1 - u0), (p[1] - w0) / (w1 - w0))
    au, aw, ad = (abs(x) for x in normal)
    if ad >= au and ad >= aw:
        return (p[0] / DEV_W, p[1] / DEV_H)
    if au >= aw:
        return (p[2] / 4.0, p[1] / DEV_H)
    return (p[0] / DEV_W, p[2] / 4.0)


def to_block(p):
    return ((U_ORIGIN_X - p[0]) / 16.0, (W_ORIGIN_Y + p[1]) / 16.0, (WALL_Z - p[2]) / 16.0)


def export_obj(mesh, obj_path, mtl_rl):
    v, vt, vn, lines = [], [], [], []
    by_mat = {}
    for f in mesh.faces:
        by_mat.setdefault(f["mat"], []).append(f)
    out = [f"# HT-100 door camera – generated by tools/gen_assets.py", f"mtllib {mtl_rl}"]
    for mat, faces in by_mat.items():
        body = [f"usemtl {mat}"]
        for f in faces:
            pts = f["pts"]
            n = ml.newell(pts)
            # split polygons with >4 vertices (should not happen) into a fan
            polys = [pts] if len(pts) <= 4 else [[pts[0], pts[i], pts[i + 1]] for i in range(1, len(pts) - 1)]
            for poly in polys:
                bn = to_block_normal(n)
                vn.append(bn)
                ni = len(vn)
                idx = []
                for p in poly:
                    v.append(to_block(p))
                    vt.append(face_uv(f, p, n))
                    idx.append(f"{len(v)}/{len(vt)}/{ni}")
                body.append("f " + " ".join(idx))
        lines += body
    out += [f"v {a:.6f} {b:.6f} {c:.6f}" for a, b, c in v]
    out += [f"vt {a:.6f} {b:.6f}" for a, b in vt]
    out += [f"vn {a:.5f} {b:.5f} {c:.5f}" for a, b, c in vn]
    out += lines
    with open(obj_path, "w") as fh:
        fh.write("\n".join(out) + "\n")
    return len(v), len(mesh.faces)


def to_block_normal(n):
    return (-n[0], n[1], -n[2])


MATERIALS = ["base", "body", "slot", "window_wall", "insert", "lens_ring", "lens_glass", "button", "tab", "decal"]


def export_mtl(path):
    out = []
    for mname in MATERIALS:
        out += [f"newmtl {mname}", "Ka 1.0 1.0 1.0", "Kd 1.0 1.0 1.0", "Ks 0.0 0.0 0.0", "d 1.0",
                f"map_Kd #{mname}", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(out))


# ------------------------------------------------------------------ textures

PAL = {
    "clean": dict(body=(224, 219, 197), base=(214, 212, 199), button=(229, 225, 205), ir=(36, 32, 80),
                  insert=(98, 102, 97), text=(64, 80, 108)),
    "aged": dict(body=(214, 204, 168), base=(207, 205, 190), button=(221, 213, 182), ir=(48, 92, 200),
                 insert=(92, 98, 90), text=(62, 76, 104)),
}


def noise_tex(size, col, amp, seed):
    rnd = random.Random(seed)
    img = Image.new("RGBA", (size, size))
    px = img.load()
    for x in range(size):
        for y in range(size):
            k = 1 + rnd.uniform(-amp, amp)
            px[x, y] = tuple(min(255, max(0, int(c * k))) for c in col) + (255,)
    return img


def dev_px(u, w, size):
    """device-front coords -> texture pixel for the planar front mapping"""
    return (u / DEV_W * size, (1 - w / DEV_H) * size)


def body_tex(pal, aged):
    p = PAL[pal]
    img = noise_tex(256, p["body"], 0.015 if not aged else 0.035, 11)
    if aged:
        rnd = random.Random(5)
        d = ImageDraw.Draw(img, "RGBA")
        # yellowed tape residue patch on the hood (lower right of the camera window)
        x0, y0 = dev_px(5.0, 6.35, 256)
        x1, y1 = dev_px(7.9, 5.3, 256)
        d.rectangle((x0, y0, x1, y1), fill=(196, 170, 96, 45))
        # grime blotches, heavier near the lower edge and left side (hand contact)
        grime = Image.new("L", (256, 256), 0)
        gd = ImageDraw.Draw(grime)
        for _ in range(90):
            u = rnd.uniform(0.2, 9.8) * (rnd.random() ** 0.6)        # more on the left (hand side)
            w = rnd.uniform(0.2, 13.0) * (rnd.random() ** 0.7)       # and toward the bottom
            x, y = dev_px(u, w, 256)
            r = rnd.uniform(2, 9)
            gd.ellipse((x - r, y - r, x + r, y + r), fill=rnd.randint(20, 60))
        grime = grime.filter(ImageFilter.GaussianBlur(4))
        img = Image.composite(Image.new("RGBA", (256, 256), (128, 112, 78, 255)), img, grime)
        d = ImageDraw.Draw(img, "RGBA")
        for _ in range(25):
            x, y = rnd.uniform(0, 256), rnd.uniform(0, 256)
            d.line([(x, y), (x + rnd.uniform(-8, 8), y + rnd.uniform(2, 9))], fill=(140, 128, 98, 90), width=1)
        img = img.filter(ImageFilter.SMOOTH)
    return img


def base_tex(pal, aged):
    p = PAL[pal]
    img = noise_tex(128, p["base"], 0.012 if not aged else 0.03, 21)
    if aged:
        rnd = random.Random(9)
        d = ImageDraw.Draw(img)
        for _ in range(22):   # wall paint / putty flecks
            x, y = rnd.uniform(0, 128), rnd.uniform(0, 128)
            r = rnd.uniform(0.6, 2)
            d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(247, 247, 244, 255))
    return img


def flat_tex(col, size=16, amp=0.03, seed=1):
    return noise_tex(size, col, amp, seed)


def insert_tex(pal, ir_on, aged):
    p = PAL[pal]
    S = 128
    img = noise_tex(S, p["insert"], 0.02, 31)
    d = ImageDraw.Draw(img, "RGBA")
    wu0, ww0, wu1, ww1 = WINDOW["u0"], WINDOW["w0"], WINDOW["u1"], WINDOW["w1"]

    def px(u, w):
        return ((u - wu0) / (wu1 - wu0) * S, (1 - (w - ww0) / (ww1 - ww0)) * S)

    # dark glass zone in the middle of the grey frame
    a = px(wu0 + 0.35, ww1 - 0.3); b = px(wu1 - 0.35, ww0 + 0.35)
    d.rounded_rectangle((a[0], a[1], b[0], b[1]), radius=4, fill=(52, 56, 54, 255))
    # IR / sensor strip
    a = px(IR_STRIP[0], IR_STRIP[3]); b = px(IR_STRIP[2], IR_STRIP[1])
    if ir_on:
        d.rectangle((a[0], a[1], b[0], b[1]), fill=(120, 20, 34, 255))
        for k in range(4):
            cx = a[0] + (b[0] - a[0]) * (k + 0.5) / 4
            cy = (a[1] + b[1]) / 2
            for rr, al in ((12, 80), (8, 150), (5, 255)):
                d.ellipse((cx - rr, cy - rr * 0.8, cx + rr, cy + rr * 0.8), fill=(255, 70, 70, al))
    else:
        d.rectangle((a[0], a[1], b[0], b[1]), fill=p["ir"] + (255,))
        for k in range(4):
            cx = a[0] + (b[0] - a[0]) * (k + 0.5) / 4
            cy = (a[1] + b[1]) / 2
            d.ellipse((cx - 5, cy - 4, cx + 5, cy + 4), fill=tuple(int(c * 1.25) for c in p["ir"]) + (255,))
    # glass reflection
    d.line([(a[0] + 4, a[1] + 3), (a[0] + 30, a[1] + 3)], fill=(255, 255, 255, 60), width=2)
    if aged:   # peeling protective film outline
        d.line([px(3.1, 10.9), px(3.6, 8.6), px(3.3, 7.0), px(5.2, 6.85), px(6.9, 7.2), px(6.4, 9.2),
                px(6.9, 10.9), px(5.6, 11.0)], fill=(190, 200, 205, 200), width=2)
    return img


def lens_glass_tex():
    S = 32
    img = Image.new("RGBA", (S, S), (14, 16, 22, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 27, 27), fill=(40, 46, 60, 255))
    d.ellipse((9, 9, 22, 22), fill=(18, 20, 28, 255))
    d.ellipse((9, 8, 14, 13), fill=(190, 196, 210, 255))
    return img


def button_tex(pal, lit):
    p = PAL[pal]
    S = 64
    img = noise_tex(S, p["button"], 0.012, 41)
    d = ImageDraw.Draw(img, "RGBA")
    pu0 = POCKET["u0"] + BUTTON["inset"]; pu1 = POCKET["u1"] - BUTTON["inset"]
    pw0 = POCKET["w0"] + BUTTON["inset"]; pw1 = POCKET["w1"] - BUTTON["inset"]
    cx = (7.61 - pu0) / (pu1 - pu0) * S
    cy = (1 - ((13.2 - 9.33) - pw0) / (pw1 - pw0)) * S
    if lit:
        d.ellipse((cx - 11, cy - 6, cx + 11, cy + 6), fill=(255, 150, 60, 90))
    d.rounded_rectangle((cx - 6, cy - 2.5, cx + 6, cy + 2.5), radius=2,
                        fill=(255, 128, 40, 255) if lit else (38, 34, 32, 255))
    # very soft concave shading toward the edges
    for i in range(6):
        d.rectangle((i, i, S - 1 - i, S - 1 - i), outline=(0, 0, 0, 8))
    return img


def decal_tex(pal):
    p = PAL[pal]
    W, H = 512, 512
    band = int(H * (DECAL["w1"] - DECAL["w0"]) / (DECAL["u1"] - DECAL["u0"]) * (W / H))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    col = p["text"] + (255,)
    # generic house pictogram
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
    # stretch the drawn band over the whole square; the decal quad's UVs squeeze it back
    return img.crop((0, 0, W, 100)).resize((W, H), Image.LANCZOS), 1.0


# ------------------------------------------------------------------ writers

def opaque(img):
    """Cutout rendering treats alpha < 0.5 as a hole – every non-decal texture must be fully opaque."""
    img = img.convert("RGBA")
    img.putalpha(255)
    return img


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


DISPLAY = {
    "gui": {"rotation": [20, 200, 0], "translation": [0.5, 0, 0], "scale": [0.95, 0.95, 0.95]},
    "fixed": {"rotation": [0, 180, 0], "translation": [0, 0, -6], "scale": [1, 1, 1]},
    "ground": {"rotation": [0, 0, 0], "translation": [0, 3, 0], "scale": [0.4, 0.4, 0.4]},
    "head": {"rotation": [0, 180, 0], "translation": [0, 13, 7], "scale": [1, 1, 1]},
    "thirdperson_righthand": {"rotation": [75, 225, 0], "translation": [0, 2.5, 0], "scale": [0.375, 0.375, 0.375]},
    "firstperson_righthand": {"rotation": [0, 225, 0], "translation": [0, 0, 0], "scale": [0.4, 0.4, 0.4]},
}


def main():
    for d in (TEX, MODELS, ITEMS, STATES):
        os.makedirs(d, exist_ok=True)
    # clear previously generated files
    for d in (TEX, MODELS):
        for fn in os.listdir(d):
            if fn.startswith(("ht100_door_camera", "door_camera")):
                os.remove(os.path.join(d, fn))

    mesh = build_mesh()
    obj_name = "ht100_door_camera"
    mtl_rl = f"{MODID}:models/block/{obj_name}.mtl"
    nv, nf = export_obj(mesh, os.path.join(MODELS, obj_name + ".obj"), mtl_rl)
    export_mtl(os.path.join(MODELS, obj_name + ".mtl"))
    print(f"mesh: {nf} faces, {nv} vertices")

    # shared textures
    opaque(flat_tex((22, 22, 20))).save(os.path.join(TEX, "ht100_door_camera_slot.png"))
    opaque(flat_tex((66, 70, 66))).save(os.path.join(TEX, "ht100_door_camera_window_wall.png"))
    opaque(flat_tex((26, 26, 28), amp=0.05)).save(os.path.join(TEX, "ht100_door_camera_lens_ring.png"))
    opaque(lens_glass_tex()).save(os.path.join(TEX, "ht100_door_camera_lens_glass.png"))
    opaque(flat_tex((190, 192, 194), amp=0.02)).save(os.path.join(TEX, "ht100_door_camera_tab.png"))

    blocks = {"ht100_door_camera": "clean", "ht100_door_camera_aged": "aged"}
    rot = {"north": 0, "east": 90, "south": 180, "west": 270}
    for block, pal in blocks.items():
        aged = pal == "aged"
        t = lambda name: f"{MODID}:block/{name}"
        opaque(body_tex(pal, aged)).save(os.path.join(TEX, f"{block}_body.png"))
        opaque(base_tex(pal, aged)).save(os.path.join(TEX, f"{block}_base.png"))
        dec, frac = decal_tex(pal)
        dec.save(os.path.join(TEX, f"{block}_decal.png"))
        for lit in (False, True):
            opaque(button_tex(pal, lit)).save(os.path.join(TEX, f"{block}_button{'_lit' if lit else ''}.png"))
            opaque(insert_tex(pal, lit, aged)).save(os.path.join(TEX, f"{block}_insert{'_ir' if lit else ''}.png"))
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
                        "body": t(f"{block}_body"),
                        "slot": t("ht100_door_camera_slot"),
                        "window_wall": t("ht100_door_camera_window_wall"),
                        "insert": t(f"{block}_insert{'_ir' if ir else ''}"),
                        "lens_ring": t("ht100_door_camera_lens_ring"),
                        "lens_glass": t("ht100_door_camera_lens_glass"),
                        "button": t(f"{block}_button{'_lit' if call else ''}"),
                        "tab": t("ht100_door_camera_tab"),
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
    # remember decal band height for the UV mapping (top of texture)
    return frac


if __name__ == "__main__":
    main()
