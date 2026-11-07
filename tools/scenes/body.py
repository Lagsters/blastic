"""Realistic people for the story scenes: a 2D skeleton with human proportions, posed by joint
angles and dressed in shaded shapes, rendered straight to palette indices.

Proportions are fractions of standing height (Drillis & Contini, as tabulated by Winter,
Biomechanics and Motor Control of Human Movement). The walk is built the way a walk happens: each
foot stands still on the ground for 60% of the cycle while the body passes over it, rolls onto
its toes and swings forward to land heel first one step (0.41 of the height) ahead; the knees
bend to meet the ankles (two-bone IK) and the hips ride as high as the standing leg reaches, so
the body rises and falls like an inverted pendulum. A walker moved CYCLE heights per gait cycle
keeps its standing foot still on the ground.

Everyone faces right (+x); y grows downwards in the image, upwards in the skeleton.
"""
from math import sin, cos, radians, pi
import numpy as np

T, K, RED, ORANGE, YELLOW, GREEN, BROWN, BLUE, SKIN, WHITE, LIGHT, GREY, DARK = \
    11, 0, 2, 3, 4, 6, 8, 9, 10, 12, 13, 14, 15
SHADE = {SKIN: ORANGE, WHITE: LIGHT, LIGHT: GREY, GREY: DARK, DARK: K, RED: BROWN, ORANGE: RED,
         YELLOW: ORANGE, GREEN: DARK, BLUE: DARK, BROWN: K, K: K}
LIGHTEN = {SKIN: WHITE, RED: ORANGE, ORANGE: SKIN, YELLOW: WHITE, BLUE: LIGHT, GREY: LIGHT,
           DARK: GREY, BROWN: ORANGE, GREEN: YELLOW, LIGHT: WHITE, WHITE: WHITE, K: DARK}

# segment lengths as fractions of height
SEG = dict(head=0.130, neck=0.040, torso=0.300, pelvis=0.040, thigh=0.245, shin=0.246, ankle=0.039,
           foot=0.152, heel=0.035, upper=0.186, fore=0.146, hand=0.090)


STEP = 0.41            # a step is about 0.41 of the height in an ordinary walk, 0.77 of the leg
CYCLE = 2 * STEP       # a gait cycle: two steps
STANCE = 0.6           # the share of the cycle a foot stands on the ground
CLEAR = 0.05           # how high a swinging foot lifts
TOE_OFF, STRIKE = -32, 14   # foot angles at push-off and as the heel comes down, degrees


def cycle_of(seg):
    """A gait cycle for these legs: the same steps for the same leg length."""
    return CYCLE * (seg["thigh"] + seg["shin"] + seg["ankle"]) / (SEG["thigh"] + SEG["shin"] + SEG["ankle"])


def smooth(u):
    return u * u * (3 - 2 * u)


def foot_at(p, cyc=CYCLE):
    """A walking foot at phase p (0 its heel strike): ankle x ahead of the hips, lift over the
    ground, foot angle (degrees, + toes up) and how it meets the ground."""
    p %= 1.0
    front = 0.24 * cyc                             # it lands ahead of the hips
    back = front - STANCE * cyc
    if p < STANCE:
        u = p / STANCE
        x = front - u * STANCE * cyc                # planted: the body passes over it
        if u < 0.12:
            return x, 0.0, STRIKE * (1 - u / 0.12), "heel"   # the forefoot coming down
        if u < 0.7:
            return x, 0.0, 0.0, "flat"
        return x, 0.0, TOE_OFF * smooth((u - 0.7) / 0.3), "toe"   # rolling onto the toes
    u = (p - STANCE) / (1 - STANCE)
    x = back + (front - back) * smooth(u)
    return x, CLEAR * cyc / CYCLE * sin(pi * u), TOE_OFF + (STRIKE - TOE_OFF) * smooth(u), "swing"


