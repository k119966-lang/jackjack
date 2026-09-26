#!/usr/bin/env python3
"""SHURIRING 15s 9:16 animatic (previs) renderer.

Implements the final storyboard timing: 8 cuts, 60 BPM grid, subtitles in the
top band, end card typography spec. Procedural previs visuals; the director's
profile photo is used (low-key graded) for the two cuts that show him.
"""
import math, os, subprocess, sys, csv, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

SP = os.path.dirname(os.path.abspath(__file__))  # fonts/ next to this script; output goes to ./animatic
OUT = f'{SP}/animatic'
os.makedirs(f'{OUT}/boards', exist_ok=True)
W, H, FPS = 1080, 1920, 30
DUR = 15.0
N = int(DUR * FPS)
BG = (10, 10, 10)
OFFWHITE = (242, 240, 235)
TAG = (217, 212, 204)
CAP = (96, 96, 94)
FONTS = f'{SP}/fonts'
F_SERIF_SB = f'{FONTS}/NotoSerifKR-600.ttf'
F_SERIF_R = f'{FONTS}/NotoSerifKR-400.ttf'
F_SANS_M = f'{FONTS}/NotoSansKR-500.ttf'
F_SANS_R = f'{FONTS}/NotoSansKR-400.ttf'
F_MONO = f'{FONTS}/IBMPlexMono-400.ttf'
PROFILE = os.path.join(SP, 'profile.png')  # 원장 프로필 사진 (저장소에는 포함하지 않음)

def font(path, size):
    return ImageFont.truetype(path, size)

# ---------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))

def ease_io(p):
    p = clamp(p)
    return 0.5 - 0.5 * math.cos(math.pi * p)

def ease_out(p):
    p = clamp(p)
    return 1 - (1 - p) ** 3

def lerp(a, b, p):
    return a + (b - a) * p

def fade(t, t_in, d_in, t_out=None, d_out=0.2):
    """opacity 0..1 with fade-in at t_in over d_in and fade-out ending at t_out."""
    if t < t_in:
        return 0.0
    a = clamp((t - t_in) / d_in) if d_in > 0 else 1.0
    if t_out is not None:
        if t > t_out:
            return 0.0
        a = min(a, clamp((t_out - t) / d_out) if d_out > 0 else 1.0)
    return a

def aa_layer(draw_fn, size=(W, H), scale=2):
    """Draw with draw_fn(draw, s) on a scale-x RGBA layer, downsample -> RGBA."""
    big = Image.new('RGBA', (size[0] * scale, size[1] * scale), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    draw_fn(d, scale)
    return big.resize(size, Image.LANCZOS)

def composite(base, layer, alpha=1.0, blur=0):
    if blur > 0:
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
    if alpha < 1.0:
        a = layer.split()[3].point(lambda v: int(v * alpha))
        layer = layer.copy(); layer.putalpha(a)
    base.alpha_composite(layer)
    return base

def new_frame():
    return Image.new('RGBA', (W, H), BG + (255,))

def draw_text_tracked(d, xy, text, fnt, fill, tracking=0, anchor_center=False):
    """Draw text with letter-spacing (px). Returns total width."""
    widths = [d.textlength(ch, font=fnt) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x, y = xy
    if anchor_center:
        x = x - total / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=fnt, fill=fill)
        x += w + tracking
    return total

def text_layer(text, fnt, fill, tracking=0, pad=40):
    """Render tracked text into a tight RGBA layer; returns (layer, width)."""
    tmp = Image.new('RGBA', (10, 10)); td = ImageDraw.Draw(tmp)
    widths = [td.textlength(ch, font=fnt) for ch in text]
    total = int(sum(widths) + tracking * (len(text) - 1))
    asc, desc = fnt.getmetrics()
    layer = Image.new('RGBA', (total + pad * 2, asc + desc + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    draw_text_tracked(d, (pad, pad), text, fnt, fill, tracking)
    return layer, total

def ink_bbox(layer):
    return layer.split()[3].getbbox()

# ---------------------------------------------------------------- subtitles
SUB_FONT = font(F_SANS_M, 108)
SUBS = [
    ("먼저, 봅니다.", 2.2, 0.3, 5.0, 0.2),
    ("슈링크, 하나만.", 5.2, 0.3, 8.5, 0.2),
    ("한 샷, 한 샷.", 9.0, 0.3, 11.8, 0.2),
]
_sub_cache = {}
def subtitle_overlay(frame, t):
    for text, t_in, d_in, t_out, d_out in SUBS:
        a = fade(t, t_in, d_in, t_out, d_out)
        if a <= 0:
            continue
        if text not in _sub_cache:
            layer, _ = text_layer(text, SUB_FONT, OFFWHITE + (255,))
            bb = ink_bbox(layer)
            _sub_cache[text] = (layer, bb)
        layer, bb = _sub_cache[text]
        # top band: ink top at y=8% of H, left at x=8%
        x = int(0.08 * W) - bb[0]
        y = int(0.08 * H) - bb[1]
        tmp = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        tmp.alpha_composite(layer, (x, y))
        composite(frame, tmp, alpha=a)

# ---------------------------------------------------------------- previs captions
CAP_FONT = font(F_SANS_R, 26)
MONO_FONT = font(F_MONO, 24)
def caption_overlay(frame, t, cut_label):
    d = ImageDraw.Draw(frame)
    y = int(0.945 * H)
    d.text((int(0.06 * W), y), cut_label, font=CAP_FONT, fill=CAP + (255,))
    tc = f"{int(t // 60):02d}:{t % 60:05.2f}"
    d.text((int(0.06 * W), y + 36), f"{tc}  60 BPM", font=MONO_FONT, fill=CAP + (255,))
    # beat dot: pulses on integer seconds (downbeat), half-size on .5
    frac = t - math.floor(t)
    pulse = max(0.0, 1 - frac / 0.25)
    r = 5 + 7 * pulse
    cx, cy = int(0.06 * W) + 300, y + 48
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(int(96 + 120 * pulse),) * 3 + (255,))
    d.text((int(0.94 * W) - 84, int(0.03 * H)), "PREVIS", font=MONO_FONT, fill=CAP + (255,))

# ---------------------------------------------------------------- profile photo grade
def load_profile_lowkey():
    im = Image.open(PROFILE).convert('RGB')
    arr = np.asarray(im).astype(np.float32)
    h, w, _ = arr.shape
    # background estimate from corners
    corners = np.concatenate([arr[:40, :40].reshape(-1, 3), arr[:40, -40:].reshape(-1, 3)])
    bgc = corners.mean(0)
    dist = np.sqrt(((arr - bgc) ** 2).sum(-1))
    mask = (dist > 34).astype(np.float32)
    # keep everything below the shoulders as subject even if grey-ish
    mask_img = Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))
    mask = np.asarray(mask_img).astype(np.float32) / 255.0
    # low-key grade: face bright, coat into shadow, far side of face darker
    ys = np.linspace(0, 1, h)[:, None]
    xs = np.linspace(0, 1, w)[None, :]
    lateral = 1.0 - 0.75 * np.clip((xs - 0.55) / 0.35, 0, 1)  # right side (viewer's) darkens
    coat = np.where(ys > 0.56, 0.22, 1.0)
    coat = np.asarray(Image.fromarray((coat * 255).astype(np.uint8)).resize((w, h)).filter(ImageFilter.GaussianBlur(25))).astype(np.float32) / 255.0
    gain = 0.66 * lateral * coat
    graded = arr * gain[..., None]
    # slight cool-neutral: reduce red a touch in shadows
    graded[..., 2] *= 1.03
    graded = graded * mask[..., None] + np.array(BG, np.float32) * (1 - mask[..., None])
    return Image.fromarray(np.clip(graded, 0, 255).astype(np.uint8))

