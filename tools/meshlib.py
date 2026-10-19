"""Tiny mesh toolkit for building Minecraft OBJ models procedurally.

Local frame used while authoring:
  u = from viewer's left (px), w = up from device bottom (px), d = out from the wall (px).
(u, w, d) is right-handed (u x w = d).  Conversion to block-model space happens on export.
"""
import math


def rounded_rect(u0, w0, u1, w1, radii, seg=6, inset=0.0):
    """CCW (seen from +d) outline of a rectangle with per-corner radii.
    radii = (bottom_left, bottom_right, top_right, top_left)."""
    u0 += inset; w0 += inset; u1 -= inset; w1 -= inset
    pts = []
    corners = [
        ((u0, w0), radii[0], 180),   # bottom-left: arc 180..270
        ((u1, w0), radii[1], 270),   # bottom-right: 270..360
        ((u1, w1), radii[2], 0),     # top-right: 0..90
        ((u0, w1), radii[3], 90),    # top-left: 90..180
    ]
    for (cu, cw), r, start in corners:
        r = max(r - inset, 0.0)
        sx = 1 if start in (270, 0) else -1
        sy = 1 if start in (0, 90) else -1
        ccu = cu - sx * r
        ccw = cw - sy * r
        for i in range(seg + 1):
            a = math.radians(start + 90.0 * i / seg)
            pts.append((ccu + r * math.cos(a), ccw + r * math.sin(a)))
    return pts


def area2(poly):
    a = 0.0
    for i in range(len(poly)):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % len(poly)]
        a += x1 * y2 - x2 * y1
    return a


def dedupe(poly, eps=1e-6):
    out = []
    for p in poly:
        if not out or abs(out[-1][0] - p[0]) > eps or abs(out[-1][1] - p[1]) > eps:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < eps and abs(out[0][1] - out[-1][1]) < eps:
        out.pop()
    return out


# ------------------------------------------------------------------ triangulation (ear clipping + hole bridging)

def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _seg_intersect(p1, p2, q1, q2):
    """proper intersection test (shared endpoints do not count)"""
    def same(a, b):
        return abs(a[0] - b[0]) < 1e-9 and abs(a[1] - b[1]) < 1e-9
    if same(p1, q1) or same(p1, q2) or same(p2, q1) or same(p2, q2):
        return False
    d1 = _cross(q1, q2, p1)
    d2 = _cross(q1, q2, p2)
    d3 = _cross(p1, p2, q1)
    d4 = _cross(p1, p2, q2)
    return ((d1 > 1e-12 and d2 < -1e-12) or (d1 < -1e-12 and d2 > 1e-12)) and \
           ((d3 > 1e-12 and d4 < -1e-12) or (d3 < -1e-12 and d4 > 1e-12))


def _in_tri(p, a, b, c):
    d1 = _cross(a, b, p)
    d2 = _cross(b, c, p)
    d3 = _cross(c, a, p)
    neg = d1 < -1e-12 or d2 < -1e-12 or d3 < -1e-12
    pos = d1 > 1e-12 or d2 > 1e-12 or d3 > 1e-12
    return not (neg and pos)