def walk_pose(p, arms=18, seg=SEG, lean=3):
    """The near foot at phase p, the far one half a cycle on; arms swing against the legs."""
    cyc = cycle_of(seg)
    return dict(feet=(foot_at(p, cyc), foot_at(p + 0.5, cyc)),
                shoulder=(-arms * cos(2 * pi * p), arms * cos(2 * pi * p)),
                elbow=(16 + 12 * (1 - cos(2 * pi * p)) / 2, 16 + 12 * (1 + cos(2 * pi * p)) / 2),
                lean=lean)


def stand_pose(lean=0, shoulder=(4, -4), elbow=(12, 12)):
    return dict(feet=((0.03, 0.0, 0.0, "flat"), (-0.03, 0.0, 0.0, "flat")),
                shoulder=shoulder, elbow=elbow, lean=lean)


def _foot_points(seg, fx, lift, ang, kind):
    """Ankle, heel and toe of a foot at ankle x fx: on the ground when it bears weight, pivoting
    on the heel or the toe; the stance x is where the flat foot's ankle would be."""
    a = radians(ang)
    d = (cos(a), sin(a))
    up = (-sin(a), cos(a))
    heel_len, toe_len, h = seg["heel"], seg["foot"] - seg["heel"], seg["ankle"]
    if kind == "toe":
        toe = (fx + toe_len, 0.0)
        sole = (toe[0] - toe_len * d[0], toe[1] - toe_len * d[1])
    elif kind == "heel":
        heel = (fx - heel_len, 0.0)
        sole = (heel[0] + heel_len * d[0], heel[1] + heel_len * d[1])
    else:
        sole = (fx, lift)
    ankle = (sole[0] + h * up[0], sole[1] + h * up[1])
    heel = (sole[0] - heel_len * d[0], sole[1] - heel_len * d[1])
    toe = (sole[0] + toe_len * d[0], sole[1] + toe_len * d[1])
    return ankle, heel, toe


class Skeleton:
    """Joint positions (x forward, y up, in heights) for a pose, the feet on y=0: the hips as
    high as the standing legs reach, the knees bent forward to meet the ankles (two-bone IK)."""

    def __init__(self, pose, seg=SEG):
        self.seg = seg
        feet = [_foot_points(seg, *f) for f in pose["feet"]]
        reach = (seg["thigh"] + seg["shin"]) * 0.985
        hy = pose.get("hip") or min(a[1] + (reach * reach - a[0] * a[0]) ** 0.5
                                    for (a, _, _), f in zip(feet, pose["feet"]) if f[3] != "swing")
        self.hip = (0.0, hy)
        self.legs = []
        t, sh = seg["thigh"], seg["shin"]
        for ankle, heel, toe in feet:
            dx, dy = ankle[0], ankle[1] - hy
            d = min((dx * dx + dy * dy) ** 0.5, t + sh - 1e-6)
            phi = np.arctan2(dy, dx)
            alpha = np.arccos(np.clip((t * t + d * d - sh * sh) / (2 * t * d), -1, 1))
            knee = (t * cos(phi + alpha), hy + t * sin(phi + alpha))
            self.legs.append(dict(knee=knee, ankle=ankle, heel=heel, toe=toe))
        lean = radians(pose["lean"])
        self.waist = (0.0, hy)
        self.neck = (seg["torso"] * sin(lean), hy + seg["torso"] * cos(lean))
        self.head = (self.neck[0] + seg["neck"] * sin(lean) + 0.01, self.neck[1] + seg["neck"] + seg["head"] / 2)
        sho = (self.neck[0] - 0.01, self.neck[1] - 0.025)
        arms = []
        for i in range(2):
            a = radians(pose["shoulder"][i])
            elbow = (sho[0] + seg["upper"] * sin(a), sho[1] - seg["upper"] * cos(a))
            f = a + radians(pose["elbow"][i])
            wrist = (elbow[0] + seg["fore"] * sin(f), elbow[1] - seg["fore"] * cos(f))
            hand = (wrist[0] + seg["hand"] * 0.6 * sin(f), wrist[1] - seg["hand"] * 0.6 * cos(f))
            arms.append(dict(shoulder=sho, elbow=elbow, wrist=wrist, hand=hand))
        self.arms = arms