PROFILE_LK = load_profile_lowkey()

def place_profile(frame, head_top_y, head_h, cx, blur=0, alpha=1.0):
    """Place the graded profile so that hair top -> head_top_y and hair-top..chin = head_h."""
    im = PROFILE_LK
    # in the photo, hair top ~ y=60, chin ~ y=760 (of 1400); face center x ~ 560 of 1123
    ph_top, ph_chin, ph_cx = 60, 760, 560
    s = head_h / (ph_chin - ph_top)
    im2 = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    x = int(cx - ph_cx * s)
    y = int(head_top_y - ph_top * s)
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    layer.paste(im2.convert('RGBA'), (x, y))
    # feather bottom into black
    grad = Image.new('L', (W, H), 255)
    gd = ImageDraw.Draw(grad)
    for i in range(0, 200):
        yy = H - 200 + i
        gd.line([(0, yy), (W, yy)], fill=int(255 * (1 - i / 200)))
    a = ImageChops.multiply(layer.split()[3], grad)
    layer.putalpha(a)
    composite(frame, layer, alpha=alpha, blur=blur)

# ---------------------------------------------------------------- skin texture
def skin_noise(size, amp=9, seed=3):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 1, (size[1] // 2, size[0] // 2)).astype(np.float32)
    n = np.asarray(Image.fromarray(np.clip(n * 40 + 128, 0, 255).astype(np.uint8)).resize(size, Image.BILINEAR)).astype(np.float32)
    return (n - 128) / 40 * amp

# ================================================================ CUT 1: cartridge window macro
C1_R = int(0.235 * W)  # cylinder radius (diameter ~47% of frame width)
C1_C = (W // 2, int(0.50 * H))
def c1_static():
    fr = new_frame()
    cx, cy = C1_C; R = C1_R
    def body(d, s):
        # cylinder face (dark grey) with a subtle top-right lit gradient approximated by two arcs
        d.ellipse([(cx - R) * s, (cy - R) * s, (cx + R) * s, (cy + R) * s], fill=(30, 30, 32, 255))
        # engraved depth ring
        r2 = int(R * 0.92)
        d.ellipse([(cx - r2) * s, (cy - r2) * s, (cx + r2) * s, (cy + r2) * s], outline=(48, 48, 50, 255), width=2 * s)
        # depth marking: three tiny engraved blocks at the lower right of the ring (unreadable at this size)
        for k in range(3):
            a = math.radians(38 + k * 7)
            x1, y1 = cx + math.cos(a) * R * 0.895, cy + math.sin(a) * R * 0.895
            d.rounded_rectangle([(x1 - 6) * s, (y1 - 4) * s, (x1 + 6) * s, (y1 + 4) * s], radius=2 * s, fill=(62, 62, 64, 255))
        # glass window with a faint radial sheen (glass, not a dial)
        rw = int(R * 0.78)
        d.ellipse([(cx - rw) * s, (cy - rw) * s, (cx + rw) * s, (cy + rw) * s], fill=(13, 14, 17, 255))
        for k in range(6):
            rr = rw * (1 - k * 0.15)
            v = 14 + k * 3
            d.ellipse([(cx - rr) * s, (cy - rr) * s, (cx + rr) * s, (cy + rr) * s], fill=(v, v + 1, v + 4, 255))
        # metallic grid under the glass
        step = 16
        for gx in range(cx - rw, cx + rw + 1, step):
            d.line([(gx * s, (cy - rw) * s), (gx * s, (cy + rw) * s)], fill=(26, 27, 31, 255), width=1 * s)
        for gy in range(cy - rw, cy + rw + 1, step):
            d.line([((cx - rw) * s, gy * s), ((cx + rw) * s, gy * s)], fill=(26, 27, 31, 255), width=1 * s)
        # rim highlight (hard light from upper right rear)
        d.arc([(cx - R) * s, (cy - R) * s, (cx + R) * s, (cy + R) * s], start=-95, end=15, fill=(150, 150, 146, 255), width=3 * s)
        d.arc([(cx - rw) * s, (cy - rw) * s, (cx + rw) * s, (cy + rw) * s], start=-80, end=-10, fill=(90, 92, 96, 255), width=2 * s)
    layer = aa_layer(body)
    # clip grid to window circle
    mask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(mask).ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
    fr.alpha_composite(layer)
    # soft glow of the rim
    glow = aa_layer(lambda d, s: d.arc([(cx - R) * s, (cy - R) * s, (cx + R) * s, (cy + R) * s], start=-95, end=15, fill=(120, 120, 118, 120), width=10 * s))
    composite(fr, glow, blur=12)
    return fr, mask

def c1_frame(fr_static, mask, t):
    fr = fr_static.copy()
    cx, cy = C1_C; R = C1_R; rw = int(R * 0.78)
    # reflection line position: left edge until 0.3, traverse to right edge by 1.7 (center at 1.0), hold
    if t <= 0.3:
        p = 0.0
    elif t >= 1.7:
        p = 1.0
    else:
        p = ease_io((t - 0.3) / 1.4)
    x = cx - rw * 0.92 + p * (2 * rw * 0.92)
    tilt = math.radians(-14)
    def band(d, s):
        # a sheet of light reflected in the glass: soft wide band with a thin bright core
        x1, y1 = x - math.sin(tilt) * rw * 1.2, cy - math.cos(tilt) * rw * 1.2
        x2, y2 = x + math.sin(tilt) * rw * 1.2, cy + math.cos(tilt) * rw * 1.2
        d.line([(x1 * s, y1 * s), (x2 * s, y2 * s)], fill=(200, 202, 206, 90), width=54 * s)
    def line(d, s):
        x1, y1 = x - math.sin(tilt) * rw * 1.2, cy - math.cos(tilt) * rw * 1.2
        x2, y2 = x + math.sin(tilt) * rw * 1.2, cy + math.cos(tilt) * rw * 1.2
        d.line([(x1 * s, y1 * s), (x2 * s, y2 * s)], fill=(238, 238, 234, 255), width=4 * s)
    core = aa_layer(line)
    soft = aa_layer(band).filter(ImageFilter.GaussianBlur(10))
    glow = core.filter(ImageFilter.GaussianBlur(14))
    # clip to window
    wmask = Image.new('L', (W, H), 0)
    ImageDraw.Draw(wmask).ellipse([cx - rw, cy - rw, cx + rw, cy + rw], fill=255)
    for lay, a in ((soft, 0.9), (glow, 0.5), (core, 1.0)):
        al = ImageChops.multiply(lay.split()[3], wmask).point(lambda v: int(v * a))
        lay = lay.copy(); lay.putalpha(al)
        fr.alpha_composite(lay)
    return fr

# ================================================================ CUT 2: director CU
def c2_frame(t):
    fr = new_frame()
    # patient jaw silhouette in the bottom third (out of focus, barely lighter than bg)
    sil = aa_layer(lambda d, s: d.ellipse([-0.2 * W * s, 0.78 * H * s, 0.9 * W * s, 1.35 * H * s], fill=(24, 22, 22, 255)))
    composite(fr, sil, blur=45)
    # director: hair top at 18% of H, head height 45% of H, face centre x ~ 52%
    place_profile(fr, head_top_y=int(0.18 * H), head_h=int(0.45 * H), cx=int(0.53 * W))
    # keep the top band clean (headroom) and a gentle vignette on the far side
    vig = aa_layer(lambda d, s: d.rectangle([0.72 * W * s, 0, W * s, H * s], fill=(10, 10, 10, 140)))
    composite(fr, vig, blur=80)
    return fr

# ================================================================ CUT 3: jawline macro with white lines
def c3_static():
    """skin plane below a lower-left -> upper-right jaw ridge; grazing light from upper right rear."""
    fr = new_frame()
    y0, y1 = 0.80 * H, 0.40 * H  # ridge from (0,y0) to (W,y1)
    arr = np.zeros((H, W, 3), np.float32)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    ridge_y = y0 + (y1 - y0) * xs / W
    below = ys - ridge_y  # >0 below the ridge (skin)
    # skin base with falloff away from the ridge (grazing light)
    base = np.array([158, 122, 106], np.float32)
    dark = np.array([46, 34, 30], np.float32)
    f = np.clip(below / (0.55 * H), 0, 1)
    f = f ** 0.8
    col = base[None, None, :] * (1 - f)[..., None] + dark[None, None, :] * f[..., None]
    # ridge highlight (bright rim along the jaw)
    rim = np.exp(-np.clip(below, 0, None) / 26.0) * (below >= 0)
    col = col + rim[..., None] * np.array([70, 58, 50], np.float32)
    # lateral falloff: brighter to the right (towards light)
    col = col * (0.70 + 0.30 * xs / W)[..., None]
    col = col + skin_noise((W, H), amp=7)[..., None]
    inside = (below >= 0).astype(np.float32)
    inside = np.asarray(Image.fromarray((inside * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))).astype(np.float32) / 255
    out = col * inside[..., None] + np.array(BG, np.float32) * (1 - inside[..., None])
    fr = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).convert('RGBA')
    return fr

def c3_line_pts(offset, x_start, length):
    """a line parallel to the ridge, 'offset' px below it, starting at x_start with given length (px along x)."""
    y0, y1 = 0.80 * H, 0.40 * H
    slope = (y1 - y0) / W
    def pt(x):
        return (x, y0 + slope * x + offset)
    return pt(x_start), pt(x_start + length)

def draw_white_line(fr, p1, p2, progress=1.0, width=6):
    x1, y1 = p1; x2, y2 = p2
    xe, ye = x1 + (x2 - x1) * progress, y1 + (y2 - y1) * progress
    core = aa_layer(lambda d, s: d.line([(x1 * s, y1 * s), (xe * s, ye * s)], fill=(238, 236, 230, 255), width=width * s))
    composite(fr, core.filter(ImageFilter.GaussianBlur(3)), alpha=0.35)
    fr.alpha_composite(core)
    return (xe, ye)

def c3_frame(static, t):
    fr = static.copy()
    L = int(4.5 * 90)  # 4.5 cm at 90 px/cm (12 cm frame width)
    p1a, p1b = c3_line_pts(150, 0.30 * W, L)
    p2a, p2b = c3_line_pts(285, 0.28 * W, L)
    draw_white_line(fr, p1a, p1b)
    draw_white_line(fr, p2a, p2b)
    p3a, p3b = c3_line_pts(420, 0.26 * W, L)
    # pen timeline (local t): 0-0.4 entry from lower-left (blurred), 0.5 contact+dimple, 0.5-1.2 stroke, 1.2-1.4 leave, 1.4-1.5 hold
    tip = None; blur = 0; alpha = 1.0
    if t < 0.5:
        p = ease_out(t / 0.5)
        sx, sy = p3a[0] - 0.28 * W, p3a[1] + 0.22 * H
        tip = (lerp(sx, p3a[0], p), lerp(sy, p3a[1], p))
        blur = int(14 * (1 - p) ** 1.5)
    elif t < 1.2:
        prog = ease_io((t - 0.5) / 0.7)
        tip = draw_white_line(fr, p3a, p3b, progress=prog)
    else:
        draw_white_line(fr, p3a, p3b, progress=1.0)
        if t < 1.4:
            p = ease_io((t - 1.2) / 0.2)
            tip = (p3b[0] - 0.05 * W * p, p3b[1] - 0.05 * H * p)
            blur = int(10 * p); alpha = 1 - 0.6 * p
        else:
            tip = None
    if tip is not None:
        tx, ty = tip
        # dimple at contact
        if 0.5 <= t < 0.62:
            dim = aa_layer(lambda d, s: d.ellipse([(tx - 14) * s, (ty - 9) * s, (tx + 14) * s, (ty + 9) * s], fill=(0, 0, 0, 70)))
            composite(fr, dim, blur=4)
        # glove + pen: dark glove mass lower-left of the tip, white pen barrel to the tip
        def pen(d, s):
            ang = math.radians(215)
            bx, by = tx + math.cos(ang) * 260, ty - math.sin(ang) * 260
            d.line([(tx * s, ty * s), (bx * s, by * s)], fill=(226, 224, 218, 255), width=16 * s)
            d.line([(tx * s, ty * s), ((tx + (bx - tx) * 0.12) * s, (ty + (by - ty) * 0.12) * s)], fill=(250, 250, 246, 255), width=8 * s)
            gx, gy = tx + math.cos(ang) * 330, ty - math.sin(ang) * 330
            d.ellipse([(gx - 150) * s, (gy - 110) * s, (gx + 150) * s, (gy + 150) * s], fill=(22, 22, 24, 255))
            d.arc([(gx - 150) * s, (gy - 110) * s, (gx + 150) * s, (gy + 150) * s], start=-120, end=-40, fill=(70, 70, 72, 255), width=4 * s)
        lay = aa_layer(pen)
        composite(fr, lay, alpha=alpha, blur=blur)
    return fr

# ================================================================ CUT 4: device silhouette
def c4_device_layer():
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    def body(d, s):
        x0, y0, x1 = 0.44 * W, 0.24 * H, 0.96 * W
        d.rounded_rectangle([x0 * s, y0 * s, x1 * s, 1.2 * H * s], radius=60 * s, fill=(17, 17, 18, 255))
        # left vertical edge rim light
        d.line([((x0 + 2) * s, (y0 + 60) * s), ((x0 + 2) * s, 1.1 * H * s)], fill=(96, 96, 94, 255), width=3 * s)
        d.arc([x0 * s, y0 * s, (x0 + 120) * s, (y0 + 120) * s], start=180, end=270, fill=(96, 96, 94, 255), width=3 * s)
        # top edge faint
        d.line([((x0 + 60) * s, (y0 + 1) * s), ((x1 - 60) * s, (y0 + 1) * s)], fill=(40, 40, 40, 255), width=2 * s)
        # screen (tilted rounded rect)
        d.rounded_rectangle([0.53 * W * s, 0.27 * H * s, 0.90 * W * s, 0.39 * H * s], radius=14 * s, fill=(84, 98, 112, 255))
        d.rounded_rectangle([0.545 * W * s, 0.283 * H * s, 0.885 * W * s, 0.375 * H * s], radius=10 * s, fill=(112, 128, 144, 255))
        # holders + handpieces on the left flank
        d.rounded_rectangle([0.455 * W * s, 0.46 * H * s, 0.478 * W * s, 0.70 * H * s], radius=10 * s, fill=(58, 60, 62, 255))  # pen type
        d.rounded_rectangle([0.488 * W * s, 0.50 * H * s, 0.522 * W * s, 0.72 * H * s], radius=14 * s, fill=(62, 64, 66, 255))  # MP type
        d.ellipse([0.480 * W * s, 0.47 * H * s, 0.530 * W * s, 0.52 * H * s], fill=(66, 68, 70, 255))
        d.line([(0.456 * W * s, 0.47 * H * s), (0.456 * W * s, 0.69 * H * s)], fill=(120, 130, 140, 255), width=2 * s)
        d.line([(0.489 * W * s, 0.51 * H * s), (0.489 * W * s, 0.71 * H * s)], fill=(120, 130, 140, 255), width=2 * s)
    lay = aa_layer(body)
    # screen glow
    glow = aa_layer(lambda d, s: d.rounded_rectangle([0.50 * W * s, 0.25 * H * s, 0.93 * W * s, 0.41 * H * s], radius=30 * s, fill=(90, 110, 130, 110)))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    out = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    out.alpha_composite(glow); out.alpha_composite(lay)
    return out

def c4_frame(dev, t):
    fr = new_frame()
    # camera slides right 2 cm over 2 s -> subject drifts left ~16 px
    dx = -int(16 * ease_io(t / 2.0))
    tmp = Image.new('RGBA', (W, H), (0, 0, 0, 0)); tmp.alpha_composite(dev, (dx, 0))
    fr.alpha_composite(tmp)
    # hand: enters from bottom at 0.5, lifts MP handpiece at 1.0, brings it toward camera 1.0-2.0
    if t >= 0.5:
        p_in = ease_out(clamp((t - 0.5) / 0.5))
        hx = 0.50 * W + dx
        hy = lerp(1.15 * H, 0.74 * H, p_in)
        lift = ease_io(clamp((t - 1.0) / 1.0))
        scale = 1 + 0.9 * lift
        blur = int(16 * lift)
        hy2 = hy - 0.08 * H * lift + 0.10 * H * lift
        hx2 = hx - 0.10 * W * lift
        def hand(d, s):
            # sleeve (navy) + glove (black) as a vertical mass, handpiece in the grip
            d.rounded_rectangle([(hx2 - 70 * scale) * s, (hy2) * s, (hx2 + 70 * scale) * s, (hy2 + 700) * s], radius=60 * s, fill=(16, 20, 32, 255))
            d.ellipse([(hx2 - 95 * scale) * s, (hy2 - 60 * scale) * s, (hx2 + 95 * scale) * s, (hy2 + 170 * scale) * s], fill=(20, 20, 22, 255))
            d.arc([(hx2 - 95 * scale) * s, (hy2 - 60 * scale) * s, (hx2 + 95 * scale) * s, (hy2 + 170 * scale) * s], start=200, end=330, fill=(72, 74, 76, 255), width=3 * s)
            if t >= 1.0:
                # handpiece lifted with the hand
                d.rounded_rectangle([(hx2 - 20 * scale) * s, (hy2 - 260 * scale) * s, (hx2 + 20 * scale) * s, (hy2 + 10) * s], radius=18 * s, fill=(190, 190, 186, 255))
                d.ellipse([(hx2 - 34 * scale) * s, (hy2 - 300 * scale) * s, (hx2 + 34 * scale) * s, (hy2 - 232 * scale) * s], fill=(150, 150, 148, 255))
        lay = aa_layer(hand)
        composite(fr, lay, blur=blur)
        if t >= 1.0:
            # holder now empty: mask the MP handpiece in the cradle
            cover = aa_layer(lambda d, s: d.rounded_rectangle([(0.484 * W + dx) * s, 0.465 * H * s, (0.532 * W + dx) * s, 0.73 * H * s], radius=14 * s, fill=(17, 17, 18, 255)))
            fr.alpha_composite(cover)
    return fr

# ================================================================ CUT 5: cartridge coupling
def c5_frame(t):
    fr = new_frame()
    hx = 0.50 * W
    head_y = 0.50 * H
    # cartridge rise: gap 36 px closes from 0.2 -> 1.0 s (5 mm/s), click at 1.0
    if t < 0.2:
        gap = 36
    elif t < 1.0:
        gap = 36 * (1 - (t - 0.2) / 0.8)
    else:
        gap = 0
    def scene(d, s):
        # top-lit white handpiece body pointing down (head at head_y)
        d.rounded_rectangle([(hx - 62) * s, 0.16 * H * s, (hx + 62) * s, (head_y - 40) * s], radius=40 * s, fill=(140, 140, 137, 255))
        d.rounded_rectangle([(hx - 48) * s, (head_y - 60) * s, (hx + 48) * s, head_y * s], radius=12 * s, fill=(160, 160, 156, 255))
        # highlight along the upper curve (top light)
        d.line([((hx - 40) * s, 0.17 * H * s), ((hx - 40) * s, (head_y - 70) * s)], fill=(215, 215, 210, 255), width=6 * s)
        # left hand (black glove) wrapped around the body: one matte mass, top edge catches the light
        d.rounded_rectangle([(hx - 150) * s, 0.30 * H * s, (hx + 150) * s, 0.47 * H * s], radius=90 * s, fill=(22, 22, 24, 255))
        d.arc([(hx - 150) * s, 0.30 * H * s, (hx + 150) * s, 0.47 * H * s], start=190, end=350, fill=(78, 78, 80, 255), width=4 * s)
        d.rounded_rectangle([(hx - 262) * s, 0.33 * H * s, (hx - 120) * s, 0.46 * H * s], radius=60 * s, fill=(18, 18, 20, 255))
        # cartridge (dark grey cylinder, glass window on top face hidden; side view)
        cy0 = head_y + gap
        d.rounded_rectangle([(hx - 44) * s, cy0 * s, (hx + 44) * s, (cy0 + 96) * s], radius=10 * s, fill=(52, 52, 54, 255))
        d.line([((hx - 44) * s, (cy0 + 2) * s), ((hx + 44) * s, (cy0 + 2) * s)], fill=(150, 150, 148, 255), width=3 * s)
        d.line([((hx - 30) * s, (cy0 + 60) * s), ((hx + 30) * s, (cy0 + 60) * s)], fill=(80, 80, 82, 255), width=2 * s)
        # right hand fingers holding the cartridge (thumb + index)
        d.ellipse([(hx - 170) * s, (cy0 + 20) * s, (hx - 30) * s, (cy0 + 200) * s], fill=(22, 22, 24, 255))
        d.ellipse([(hx + 30) * s, (cy0 + 20) * s, (hx + 170) * s, (cy0 + 200) * s], fill=(22, 22, 24, 255))
        d.arc([(hx - 170) * s, (cy0 + 20) * s, (hx - 30) * s, (cy0 + 200) * s], start=200, end=320, fill=(74, 74, 76, 255), width=4 * s)
        d.arc([(hx + 30) * s, (cy0 + 20) * s, (hx + 170) * s, (cy0 + 200) * s], start=220, end=340, fill=(74, 74, 76, 255), width=4 * s)
        # wrists / forearms to the bottom edge (dark)
        d.rounded_rectangle([(hx - 260) * s, (cy0 + 150) * s, (hx - 60) * s, 1.1 * H * s], radius=60 * s, fill=(16, 16, 18, 255))
        d.rounded_rectangle([(hx + 60) * s, (cy0 + 150) * s, (hx + 260) * s, 1.1 * H * s], radius=60 * s, fill=(16, 16, 18, 255))
    fr.alpha_composite(aa_layer(scene))
    # seam glint: 2 frames at the click (t in [1.0, 1.0+2/FPS))
    if 1.0 <= t < 1.0 + 2 / FPS:
        g = aa_layer(lambda d, s: d.line([((hx - 44) * s, head_y * s), ((hx + 44) * s, head_y * s)], fill=(240, 240, 236, 255), width=4 * s))
        composite(fr, g.filter(ImageFilter.GaussianBlur(3)), alpha=0.8)
        fr.alpha_composite(g)
    return fr

# ================================================================ CUT 6: 45-degree high angle
def c6_static():
    fr = new_frame()
    # director's face at the top, slightly soft, looking down (previs uses the profile photo)
    place_profile(fr, head_top_y=int(0.18 * H), head_h=int(0.22 * H), cx=int(0.36 * W), blur=3, alpha=0.9)
    # negative fill: darken everything but the face area a bit more
    # patient jaw at the bottom: curved skin band lit by a side-back grazing light
    arr = np.zeros((H, W, 3), np.float32) + np.array(BG, np.float32)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    # jaw curve: y = 0.95H at x=0.2W -> 0.62H at x=0.95W (quadratic-ish)
    u = np.clip((xs - 0.20 * W) / (0.75 * W), 0, 1)
    jaw_y = 0.95 * H - 0.33 * H * (u ** 0.8)
    below = ys - jaw_y
    inside = (below >= 0) & (xs >= 0.12 * W)
    f = np.clip(below / (0.30 * H), 0, 1) ** 0.9
    base = np.array([150, 116, 100], np.float32); dark = np.array([40, 30, 27], np.float32)
    col = base * (1 - f)[..., None] + dark * f[..., None]
    rim = np.exp(-np.clip(below, 0, None) / 22.0)
    col = col + rim[..., None] * np.array([80, 66, 56], np.float32)
    col = col * (0.6 + 0.4 * u)[..., None] + skin_noise((W, H), amp=6, seed=7)[..., None]
    m = inside.astype(np.float32)
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32) / 255
    arr = col * m[..., None] + arr * (1 - m[..., None])
    skin = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert('RGBA')
    # keep bg where not skin
    a = Image.fromarray((m * 255).astype(np.uint8))
    skin.putalpha(a)
    fr.alpha_composite(skin)
    return fr

