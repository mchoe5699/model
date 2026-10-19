"""Generate textures, block models, blockstates and item models for the HT-100 door camera.

Run from the repository root:  python3 tools/gen_assets.py

Front textures are drawn as the device seen from the front (viewer's left = image left).
Every element's front (north) face uses automatic UVs, so each element picks up the matching
region of this one front image.  Scale: 16 texture pixels per model pixel (256x256 texture).
"""
import json
import os
import random

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ASSETS = os.path.join(ROOT, "src/main/resources/assets/qwertys_model")
TEX = os.path.join(ASSETS, "textures/block")
MODELS = os.path.join(ASSETS, "models/block")
ITEMS = os.path.join(ASSETS, "models/item")
STATES = os.path.join(ASSETS, "blockstates")

S = 16          # texture px per model px
SIZE = 16 * S   # 256


def vx(x):
    """model x (north face) -> image x"""
    return int(round((16 - x) * S))


def vy(y):
    return int(round((16 - y) * S))


def rect(x1, y1, x2, y2):
    """model-space rectangle on the front -> image box (left, top, right, bottom)"""
    return (vx(max(x1, x2)), vy(max(y1, y2)), vx(min(x1, x2)) - 1, vy(min(y1, y2)) - 1)


# ---------------------------------------------------------------- geometry (model px, facing north)
BRACKET = (3.0, 1.5, 15.0, 13.0, 14.5, 16.0)
BODY = (3.25, 1.75, 13.0, 12.75, 14.25, 15.0)
PANEL = (3.75, 6.25, 12.75, 12.25, 13.75, 13.0)       # upper cover with logo + window
WINDOW = (5.5, 7.0, 12.55, 10.5, 11.75, 12.75)          # dark window frame
LENS = (7.25, 7.5, 12.35, 8.75, 9.0, 12.55)             # lens barrel
BUTTON = (4.25, 2.75, 12.5, 6.75, 5.75, 13.0)           # call button (viewer's right)
TAB = (7.5, 1.75, 12.85, 8.5, 2.5, 13.0)                # bottom latch tab

PALETTES = {
    "clean": dict(
        body=(222, 217, 196), body_dark=(196, 190, 168), body_light=(236, 232, 214),
        bracket=(214, 211, 196), panel=(226, 221, 201), grille=(70, 68, 60),
        window_frame=(96, 99, 95), glass=(24, 26, 40), ir=(32, 30, 74), ir_on=(150, 30, 45),
        text=(70, 82, 104), button=(228, 224, 206), led_off=(40, 36, 34), led_on=(255, 120, 40),
        tab=(186, 188, 190),
    ),
    "aged": dict(
        body=(212, 202, 168), body_dark=(182, 171, 136), body_light=(226, 218, 188),
        bracket=(206, 203, 186), panel=(216, 207, 174), grille=(62, 58, 48),
        window_frame=(88, 92, 86), glass=(28, 30, 40), ir=(44, 82, 190), ir_on=(170, 40, 60),
        text=(66, 78, 100), button=(220, 212, 182), led_off=(40, 36, 34), led_on=(255, 120, 40),
        tab=(188, 190, 192),
    ),
}


def shade_box(d, box, base, light, dark, bevel=3):
    l, t, r, b = box
    d.rectangle(box, fill=base)
    for i in range(bevel):
        d.line([(l + i, t + i), (r - i, t + i)], fill=light)
        d.line([(l + i, t + i), (l + i, b - i)], fill=light)
        d.line([(l + i, b - i), (r - i, b - i)], fill=dark)
        d.line([(r - i, t + i), (r - i, b - i)], fill=dark)