class Paint:
    """A sprite being painted: shapes in skeleton coordinates (heights), light from the upper
    right; px is the figure's height in pixels."""

    def __init__(self, w, h, px, foot_x):
        self.img = np.full((h, w), T)
        self.px, self.h, self.foot_x = px, h, foot_x
        yy, xx = np.mgrid[0:h, 0:w]
        self.half = (xx + yy) % 2 == 0                      # a checkerboard for the half tones
        self.x = (xx + 0.5 - foot_x) / px
        self.y = (h - 0.5 - yy) / px

    def capsule(self, a, b, r, col, shade=True):
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy or 1e-9
        t = np.clip(((self.x - ax) * dx + (self.y - ay) * dy) / L2, 0, 1)
        nx, ny = self.x - (ax + t * dx), self.y - (ay + t * dy)
        m = nx * nx + ny * ny <= r * r
        self.fill(m, col, nx, ny, r, shade)
        return m

    def blob(self, c, rx, ry, col, shade=True):
        nx, ny = (self.x - c[0]) / rx, (self.y - c[1]) / ry
        m = nx * nx + ny * ny <= 1
        self.fill(m, col, nx, ny, 1.0, shade)
        return m

    def poly(self, pts, col, shade=True):
        from PIL import Image, ImageDraw
        h, w = self.img.shape
        m = Image.new("1", (w, h))
        ImageDraw.Draw(m).polygon([(x * self.px + self.foot_x, h - y * self.px) for x, y in pts], fill=1)
        m = np.array(m, bool)
        self.img[m] = col
        if shade:                                           # shadow along its back edge, row by row
            left = np.where(m.any(axis=1), m.argmax(axis=1), 0)[:, None]
            depth = (np.arange(w)[None, :] - left) / self.px
            dk = SHADE.get(col, col)
            self.img[m & (depth < 0.018)] = dk
            self.img[m & (depth >= 0.018) & (depth < 0.034) & self.half] = dk
        return m

    def fill(self, m, col, nx, ny, r, shade, flat=False):
        """Paint a round form lit from the upper right: shadow, a dithered half shadow, the
        colour, a dithered sheen and a highlight on the lit edge."""
        self.img[m] = col
        if not shade:
            return
        lit = (nx * 0.6 + ny * 0.8) / r
        dk, lt = SHADE.get(col, col), LIGHTEN.get(col, col)
        self.img[m & (lit < -0.45)] = dk
        self.img[m & (lit >= -0.45) & (lit < -0.15) & self.half] = dk
        self.img[m & (lit > 0.55) & (lit <= 0.8) & self.half] = lt
        self.img[m & (lit > 0.8)] = lt

    def dot(self, p, col):
        x = int(p[0] * self.px + self.foot_x)
        y = int(self.h - 1 - p[1] * self.px)
        if 0 <= x < self.img.shape[1] and 0 <= y < self.img.shape[0]:
            self.img[y, x] = col

    def outline(self):
        o = self.img != T
        edge = np.zeros_like(o)
        edge[1:, :] |= o[:-1, :]
        edge[:-1, :] |= o[1:, :]
        edge[:, 1:] |= o[:, :-1]
        edge[:, :-1] |= o[:, 1:]
        self.img[edge & ~o] = K
        return self.img


def limb(P, a, b, c, r1, r2, col, col2=None):
    """An upper and a lower limb segment from a through b to c."""
    P.capsule(a, b, r1, col)
    P.capsule(b, c, r2, col2 if col2 is not None else col)


def dark(col):
    return SHADE.get(col, col)