def c6_tip_pos(t):
    """contact point along the jaw; shot 1 at 0.2-0.5 (press at 0.5), shot 2 at 1.2-1.5 (press at 1.5)."""
    base_x = 0.60 * W
    def shot(tl):  # returns (dx, lift) during a 0.3 s shot motion
        if tl < 0: return 0.0, 0.0
        if tl < 0.1: return 0.0, 10 * ease_out(tl / 0.1)
        if tl < 0.2: return 40 * ease_io((tl - 0.1) / 0.1), 10.0
        if tl < 0.3: return 40.0, 10 * (1 - ease_out((tl - 0.2) / 0.1))
        return 40.0, 0.0
    dx1, l1 = shot(t - 0.2)
    dx2, l2 = shot(t - 1.2)
    return base_x + dx1 + dx2, l1 + l2

def c6_frame(static, t):
    fr = static.copy()
    x, lift = c6_tip_pos(t)
    u = clamp((x - 0.20 * W) / (0.75 * W))
    jaw_y = 0.95 * H - 0.33 * H * (u ** 0.8)
    ty = jaw_y + 30 - lift
    # white lines on the jaw near the contact point
    for k, off in enumerate((-70, 0, 70)):
        xa = 0.50 * W + off; xb = xa + 150
        ua, ub = clamp((xa - 0.2 * W) / (0.75 * W)), clamp((xb - 0.2 * W) / (0.75 * W))
        ya = 0.95 * H - 0.33 * H * (ua ** 0.8) + 60; yb = 0.95 * H - 0.33 * H * (ub ** 0.8) + 60
        lay = aa_layer(lambda d, s, xa=xa, ya=ya, xb=xb, yb=yb: d.line([(xa * s, ya * s), (xb * s, yb * s)], fill=(236, 234, 228, 255), width=4 * s))
        fr.alpha_composite(lay)
    # handpiece from upper-left (eye) to the tip: diagonal
    ex, ey = 0.36 * W, 0.34 * H
    def hp(d, s):
        # glove mass mid-frame and the handpiece
        mx, my = lerp(ex, x, 0.55), lerp(ey, ty, 0.55)
        d.line([((mx - 40) * s, (my - 40) * s), (x * s, (ty - 30) * s)], fill=(196, 196, 192, 255), width=34 * s)
        d.line([((mx - 40) * s, (my - 40) * s), (x * s, (ty - 30) * s)], fill=(226, 226, 222, 255), width=8 * s)
        d.ellipse([(mx - 130) * s, (my - 120) * s, (mx + 110) * s, (my + 110) * s], fill=(22, 22, 24, 255))
        d.arc([(mx - 130) * s, (my - 120) * s, (mx + 110) * s, (my + 110) * s], start=200, end=330, fill=(80, 80, 82, 255), width=4 * s)
        # cartridge head at the tip
        d.rounded_rectangle([(x - 26) * s, (ty - 70) * s, (x + 26) * s, ty * s], radius=8 * s, fill=(48, 48, 50, 255))
        d.line([((x - 26) * s, (ty - 68) * s), ((x + 26) * s, (ty - 68) * s)], fill=(140, 140, 138, 255), width=2 * s)
    fr.alpha_composite(aa_layer(hp))
    # gel sheen at the contact
    gel = aa_layer(lambda d, s: d.ellipse([(x - 60) * s, (ty - 12) * s, (x + 60) * s, (ty + 22) * s], fill=(200, 200, 196, 60)))
    composite(fr, gel, blur=6)
    return fr