def draw_house_logo(d, cx, top, col):
    """Small generic house pictogram (not a brand logo)."""
    w, h = 26, 18
    d.line([(cx - w // 2, top + h // 2), (cx, top), (cx + w // 2, top + h // 2)], fill=col, width=3)
    d.rectangle((cx - w // 2 + 5, top + h // 2, cx + w // 2 - 5, top + h), outline=col, width=2)


def draw_text_bar(d, x, y, w, h, col):
    """Tiny 'printed text' strokes – readable as lettering at block scale without real glyphs."""
    d.rectangle((x, y, x + w, y + h), fill=None)
    cursor = x
    rnd = random.Random(x * 31 + y)
    while cursor < x + w:
        cw = rnd.choice([4, 5, 6])
        d.rectangle((cursor, y, cursor + cw - 2, y + h), fill=col)
        cursor += cw + 1


def front_texture(pal, ir_lit, led_lit, aged):
    p = PALETTES[pal]
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # wall bracket (only its rim shows around the body)
    shade_box(d, rect(*BRACKET[0:2], *BRACKET[3:5]), p["bracket"], p["body_light"], p["body_dark"], 2)

    # body
    shade_box(d, rect(*BODY[0:2], *BODY[3:5]), p["body"], p["body_light"], p["body_dark"], 4)

    # speaker grille: 6 horizontal slots, lower left (viewer) = high model x
    gl, gt, gr, gb = rect(7.0, 2.6, 12.0, 5.75)
    rows = 6
    for i in range(rows):
        yy = gt + 4 + i * ((gb - gt - 8) // (rows - 1))
        d.rectangle((gl, yy, gr, yy + 3), fill=p["grille"])
        d.line([(gl, yy + 4), (gr, yy + 4)], fill=p["body_light"])

    # mic slits, top right (viewer) = low model x
    ml, mt, mr, mb = rect(3.55, 12.4, 3.95, 13.6)
    for i in range(2):
        yy = mt + 2 + i * 8
        d.rectangle((ml, yy, mr, yy + 2), fill=p["grille"])

    # upper cover panel
    shade_box(d, rect(*PANEL[0:2], *PANEL[3:5]), p["panel"], p["body_light"], p["body_dark"], 3)
    # seam under the panel
    pl, pt, pr, pb = rect(*PANEL[0:2], *PANEL[3:5])
    d.line([(pl, pb + 1), (pr, pb + 1)], fill=p["body_dark"], width=2)

    # logo + model text above the window
    lx = vx(11.7)
    draw_house_logo(d, lx + 16, vy(13.45), p["text"])
    draw_text_bar(d, lx + 40, vy(13.4), 64, 7, p["text"])       # "HT-100"
    draw_text_bar(d, lx + 40, vy(12.75), 82, 4, p["text"])      # "DOOR CAMERA"

    # window frame + glass
    shade_box(d, rect(*WINDOW[0:2], *WINDOW[3:5]), p["window_frame"], (130, 133, 128), (70, 72, 70), 3)
    wl, wt, wr, wb = rect(5.85, 7.25, 10.15, 11.45)
    d.rectangle((wl, wt, wr, wb), fill=p["glass"])
    # IR / sensor strip (top of window)
    il, it, ir_, ib = rect(6.2, 9.6, 9.8, 11.1)
    d.rectangle((il, it, ir_, ib), fill=p["ir_on"] if ir_lit else p["ir"])
    if ir_lit:
        for k in range(4):
            cx = il + 10 + k * ((ir_ - il - 20) // 3)
            d.ellipse((cx - 5, it + 8, cx + 5, it + 18), fill=(235, 70, 80))
    # glass reflection
    d.line([(wl + 6, wt + 4), (wl + 30, wt + 4)], fill=(80, 84, 104), width=2)

    # lens
    cx, cy = vx(8.0), vy(8.25)
    d.ellipse((cx - 13, cy - 13, cx + 12, cy + 12), fill=(12, 12, 14))
    d.ellipse((cx - 9, cy - 9, cx + 8, cy + 8), fill=(55, 58, 66))
    d.ellipse((cx - 5, cy - 5, cx + 4, cy + 4), fill=(20, 22, 30))
    d.ellipse((cx - 6, cy - 7, cx - 2, cy - 3), fill=(170, 175, 190))

    # call button
    shade_box(d, rect(*BUTTON[0:2], *BUTTON[3:5]), p["button"], (245, 242, 228), p["body_dark"], 3)
    bl, bt, br, bb = rect(*BUTTON[0:2], *BUTTON[3:5])
    led = (bl + (br - bl) // 2 - 7, bt + 7, bl + (br - bl) // 2 + 7, bt + 11)
    d.rounded_rectangle(led, radius=2, fill=p["led_on"] if led_lit else p["led_off"])

    # latch tab
    shade_box(d, rect(*TAB[0:2], *TAB[3:5]), p["tab"], (215, 217, 220), (150, 152, 155), 2)

    if aged:
        rnd = random.Random(1234)
        px = img.load()
        bl_, bt_, br_, bb_ = rect(*BODY[0:2], *BODY[3:5])
        # grime / scuffs / tape residue
        for _ in range(900):
            x = rnd.randint(bl_, br_)
            y = rnd.randint(bt_, bb_)
            r, g, b, a = px[x, y]
            if a and (r + g + b) > 450:
                k = rnd.uniform(0.82, 0.95)
                px[x, y] = (int(r * k), int(g * k), int(b * k * 0.97), a)
        for _ in range(12):
            x = rnd.randint(bl_ + 6, br_ - 6)
            y = rnd.randint(bt_ + 6, bb_ - 6)
            d.line([(x, y), (x + rnd.randint(-12, 12), y + rnd.randint(2, 10))], fill=(150, 140, 112), width=1)
        # peeled protective film on the window (lighter ragged outline)
        d.line([(wl + 8, wt + 6), (wl + 14, wt + 40), (wl + 8, wb - 6), (wl + 30, wb - 4),
                (wr - 10, wb - 8), (wr - 6, wt + 30), (wr - 18, wt + 4)], fill=(150, 160, 170), width=2)
        # paint flecks on the bracket rim
        brl, brt, brr, brb = rect(*BRACKET[0:2], *BRACKET[3:5])
        for _ in range(40):
            x = rnd.choice([rnd.randint(brl, brl + 4), rnd.randint(brr - 4, brr)])
            y = rnd.randint(brt, brb)
            d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(246, 246, 242))

    return img


def side_texture(pal, aged):
    p = PALETTES[pal]
    img = Image.new("RGBA", (64, 64), p["body"] + (255,))
    rnd = random.Random(7 if aged else 3)
    px = img.load()
    for x in range(64):
        for y in range(64):
            k = rnd.uniform(0.96, 1.02) if not aged else rnd.uniform(0.88, 1.01)
            r, g, b = p["body"]
            px[x, y] = (min(255, int(r * k)), min(255, int(g * k)), min(255, int(b * k)), 255)
    if aged:
        d = ImageDraw.Draw(img)
        for _ in range(10):
            x, y = rnd.randint(0, 63), rnd.randint(0, 63)
            d.ellipse((x - 2, y - 1, x + 2, y + 1), fill=(244, 244, 240))
    return img


def element(frm, to, front_tex="#front", ao=True):
    faces = {}
    for f in ("north", "south", "east", "west", "up", "down"):
        faces[f] = {"texture": front_tex if f == "north" else "#side"}
    return {"from": list(frm), "to": list(to), "faces": faces}


def base_model():
    elems = []
    for box in (BRACKET, BODY, PANEL, WINDOW, LENS, BUTTON, TAB):
        elems.append(element(box[0:3], box[3:6]))
    elems[0]["faces"]["south"]["cullface"] = "south"
    return {
        "parent": "block/block",
        "ambientocclusion": False,
        "textures": {"particle": "#side"},
        "display": {
            "gui": {"rotation": [15, 200, 0], "translation": [0, 0, 0], "scale": [0.85, 0.85, 0.85]},
            "fixed": {"rotation": [0, 180, 0], "translation": [0, 0, -4], "scale": [0.9, 0.9, 0.9]},
            "ground": {"rotation": [0, 0, 0], "translation": [0, 3, 0], "scale": [0.4, 0.4, 0.4]},
            "thirdperson_righthand": {"rotation": [75, 225, 0], "translation": [0, 2.5, 0], "scale": [0.375, 0.375, 0.375]},
            "firstperson_righthand": {"rotation": [0, 225, 0], "translation": [0, 0, 0], "scale": [0.4, 0.4, 0.4]},
        },
        "elements": elems,
    }


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    write_json(os.path.join(MODELS, "door_camera_base.json"), base_model())

    blocks = {"ht100_door_camera": "clean", "ht100_door_camera_aged": "aged"}
    rot = {"north": 0, "east": 90, "south": 180, "west": 270}
    for block, pal in blocks.items():
        aged = pal == "aged"
        side = f"{block}_side"
        side_texture(pal, aged).save(os.path.join(TEX, side + ".png"))
        variants = {}
        for ir in (False, True):
            for led in (False, True):
                suffix = ("_ir" if ir else "") + ("_call" if led else "")
                tex = f"{block}_front{suffix}"
                front_texture(pal, ir, led, aged).save(os.path.join(TEX, tex + ".png"))
                write_json(os.path.join(MODELS, f"{block}{suffix}.json"), {
                    "parent": "qwertys_model:block/door_camera_base",
                    "textures": {"front": f"qwertys_model:block/{tex}",
                                 "side": f"qwertys_model:block/{side}"},
                })
        for facing, y in rot.items():
            for call in (0, 1, 2):
                for lit in (False, True):
                    suffix = ("_ir" if lit else "") + ("_call" if call > 0 else "")
                    v = {"model": f"qwertys_model:block/{block}{suffix}"}
                    if y:
                        v["y"] = y
                    variants[f"call={call},facing={facing},lit={str(lit).lower()}"] = v
        write_json(os.path.join(STATES, block + ".json"), {"variants": variants})
        write_json(os.path.join(ITEMS, block + ".json"), {"parent": f"qwertys_model:block/{block}"})

    # preview sheet for README
    prev = Image.new("RGBA", (SIZE * 2 + 16, SIZE), (255, 255, 255, 255))
    prev.alpha_composite(front_texture("clean", False, True, False), (0, 0))
    prev.alpha_composite(front_texture("aged", True, False, True), (SIZE + 16, 0))
    prev.save(os.path.join(ROOT, "docs_preview.png"))


if __name__ == "__main__":
    main()