def leg(P, s, i, cloth, boot, boot_top=0.5, w=1.0):
    """Leg i (1 the far one, darker): thigh and shin in cloth, a boot from boot_top of the shin."""
    lg = s.legs[i]
    tone = dark if i == 1 else (lambda c: c)
    P.capsule(s.hip, lg["knee"], 0.042 * w, tone(cloth))
    k, a = lg["knee"], lg["ankle"]
    mid = (k[0] + (a[0] - k[0]) * boot_top, k[1] + (a[1] - k[1]) * boot_top)
    P.capsule(k, mid, 0.032 * w, tone(cloth))
    P.capsule(mid, a, 0.032 * w, tone(boot))
    P.poly([lg["heel"], (lg["heel"][0], lg["heel"][1] + 0.04 * w), (a[0] + 0.02 * w, a[1]), lg["toe"]], tone(boot),
           shade=False)
    P.capsule(lg["heel"], lg["toe"], 0.011 * w, K)                             # the sole


def foot_only(P, s, i, boot):
    """Just a shoe under a long skirt or robe."""
    lg = s.legs[i]
    tone = dark if i == 1 else (lambda c: c)
    P.poly([lg["heel"], (lg["heel"][0], lg["heel"][1] + 0.035), (lg["ankle"][0] + 0.02, lg["ankle"][1]), lg["toe"]],
           tone(boot), shade=False)
    P.capsule(lg["heel"], lg["toe"], 0.01, K)


def arm(P, s, i, sleeve, skin=SKIN, w=1.0):
    """Arm i (1 the far one, darker): sleeve to the wrist, the hand."""
    a = s.arms[i]
    tone = dark if i == 1 else (lambda c: c)
    limb(P, a["shoulder"], a["elbow"], a["wrist"], 0.027 * w, 0.023 * w, tone(sleeve))
    P.capsule(a["wrist"], a["hand"], 0.019 * w, tone(skin))


def torso(P, s, col, w=1.0):
    """A body seen from the side: the chest deeper than the waist, shoulders rounded."""
    wx, wy = s.waist
    nx, ny = s.neck
    P.poly([(wx - 0.05 * w, wy - 0.02), (nx - 0.06 * w, ny - 0.04), (nx - 0.03 * w, ny + 0.005),
            (nx + 0.03 * w, ny + 0.0), (nx + 0.07 * w, ny - 0.06), (wx + 0.075 * w, wy + 0.12),
            (wx + 0.055 * w, wy - 0.02)], col)


def skirt(P, s, col, hem=0.05, flare=0.05, top=0.0):
    """A long skirt or robe from the waist, its hem spread over both legs as they move."""
    wx, wy = s.waist
    xs = [s.legs[i][k][0] for i in (0, 1) for k in ("ankle", "knee")]
    back, front = min(xs) - flare, max(xs) + flare
    P.poly([(wx - 0.06, wy + top), (wx + 0.07, wy + top), (front, hem), (back, hem)], col)
    P.capsule((back, hem), (front, hem), 0.008, dark(col))


def coat(P, s, col, length=0.25):
    """A coat from the shoulders to below the knees, swinging out over the leading leg."""
    wx, wy = s.waist
    nx, ny = s.neck
    knees = [s.legs[i]["knee"][0] for i in (0, 1)]
    hem = wy - length
    P.poly([(nx - 0.06, ny - 0.04), (nx + 0.07, ny - 0.06), (wx + 0.075, wy + 0.1), (max(knees) + 0.05, hem),
            (min(knees) - 0.06, hem), (wx - 0.06, wy)], col)