# ================================================================ CUT 7: contact macro with gel
def c7_static():
    fr = new_frame()
    hy = int(0.55 * H)
    arr = np.zeros((H, W, 3), np.float32) + np.array(BG, np.float32)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    below = ys - hy
    f = np.clip(below / (0.45 * H), 0, 1) ** 0.7
    base = np.array([96, 74, 66], np.float32); near = np.array([120, 94, 84], np.float32)
    col = base * (1 - f)[..., None] + near * f[..., None]
    # backlit horizon: thin bright edge along the horizon
    rim = np.exp(-np.clip(below, 0, None) / 10.0)
    col = col + rim[..., None] * np.array([90, 86, 82], np.float32)
    col = col + skin_noise((W, H), amp=5, seed=11)[..., None]
    m = (below >= 0).astype(np.float32)
    arr = col * m[..., None] + arr * (1 - m[..., None])
    fr = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert('RGBA')
    # white lines on the skin (foreshortened)
    for k, (x0, y0, x1, y1) in enumerate(((0.16 * W, hy + 110, 0.44 * W, hy + 96), (0.58 * W, hy + 150, 0.86 * W, hy + 130))):
        lay = aa_layer(lambda d, s, x0=x0, y0=y0, x1=x1, y1=y1: d.line([(x0 * s, y0 * s), (x1 * s, y1 * s)], fill=(230, 228, 222, 255), width=5 * s))
        fr.alpha_composite(lay)
    # gel patch: soft sheen ellipse around the contact zone
    gel = aa_layer(lambda d, s: d.ellipse([0.22 * W * s, (hy - 6) * s, 0.78 * W * s, (hy + 70) * s], fill=(140, 150, 160, 40)))
    composite(fr, gel, blur=16)
    return fr