def triangulate(outer, holes=()):
    """Return list of triangles (each 3 points) covering outer minus holes."""
    outer = dedupe(outer)
    if area2(outer) < 0:
        outer = outer[::-1]
    hs = []
    for h in holes:
        h = dedupe(h)
        if area2(h) > 0:
            h = h[::-1]          # holes clockwise
        hs.append(h)
    all_edges = []
    for h in hs:
        all_edges += [(h[i], h[(i + 1) % len(h)]) for i in range(len(h))]

    poly = list(outer)
    for h in sorted(hs, key=lambda hh: -max(p[0] for p in hh)):
        mi = max(range(len(h)), key=lambda i: (h[i][0], h[i][1]))
        m = h[mi]
        best, best_d = None, 1e18
        poly_edges = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
        for vi, v in enumerate(poly):
            if v[0] < m[0] - 1e-9:
                continue
            dd = (v[0] - m[0]) ** 2 + (v[1] - m[1]) ** 2
            if dd >= best_d:
                continue
            ok = True
            for e in poly_edges + all_edges:
                if _seg_intersect(m, v, e[0], e[1]):
                    ok = False
                    break
            if ok:
                best, best_d = vi, dd
        if best is None:   # fall back: any visible vertex
            for vi, v in enumerate(poly):
                if all(not _seg_intersect(m, v, e[0], e[1]) for e in poly_edges + all_edges):
                    best = vi
                    break
        hole_seq = h[mi:] + h[:mi] + [h[mi]]
        poly = poly[:best + 1] + hole_seq + poly[best:]

    tris = []
    idx = list(range(len(poly)))
    guard = 0
    while len(idx) > 3 and guard < 100000:
        guard += 1
        n = len(idx)
        clipped = False
        for k in range(n):
            ia, ib, ic = idx[(k - 1) % n], idx[k], idx[(k + 1) % n]
            a, b, c = poly[ia], poly[ib], poly[ic]
            if _cross(a, b, c) <= 1e-12:
                continue
            ear = True
            for j in idx:
                if j in (ia, ib, ic):
                    continue
                p = poly[j]
                if (abs(p[0] - a[0]) < 1e-9 and abs(p[1] - a[1]) < 1e-9) or \
                   (abs(p[0] - b[0]) < 1e-9 and abs(p[1] - b[1]) < 1e-9) or \
                   (abs(p[0] - c[0]) < 1e-9 and abs(p[1] - c[1]) < 1e-9):
                    continue
                if _in_tri(p, a, b, c):
                    ear = False
                    break
            if ear:
                tris.append((a, b, c))
                idx.pop(k)
                clipped = True
                break
        if not clipped:
            # remove a degenerate/collinear vertex and continue
            for k in range(n):
                a, b, c = poly[idx[(k - 1) % n]], poly[idx[k]], poly[idx[(k + 1) % n]]
                if abs(_cross(a, b, c)) <= 1e-12:
                    idx.pop(k)
                    clipped = True
                    break
            if not clipped:
                raise RuntimeError("triangulation failed")
    if len(idx) == 3:
        a, b, c = (poly[i] for i in idx)
        if abs(_cross(a, b, c)) > 1e-12:
            tris.append((a, b, c))
    return tris


# ------------------------------------------------------------------ mesh

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def newell(pts):
    nx = ny = nz = 0.0
    for i in range(len(pts)):
        x1, y1, z1 = pts[i]
        x2, y2, z2 = pts[(i + 1) % len(pts)]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    l = math.sqrt(nx * nx + ny * ny + nz * nz)
    if l < 1e-12:
        return None
    return (nx / l, ny / l, nz / l)


class Mesh:
    def __init__(self):
        self.faces = []   # dict(mat, pts[(u,w,d)], uvmode, group)

    def face(self, mat, pts, outward, uv=None, group=None):
        n = newell(pts)
        if n is None:
            return
        if _dot(n, outward) < 0:
            pts = pts[::-1]
        self.faces.append(dict(mat=mat, pts=list(pts), uv=uv, group=group))

    def strip(self, mat, loop_a, loop_b, interior, uv=None, group=None, outward_fn=None):
        n = len(loop_a)
        for i in range(n):
            j = (i + 1) % n
            q = [loop_a[i], loop_a[j], loop_b[j], loop_b[i]]
            c = tuple(sum(p[k] for p in q) / 4 for k in range(3))
            ow = outward_fn(c) if outward_fn else _sub(c, interior)
            self.face(mat, q, ow, uv, group)

    def cap(self, mat, outer2d, d, normal_sign, holes2d=(), uv=None, group=None):
        for tri in triangulate(outer2d, holes2d):
            self.face(mat, [(p[0], p[1], d) for p in tri], (0, 0, normal_sign), uv, group)