def head(P, s, hair, skin=SKIN, long_hair=False, beard=None, moustache=None, old=False):
    """A head turned to the right: skull and hair, face, nose, ear, eye and brow, mouth; the
    small features never shrink below a pixel, and at close-up size get lids, iris and lips.
    P.talk opens the mouth, P.blink shuts the eyes."""
    hx, hy = s.head
    k = s.seg["head"] / SEG["head"]

    def q(dx, dy):
        return hx + dx * k, hy + dy * k
    P.capsule(s.neck, (s.neck[0] + 0.005, s.neck[1] + 0.04 * k), 0.022 * k, skin)
    if long_hair:
        P.poly([q(-0.055, 0.02), q(-0.075, -0.22), q(-0.02, -0.21), q(0.0, -0.02)], hair)
    P.blob(q(-0.012, 0.006), 0.05 * k, 0.062 * k, hair)
    P.blob(q(0.006, -0.006), 0.046 * k, 0.058 * k, skin)
    nose = 0.07 if old else 0.064
    P.poly([q(0.044, 0.004), q(nose, -0.016), q(0.05, -0.026), q(0.044, -0.022)], skin, shade=False)
    if old:
        P.blob(q(0.058, -0.02), 0.012 * k, 0.011 * k, skin, shade=False)       # an old woman's round nose tip
    P.blob(q(-0.026, -0.002), 0.011 * k, 0.016 * k, dark(skin))                # ear
    P.poly([q(-0.05, 0.03), q(-0.02, 0.062), q(0.035, 0.06), q(0.052, 0.035), q(0.012, 0.042), q(-0.045, 0.0)],
           hair, shade=False)
    if beard is not None:
        P.poly([q(-0.02, -0.01), q(0.05, -0.03), q(0.05, -0.08), q(0.02, -0.14), q(-0.01, -0.1)], beard)
    eye = q(0.028, 0.008)
    if getattr(P, "blink", False):
        feature(P, eye, 0.009 * k, 0.0015 * k, K)
    else:
        feature(P, eye, 0.009 * k, 0.006 * k, WHITE)
        feature(P, q(0.033, 0.008), 0.0045 * k, 0.0055 * k, K)
        if P.px * k > 150:
            feature(P, q(0.032, 0.009), 0.004 * k, 0.005 * k, BLUE if hair in (YELLOW, BROWN) else BROWN)
            feature(P, q(0.033, 0.0085), 0.002 * k, 0.0025 * k, K)
            feature(P, q(0.027, 0.0135), 0.01 * k, 0.0012 * k, K)              # the upper lid
    feature(P, q(0.026, 0.022), 0.012 * k, 0.003 * k, dark(hair) if hair not in (K, WHITE, LIGHT) else K)
    if old and P.px * k > 150:
        for d in (0.0, 0.01):                                                  # wrinkles
            feature(P, q(0.014 + d, -0.01 - d), 0.008 * k, 0.001 * k, dark(skin))
    if moustache is not None:
        P.poly([q(0.01, -0.026), q(0.06, -0.028), q(0.085, -0.048), q(0.055, -0.036), q(0.015, -0.036)],
               moustache, shade=False)
    mouth = q(0.036, -0.038)
    if getattr(P, "talk", False):
        feature(P, mouth, 0.012 * k, 0.008 * k, K)
        if P.px * k > 150:
            feature(P, q(0.036, -0.034), 0.009 * k, 0.002 * k, WHITE)
            feature(P, q(0.036, -0.043), 0.007 * k, 0.003 * k, RED)
    else:
        feature(P, mouth, 0.012 * k, 0.0035 * k, dark(skin) if beard is not None or old else RED)
    if P.px * k > 150 and beard is None and not old:
        feature(P, q(0.01, -0.015), 0.012 * k, 0.008 * k, ORANGE if skin == SKIN else dark(skin))   # cheek


def feature(P, c, rx, ry, col):
    """A small shape on the face, never smaller than a pixel."""
    m = P.blob(c, rx, ry, col, shade=False)
    if not m.any():
        P.dot(c, col)