def c7_frame(static, t):
    fr = static.copy()
    hy = 0.55 * H
    cx = 0.50 * W
    # local timeline: 0-0.7 hold; 0.7-1.0 shot3 (lift 10px, slide 40px, press); 1.0-1.5 hold; 1.57-1.8 lift/exit; 1.8-2.0 hold empty
    lift = 0.0; dx = 0.0; exit_p = 0.0
    if 0.7 <= t < 0.8: lift = 10 * ease_out((t - 0.7) / 0.1)
    elif 0.8 <= t < 0.9: lift = 10; dx = 40 * ease_io((t - 0.8) / 0.1)
    elif 0.9 <= t < 1.0: lift = 10 * (1 - ease_out((t - 0.9) / 0.1)); dx = 40
    elif t >= 1.0: dx = 40
    if t >= 1.57:
        exit_p = clamp((t - 1.57) / 0.23) ** 1.7  # accelerating exit toward upper right (slow peel, fast leave)
    x = cx + dx
    if t < 1.8:
        # cartridge head (side view) + handpiece going up-right into darkness
        yoff = -lift - exit_p * 0.55 * H
        xoff = exit_p * 0.75 * W
        cw, ch = int(0.24 * W), int(0.13 * W)
        blur = int(exit_p * 10)
        def head(d, s):
            X = x + xoff; Y = hy + yoff
            d.rounded_rectangle([(X - cw) * s, (Y - ch) * s, (X + cw) * s, Y * s], radius=14 * s, fill=(42, 42, 44, 255))
            d.line([((X - cw) * s, (Y - ch + 3) * s), ((X + cw) * s, (Y - ch + 3) * s)], fill=(150, 150, 148, 255), width=3 * s)
            d.line([((X - cw * 0.8) * s, (Y - 4) * s), ((X + cw * 0.8) * s, (Y - 4) * s)], fill=(24, 24, 26, 255), width=3 * s)
            # handpiece body up-right, fading to black
            for i in range(10):
                a = int(255 * (1 - i / 10) ** 1.2)
                x1 = X + i * 60; y1 = Y - ch - i * 90
                d.line([(x1 * s, y1 * s), ((x1 + 60) * s, (y1 - 90) * s)], fill=(190, 190, 186, a), width=70 * s)
            # window turns to camera during the exit: bright reflection ellipse on the head face
            if exit_p > 0.10:
                q = clamp((exit_p - 0.10) / 0.35)
                d.ellipse([(X - cw * 0.6 * q) * s, (Y - ch * 0.5 - 30 * q) * s, (X + cw * 0.6 * q) * s, (Y - ch * 0.5 + 30 * q) * s], fill=(236, 236, 232, int(220 * q)))
        lay = aa_layer(head)
        composite(fr, lay, blur=blur)
        # gel ring at the rim (backlit), brightens on press (4 frames after 1.0)
        ring_a = 0.45 if lift < 5 else 0.2
        if 1.0 <= t < 1.0 + 4 / FPS: ring_a = 0.95
        if t < 1.57:
            ring = aa_layer(lambda d, s: d.ellipse([(x - cw) * s, (hy - 10) * s, (x + cw) * s, (hy + 14) * s], outline=(214, 226, 236, 255), width=5 * s))
            composite(fr, ring.filter(ImageFilter.GaussianBlur(4)), alpha=ring_a)
            composite(fr, ring, alpha=ring_a * 0.9)
        else:
            # gel thread stretching from the skin to the rim, breaks at ~1.68
            if t < 1.69:
                p = (t - 1.57) / 0.12
                X = x + xoff; Y = hy + yoff
                thread = aa_layer(lambda d, s: d.line([(x * s, hy * s), ((x + (X - x) * 0.5) * s, (Y - 4) * s)], fill=(210, 222, 232, 255), width=max(1, int(4 * (1 - p))) * s))
                composite(fr, thread, alpha=0.9)
            # residual sheen
            res = aa_layer(lambda d, s: d.ellipse([(x - cw) * s, (hy - 6) * s, (x + cw) * s, (hy + 12) * s], fill=(180, 196, 210, 50)))
            composite(fr, res, blur=6)
    else:
        res = aa_layer(lambda d, s: d.ellipse([(x - int(0.24 * W)) * s, (hy - 6) * s, (x + int(0.24 * W)) * s, (hy + 12) * s], fill=(180, 196, 210, 40)))
        composite(fr, res, blur=6)
    # keep the top band (y < 16%) clear of the exiting handpiece: negative fill / flag
    band = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    for i in range(60):
        yy = int(0.16 * H) - 60 + i
        bd.line([(0, yy), (W, yy)], fill=(10, 10, 10, int(255 * (1 - i / 60))))
    bd.rectangle([0, 0, W, int(0.16 * H) - 60], fill=(10, 10, 10, 255))
    fr.alpha_composite(band)
    # match the end-card black: darken the frame progressively in the last 0.2 s so 90% is black
    if t >= 1.8:
        p = clamp((t - 1.8) / 0.2)
        dark = Image.new('RGBA', (W, H), (10, 10, 10, int(110 * p)))
        fr.alpha_composite(dark)
    return fr