def filleted_solid(mesh, mat, profile, d_back, d_front, fillet, fseg=4, holes=(),
                   back_cap=True, front_mat=None, group=None, uv=None):
    """Extrude profile(inset)->2D loop from d_back to d_front with a rounded front edge.
    holes: list of dict(loop=2D loop, depth=float, mat=wall material, floor_mat=...)"""
    base = profile(0.0)
    cu = sum(p[0] for p in base) / len(base)
    cw = sum(p[1] for p in base) / len(base)
    interior = (cu, cw, (d_back + d_front) / 2)
    loops = [[(p[0], p[1], d_back) for p in base]]
    if fillet > 0:
        loops.append([(p[0], p[1], d_front - fillet) for p in base])
        for k in range(1, fseg + 1):
            a = math.radians(90.0 * k / fseg)
            ins = fillet * (1 - math.cos(a))
            dd = d_front - fillet + fillet * math.sin(a)
            loops.append([(p[0], p[1], dd) for p in profile(ins)])
        front_loop = profile(fillet)
    else:
        loops.append([(p[0], p[1], d_front) for p in base])
        front_loop = base
    for la, lb in zip(loops, loops[1:]):
        mesh.strip(mat, la, lb, interior, uv, group)
    hole_loops = [h["loop"] for h in holes]
    mesh.cap(front_mat or mat, front_loop, d_front, +1, hole_loops, uv, group)
    if back_cap:
        mesh.cap(mat, base, d_back, -1, (), uv, group)
    for h in holes:
        recess(mesh, h["loop"], d_front, d_front - h["depth"], h.get("mat", mat),
               h.get("floor_mat", h.get("mat", mat)), group, h.get("floor_uv"))


def recess(mesh, loop2d, d_top, d_floor, wall_mat, floor_mat, group=None, floor_uv=None):
    cu = sum(p[0] for p in loop2d) / len(loop2d)
    cw = sum(p[1] for p in loop2d) / len(loop2d)
    top = [(p[0], p[1], d_top) for p in loop2d]
    bot = [(p[0], p[1], d_floor) for p in loop2d]
    mesh.strip(wall_mat, top, bot, None, None, group,
               outward_fn=lambda c: (cu - c[0], cw - c[1], 0.0))
    mesh.cap(floor_mat, loop2d, d_floor, +1, (), floor_uv, group)


def cylinder_ring(mesh, mat, cu, cw, r, d0, d1, seg=24, inward=False, group=None, uv=None):
    a = [(cu + r * math.cos(2 * math.pi * i / seg), cw + r * math.sin(2 * math.pi * i / seg), d0) for i in range(seg)]
    b = [(p[0], p[1], d1) for p in a]
    sign = -1 if inward else 1
    mesh.strip(mat, a, b, None, uv, group,
               outward_fn=lambda c: (sign * (c[0] - cu), sign * (c[1] - cw), 0.0))


def annulus(mesh, mat, cu, cw, r0, r1, d, seg=24, group=None, uv=None):
    for i in range(seg):
        a0 = 2 * math.pi * i / seg
        a1 = 2 * math.pi * (i + 1) / seg
        q = [(cu + r0 * math.cos(a0), cw + r0 * math.sin(a0), d),
             (cu + r1 * math.cos(a0), cw + r1 * math.sin(a0), d),
             (cu + r1 * math.cos(a1), cw + r1 * math.sin(a1), d),
             (cu + r0 * math.cos(a1), cw + r0 * math.sin(a1), d)]
        mesh.face(mat, q, (0, 0, 1), uv, group)


def dome(mesh, mat, cu, cw, r, d_base, height, seg=24, rings=3, group=None, uv=None):
    prev = [(cu + r * math.cos(2 * math.pi * i / seg), cw + r * math.sin(2 * math.pi * i / seg), d_base) for i in range(seg)]
    for k in range(1, rings + 1):
        t = k / rings
        rr = r * math.cos(t * math.pi / 2)
        dd = d_base + height * math.sin(t * math.pi / 2)
        if k == rings:
            apex = (cu, cw, dd)
            for i in range(seg):
                tri = [prev[i], prev[(i + 1) % seg], apex]
                c = tuple(sum(p[j] for p in tri) / 3 for j in range(3))
                mesh.face(mat, tri, _sub(c, (cu, cw, d_base - r)), uv, group)
        else:
            cur = [(cu + rr * math.cos(2 * math.pi * i / seg), cw + rr * math.sin(2 * math.pi * i / seg), dd) for i in range(seg)]
            mesh.strip(mat, prev, cur, (cu, cw, d_base - r), uv, group)
            prev = cur