def dress_dratewka(P, s):
    """The young shoemaker: white shirt, brown leather apron, dark breeches, brown boots, a red
    cap with a feather."""
    arm(P, s, 1, WHITE)
    leg(P, s, 1, DARK, BROWN)
    leg(P, s, 0, DARK, BROWN)
    torso(P, s, WHITE)
    wx, wy = s.waist
    nx, ny = s.neck
    P.poly([(nx + 0.045, ny - 0.07), (nx + 0.075, ny - 0.08), (wx + 0.085, wy - 0.18), (wx + 0.0, wy - 0.2),
            (wx + 0.035, wy)], BROWN)                                          # the leather apron
    P.capsule((nx + 0.05, ny - 0.07), (nx - 0.02, ny + 0.0), 0.006, BROWN)
    arm(P, s, 0, WHITE)
    head(P, s, hair=BROWN)
    hx, hy = s.head
    P.poly([(hx - 0.058, hy + 0.045), (hx - 0.03, hy + 0.085), (hx + 0.04, hy + 0.08), (hx + 0.06, hy + 0.05),
            (hx + 0.09, hy + 0.04), (hx + 0.05, hy + 0.035)], RED)              # cap with its peak
    P.capsule((hx - 0.02, hy + 0.08), (hx - 0.05, hy + 0.13), 0.007, WHITE)     # feather


def dress_wanda(P, s):
    """The princess: a red skirt to the ankles over the stride, white blouse, red bodice, a
    long golden braid and a wreath of flowers."""
    arm(P, s, 1, WHITE)
    for i in (1, 0):
        foot_only(P, s, i, K)
    skirt(P, s, RED, hem=0.04)
    torso(P, s, WHITE, 0.92)
    wx, wy = s.waist
    nx, ny = s.neck
    P.poly([(wx - 0.045, wy), (nx - 0.04, ny - 0.1), (nx + 0.06, ny - 0.1), (wx + 0.065, wy)], RED)   # bodice
    for k in range(3):                                                         # corals
        P.blob((nx + 0.035 - k * 0.012, ny - 0.035 + k * 0.004), 0.006, 0.006, RED, shade=False)
    arm(P, s, 0, WHITE)
    hx, hy = s.head
    P.capsule((hx - 0.05, hy - 0.01), (hx - 0.07, hy - 0.28), 0.018, YELLOW)    # the braid
    for k in range(6):
        P.capsule((hx - 0.052 - k * 0.003, hy - 0.03 - k * 0.04), (hx - 0.06 - k * 0.003, hy - 0.05 - k * 0.04),
                  0.004, ORANGE, shade=False)
    head(P, s, hair=YELLOW)
    P.capsule((hx - 0.055, hy + 0.04), (hx + 0.045, hy + 0.055), 0.01, GREEN)   # the wreath
    for k, col in enumerate((RED, WHITE, BLUE, RED, WHITE)):
        P.blob((hx - 0.05 + k * 0.022, hy + 0.04 + k * 0.003 + 0.008), 0.007, 0.007, col, shade=False)


def dress_twardowski(P, s):
    """Master Twardowski, a nobleman: blue kontusz to the knees over a red zupan, a yellow sash,
    red trousers and yellow boots, a fur kolpak with a heron's plume, long moustaches."""
    arm(P, s, 1, BLUE)
    leg(P, s, 1, RED, YELLOW, 0.4)
    leg(P, s, 0, RED, YELLOW, 0.4)
    coat(P, s, BLUE, 0.24)
    torso(P, s, BLUE)
    wx, wy = s.waist
    nx, ny = s.neck
    P.poly([(nx + 0.03, ny - 0.01), (nx + 0.07, ny - 0.06), (wx + 0.075, wy + 0.1), (wx + 0.04, wy - 0.2),
            (wx + 0.02, wy - 0.2)], RED)                                        # the zupan
    P.poly([(wx - 0.05, wy + 0.02), (wx + 0.07, wy + 0.04), (wx + 0.075, wy + 0.07), (wx - 0.05, wy + 0.06)], YELLOW)
    arm(P, s, 0, BLUE)
    head(P, s, hair=K, moustache=K)
    hx, hy = s.head
    P.poly([(hx - 0.05, hy + 0.03), (hx - 0.05, hy + 0.1), (hx + 0.05, hy + 0.1), (hx + 0.055, hy + 0.03)], BROWN)
    P.capsule((hx + 0.04, hy + 0.09), (hx + 0.08, hy + 0.16), 0.006, WHITE)     # the plume