# ================================================================ CUT 8: end card
def endcard(bg=BG, c12=OFFWHITE, c3=TAG):
    fr = Image.new('RGBA', (W, H), bg + (255,))
    f1 = font(F_SERIF_SB, 218)     # 殊璃鈴 glyph height ~ 10% H
    f2 = font(F_SANS_R, 86)        # SHURIRING cap height ~ 3.2% H
    f3s = font(F_SERIF_R, 84)      # 하나만. glyph height ~ 3.8% H
    f3l = font(F_SANS_R, 84)       # HIFU in sans
    l1, w1 = text_layer("殊璃鈴", f1, c12 + (255,), tracking=22)
    l2, w2 = text_layer("SHURIRING", f2, c12 + (255,), tracking=24)
    # line 3 mixed: 'HIFU,' sans + ' 하나만.' serif
    tmp = Image.new('RGBA', (10, 10)); td = ImageDraw.Draw(tmp)
    wa = td.textlength("HIFU,", font=f3l); wb = td.textlength(" 하나만.", font=f3s)
    l3 = Image.new('RGBA', (int(wa + wb) + 80, 200), (0, 0, 0, 0)); d3 = ImageDraw.Draw(l3)
    d3.text((40, 40), "HIFU,", font=f3l, fill=c3 + (255,))
    d3.text((40 + wa, 40), " 하나만.", font=f3s, fill=c3 + (255,))
    b1, b2, b3 = ink_bbox(l1), ink_bbox(l2), ink_bbox(l3)
    h1, h2, h3 = b1[3] - b1[1], b2[3] - b2[1], b3[3] - b3[1]
    gap12 = int(0.55 * h1); gap23 = int(0.9 * h2)
    total = h1 + gap12 + h2 + gap23 + h3
    top = int(0.46 * H - total / 2)
    # tracked text: visually centre by ink box (last tracking gap excluded)
    for lay, bb, y in ((l1, b1, top), (l2, b2, top + h1 + gap12), (l3, b3, top + h1 + gap12 + h2 + gap23)):
        crop = lay.crop(bb)
        fr.alpha_composite(crop, (int(W / 2 - crop.width / 2), y))
    return fr

def c8_frame(card, t):
    fr = new_frame()
    a = ease_out(clamp(t / 0.3))
    composite(fr, card, alpha=a)
    return fr

# ================================================================ assembly
CUTS = [
    (0.0, 2.0, 'C1  0.0–2.0  카트리지 트랜스듀서 창 매크로 · 반사선 횡단(1.0 중앙) · 실촬영(클립온 매크로)'),
    (2.0, 3.5, 'C2  2.0–3.5  원장 CU · 실촬영에서는 시선을 환자 턱선(아래)으로, 무표정 · 흰 가운은 -2stop 그늘'),
    (3.5, 5.0, 'C3  3.5–5.0  턱선 매크로 · 흰 펜 세 번째 선 4.0–4.7 · 실촬영(모델) 또는 AI P3'),
    (5.0, 7.0, 'C4  5.0–7.0  슈링크 유니버스 실루엣 · 2cm 병진 · 6.0 핸드피스 집어들기 · 실촬영 필수'),
    (7.0, 8.5, 'C5  7.0–8.5  카트리지 결합 · 5mm/s 상승 · 8.0 안착 · 실촬영'),
    (8.5, 10.0, 'C6  8.5–10.0  45° 부감 · 눈→손→팁 한 직선 · 9.0 / 10.0 두 샷 · 실촬영 필수'),
    (10.0, 12.0, 'C7  10.0–12.0  접촉 매크로 · 11.0 샷3 젤 고리 · 11.57 이탈·젤 실·창 반사 · 실촬영 또는 AI P7'),
    (12.0, 15.0, 'C8  12.0–15.0  엔딩 카드 · 12.0–12.3 페이드인 · 완전 노출 2.7초'),
]