def dress_devil(P, s):
    """The devil as a gentleman: a long dark coat, red waistcoat, red skin, black hair, horns
    and a tail."""
    wx, wy = s.waist
    P.capsule((wx - 0.04, wy - 0.05), (wx - 0.13, wy - 0.2), 0.012, RED)         # the tail
    P.capsule((wx - 0.13, wy - 0.2), (wx - 0.1, wy - 0.27), 0.012, RED)
    P.poly([(wx - 0.1, wy - 0.27), (wx - 0.12, wy - 0.3), (wx - 0.08, wy - 0.29)], RED, shade=False)
    arm(P, s, 1, DARK, RED)
    leg(P, s, 1, K, K)
    leg(P, s, 0, K, K)
    coat(P, s, DARK, 0.28)
    torso(P, s, DARK)
    nx, ny = s.neck
    P.poly([(nx + 0.03, ny - 0.01), (nx + 0.07, ny - 0.06), (wx + 0.075, wy + 0.1), (wx + 0.04, wy - 0.02)], RED)
    arm(P, s, 0, DARK, RED)
    head(P, s, hair=K, skin=RED, moustache=K)
    hx, hy = s.head
    for dx in (-0.03, 0.02):                                                    # horns
        P.poly([(hx + dx - 0.012, hy + 0.05), (hx + dx - 0.03, hy + 0.12), (hx + dx + 0.012, hy + 0.055)], K)


def dress_krak(P, s):
    """King Krak: a red robe to the floor edged with ermine, a golden crown, a long white beard."""
    arm(P, s, 1, RED)
    skirt(P, s, RED, hem=0.0, flare=0.08, top=0.12)
    torso(P, s, RED, 1.1)
    wx, wy = s.waist
    P.capsule((wx + 0.07, wy + 0.1), (wx + 0.11, 0.01), 0.018, WHITE)             # the ermine edge
    for k in range(5):
        P.dot((wx + 0.075 + k * 0.008, wy + 0.06 - k * 0.11), K)
    P.capsule((-0.12, 0.012), (0.18, 0.012), 0.014, WHITE)
    arm(P, s, 0, RED)
    head(P, s, hair=WHITE, beard=WHITE)
    hx, hy = s.head
    crown = [(hx - 0.05, hy + 0.04), (hx - 0.05, hy + 0.1), (hx - 0.03, hy + 0.075), (hx - 0.005, hy + 0.105),
             (hx + 0.02, hy + 0.075), (hx + 0.045, hy + 0.1), (hx + 0.05, hy + 0.04)]
    P.poly(crown, YELLOW)
    P.blob((hx, hy + 0.06), 0.008, 0.008, RED, shade=False)


def dress_dwarf(P, s):
    """A Wroclaw dwarf: a gnome in a blue coat and a tall red cap, a long white beard."""
    arm(P, s, 1, BLUE, w=1.3)
    leg(P, s, 1, BROWN, K, 0.3, w=1.3)
    leg(P, s, 0, BROWN, K, 0.3, w=1.3)
    coat(P, s, BLUE, 0.05)
    torso(P, s, BLUE, 1.5)
    arm(P, s, 0, BLUE, w=1.3)
    head(P, s, hair=WHITE, beard=WHITE)
    hx, hy = s.head
    k = s.seg["head"] / SEG["head"]
    P.poly([(hx - 0.055 * k, hy + 0.035 * k), (hx - 0.01 * k, hy + 0.17 * k), (hx + 0.055 * k, hy + 0.035 * k)], RED)