def build():
    c1s, c1m = c1_static()
    c3s = c3_static()
    c4d = c4_device_layer()
    c6s = c6_static()
    c7s = c7_static()
    card = endcard()
    card.convert('RGB').save(f'{OUT}/endcard_night_1080x1920.png')
    endcard(bg=(20, 20, 20), c12=(255, 255, 255), c3=(230, 226, 218)).convert('RGB').save(f'{OUT}/endcard_day_1080x1920.png')
    board_times = {0: 1.0, 1: 3.0, 2: 4.5, 3: 6.2, 4: 8.0, 5: 9.0, 6: 11.62, 7: 14.0}
    ff = f'{SP}/ffmpeg'
    cmd = [ff, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', f'{OUT}/shuriring_15s_animatic.mp4']
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(N):
        t = i / FPS
        for ci, (a, b, label) in enumerate(CUTS):
            if a <= t < b or (ci == len(CUTS) - 1 and t >= a):
                break
        tl = t - a
        if ci == 0: fr = c1_frame(c1s, c1m, tl)
        elif ci == 1: fr = c2_frame(tl)
        elif ci == 2: fr = c3_frame(c3s, tl)
        elif ci == 3: fr = c4_frame(c4d, tl)
        elif ci == 4: fr = c5_frame(tl)
        elif ci == 5: fr = c6_frame(c6s, tl)
        elif ci == 6: fr = c7_frame(c7s, tl)
        else: fr = c8_frame(card, tl)
        subtitle_overlay(fr, t)
        if ci in board_times and abs(t - board_times[ci]) < 0.5 / FPS:
            fr.convert('RGB').save(f'{OUT}/boards/C{ci + 1}_{board_times[ci]:05.2f}s.png')
        caption_overlay(fr, t, label)
        proc.stdin.write(fr.convert('RGB').tobytes())
        if i % 30 == 0:
            print(f'frame {i}/{N} t={t:.2f}', flush=True)
    proc.stdin.close(); proc.wait()
    print('encoded', proc.returncode)

def write_sidecars():
    # SRT
    def ts(x):
        ms = int(round(x * 1000)); h, r = divmod(ms, 3600000); m, r = divmod(r, 60000); s, ms = divmod(r, 1000)
        return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
    with open(f'{OUT}/subtitles.srt', 'w', encoding='utf-8') as f:
        for i, (text, t_in, d_in, t_out, d_out) in enumerate(SUBS, 1):
            f.write(f'{i}\n{ts(t_in)} --> {ts(t_out)}\n{text}\n\n')
    rows = [
        ('C1', 0.0, 2.0, '카트리지 창 매크로', '1.0 반사선 창 중앙 통과', '없음', '실촬영(클립온 매크로) · AI P1 프리비즈'),
        ('C2', 2.0, 3.5, '원장 CU 관찰', '2.6–3.0 시선 이동 · 3.0 깜빡임', '먼저, 봅니다. (2.2 in → 5.0)', '실촬영 필수 · AI P2 프리비즈'),
        ('C3', 3.5, 5.0, '턱선 매크로 · 흰 펜 3번째 선', '4.0 접촉·딤플 · 4.0–4.7 획 · 4.9 정지', '유지', '실촬영(모델) 또는 AI P3'),
        ('C4', 5.0, 7.0, '슈링크 유니버스 실루엣', '5.5 손 진입 · 6.0 핸드피스 집어들기', '슈링크, 하나만. (5.2 in → 8.5)', '실촬영 필수 · AI P4 프리비즈'),
        ('C5', 7.0, 8.5, '카트리지 결합', '7.2–8.0 상승 · 8.0 안착(1~2프레임)', '유지', '실촬영 · AI P5 프리비즈'),
        ('C6', 8.5, 10.0, '45° 부감 · 눈→손→팁', '9.0 샷1+사케이드 · 10.0 샷2', '한 샷, 한 샷. (9.0 in → 11.8)', '실촬영 필수 · AI P6 프리비즈'),
        ('C7', 10.0, 12.0, '접촉 매크로 · 젤', '11.0 샷3 젤 고리 · 11.57 이탈·젤 실 · 11.8 창 반사·소실', '유지 → 11.6 아웃', '실촬영 또는 AI P7'),
        ('C8', 12.0, 15.0, '엔딩 카드', '12.0–12.3 페이드인 · 12.3–15.0 정지', '카드', '후반 그래픽'),
    ]
    with open(f'{OUT}/timeline.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f); w.writerow(['cut', 'in_s', 'out_s', 'dur_s', 'scene', 'events', 'subtitle', 'source'])
        for r in rows:
            w.writerow([r[0], r[1], r[2], round(r[2] - r[1], 2), r[3], r[4], r[5], r[6]])

if __name__ == '__main__':
    write_sidecars()
    build()