def dress_jaga(P, s):
    """Baba Jaga, bent with age: a long grey dress, a shawl, a red kerchief over grey hair."""
    arm(P, s, 1, GREY)
    for i in (1, 0):
        foot_only(P, s, i, K)
    skirt(P, s, GREY, hem=0.02, flare=0.06)
    torso(P, s, GREY, 1.1)
    arm(P, s, 0, GREY)
    head(P, s, hair=LIGHT, old=True)
    hx, hy = s.head
    P.poly([(hx - 0.06, hy - 0.05), (hx - 0.06, hy + 0.04), (hx - 0.02, hy + 0.07), (hx + 0.04, hy + 0.06),
            (hx + 0.045, hy + 0.035), (hx - 0.02, hy + 0.03), (hx - 0.03, hy - 0.06)], RED)   # kerchief
    for k in range(4):
        P.dot((hx - 0.045 + k * 0.02, hy + 0.045), WHITE)


def dress_witch(P, s):
    """A witch of Sleza: young, long black hair, a green dress to the ground, barefoot."""
    arm(P, s, 1, GREEN)
    for i in (1, 0):
        foot_only(P, s, i, SKIN)
    skirt(P, s, GREEN, hem=0.03)
    torso(P, s, GREEN, 0.92)
    arm(P, s, 0, GREEN)
    head(P, s, hair=K, long_hair=True)


def figure(dress, pose, px, w, h, seg=SEG, talk=False, blink=False, before=None, after=None, at=None):
    """A dressed figure standing on the sprite's bottom row, its hips at x = w / 2 (or at x);
    before / after paint props behind or in front of it."""
    s = Skeleton(pose, seg)
    P = Paint(w, h, px, w / 2 if at is None else at)
    P.talk, P.blink = talk, blink
    if before:
        before(P, s)
    dress(P, s)
    if after:
        after(P, s)
    return P.outline()


def head_at(pose, px, h, w, seg=SEG, at=None):
    """Where the head's centre lands in a figure's picture, in pixels."""
    s = Skeleton(pose, seg)
    return (w / 2 if at is None else at) + s.head[0] * px, h - s.head[1] * px


def broom_in_hand(P, s):
    """A broom held upright in the near hand, its bristles on the ground."""
    x = s.arms[0]["hand"][0]
    P.capsule((x, 0.12), (x + 0.02, 0.95), 0.012, BROWN)
    P.poly([(x - 0.05, 0.0), (x - 0.01, 0.16), (x + 0.03, 0.16), (x + 0.07, 0.0)], YELLOW)


def broom_ridden(P, s):
    """A broom under a sitting rider, bristles trailing behind."""
    y = s.hip[1] - 0.035
    P.capsule((-0.3, y), (0.42, y + 0.02), 0.012, BROWN)
    P.poly([(-0.3, y + 0.04), (-0.52, y + 0.08), (-0.55, y - 0.06), (-0.3, y - 0.03)], YELLOW)


def ride_pose(lean=25, hip=0.3):
    """Sitting astride, knees up, hands forward on the broomstick or the reins."""
    return dict(hip=hip, feet=((0.16, hip - 0.36, -30, "swing"), (0.12, hip - 0.36, -30, "swing")),
                shoulder=(70, 60), elbow=(10, 15), lean=lean)


def dance_pose(k, lean=0):
    """Dancing round the fire: arms raised in turn, weight on one foot then the other."""
    up, down = (160, 30) if k == 0 else (30, 160)
    return dict(feet=((0.05 if k else 0.1, 0.0, 0.0, "flat"), (-0.06 if k else -0.02, 0.04 * k, -20 * k, "flat")),
                shoulder=(up, down), elbow=(25, 25), lean=lean)


def cast_pose(lean=22):
    """Casting: the near arm thrust up and forward, the far one low."""
    return dict(feet=((0.03, 0.0, 0.0, "flat"), (-0.04, 0.0, 0.0, "flat")), shoulder=(125, 10), elbow=(8, 15), lean=lean)


DWARF = dict(SEG, head=0.26, neck=0.02, torso=0.27, thigh=0.17, shin=0.16, ankle=0.03, foot=0.13, heel=0.03,
             upper=0.16, fore=0.12, hand=0.07)
OLD = SEG                              # Baba Jaga is the same frame, bent (lean)
