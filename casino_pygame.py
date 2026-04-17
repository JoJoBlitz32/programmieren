#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Joas Casino Royale — Pygame Edition"""

import pygame, random, json, sys, math, struct
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Init
# ─────────────────────────────────────────────────────────────────────────────
pygame.mixer.pre_init(44100, -16, 1, 1024)
pygame.init()
W, H = 1280, 720
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Casino Royale")
clock = pygame.time.Clock()
FPS   = 60

SAVE_FILE      = Path.home() / ".casino_royale_pg.json"
STARTING_COINS = 1_000

# ── Colors ────────────────────────────────────────────────────────────────────
BG      = (10,  32,  20)
FELT    = (20,  65,  40)
PANEL   = (7,   18,  11)
PANELB  = (14,  36,  22)
GOLD    = (255, 215, 0)
GOLD2   = (200, 160, 0)
GOLD3   = (140, 100, 0)
WHITE   = (255, 255, 255)
CREAM   = (255, 248, 220)
RED     = (210, 40,  40)
DKRED   = (140, 20,  20)
BLACK   = (15,  15,  15)
GRAY    = (120, 120, 120)
LGRAY   = (190, 190, 190)
WINC    = (50,  210, 85)
LOSEC   = (210, 50,  50)
BLUE    = (60,  130, 220)
DKBLUE  = (30,  60,  150)
ROULRED = (200, 40,  40)
DARKGRN = (10,  90,  30)

# ── Fonts ─────────────────────────────────────────────────────────────────────
_f      = "arial"
F_TITLE = pygame.font.SysFont(_f, 56, bold=True)
F_LG    = pygame.font.SysFont(_f, 34, bold=True)
F_MDB   = pygame.font.SysFont(_f, 22, bold=True)
F_MD    = pygame.font.SysFont(_f, 22)
F_SM    = pygame.font.SysFont(_f, 17)
F_SMB   = pygame.font.SysFont(_f, 17, bold=True)
F_XS    = pygame.font.SysFont(_f, 13)
F_HUGE  = pygame.font.SysFont(_f, 72, bold=True)

# ─────────────────────────────────────────────────────────────────────────────
# Sound system  (all sounds generated procedurally — no audio files needed)
# ─────────────────────────────────────────────────────────────────────────────
def _make_snd(gen_fn, dur, sr=44100):
    """Build a mono 16-bit Sound.  gen_fn(t_sec, progress 0-1) -> float [-1,1]."""
    n   = int(sr * dur)
    buf = struct.pack(
        f"<{n}h",
        *[max(-32767, min(32767, int(gen_fn(i / sr, i / n) * 32767)))
          for i in range(n)]
    )
    return pygame.mixer.Sound(buffer=buf)


class SoundManager:
    _SETTINGS = Path.home() / ".casino_royale_settings.json"

    def __init__(self):
        self.master = 0.7
        self.sfx    = 1.0
        self._snds  = {}
        try:
            self._build()
        except Exception:
            pass          # no crash if mixer unavailable
        self._load()

    # ── sound generation ──────────────────────────────────────────────────────
    def _build(self):
        p2 = 2 * math.pi
        def s(f, t): return math.sin(p2 * f * t)

        # Button click — soft 650 Hz tap
        self._snds["click"] = _make_snd(
            lambda t, p: s(650, t) * math.exp(-t * 70) * 0.65, 0.06)

        # Coin clink — metallic harmonics
        self._snds["coin"] = _make_snd(
            lambda t, p: (s(1100,t)*0.5 + s(1650,t)*0.3 + s(550,t)*0.2)
                         * math.exp(-t * 14), 0.22)

        # Card swish — white-noise burst
        self._snds["card"] = _make_snd(
            lambda t, p: random.uniform(-1, 1) * math.exp(-t * 28) * 0.8, 0.09)

        # Dice rattle — noise pulses
        self._snds["dice"] = _make_snd(
            lambda t, p: random.uniform(-1, 1)
                         * abs(math.sin(t * 32)) * (1 - p) ** 0.5, 0.34)

        # Coin-flip whoosh — noise with arc envelope
        self._snds["flip"] = _make_snd(
            lambda t, p: random.uniform(-1, 1) * math.sin(math.pi * p) * 0.85, 0.44)

        # Roulette spin whir — pitch sweep up
        self._snds["spin"] = _make_snd(
            lambda t, p: s(150 + 700 * p, t) * math.sin(math.pi * p) * 0.55, 0.40)

        # Small win — C E G C5 ascending arpeggio
        _wn = [261.63, 329.63, 392.0, 523.25]
        def _win(t, p):
            i = min(3, int(p * 4)); lp = p * 4 - i
            return (s(_wn[i], t) + s(_wn[i]*2, t)*0.2) * math.sin(math.pi * lp) * 0.7
        self._snds["win"] = _make_snd(_win, 0.74)

        # Jackpot — C E G C5 E5 G5 fast fanfare
        _jp = [261.63, 329.63, 392.0, 523.25, 659.25, 783.99]
        def _jackpot(t, p):
            i = min(5, int(p * 6)); lp = p * 6 - i
            return (s(_jp[i], t)*0.7 + s(_jp[i]*2, t)*0.25) * math.sin(math.pi * lp)
        self._snds["jackpot"] = _make_snd(_jackpot, 1.20)

        # Lose — G Eb C descending minor
        _ln = [392.0, 311.13, 261.63]
        def _lose(t, p):
            i = min(2, int(p * 3)); lp = p * 3 - i
            return s(_ln[i], t) * math.sin(math.pi * lp) * (1 - p * 0.4) * 0.65
        self._snds["lose"] = _make_snd(_lose, 0.68)

    # ── persistence ───────────────────────────────────────────────────────────
    def _load(self):
        try:
            if self._SETTINGS.exists():
                d = json.loads(self._SETTINGS.read_text())
                self.master = float(d.get("master", 0.7))
                self.sfx    = float(d.get("sfx",    1.0))
        except Exception:
            pass

    def save(self):
        try:
            self._SETTINGS.write_text(
                json.dumps({"master": self.master, "sfx": self.sfx}, indent=2))
        except Exception:
            pass

    # ── playback ──────────────────────────────────────────────────────────────
    def play(self, name):
        snd = self._snds.get(name)
        if snd:
            snd.set_volume(max(0.0, min(1.0, self.master * self.sfx)))
            snd.play()

# ── Slot symbols ──────────────────────────────────────────────────────────────
SLOT_DEFS = [
    ("BAR",  (230, 200, 50),  20, 22),
    ("7",    (220, 50,  50),  50, 12),
    ("Star", (255, 215, 0),   12, 18),
    ("Dia",  (80,  170, 255),  8, 15),
    ("Hrt",  (255, 100, 150),  6, 15),
    ("Club", (80,  210, 100),  4, 12),
    ("WILD", (190, 80,  255), 100, 6),
]
S_NAMES   = [d[0] for d in SLOT_DEFS]
S_WEIGHTS = [d[3] for d in SLOT_DEFS]
S_PAY     = {d[0]: d[2] for d in SLOT_DEFS}
S_COLOR   = {d[0]: d[1] for d in SLOT_DEFS}

# ── Cards ─────────────────────────────────────────────────────────────────────
SUITS    = ["S","C","H","D"]
RANKS    = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]
RED_S    = {"H","D"}
SUIT_SYM = {"S":"♠","C":"♣","H":"♥","D":"♦"}

# ── Roulette ──────────────────────────────────────────────────────────────────
RED_NUMS    = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
WHEEL_NUMS  = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,
               10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]

# ── Dice ─────────────────────────────────────────────────────────────────────
DICE_DOTS = [
    [(0.5, 0.5)],
    [(0.25,0.25),(0.75,0.75)],
    [(0.25,0.25),(0.5,0.5),(0.75,0.75)],
    [(0.25,0.25),(0.75,0.25),(0.25,0.75),(0.75,0.75)],
    [(0.25,0.25),(0.75,0.25),(0.5,0.5),(0.25,0.75),(0.75,0.75)],
    [(0.25,0.25),(0.75,0.25),(0.25,0.5),(0.75,0.5),(0.25,0.75),(0.75,0.75)],
]

# ── Lobby cabinet colors ──────────────────────────────────────────────────────
GAME_COLORS = {
    "slots":     (230, 130, 30),
    "blackjack": (40,  180, 80),
    "roulette":  (200, 40,  40),
    "dice":      (60,  130, 220),
    "hilo":      (150, 80,  220),
    "coinflip":  (210, 175, 0),
}

# ─────────────────────────────────────────────────────────────────────────────
# Player
# ─────────────────────────────────────────────────────────────────────────────
class Player:
    def __init__(self, name, coins=STARTING_COINS):
        self.name  = name
        self.coins = coins
        self.stats = {"games":0,"won":0,"lost":0,"biggest_win":0,"sessions":0}

    def win(self, amount):
        self.coins += amount
        self.stats["won"]   += amount
        self.stats["games"] += 1
        if amount > self.stats["biggest_win"]:
            self.stats["biggest_win"] = amount

    def lose(self, amount):
        self.coins -= amount
        self.stats["lost"]  += amount
        self.stats["games"] += 1

    def push(self):
        self.stats["games"] += 1

    def save(self):
        SAVE_FILE.write_text(json.dumps(
            {"name":self.name,"coins":self.coins,"stats":self.stats}, indent=2))

    @staticmethod
    def load():
        if SAVE_FILE.exists():
            try:
                d = json.loads(SAVE_FILE.read_text())
                p = Player(d["name"], d["coins"])
                p.stats = {**p.stats, **d.get("stats",{})}
                return p
            except: pass
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────────────────────
def txt(font, text, color=WHITE):
    return font.render(str(text), True, color)

def panel(surf, rect, bg=PANEL, border=GOLD, bw=2, r=10):
    pygame.draw.rect(surf, bg, rect, border_radius=r)
    if bw:
        pygame.draw.rect(surf, border, rect, bw, border_radius=r)

def top_bar(surf, title, player, back_btn):
    pygame.draw.rect(surf, PANEL, (0, 0, W, 70))
    pygame.draw.line(surf, GOLD, (0,70),(W,70), 2)
    back_btn.draw(surf)
    s = txt(F_LG, title, GOLD)
    surf.blit(s, s.get_rect(centerx=W//2, centery=35))
    b = txt(F_MDB, f"Balance:  {player.coins:,} c", GOLD)
    surf.blit(b, b.get_rect(right=W-20, centery=35))

def draw_card(surf, rank, suit, x, y, w=72, h=104, hidden=False):
    r = pygame.Rect(x, y, w, h)
    if hidden:
        pygame.draw.rect(surf, DKBLUE, r, border_radius=8)
        pygame.draw.rect(surf, BLUE,   r, 2, border_radius=8)
        for i in range(0, w, 10):
            pygame.draw.line(surf, (40,70,130),(x+i,y),(x+i,y+h),1)
        for j in range(0, h, 10):
            pygame.draw.line(surf, (40,70,130),(x,y+j),(x+w,y+j),1)
        pygame.draw.rect(surf, BLUE, r, 2, border_radius=8)
        return
    pygame.draw.rect(surf, CREAM, r, border_radius=8)
    pygame.draw.rect(surf, LGRAY, r, 1, border_radius=8)
    color = RED if suit in RED_S else BLACK
    sym   = SUIT_SYM[suit]
    rl = F_SMB.render(rank, True, color)
    sl = F_XS.render(sym,  True, color)
    surf.blit(rl, (x+4, y+3))
    surf.blit(sl, (x+4, y+3+rl.get_height()))
    cs = F_LG.render(sym, True, color)
    surf.blit(cs, cs.get_rect(centerx=x+w//2, centery=y+h//2))
    rr = F_SMB.render(rank, True, color)
    sr = F_XS.render(sym,  True, color)
    surf.blit(rr, (x+w-4-rr.get_width(), y+h-3-rr.get_height()-sr.get_height()))
    surf.blit(sr, (x+w-4-sr.get_width(), y+h-3-sr.get_height()))

def draw_die(surf, value, x, y, size=80):
    r = pygame.Rect(x, y, size, size)
    # 3D effect: bottom/right shadow face
    pygame.draw.rect(surf, (160,155,140), (x+size//10, y+size//10, size, size), border_radius=12)
    pygame.draw.rect(surf, CREAM, r, border_radius=12)
    pygame.draw.rect(surf, (100,95,85), r, 2, border_radius=12)
    for fx, fy in DICE_DOTS[value-1]:
        pygame.draw.circle(surf, (30,30,30),
            (int(x+fx*size)+1, int(y+fy*size)+1), max(6, size//12))
        pygame.draw.circle(surf, (40,40,40),
            (int(x+fx*size), int(y+fy*size)), max(6, size//12))

def draw_glow(surf, cx, cy, color, radii=None):
    if radii is None:
        radii = [(180,8),(120,16),(70,28),(35,45)]
    for r, a in radii:
        s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color, a), (r, r), r)
        surf.blit(s, (cx-r, cy-r))

def draw_felt_bg(surf):
    """Green casino felt table with wooden rail."""
    surf.fill((10, 36, 16))
    oval = pygame.Rect(36, 78, W-72, H-140)
    # Layered felt
    pygame.draw.ellipse(surf, (14, 48, 22), oval)
    pygame.draw.ellipse(surf, (17, 56, 27), oval.inflate(-30,-22))
    pygame.draw.ellipse(surf, (20, 64, 32), oval.inflate(-60,-44))
    # Wooden rail
    pygame.draw.ellipse(surf, (62, 40, 14), oval, 26)
    pygame.draw.ellipse(surf, (82, 54, 20), oval, 16)
    pygame.draw.ellipse(surf, (105, 70, 28), oval, 8)
    pygame.draw.ellipse(surf, (130, 88, 36), oval, 3)

def draw_chips(surf, cx, cy, amount):
    """Draw a casino chip stack for 'amount'."""
    if amount <= 0: return
    chip_defs = [(500,(160,50,200)),(100,(60,130,220)),(25,(200,50,50)),(5,(50,160,70)),(1,(200,200,200))]
    chips = []
    rem = amount
    for val, col in chip_defs:
        n = min(4, rem // val)
        chips.extend([col]*n)
        rem -= n*val
    if not chips: chips = [(200,200,200)]
    chips = chips[:8]
    for i, col in enumerate(reversed(chips)):
        iy = cy - i*5
        dark = (max(0,col[0]-50), max(0,col[1]-50), max(0,col[2]-50))
        light = (min(255,col[0]+60), min(255,col[1]+60), min(255,col[2]+60))
        pygame.draw.ellipse(surf, dark,  (cx-21, iy-2, 42, 14))
        pygame.draw.ellipse(surf, col,   (cx-20, iy-7, 40, 12))
        pygame.draw.ellipse(surf, light, (cx-20, iy-7, 40, 12), 2)
        pygame.draw.line(surf, light, (cx-14, iy-7), (cx+14, iy-7), 1)
    lbl = F_XS.render(f"{amount:,} c", True, CREAM)
    surf.blit(lbl, lbl.get_rect(centerx=cx, top=cy+8))

def draw_roulette_wheel(surf, cx, cy, r, angle=0.0):
    """Draw a full roulette wheel at given center+radius+rotation angle (radians)."""
    n   = len(WHEEL_NUMS)
    seg = 2 * math.pi / n
    # Outer wood rim
    pygame.draw.circle(surf, (48, 32, 12), (cx, cy), r+12)
    pygame.draw.circle(surf, (72, 50, 20), (cx, cy), r+8, 6)
    pygame.draw.circle(surf, (105,72, 28), (cx, cy), r+3, 3)
    # Number pockets
    for i, num in enumerate(WHEEL_NUMS):
        a1 = i * seg + angle - math.pi/2
        a2 = (i+1)*seg + angle - math.pi/2
        col = (18,115,38) if num==0 else (172,28,28) if num in RED_NUMS else (14,14,14)
        pts = [(cx, cy)]
        for s in range(8):
            a = a1 + (a2-a1)*s/7
            pts.append((int(cx+r*math.cos(a)), int(cy+r*math.sin(a))))
        pygame.draw.polygon(surf, col, pts)
        # Pocket divider at the start edge of this pocket
        pygame.draw.line(surf, (65,46,18),
            (int(cx + 0.46*r*math.cos(a1)), int(cy + 0.46*r*math.sin(a1))),
            (int(cx + r     *math.cos(a1)), int(cy + r     *math.sin(a1))), 1)
    # Clean outer edge
    pygame.draw.circle(surf, (90, 62, 24), (cx, cy), r, 3)
    # Inner felt
    ir = int(r * 0.44)
    pygame.draw.circle(surf, (16, 60, 28), (cx, cy), ir)
    pygame.draw.circle(surf, (22, 76, 36), (cx, cy), int(ir*0.84))
    # Spokes
    for s in range(8):
        sa = s * math.pi/4 + angle
        pygame.draw.line(surf, (52, 36, 14),
            (cx, cy),
            (int(cx+ir*math.cos(sa)), int(cy+ir*math.sin(sa))), 2)
    # Center hub
    pygame.draw.circle(surf, (45, 30, 10), (cx, cy), int(r*0.13))
    pygame.draw.circle(surf, GOLD3,         (cx, cy), int(r*0.075))
    pygame.draw.circle(surf, GOLD2,         (cx, cy), int(r*0.04))

def draw_roulette_ball(surf, cx, cy, r, angle):
    orbit = r - 16
    bx = int(cx + orbit * math.cos(angle))
    by = int(cy + orbit * math.sin(angle))
    pygame.draw.circle(surf, (30,30,30), (bx+2,by+2), 8)
    pygame.draw.circle(surf, (210,210,210), (bx,by), 8)
    pygame.draw.circle(surf, WHITE,          (bx,by), 6)
    pygame.draw.circle(surf, (180,180,180),  (bx-2,by-2), 3)

# ─────────────────────────────────────────────────────────────────────────────
# Card fly animation
# ─────────────────────────────────────────────────────────────────────────────
class CardFly:
    """Animates one card sliding from the deck (top-right) to its table spot."""
    SX, SY = W - 50, 126  # source: the on-screen deck pile (below top bar)
    DUR    = 0.28          # seconds for the flight

    def __init__(self, rank, suit, tx, ty, delay=0.0, hidden=False):
        self.rank, self.suit = rank, suit
        self.tx, self.ty = tx, ty
        self.delay  = delay
        self.hidden = hidden
        self.t      = 0.0
        self.done   = False
        self._hand  = 'p'  # 'p' or 'd', set by caller

    def update(self, dt):
        self.t += dt
        if self.t >= self.delay + self.DUR:
            self.done = True

    def _ease(self):
        if self.t < self.delay:
            return 0.0
        p = min(1.0, (self.t - self.delay) / self.DUR)
        return 1.0 - (1.0 - p) ** 3   # ease-out cubic

    def draw(self, surf, cw, ch):
        e = self._ease()
        if e <= 0.0 or self.done:
            return
        x = int(self.SX + (self.tx - self.SX) * e)
        # arc: card sails upward in the middle of its path
        p_raw = min(1.0, max(0.0, (self.t - self.delay) / self.DUR))
        arc   = math.sin(p_raw * math.pi) * -54
        y     = int(self.SY + (self.ty - self.SY) * e + arc)
        # slight scale-in: 68 % → 100 %
        sc  = 0.68 + 0.32 * e
        cw2 = max(4, int(cw * sc))
        ch2 = max(4, int(ch * sc))
        draw_card(surf, self.rank, self.suit,
                  x - (cw2 - cw) // 2,
                  y - (ch2 - ch) // 2,
                  cw2, ch2, self.hidden)

# ─────────────────────────────────────────────────────────────────────────────
# Button
# ─────────────────────────────────────────────────────────────────────────────
class Btn:
    def __init__(self, rect, label, bg=FELT, hover=GOLD2,
                 tc=WHITE, font=None, border=GOLD, bw=2, r=8):
        self.rect   = pygame.Rect(rect)
        self.label  = label
        self.bg     = bg
        self.hover  = hover
        self.tc     = tc
        self.font   = font or F_MDB
        self.border = border
        self.bw     = bw
        self.r      = r
        self.on     = True

    def draw(self, surf):
        mp  = pygame.mouse.get_pos()
        hot = self.rect.collidepoint(mp) and self.on
        bg  = self.hover if hot else (GRAY if not self.on else self.bg)
        pygame.draw.rect(surf, bg, self.rect, border_radius=self.r)
        if self.bw:
            bc = self.border if self.on else (60,60,60)
            pygame.draw.rect(surf, bc, self.rect, self.bw, border_radius=self.r)
        tc = self.tc if self.on else GRAY
        s  = self.font.render(self.label, True, tc)
        surf.blit(s, s.get_rect(center=self.rect.center))

    def clicked(self, event):
        if (self.on and event.type == pygame.MOUSEBUTTONDOWN
                and event.button == 1 and self.rect.collidepoint(event.pos)):
            SND.play("click")
            return True
        return False

# ─────────────────────────────────────────────────────────────────────────────
# Bet Selector
# ─────────────────────────────────────────────────────────────────────────────
class BetSelector:
    TOTAL_H = 120

    def __init__(self, cx, y, player, minimum=10):
        self.player  = player
        self.minimum = minimum
        self.bet     = minimum
        self.cx      = cx
        self.y       = y

        bw, bh, gap = 80, 34, 10
        total_w = 4*bw + 3*gap
        rx      = cx - total_w // 2
        row1y   = y + 44
        row2y   = row1y + bh + 8

        self._btns = [
            Btn((rx,               row1y, bw, bh), "-100", DKRED,  RED),
            Btn((rx+bw+gap,        row1y, bw, bh), " -10", DKRED,  RED),
            Btn((rx+2*(bw+gap),    row1y, bw, bh), "+10",  PANEL, WINC,
                tc=WINC, border=WINC),
            Btn((rx+3*(bw+gap),    row1y, bw, bh), "+100", PANEL, WINC,
                tc=WINC, border=WINC),
            Btn((cx-bw-gap//2,     row2y, bw, bh), "MIN",  PANELB, GOLD2,
                tc=GOLD, border=GOLD2),
            Btn((cx+gap//2,        row2y, bw, bh), "MAX",  PANELB, GOLD2,
                tc=GOLD, border=GOLD2),
        ]

    def draw(self, surf):
        label = txt(F_LG, f"BET:  {self.bet:,} c", GOLD)
        surf.blit(label, label.get_rect(centerx=self.cx, top=self.y))
        for b in self._btns:
            b.draw(surf)

    def handle(self, event):
        deltas = [-100, -10, 10, 100, None, None]
        for i, b in enumerate(self._btns):
            if b.clicked(event):
                if   i == 4: self.bet = self.minimum
                elif i == 5: self.bet = self.player.coins
                else:        self.bet += deltas[i]
                self.bet = max(self.minimum, min(self.player.coins, self.bet))

    @property
    def value(self): return self.bet

# ─────────────────────────────────────────────────────────────────────────────
# Floating message
# ─────────────────────────────────────────────────────────────────────────────
class Msg:
    def __init__(self):
        self.text  = ""
        self.color = WHITE
        self.timer = 0.0

    def show(self, text, color=WHITE, dur=2.2):
        self.text  = text
        self.color = color
        self.timer = dur

    def update(self, dt):
        if self.timer > 0:
            self.timer -= dt

    def draw(self, surf, cx=W//2, cy=H-60):
        if self.timer <= 0 or not self.text:
            return
        alpha = min(255, int(255 * min(self.timer, 0.4) / 0.4))
        s   = F_LG.render(self.text, True, self.color)
        tmp = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        tmp.fill((0,0,0,0))
        tmp.blit(s,(0,0))
        tmp.set_alpha(alpha)
        surf.blit(tmp, tmp.get_rect(centerx=cx, centery=cy))

# ─────────────────────────────────────────────────────────────────────────────
# Volume Slider
# ─────────────────────────────────────────────────────────────────────────────
class Slider:
    """Horizontal drag-slider; value is a float in [0.0, 1.0]."""
    TRACK_H = 18
    KNOB_R  = 14

    def __init__(self, cx, y, w, label, value=0.7):
        self.cx    = cx
        self.y     = y
        self.w     = w
        self.label = label
        self.value = max(0.0, min(1.0, float(value)))
        self._drag = False
        self._rx   = cx - w // 2      # left edge of track

    def _knob_x(self):
        return int(self._rx + self.value * self.w)

    def handle(self, event):
        kx = self._knob_x()
        ky = self.y + self.TRACK_H // 2
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit_knob  = math.hypot(event.pos[0] - kx, event.pos[1] - ky) <= self.KNOB_R + 8
            hit_track = pygame.Rect(self._rx, self.y, self.w, self.TRACK_H).collidepoint(event.pos)
            if hit_knob or hit_track:
                self._drag = True
                self._update(event.pos[0])
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._drag = False
        elif event.type == pygame.MOUSEMOTION and self._drag:
            self._update(event.pos[0])

    def _update(self, mx):
        self.value = max(0.0, min(1.0, (mx - self._rx) / self.w))

    def draw(self, surf):
        kx = self._knob_x()
        ky = self.y + self.TRACK_H // 2
        # Label + percentage
        pct = int(self.value * 100)
        lbl = F_MDB.render(f"{self.label}:  {pct} %", True, GOLD)
        surf.blit(lbl, lbl.get_rect(centerx=self.cx, bottom=self.y - 10))
        # Track background
        trect = pygame.Rect(self._rx, self.y, self.w, self.TRACK_H)
        pygame.draw.rect(surf, (28, 36, 46), trect, border_radius=9)
        pygame.draw.rect(surf, (55, 68, 82), trect, 1, border_radius=9)
        # Filled portion
        fw = kx - self._rx
        if fw > 0:
            pygame.draw.rect(surf, GOLD2,
                             pygame.Rect(self._rx, self.y, fw, self.TRACK_H),
                             border_radius=9)
        # Knob shadow
        shd = pygame.Surface((self.KNOB_R*2+6, self.KNOB_R*2+6), pygame.SRCALPHA)
        pygame.draw.circle(shd, (0,0,0,60), (self.KNOB_R+4, self.KNOB_R+5), self.KNOB_R+2)
        surf.blit(shd, (kx - self.KNOB_R - 2, ky - self.KNOB_R - 1))
        # Knob
        pygame.draw.circle(surf, GOLD3, (kx, ky), self.KNOB_R + 2)
        pygame.draw.circle(surf, GOLD,  (kx, ky), self.KNOB_R)
        pygame.draw.circle(surf, WHITE, (kx - 4, ky - 4), self.KNOB_R // 3)

# ─────────────────────────────────────────────────────────────────────────────
# Slot Reel
# ─────────────────────────────────────────────────────────────────────────────
SYM_H  = 88
REEL_W = 114
REEL_H = SYM_H * 3

class SlotReel:
    def __init__(self):
        self.symbols  = random.choices(S_NAMES, weights=S_WEIGHTS, k=30)
        self.offset   = 0.0
        self.speed    = 0.0
        self.spinning = False
        self.stopped  = True
        self.stop_ms  = 0
        self.target   = None

    def spin(self, target_sym, stop_ms):
        self.target   = target_sym
        self.speed    = 1800.0
        self.spinning = True
        self.stopped  = False
        self.stop_ms  = stop_ms
        self.symbols  = self.symbols + random.choices(S_NAMES, weights=S_WEIGHTS, k=60)
        self.offset   = 0.0

    def update(self, dt):
        if not self.spinning: return
        self.offset += self.speed * dt
        if pygame.time.get_ticks() >= self.stop_ms:
            ci = (int(self.offset / SYM_H) + 1) % len(self.symbols)
            self.symbols[ci] = self.target
            self.offset   = int(self.offset / SYM_H) * float(SYM_H)
            self.spinning = False
            self.stopped  = True

    def center_sym(self):
        return self.symbols[(int(self.offset / SYM_H) + 1) % len(self.symbols)]

    def draw(self, surf, x, y):
        rsurf = pygame.Surface((REEL_W, REEL_H))
        rsurf.fill((8,10,14))
        first = int(self.offset / SYM_H)
        frac  = int(self.offset % SYM_H)
        for row in range(4):
            idx = (first + row) % len(self.symbols)
            sym = self.symbols[idx]
            col = S_COLOR[sym]
            ry  = row * SYM_H - frac
            tile = pygame.Rect(4, ry+4, REEL_W-8, SYM_H-8)
            pygame.draw.rect(rsurf, col,   tile, border_radius=8)
            pygame.draw.rect(rsurf, BLACK, tile, 1, border_radius=8)
            # Shine
            shine_r = pygame.Rect(4, ry+4, REEL_W-8, 16)
            shine_s = pygame.Surface((REEL_W-8, 16), pygame.SRCALPHA)
            shine_s.fill((255,255,255,30))
            rsurf.blit(shine_s, (4, ry+4))
            lbl  = F_MDB.render(sym, True, BLACK)
            lx   = REEL_W//2 - lbl.get_width()//2
            ly   = ry + SYM_H//2 - lbl.get_height()//2
            rsurf.blit(lbl, (lx+1, ly+1))
            rsurf.blit(F_MDB.render(sym, True, WHITE), (lx, ly))
        surf.blit(rsurf, (x, y))
        pygame.draw.rect(surf, (40,44,54), (x, y, REEL_W, REEL_H), 3, border_radius=5)
        # Payline window highlight
        cy_win = y + SYM_H
        pygame.draw.rect(surf, GOLD, (x-6, cy_win-4, REEL_W+12, SYM_H+8), 3)

# ─────────────────────────────────────────────────────────────────────────────
# Name Input Screen
# ─────────────────────────────────────────────────────────────────────────────
class NameInputState:
    def __init__(self):
        self.text       = ""
        self.cursor_vis = True
        self.cursor_t   = 0.0
        self.err        = ""

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                name = self.text.strip()
                if not name:
                    self.err = "Please enter a name."
                    return None
                return ("new_player", name)
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif len(self.text) < 20 and event.unicode.isprintable():
                self.text += event.unicode
        return None

    def update(self, dt):
        self.cursor_t += dt
        if self.cursor_t >= 0.5:
            self.cursor_vis = not self.cursor_vis
            self.cursor_t   = 0.0

    def draw(self, surf):
        surf.fill(BG)
        draw_glow(surf, W//2, 0, (255,200,100), [(300,6),(180,12),(90,22)])
        t = F_TITLE.render("CASINO ROYALE", True, GOLD)
        surf.blit(t, t.get_rect(centerx=W//2, centery=210))
        sub = F_MD.render("Enter your name to begin", True, LGRAY)
        surf.blit(sub, sub.get_rect(centerx=W//2, centery=270))
        pygame.draw.line(surf, GOLD3, (W//2-300,300),(W//2+300,300), 1)
        prompt = F_MDB.render("Your Name:", True, WHITE)
        surf.blit(prompt, prompt.get_rect(centerx=W//2, centery=350))
        box = pygame.Rect(W//2-180, 375, 360, 52)
        pygame.draw.rect(surf, PANELB, box, border_radius=8)
        pygame.draw.rect(surf, GOLD,   box, 2, border_radius=8)
        disp   = self.text + ("|" if self.cursor_vis else " ")
        tinput = F_MDB.render(disp, True, WHITE)
        surf.blit(tinput, tinput.get_rect(centerx=W//2, centery=401))
        hint = F_SM.render("Press Enter to continue", True, GRAY)
        surf.blit(hint, hint.get_rect(centerx=W//2, centery=448))
        if self.err:
            surf.blit(F_SMB.render(self.err, True, LOSEC),
                      F_SMB.render(self.err, True, LOSEC).get_rect(centerx=W//2, centery=476))
        pygame.draw.line(surf, GOLD3, (W//2-300,500),(W//2+300,500), 1)

# ─────────────────────────────────────────────────────────────────────────────
# Lobby — casino floor with slot-machine cabinets
# ─────────────────────────────────────────────────────────────────────────────
GAME_LIST = [
    ("slots",     "SLOT MACHINE",  "Match 3 symbols"),
    ("blackjack", "BLACKJACK",     "Beat dealer to 21"),
    ("roulette",  "ROULETTE",      "Bet on the wheel"),
    ("dice",      "DICE DUEL",     "Predict the roll"),
    ("hilo",      "HI-LO",         "Higher or Lower?"),
    ("coinflip",  "COIN FLIP",     "Double or nothing"),
]

CAB_W, CAB_H  = 366, 220
CAB_COLS      = 3
CAB_ROWS      = 2
CAB_GAP_X     = 26
CAB_GAP_Y     = 28
CAB_START_X   = (W - (CAB_COLS*CAB_W + (CAB_COLS-1)*CAB_GAP_X)) // 2
CAB_START_Y   = 135


def _draw_cabinet_icon(surf, game_key, sx, sy, sw, sh):
    cx, cy = sx + sw//2, sy + sh//2

    if game_key == "slots":
        for i, c in enumerate([(220,50,50), GOLD, (220,50,50)]):
            s = F_LG.render("7", True, c)
            surf.blit(s, s.get_rect(centerx=cx+(i-1)*30, centery=cy))

    elif game_key == "blackjack":
        cw2, ch2 = 42, 60
        for di, (ox, oy, rk, su, clr) in enumerate([
                (-24, -5, "A", "S", BLACK), (6, 5, "K", "H", RED)]):
            rx2, ry2 = cx+ox, cy+oy
            pygame.draw.rect(surf, CREAM, (rx2,ry2,cw2,ch2), border_radius=5)
            pygame.draw.rect(surf, LGRAY, (rx2,ry2,cw2,ch2), 1, border_radius=5)
            surf.blit(F_SMB.render(rk, True, clr), (rx2+3, ry2+2))
            surf.blit(F_XS.render(SUIT_SYM[su], True, clr), (rx2+3, ry2+18))
            big = F_MD.render(SUIT_SYM[su], True, clr)
            surf.blit(big, big.get_rect(centerx=rx2+cw2//2, centery=ry2+ch2//2))

    elif game_key == "roulette":
        R = 38
        pygame.draw.circle(surf, (20,20,20), (cx,cy), R)
        for i in range(18):
            a1 = i*20 * math.pi/180
            a2 = (i*20+10) * math.pi/180
            points = [(cx,cy)]
            for a in [a1, (a1+a2)/2, a2]:
                points.append((cx+int(R*math.cos(a)), cy+int(R*math.sin(a))))
            pygame.draw.polygon(surf, ROULRED if i%2==0 else (30,30,30), points)
        pygame.draw.circle(surf, (25,25,25), (cx,cy), R, 2)
        pygame.draw.circle(surf, (50,50,50), (cx,cy), 14)
        pygame.draw.circle(surf, GOLD,       (cx,cy), 5)

    elif game_key == "dice":
        ds = 40
        for ox, oy, val in [(-26,-8,5),(10,-8,3)]:
            dx, dy = cx+ox, cy+oy
            pygame.draw.rect(surf, CREAM, (dx,dy,ds,ds), border_radius=7)
            pygame.draw.rect(surf, GRAY,  (dx,dy,ds,ds), 1, border_radius=7)
            for fx, fy in DICE_DOTS[val-1]:
                pygame.draw.circle(surf, BLACK, (int(dx+fx*ds),int(dy+fy*ds)), 4)

    elif game_key == "hilo":
        pygame.draw.polygon(surf, WINC,
            [(cx,cy-32),(cx-16,cy-14),(cx+16,cy-14)])
        pygame.draw.polygon(surf, LOSEC,
            [(cx,cy+32),(cx-16,cy+14),(cx+16,cy+14)])
        q = F_MDB.render("?", True, CREAM)
        surf.blit(q, q.get_rect(center=(cx, cy)))

    elif game_key == "coinflip":
        pygame.draw.circle(surf, GOLD2,  (cx,cy), 36)
        pygame.draw.circle(surf, GOLD3,  (cx,cy), 36, 3)
        pygame.draw.circle(surf, GOLD,   (cx,cy), 28)
        surf.blit(F_MDB.render("H", True, BLACK),
                  F_MDB.render("H", True, BLACK).get_rect(center=(cx,cy)))


def draw_cabinet(surf, x, y, game_key, game_name, game_desc, hovered):
    w, h  = CAB_W, CAB_H
    color = GAME_COLORS[game_key]
    tick  = pygame.time.get_ticks()
    shd = pygame.Surface((w+8, h+8), pygame.SRCALPHA)
    pygame.draw.rect(shd, (0,0,0,70), (0,0,w+8,h+8), border_radius=14)
    surf.blit(shd, (x+4, y+4))
    body_c = (44, 52, 62) if hovered else (32, 38, 46)
    pygame.draw.rect(surf, body_c, (x,y,w,h), border_radius=12)
    for sx2 in [x+10, x+w-16]:
        pygame.draw.rect(surf, (55,63,74), (sx2,y+50,6,h-70), border_radius=3)
    mh = 44
    pygame.draw.rect(surf, color, (x,y,w,mh),
                     border_top_left_radius=12, border_top_right_radius=12)
    shine = pygame.Surface((w, mh//2), pygame.SRCALPHA)
    shine.fill((255,255,255,25))
    surf.blit(shine, (x, y))
    tl = F_MDB.render(game_name, True, BLACK)
    surf.blit(tl, tl.get_rect(centerx=x+w//2, centery=y+mh//2))
    scr_x, scr_y = x+20, y+mh+10
    scr_w, scr_h = w-40, 108
    pygame.draw.rect(surf, (5,8,12),   (scr_x-4,scr_y-4,scr_w+8,scr_h+8), border_radius=8)
    pygame.draw.rect(surf, (12,16,22), (scr_x,scr_y,scr_w,scr_h),          border_radius=6)
    _draw_cabinet_icon(surf, game_key, scr_x, scr_y, scr_w, scr_h)
    led_y   = scr_y + scr_h + 10
    phase   = (tick // 350) % 2
    n_leds  = 10
    led_gap = (w - 40) // n_leds
    for i in range(n_leds):
        lx2  = x + 20 + i * led_gap + led_gap//2
        on   = (i + phase) % 2 == 0
        lc   = color if on else (color[0]//5, color[1]//5, color[2]//5)
        pygame.draw.circle(surf, lc, (lx2, led_y), 5)
    cs_x = x + w//2 - 14
    cs_y = y + h - 36
    pygame.draw.rect(surf, (18,22,28), (cs_x,cs_y,28,9), border_radius=4)
    pygame.draw.rect(surf, (50,56,66), (cs_x,cs_y,28,9), 1, border_radius=4)
    dl = F_XS.render(game_desc, True, LGRAY if not hovered else WHITE)
    surf.blit(dl, dl.get_rect(centerx=x+w//2, centery=y+h-16))
    border_c = GOLD if hovered else (color[0]//2, color[1]//2, color[2]//2)
    pygame.draw.rect(surf, border_c, (x,y,w,h), 3 if hovered else 2, border_radius=12)
    if hovered:
        glow = pygame.Surface((w,h), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*color, 18), (0,0,w,h), border_radius=12)
        surf.blit(glow, (x,y))


def draw_lobby_bg(surf):
    surf.fill((6,18,11))
    ts = 72
    for tx in range(0, W, ts):
        for ty in range(0, H, ts):
            if (tx//ts + ty//ts) % 2 == 0:
                pygame.draw.rect(surf, (8,22,13), (tx,ty,ts,ts))
    for tx in range(0, W, ts):
        pygame.draw.line(surf, (11,30,17), (tx,0),(tx,H), 1)
    for ty in range(0, H, ts):
        pygame.draw.line(surf, (11,30,17), (0,ty),(W,ty), 1)
    for lx in [W//4, W//2, 3*W//4]:
        draw_glow(surf, lx, 0, (255,220,140), [(260,7),(160,13),(80,22),(30,35)])


class LobbyState:
    def __init__(self, player):
        self.player     = player
        self._rects     = []
        for i, (key,_,_) in enumerate(GAME_LIST):
            col = i % CAB_COLS
            row = i // CAB_COLS
            x   = CAB_START_X + col*(CAB_W+CAB_GAP_X)
            y   = CAB_START_Y + row*(CAB_H+CAB_GAP_Y)
            self._rects.append((key, pygame.Rect(x,y,CAB_W,CAB_H)))
        bot = H - 46
        self.settings_btn = Btn((W//2-340, bot, 150, 38), "SETTINGS",
                                PANELB, GOLD2, tc=GOLD, border=GOLD2, font=F_SMB)
        self.stats_btn    = Btn((W//2-170, bot, 150, 38), "MY STATS",
                                PANELB, GOLD2, tc=GOLD, border=GOLD, font=F_SMB)
        self.quit_btn     = Btn((W//2+20,  bot, 150, 38), "EXIT",
                                DKRED,  RED,  tc=WHITE, border=RED,  font=F_SMB)

    def handle_event(self, event):
        if self.settings_btn.clicked(event): return "settings"
        if self.stats_btn.clicked(event):    return "stats"
        if self.quit_btn.clicked(event):     return "quit"
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for key, rect in self._rects:
                if rect.collidepoint(event.pos):
                    SND.play("click")
                    return key
        return None

    def update(self, dt): pass

    def draw(self, surf):
        draw_lobby_bg(surf)
        pygame.draw.rect(surf, (4,12,8), (0,0,W,126))
        pygame.draw.line(surf, GOLD, (0,126),(W,126), 2)
        t = F_TITLE.render("CASINO ROYALE", True, GOLD)
        surf.blit(t, t.get_rect(centerx=W//2, centery=48))
        bal = F_MDB.render(
            f"{self.player.name}   |   Balance:  {self.player.coins:,} c",
            True, CREAM)
        surf.blit(bal, bal.get_rect(centerx=W//2, centery=96))
        pygame.draw.rect(surf, (4,12,8), (0,H-56,W,56))
        pygame.draw.line(surf, GOLD3, (0,H-56),(W,H-56), 1)
        self.settings_btn.draw(surf)
        self.stats_btn.draw(surf)
        self.quit_btn.draw(surf)
        mouse = pygame.mouse.get_pos()
        for i, (key, name, desc) in enumerate(GAME_LIST):
            _, rect = self._rects[i]
            hovered = rect.collidepoint(mouse)
            draw_cabinet(surf, rect.x, rect.y, key, name, desc, hovered)

# ─────────────────────────────────────────────────────────────────────────────
# Slot Machine  — cabinet body + animated lever
# ─────────────────────────────────────────────────────────────────────────────
# Machine body geometry
_M_X, _M_Y, _M_W, _M_H = 78, 74, 1060, 612
_M_CX = _M_X + _M_W // 2   # = 608
# Lever geometry (outside machine, on the right)
_LEV_X      = 1198   # pole x
_LEV_ARM_Y  = 308    # where arm meets machine / pivot height
_LEV_UP_Y   = 188    # ball position when idle (handle up)
_LEV_DOWN_Y = 528    # ball position when pulled (handle down)
_LEV_R      = 24     # ball radius


class SlotsState:
    def __init__(self, player):
        self.player      = player
        self.reels       = [SlotReel() for _ in range(3)]
        self.msg         = Msg()
        self.bet_sel     = BetSelector(_M_CX, 428, player)
        self.back_btn    = Btn((20,18,90,36),"< Back",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_SM)
        self.state       = "idle"
        self.result      = []
        self._bet_placed = 0
        self._win_flash  = 0.0   # seconds of payline glow remaining
        # Lever animation
        self.lever_y     = 0.0   # 0=up, 1=down
        self.lever_anim  = "idle"
        self.lever_t     = 0.0

    # ── lever helpers ──────────────────────────────────────────────────────────
    def _lever_ball_pos(self):
        y = _LEV_UP_Y + self.lever_y * (_LEV_DOWN_Y - _LEV_UP_Y)
        return (_LEV_X, int(y))

    def _can_spin(self):
        return self.player.coins >= self.bet_sel.value and self.player.coins >= 10

    def _pull_and_spin(self):
        self.lever_anim = "pulling"
        self.lever_t    = 0.0
        SND.play("spin")
        self._do_spin()

    # ── handle ────────────────────────────────────────────────────────────────
    def handle_event(self, event):
        if self.back_btn.clicked(event):
            return "game_over" if self.player.coins <= 0 else "lobby"

        lever_clicked = False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            bx, by = self._lever_ball_pos()
            if math.hypot(event.pos[0]-bx, event.pos[1]-by) <= _LEV_R + 14:
                lever_clicked = True

        if self.state == "idle":
            self.bet_sel.handle(event)
            if lever_clicked and self._can_spin():
                self._pull_and_spin()
        elif self.state == "result":
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.player.coins <= 0:
                    return "game_over"
                self.state = "idle"
                if lever_clicked and self._can_spin():
                    self._pull_and_spin()
        return None

    def _do_spin(self):
        self._bet_placed = self.bet_sel.value
        self.result      = random.choices(S_NAMES, weights=S_WEIGHTS, k=3)
        now              = pygame.time.get_ticks()
        for i, reel in enumerate(self.reels):
            reel.spin(self.result[i], now+1500+i*600)
        self.state = "spinning"

    def update(self, dt):
        self.msg.update(dt)
        self._win_flash = max(0.0, self._win_flash - dt)
        for r in self.reels: r.update(dt)
        if self.state == "spinning" and all(r.stopped for r in self.reels):
            self._resolve()
        # Lever physics
        if self.lever_anim == "pulling":
            self.lever_t += dt
            self.lever_y  = min(1.0, self.lever_t / 0.22)
            if self.lever_y >= 1.0:
                self.lever_anim = "returning"
                self.lever_t    = 0.0
        elif self.lever_anim == "returning":
            self.lever_t += dt
            self.lever_y  = max(0.0, 1.0 - self.lever_t / 0.5)
            if self.lever_y <= 0.0:
                self.lever_anim = "idle"

    def _resolve(self):
        a, b, c = self.result
        bet     = self._bet_placed
        if a == b == c:
            gain = bet * S_PAY[a]
            self.player.win(gain)
            self.msg.show(f"JACKPOT!  {a} x3  +{gain:,} c", WINC, 3.5)
            SND.play("jackpot")
            self._win_flash = 2.5
        elif a == b or b == c or a == c:
            self.player.push()
            self.msg.show("Two matching — push!  Bet returned.", GOLD)
            SND.play("coin")
            self._win_flash = 1.0
        else:
            self.player.lose(bet)
            self.msg.show(f"No match  —  -{bet:,} c", LOSEC)
            SND.play("lose")
        if self.player.coins <= 0: self.player.coins = 0
        self.player.save()
        self.bet_sel.bet = max(10, min(self.bet_sel.bet, self.player.coins))
        self.state = "result"

    # ── draw helpers ──────────────────────────────────────────────────────────
    def _draw_machine_body(self, surf):
        mx, my, mw, mh = _M_X, _M_Y, _M_W, _M_H
        # Drop shadow
        shd = pygame.Surface((mw+12,mh+12), pygame.SRCALPHA)
        pygame.draw.rect(shd,(0,0,0,90),(0,0,mw+12,mh+12),border_radius=20)
        surf.blit(shd,(mx+6,my+6))
        # Outer shell
        pygame.draw.rect(surf,(36,42,52),(mx,my,mw,mh),border_radius=18)
        # Inner panel
        pygame.draw.rect(surf,(48,56,68),(mx+8,my+8,mw-16,mh-16),border_radius=14)
        # Side chrome rails
        for sx2 in [mx+18, mx+mw-24]:
            pygame.draw.rect(surf,(62,70,84),(sx2,my+70,8,mh-110),border_radius=4)
            pygame.draw.rect(surf,(90,100,115),(sx2+1,my+70,3,mh-110),border_radius=4)
        # Bottom plate
        bpy = my+mh-52
        pygame.draw.rect(surf,(28,34,42),(mx,bpy,mw,52),
                         border_bottom_left_radius=18,border_bottom_right_radius=18)
        pygame.draw.rect(surf,(44,52,64),(mx,bpy,mw,52),2,
                         border_bottom_left_radius=18,border_bottom_right_radius=18)
        # Coin slot on bottom plate
        csx,csy = mx+mw//2-22, bpy+20
        pygame.draw.rect(surf,(16,20,26),(csx,csy,44,10),border_radius=5)
        pygame.draw.rect(surf,(48,56,68),(csx,csy,44,10),1,border_radius=5)
        surf.blit(F_XS.render("INSERT COIN",True,(50,58,70)),
                  F_XS.render("INSERT COIN",True,(50,58,70)).get_rect(centerx=mx+mw//2,top=csy+12))
        # Outer border
        pygame.draw.rect(surf,GOLD3,(mx,my,mw,mh),2,border_radius=18)

    def _draw_marquee(self, surf):
        mx, my, mw = _M_X, _M_Y, _M_W
        mh_q = 62
        acc = GAME_COLORS["slots"]
        pygame.draw.rect(surf, acc, (mx,my,mw,mh_q),
                         border_top_left_radius=18,border_top_right_radius=18)
        # Shine
        sh = pygame.Surface((mw,28),pygame.SRCALPHA)
        sh.fill((255,255,255,30))
        surf.blit(sh,(mx,my))
        # Title
        tl = F_LG.render("SLOT  MACHINE", True, BLACK)
        surf.blit(tl, tl.get_rect(centerx=mx+mw//2, centery=my+mh_q//2))
        # LED strip along marquee bottom
        tick  = pygame.time.get_ticks()
        phase = (tick//220)%2
        n_led = 24
        lgap  = (mw-40)//n_led
        for i in range(n_led):
            lx2 = mx+20+i*lgap+lgap//2
            on  = (i+phase)%2==0
            lc  = GOLD if on else (GOLD3[0]//2,GOLD3[1]//2,GOLD3[2]//2)
            pygame.draw.circle(surf,lc,(lx2,my+mh_q-8),5)

    def _draw_reel_window(self, surf):
        rw_total = 3*REEL_W + 2*20
        rx = _M_CX - rw_total//2
        ry = 150
        bw2 = rw_total+40
        bh2 = REEL_H+40
        # Outer bezel
        pygame.draw.rect(surf,(22,26,34),(rx-20,ry-20,bw2,bh2),border_radius=14)
        pygame.draw.rect(surf,(40,46,58),(rx-20,ry-20,bw2,bh2),2,border_radius=14)
        # Inner dark recess
        pygame.draw.rect(surf,(6,8,12),(rx-14,ry-14,bw2-12,bh2-12),border_radius=10)
        # Reels
        for i, reel in enumerate(self.reels):
            reel.draw(surf, rx+i*(REEL_W+20), ry)
        # Glass overlay
        glass = pygame.Surface((bw2-12,bh2-12),pygame.SRCALPHA)
        pygame.draw.rect(glass,(180,220,255,8),(0,0,bw2-12,bh2-12),border_radius=10)
        surf.blit(glass,(rx-14,ry-14))
        # PAY label with arrows
        py_cy = ry + REEL_H//2
        surf.blit(F_XS.render("PAY",True,GOLD),(rx-46,py_cy-8))
        pygame.draw.polygon(surf,GOLD,[(rx-48,py_cy),(rx-38,py_cy-6),(rx-38,py_cy+6)])
        # Win-flash glow on payline
        if self._win_flash > 0:
            pulse = abs(math.sin(self._win_flash * 9))
            glow_s = pygame.Surface((bw2, SYM_H+16), pygame.SRCALPHA)
            ga = int(60 * pulse)
            pygame.draw.rect(glow_s, (255,215,0,ga),
                             (0,0,bw2,SYM_H+16), border_radius=8)
            surf.blit(glow_s, (rx-20, ry+SYM_H-8))
            # Bright border on payline frame
            bc = (int(180+75*pulse), int(150+65*pulse), 0)
            pygame.draw.rect(surf, bc, (rx-6, ry+SYM_H-4, bw2-8, SYM_H+8), 3)

    def _draw_paytable(self, surf):
        px, py = _M_X+22, 148
        pw, ph = 196, 400
        panel(surf,(px,py,pw,ph),PANELB,GOLD3,1,8)
        hdr = F_SMB.render("PAYTABLE",True,GOLD)
        surf.blit(hdr, hdr.get_rect(centerx=px+pw//2,top=py+8))
        pygame.draw.line(surf,GOLD3,(px+8,py+30),(px+pw-8,py+30),1)
        for i,(name,col,pay,_) in enumerate(SLOT_DEFS):
            y2 = py+40+i*50
            # Color swatch
            pygame.draw.rect(surf,col,(px+10,y2+2,18,18),border_radius=3)
            surf.blit(F_SM.render(name,True,col),(px+34,y2))
            surf.blit(F_XS.render(f"x3  =  {pay}x bet",True,LGRAY),(px+34,y2+17))

    def _draw_lever(self, surf):
        bx, by = self._lever_ball_pos()
        arm_x0 = _M_X + _M_W  # machine right edge
        arm_y  = _LEV_ARM_Y

        # Wall mount bracket
        pygame.draw.rect(surf,(50,58,70),(arm_x0-2,arm_y-22,52,44),border_radius=8)
        pygame.draw.rect(surf,(70,80,94),(arm_x0-2,arm_y-22,52,44),2,border_radius=8)
        pygame.draw.circle(surf,(60,70,84),(_LEV_X,arm_y),14)
        pygame.draw.circle(surf,(80,92,108),(_LEV_X,arm_y),14,2)

        # Pole shadow
        pygame.draw.line(surf,(20,20,24),(_LEV_X+3,arm_y+2),( _LEV_X+3,by+2),10)
        # Pole body
        pygame.draw.line(surf,(56,62,76),(_LEV_X,arm_y),(_LEV_X,by),12)
        # Pole highlight
        pygame.draw.line(surf,(120,128,148),(_LEV_X-2,arm_y),(_LEV_X-2,by),4)

        # Ball shadow
        shd = pygame.Surface((_LEV_R*2+8,_LEV_R*2+8),pygame.SRCALPHA)
        pygame.draw.circle(shd,(0,0,0,80),(_LEV_R+6,_LEV_R+6),_LEV_R+2)
        surf.blit(shd,(bx-_LEV_R-2,by-_LEV_R+4))

        # Ball: disabled when can't spin
        can = self._can_spin() and self.state in ("idle","result")
        bc  = RED if can else (80,80,80)
        bc2 = DKRED if can else (50,50,50)
        pygame.draw.circle(surf,bc2,(bx,by),_LEV_R)
        pygame.draw.circle(surf,bc, (bx,by),_LEV_R-3)
        # Shine
        if can:
            pygame.draw.circle(surf,(240,120,120),(bx-6,by-7),_LEV_R//3)
        pygame.draw.circle(surf,bc2,(bx,by),_LEV_R,2)

        # PULL hint
        if self.lever_anim == "idle" and self.state == "idle":
            pulse = abs(math.sin(pygame.time.get_ticks()*0.003))
            hc = (int(180+75*pulse),int(140+60*pulse),0)
            ht = F_XS.render("PULL", True, hc)
            surf.blit(ht, ht.get_rect(centerx=bx,top=by+_LEV_R+6))

    def draw(self, surf):
        surf.fill((8,20,12))
        # Subtle floor tile
        for tx in range(0,W,48):
            for ty in range(70,H,48):
                if (tx//48+ty//48)%2==0:
                    pygame.draw.rect(surf,(10,24,14),(tx,ty,48,48))
        top_bar(surf,"SLOT MACHINE",self.player,self.back_btn)
        self._draw_machine_body(surf)
        self._draw_marquee(surf)
        self._draw_paytable(surf)
        self._draw_reel_window(surf)
        self._draw_lever(surf)

        # BetSelector + state UI
        if self.state == "idle":
            self.bet_sel.draw(surf)
            hint = F_SM.render("Click the lever  ──▶  to spin!", True, GRAY)
            surf.blit(hint, hint.get_rect(centerx=_M_CX, top=562))
        elif self.state == "spinning":
            s = F_LG.render("Spinning...", True, GOLD)
            surf.blit(s, s.get_rect(centerx=_M_CX, centery=500))
        elif self.state == "result":
            self.bet_sel.draw(surf)
            s = F_SM.render("Pull lever or click to spin again", True, GRAY)
            surf.blit(s, s.get_rect(centerx=_M_CX, top=562))
        self.msg.draw(surf, cx=_M_CX, cy=600)

# ─────────────────────────────────────────────────────────────────────────────
# Blackjack  — green felt table
# ─────────────────────────────────────────────────────────────────────────────
def make_deck():
    d = [(r,s) for s in SUITS for r in RANKS]
    random.shuffle(d); return d

def card_val(r):
    if r in ("J","Q","K"): return 10
    if r == "A": return 11
    return int(r)

def hand_val(hand):
    v = sum(card_val(r) for r,_ in hand)
    a = sum(1 for r,_ in hand if r=="A")
    while v > 21 and a: v -= 10; a -= 1
    return v

class BlackjackState:
    CW, CH, GAP = 82, 118, 14

    def __init__(self, player):
        self.player    = player
        self.back_btn  = Btn((20,18,90,36),"< Back",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_SM)
        self.deal_btn  = Btn((W//2-65,610,130,46),"DEAL",GOLD3,GOLD,tc=BLACK,font=F_MDB)
        self.hit_btn   = Btn((W//2-220,610,120,46),"HIT", (14,70,30),WINC,tc=WINC,border=WINC,font=F_MDB)
        self.stand_btn = Btn((W//2-90, 610,120,46),"STAND",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_MDB)
        self.dbl_btn   = Btn((W//2+40, 610,140,46),"DOUBLE",DKRED,RED,tc=WHITE,border=RED,font=F_MDB)
        self.bet_sel   = BetSelector(W//2, 488, player)
        self.msg       = Msg()
        self.state     = "bet"
        self.ph=[]; self.dh=[]; self.deck=[]; self.bet=10
        # Card-fly animation
        self._flies   = []    # active CardFly objects
        self._land_p  = 0     # player cards visually on the table
        self._land_d  = 0     # dealer cards visually on the table
        self._anim_cb = None  # called when all flies have landed

    def handle_event(self, event):
        if self.back_btn.clicked(event):
            return "game_over" if self.player.coins <= 0 else "lobby"
        if self.state == "anim":
            return None          # block everything while cards are flying
        if self.state == "bet":
            self.bet_sel.handle(event)
            if self.deal_btn.clicked(event): self._deal()
        elif self.state == "player":
            if self.hit_btn.clicked(event):
                self.ph.append(self.deck.pop())
                self._land_p = len(self.ph) - 1
                self._queue_fly('p', len(self.ph) - 1)
                def _cb_hit():
                    if hand_val(self.ph) > 21: self._end("bust")
                    else: self.state = "player"
                self._anim_cb = _cb_hit
                self.state = "anim"
            elif self.stand_btn.clicked(event):
                self._dealer_play()
            elif self.dbl_btn.clicked(event) and self.dbl_btn.on:
                self.bet *= 2
                self.ph.append(self.deck.pop())
                self._land_p = len(self.ph) - 1
                self._queue_fly('p', len(self.ph) - 1)
                def _cb_dbl():
                    if hand_val(self.ph) > 21: self._end("bust")
                    else: self._dealer_play()
                self._anim_cb = _cb_dbl
                self.state = "anim"
        elif self.state == "result":
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.player.coins <= 0: return "game_over"
                self.state = "bet"
                self.bet_sel.bet = max(10, min(self.bet_sel.bet, self.player.coins))
        return None

    def _deal(self):
        self.bet  = self.bet_sel.value
        self.deck = make_deck()
        self.ph   = [self.deck.pop(), self.deck.pop()]
        self.dh   = [self.deck.pop(), self.deck.pop()]
        self._land_p = 0
        self._land_d = 0
        self._flies  = []
        p_bj = hand_val(self.ph) == 21
        d_bj = hand_val(self.dh) == 21
        # Animated staggered deal: player[0] → dealer[0] → player[1] → dealer[1]
        self._queue_fly('p', 0, delay=0.00)
        self._queue_fly('d', 0, delay=0.26)
        self._queue_fly('p', 1, delay=0.52)
        self._queue_fly('d', 1, delay=0.78, hidden=True)
        if p_bj or d_bj:
            def _cb(): self._end("bj_check", p_bj=p_bj, d_bj=d_bj)
        else:
            def _cb():
                self.state = "player"
                self.dbl_btn.on = self.player.coins >= self.bet
        self._anim_cb = _cb
        self.state = "anim"

    def _queue_fly(self, hand, idx, delay=0.0, hidden=False):
        """Enqueue a CardFly for self.ph[idx] or self.dh[idx]."""
        cx = W // 2
        if hand == 'p':
            n    = len(self.ph)
            ty   = 298 + 36
            r, s = self.ph[idx]
        else:
            n    = len(self.dh)
            ty   = 86 + 36
            r, s = self.dh[idx]
        x0 = cx - (n * (self.CW + self.GAP) - self.GAP) // 2
        tx = x0 + idx * (self.CW + self.GAP)
        f  = CardFly(r, s, tx, ty, delay=delay, hidden=hidden)
        f._hand = hand
        self._flies.append(f)

    def _dealer_play(self):
        while hand_val(self.dh) < 17: self.dh.append(self.deck.pop())
        self._end("compare")

    def _end(self, reason, p_bj=False, d_bj=False):
        pv=hand_val(self.ph); dv=hand_val(self.dh); bet=self.bet
        if reason == "bust":
            self.player.lose(bet); self.msg.show(f"Bust!  -{bet:,} c",LOSEC)
            SND.play("lose")
        elif reason == "bj_check":
            if p_bj and not d_bj:
                w=int(bet*1.5); self.player.win(w)
                self.msg.show(f"BLACKJACK!  +{w:,} c",WINC,3.0); SND.play("jackpot")
            elif d_bj and not p_bj:
                self.player.lose(bet); self.msg.show(f"Dealer Blackjack  -{bet:,} c",LOSEC)
                SND.play("lose")
            else:
                self.player.push(); self.msg.show("Both Blackjack — Push!",GOLD)
                SND.play("coin")
        elif reason == "compare":
            if dv>21:
                self.player.win(bet); self.msg.show(f"Dealer busts!  +{bet:,} c",WINC)
                SND.play("win")
            elif pv>dv:
                self.player.win(bet); self.msg.show(f"You win {pv} vs {dv}!  +{bet:,} c",WINC)
                SND.play("win")
            elif pv<dv:
                self.player.lose(bet); self.msg.show(f"Dealer wins {dv} vs {pv}  -{bet:,} c",LOSEC)
                SND.play("lose")
            else:
                self.player.push(); self.msg.show(f"Push — {pv} vs {dv}",GOLD)
                SND.play("coin")
        if self.player.coins<=0: self.player.coins=0
        self.player.save(); self.state="result"

    def update(self, dt):
        self.msg.update(dt)
        if not self._flies:
            return
        still = []
        for f in self._flies:
            was = f.done
            f.update(dt)
            if f.done and not was:
                SND.play("card")
                if f._hand == 'p':
                    self._land_p = min(len(self.ph), self._land_p + 1)
                else:
                    self._land_d = min(len(self.dh), self._land_d + 1)
            if not f.done:
                still.append(f)
        self._flies = still
        if not self._flies and self._anim_cb:
            cb, self._anim_cb = self._anim_cb, None
            cb()

    def _draw_hand(self, surf, hand, x0, y, hide_second=False):
        for i,(r,s) in enumerate(hand):
            draw_card(surf,r,s,x0+i*(self.CW+self.GAP),y,self.CW,self.CH,hidden=(i==1 and hide_second))

    def _draw_zone_label(self, surf, label, score_str, cx, y, score_col=LGRAY):
        bg = pygame.Rect(cx-90, y, 180, 28)
        pygame.draw.rect(surf, (0,0,0,100), bg, border_radius=6)
        pygame.draw.rect(surf, GOLD3, bg, 1, border_radius=6)
        lbl = F_SMB.render(label, True, CREAM)
        scr = F_SMB.render(score_str, True, score_col)
        surf.blit(lbl, (cx-86, y+4))
        surf.blit(scr, (cx+86-scr.get_width(), y+4))

    def draw(self, surf):
        draw_felt_bg(surf)
        top_bar(surf, "BLACKJACK", self.player, self.back_btn)

        is_anim = self.state == "anim"
        hiding  = self.state in ("player", "anim")
        cx      = W // 2
        dealer_y, player_y = 86, 298

        # How many cards to show (partial during animation, full otherwise)
        show_d = self._land_d if is_anim else len(self.dh)
        show_p = self._land_p if is_anim else len(self.ph)

        # ── Deck pile — bottom-right, below player cards ───────────────────
        # (cards fly from here; kept well away from top bar & balance)
        dk_x, dk_y = W - 88, 80   # just below the top bar on the right
        for di in range(2):
            rx2, ry2 = dk_x + di*3, dk_y + di*3
            pygame.draw.rect(surf, DKBLUE, (rx2, ry2, 62, 86), border_radius=7)
            for ii in range(0, 62, 10):          # cross-hatch lines
                pygame.draw.line(surf, (40,70,130), (rx2+ii, ry2), (rx2+ii, ry2+86), 1)
            pygame.draw.rect(surf, BLUE,   (rx2, ry2, 62, 86), 2, border_radius=7)
        surf.blit(F_XS.render("DECK", True, (80,120,200)),
                  F_XS.render("DECK", True, (80,120,200)).get_rect(centerx=dk_x+34, top=dk_y+90))

        # ── Dealer zone ────────────────────────────────────────────────────
        score_d = ""
        if self.dh:
            score_d = (f"({card_val(self.dh[0][0])} + ?)" if hiding
                       else f"({hand_val(self.dh)})")
        self._draw_zone_label(surf, "DEALER", score_d, cx, dealer_y)
        if show_d > 0:
            x0 = cx - (show_d*(self.CW+self.GAP)-self.GAP)//2
            for i in range(show_d):
                r, s = self.dh[i]
                draw_card(surf, r, s, x0+i*(self.CW+self.GAP),
                          dealer_y+36, self.CW, self.CH, hidden=(i==1 and hiding))

        # ── Rail ───────────────────────────────────────────────────────────
        pygame.draw.rect(surf,(110,72,28),(0,272,W,14))
        pygame.draw.rect(surf,(140,95,36),(0,272,W,14),1)

        # ── Player zone ────────────────────────────────────────────────────
        score_p = f"({hand_val(self.ph)})" if self.ph else ""
        sc_col  = (LOSEC if self.ph and hand_val(self.ph)>21
                   else WINC if self.ph and hand_val(self.ph)==21 else GOLD)
        self._draw_zone_label(surf, "YOU", score_p, cx, player_y, sc_col)
        if show_p > 0:
            x0 = cx - (show_p*(self.CW+self.GAP)-self.GAP)//2
            for i in range(show_p):
                r, s = self.ph[i]
                draw_card(surf, r, s, x0+i*(self.CW+self.GAP),
                          player_y+36, self.CW, self.CH)

        # ── Flying cards (always drawn on top) ─────────────────────────────
        for f in self._flies:
            f.draw(surf, self.CW, self.CH)

        # ── Chip display — left side, below player cards (y 452+) ─────────
        if self.state in ("player", "result", "anim") and self.bet > 0:
            chip_cx, chip_cy = 76, 550
            draw_chips(surf, chip_cx, chip_cy, self.bet)
            lbl_b = F_SMB.render("YOUR BET", True, GOLD2)
            surf.blit(lbl_b, lbl_b.get_rect(centerx=chip_cx, bottom=chip_cy - 30))
            amt_b = F_MDB.render(f"{self.bet:,} c", True, GOLD)
            surf.blit(amt_b, amt_b.get_rect(centerx=chip_cx, top=chip_cy + 12))

        # ── State UI ───────────────────────────────────────────────────────
        if self.state == "bet":
            self.bet_sel.draw(surf)
            self.deal_btn.on = self.player.coins >= 10
            self.deal_btn.draw(surf)
        elif self.state == "anim":
            pass   # no buttons — wait for cards to land
        elif self.state == "player":
            self.hit_btn.draw(surf)
            self.stand_btn.draw(surf)
            self.dbl_btn.draw(surf)
        elif self.state == "result":
            surf.blit(F_SM.render("Click anywhere to play again", True, GRAY),
                      F_SM.render("Click anywhere to play again", True, GRAY)
                      .get_rect(centerx=cx, centery=672))

        self.msg.draw(surf, cx=cx, cy=488)

# ─────────────────────────────────────────────────────────────────────────────
# Roulette  — left panel betting UI + right-side spinning wheel
# ─────────────────────────────────────────────────────────────────────────────
ROUL_BETS = [
    ("number","Number (35:1)",35),("red","Red (1:1)",1),
    ("black","Black (1:1)",1),("odd","Odd (1:1)",1),
    ("even","Even (1:1)",1),("low","Low 1-18 (1:1)",1),
    ("high","High 19-36 (1:1)",1),("dozen1","1st Dozen (2:1)",2),
    ("dozen2","2nd Dozen (2:1)",2),("dozen3","3rd Dozen (2:1)",2),
]
# Wheel constants
_WHL_CX, _WHL_CY, _WHL_R = 968, 382, 218


class RouletteState:
    def __init__(self, player):
        self.player    = player
        self.back_btn  = Btn((20,18,90,36),"< Back",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_SM)
        # Spin button in left panel
        self.spin_btn  = Btn((210, 606, 160, 44), "SPIN",
                             GOLD3, GOLD, tc=BLACK, font=F_MDB)
        # BetSelector left-panel-centred
        self.bet_sel   = BetSelector(300, 462, player)
        self.msg       = Msg()
        self.state     = "pick"
        self.sel_type  = None
        self.pick_num  = 0
        self.spin_anim     = 0.0
        self.result        = -1
        self.bet_locked    = 0        # bet amount frozen when SPIN is clicked
        # Wheel / ball angles
        self.wheel_angle   = 0.0
        self.ball_angle    = 0.0
        self.ball_vis      = False
        # Settling phase (ball eases into pocket after wheel stops)
        self.settle_t      = 0.0
        self.settle_start  = 0.0
        self.settle_target = 0.0

        self.type_btns = []
        for i,(key,label,pays) in enumerate(ROUL_BETS):
            col=i%2; row=i//2
            x=28+col*282; y=86+row*46
            self.type_btns.append((key,
                Btn((x,y,268,38),label,PANELB,GOLD2,tc=LGRAY,border=GOLD3,font=F_SM)))

        self.num_btns = []
        for n in range(37):
            nc=n%6; nr=n//6
            x=28+nc*54; y=388+nr*44
            self.num_btns.append(Btn((x,y,48,36),str(n),
                bg=ROULRED if n in RED_NUMS else (PANEL if n>0 else DARKGRN),
                hover=GOLD2,tc=WHITE,font=F_SMB,border=GOLD3))

    def handle_event(self, event):
        if self.back_btn.clicked(event):
            return "game_over" if self.player.coins <= 0 else "lobby"
        if self.state in ("pick","pick_num"):
            for key,btn in self.type_btns:
                if btn.clicked(event):
                    self.sel_type=key
                    self.state="pick_num" if key=="number" else "bet"
            if self.state=="pick_num":
                for n,btn in enumerate(self.num_btns):
                    if btn.clicked(event):
                        self.pick_num=n; self.state="bet"
        elif self.state=="bet":
            self.bet_sel.handle(event)
            if self.spin_btn.clicked(event):
                self.bet_locked = self.bet_sel.value   # lock bet NOW
                self.result     = random.randint(0,36)
                self.spin_anim  = 0.0
                self.ball_vis   = True
                self.state      = "spinning"
                SND.play("spin")
        elif self.state=="result":
            if event.type==pygame.MOUSEBUTTONDOWN:
                if self.player.coins<=0: return "game_over"
                self.state="pick"; self.sel_type=None; self.ball_vis=False
        return None

    def update(self, dt):
        self.msg.update(dt)
        if self.state == "spinning":
            self.spin_anim += dt
            # Wheel decelerates to nearly-stop over ~2 s
            wheel_spd = max(0.0, 12.0 * math.exp(-self.spin_anim * 2.1))
            # Ball slightly faster; also decelerates
            ball_spd  = max(0.0, 18.0 * math.exp(-self.spin_anim * 1.55))
            self.wheel_angle -= wheel_spd * dt
            self.ball_angle  += ball_spd  * dt
            if self.spin_anim >= 2.3:
                self._start_settling()

        elif self.state == "settling":
            self.settle_t += dt
            progress = min(1.0, self.settle_t / 1.1)
            # Ease-out cubic: fast start, smooth stop
            t = 1.0 - (1.0 - progress) ** 3
            self.ball_angle = self.settle_start + (self.settle_target - self.settle_start) * t
            if progress >= 1.0:
                self._resolve()

        elif self.state not in ("result",):
            # Idle slow drift while picking a bet
            self.wheel_angle -= 0.35 * dt

    def _start_settling(self):
        """Freeze the wheel and compute the target pocket angle for the ball."""
        self.state     = "settling"
        self.settle_t  = 0.0
        self.settle_start = self.ball_angle

        n_pockets = len(WHEEL_NUMS)
        seg = 2.0 * math.pi / n_pockets
        try:
            idx = WHEEL_NUMS.index(self.result)
        except ValueError:
            idx = 0

        # Centre of the result pocket in current screen coordinates.
        # wheel_angle is now frozen, so this position won't move.
        pocket_screen = idx * seg + self.wheel_angle - math.pi / 2 + seg * 0.5

        # Always travel *forward* (ball_angle increases).
        diff = (pocket_screen - self.settle_start) % (2.0 * math.pi)
        # If the pocket is already very close (< 90°) the ball just grazed it;
        # add one more full rotation so the deceleration looks natural.
        if diff < math.pi / 2:
            diff += 2.0 * math.pi

        self.settle_target = self.settle_start + diff

    def _resolve(self):
        """Called once the ball has physically settled into its pocket."""
        n = self.result; t = self.sel_type; bet = self.bet_locked
        won = False
        if   t=="number"  and n==self.pick_num:           won=True
        elif t=="red"     and n in RED_NUMS:               won=True
        elif t=="black"   and n not in RED_NUMS and n!=0:  won=True
        elif t=="odd"     and n!=0 and n%2==1:             won=True
        elif t=="even"    and n!=0 and n%2==0:             won=True
        elif t=="low"     and 1<=n<=18:                    won=True
        elif t=="high"    and 19<=n<=36:                   won=True
        elif t=="dozen1"  and 1<=n<=12:                    won=True
        elif t=="dozen2"  and 13<=n<=24:                   won=True
        elif t=="dozen3"  and 25<=n<=36:                   won=True
        pays = next(p for k,_,p in ROUL_BETS if k==t)
        if won:
            gain = bet * pays; self.player.win(gain)
            self.msg.show(f"WIN!  {n}  +{gain:,} c", WINC)
            SND.play("win")
        else:
            self.player.lose(bet)
            self.msg.show(f"LOSE  {n}  -{bet:,} c", LOSEC)
            SND.play("lose")
        # ball_angle is already correct — settling placed it in the pocket
        if self.player.coins <= 0: self.player.coins = 0
        self.player.save()
        self.state = "result"

    def draw(self, surf):
        draw_felt_bg(surf)
        top_bar(surf,"ROULETTE",self.player,self.back_btn)

        # ── Left panel: bet type buttons ──
        for key,btn in self.type_btns:
            btn.tc = GOLD  if key==self.sel_type else LGRAY
            btn.bg = (18,60,30) if key==self.sel_type else PANELB
            btn.draw(surf)

        if self.state in ("pick_num","bet") and self.sel_type=="number":
            panel(surf,(18,378,370,272),PANELB,GOLD3,1)
            for n,btn in enumerate(self.num_btns):
                btn.bw=2 if n==self.pick_num else 1
                btn.border=GOLD if n==self.pick_num else GOLD3
                btn.draw(surf)

        if self.state=="bet":
            if self.sel_type:
                info=next((l for k,l,_ in ROUL_BETS if k==self.sel_type),"")
                s=F_SMB.render(f"Bet on:  {info}",True,GOLD)
                surf.blit(s, s.get_rect(left=28,top=314))
                if self.sel_type=="number":
                    surf.blit(F_MDB.render(f"Number:  {self.pick_num}",True,CREAM),
                              (28,338))
            self.bet_sel.draw(surf)
            self.spin_btn.on=self.player.coins>=10
            self.spin_btn.draw(surf)

        # ── Right panel: roulette wheel ──
        cx,cy,r = _WHL_CX, _WHL_CY, _WHL_R
        draw_roulette_wheel(surf, cx, cy, r, self.wheel_angle)
        if self.ball_vis:
            draw_roulette_ball(surf, cx, cy, r, self.ball_angle)

        # Result or spinning overlay on wheel
        if self.state in ("spinning", "settling"):
            if self.state == "settling":
                pulse = abs(math.sin(self.settle_t * 10))
                lc = (int(200+55*pulse), int(170+45*pulse), 0)
                lbl = F_SMB.render("Landing...", True, lc)
                surf.blit(lbl, lbl.get_rect(centerx=cx, top=cy+r+18))
        elif self.state == "result":
            n  = self.result
            nc = ROULRED if n in RED_NUMS else (DARKGRN if n==0 else (20,20,20))
            tag= "RED" if n in RED_NUMS else ("ZERO" if n==0 else "BLACK")
            box = pygame.Rect(cx-80, cy+r+14, 160, 68)
            pygame.draw.rect(surf, nc, box, border_radius=10)
            pygame.draw.rect(surf, GOLD, box, 2, border_radius=10)
            surf.blit(F_HUGE.render(f"{n:02d}",True,WHITE),
                      F_HUGE.render(f"{n:02d}",True,WHITE).get_rect(centerx=cx,top=cy+r+14))
            surf.blit(F_SMB.render(tag,True,WHITE),
                      F_SMB.render(tag,True,WHITE).get_rect(centerx=cx,top=cy+r+82))
            surf.blit(F_SM.render("Click to spin again",True,GRAY),
                      F_SM.render("Click to spin again",True,GRAY).get_rect(centerx=cx,top=cy+r+102))
        else:
            # Show wheel label
            surf.blit(F_SM.render("Roulette Wheel",True,GRAY),
                      F_SM.render("Roulette Wheel",True,GRAY).get_rect(centerx=cx,top=cy+r+14))

        if self.state == "result":
            self.msg.draw(surf,cx=300,cy=680)
        else:
            self.msg.draw(surf,cx=300,cy=680)

# ─────────────────────────────────────────────────────────────────────────────
# Dice  — felt table with animated shaker cup
# ─────────────────────────────────────────────────────────────────────────────
DICE_BETS_DEF = [
    ("high","High sum (8-12)",1),("low","Low sum (2-6)",1),
    ("seven","Lucky 7",4),("doubles","Doubles",5),
    ("eleven","Eleven",6),("snake","Snake Eyes (1+1)",10),
]


class DiceState:
    def __init__(self, player):
        self.player   = player
        self.back_btn = Btn((20,18,90,36),"< Back",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_SM)
        self.roll_btn = Btn((W//2-70,612,140,46),"ROLL DICE",GOLD3,GOLD,tc=BLACK,font=F_MDB)
        self.bet_sel  = BetSelector(W//2, 470, player)
        self.msg      = Msg()
        self.state    = "pick"
        self.sel      = None
        self.d1=self.d2=1
        self.anim_t=0.0; self.anim_d1=1; self.anim_d2=1
        self.cup_tilt = 0.0  # 0=upright, 1=fully tipped

        self.bet_btns=[]
        for i,(key,label,pays) in enumerate(DICE_BETS_DEF):
            col=i%2; row=i//2
            x=W//2-300+col*308; y=86+row*68
            self.bet_btns.append((key,
                Btn((x,y,292,56),f"{label}   pays {pays}:1",
                    PANELB,GOLD2,tc=LGRAY,border=GOLD3,font=F_SM)))

    def handle_event(self, event):
        if self.back_btn.clicked(event):
            return "game_over" if self.player.coins <= 0 else "lobby"
        if self.state in ("pick","bet"):
            for key,btn in self.bet_btns:
                if btn.clicked(event):
                    self.sel=key; self.state="bet"
            if self.state=="bet":
                self.bet_sel.handle(event)
                if self.roll_btn.clicked(event):
                    self.d1=random.randint(1,6); self.d2=random.randint(1,6)
                    self.anim_t=0.0; self.cup_tilt=0.0; self.state="rolling"
                    SND.play("dice")
        elif self.state=="result":
            if event.type==pygame.MOUSEBUTTONDOWN:
                if self.player.coins<=0: return "game_over"
                self.state="pick"; self.sel=None
        return None

    def update(self, dt):
        self.msg.update(dt)
        if self.state=="rolling":
            self.anim_t+=dt
            self.anim_d1=random.randint(1,6); self.anim_d2=random.randint(1,6)
            # Cup tips over the first 0.6s, then dice roll out
            self.cup_tilt = min(1.0, self.anim_t/0.6)
            if self.anim_t>=1.6: self._resolve()

    def _resolve(self):
        d1,d2=self.d1,self.d2; total=d1+d2; bet=self.bet_sel.value; t=self.sel
        won=False
        if   t=="high"    and total>=8:          won=True
        elif t=="low"     and total<=6:           won=True
        elif t=="seven"   and total==7:           won=True
        elif t=="doubles" and d1==d2:             won=True
        elif t=="eleven"  and total==11:          won=True
        elif t=="snake"   and d1==1 and d2==1:    won=True
        pays=next(p for k,_,p in DICE_BETS_DEF if k==t)
        if won:
            gain=bet*pays; self.player.win(gain)
            self.msg.show(f"WIN!  {d1}+{d2}={total}  +{gain:,} c",WINC)
            SND.play("win")
        else:
            self.player.lose(bet)
            self.msg.show(f"LOSE  {d1}+{d2}={total}  -{bet:,} c",LOSEC)
            SND.play("lose")
        if self.player.coins<=0: self.player.coins=0
        self.player.save(); self.state="result"

    def _draw_cup(self, surf, cx, cy, tilt):
        """Draw a dice shaker cup that tips from upright to 90°."""
        angle = tilt * math.pi/2  # 0 to 90 degrees
        # Cup is a trapezoid: top narrower than bottom
        cw_top, cw_bot, ch = 52, 72, 90
        # Rotate around bottom-center pivot
        px, py = cx, cy  # pivot at bottom center of cup
        cos_a, sin_a = math.cos(angle), math.sin(angle)

        def rot(x, y):
            rx = px + (x-px)*cos_a - (y-py)*sin_a
            ry = py + (x-px)*sin_a + (y-py)*cos_a
            return (int(rx), int(ry))

        # Cup outline points (before rotation)
        tl = rot(cx-cw_top//2, cy-ch)
        tr = rot(cx+cw_top//2, cy-ch)
        br = rot(cx+cw_bot//2, cy)
        bl = rot(cx-cw_bot//2, cy)
        cup_pts = [tl, tr, br, bl]

        # Shadow
        shd_pts = [(p[0]+4, p[1]+4) for p in cup_pts]
        shd_s = pygame.Surface((W,H), pygame.SRCALPHA)
        pygame.draw.polygon(shd_s,(0,0,0,60),shd_pts)
        surf.blit(shd_s,(0,0))

        # Cup body
        pygame.draw.polygon(surf,(75,80,95),cup_pts)
        pygame.draw.polygon(surf,(95,102,120),cup_pts,3)
        # Top rim
        pygame.draw.line(surf,(130,138,158),tl,tr,5)
        # Bottom rim band
        pygame.draw.line(surf,(110,118,138),bl,br,4)
        # Handle nub
        handle_top = rot(cx+cw_bot//2+10, cy-12)
        handle_bot = rot(cx+cw_bot//2+10, cy+8)
        pygame.draw.line(surf,(110,115,135),br,handle_top,8)
        pygame.draw.line(surf,(110,115,135),br,handle_bot,8)

    def draw(self, surf):
        draw_felt_bg(surf)
        top_bar(surf,"DICE DUEL",self.player,self.back_btn)

        for key,btn in self.bet_btns:
            btn.tc=GOLD if key==self.sel else LGRAY
            btn.bg=(18,60,30) if key==self.sel else PANELB
            btn.draw(surf)

        # Cup and dice area
        cup_cx, cup_cy = W//2, 348
        dice_y = cup_cy - 40

        if self.state == "bet" and self.sel:
            # Show idle cup
            self._draw_cup(surf, cup_cx, cup_cy, 0.0)
            # Shake hint dots
            t_now = pygame.time.get_ticks()/1000
            for di in range(3):
                ox = int(math.sin(t_now*6+di*2)*4)
                oy = int(math.cos(t_now*6+di*2)*4)
                pygame.draw.circle(surf,GOLD,(cup_cx-20+di*20+ox,cup_cy-120+oy),4)

        elif self.state == "rolling":
            self._draw_cup(surf, cup_cx, cup_cy, self.cup_tilt)
            if self.cup_tilt > 0.5:
                # Dice spill out as cup tips
                shake = int(math.sin(self.anim_t*30)*5)
                draw_die(surf,self.anim_d1,W//2-130+shake,dice_y,92)
                draw_die(surf,self.anim_d2,W//2+38+shake, dice_y,92)

        elif self.state == "result":
            draw_die(surf,self.d1,W//2-130,dice_y,92)
            draw_die(surf,self.d2,W//2+38, dice_y,92)
            total=self.d1+self.d2
            surf.blit(F_LG.render(f"Sum:  {total}",True,GOLD),
                      F_LG.render(f"Sum:  {total}",True,GOLD).get_rect(centerx=W//2,top=dice_y+100))
            surf.blit(F_SM.render("Click to play again",True,GRAY),
                      F_SM.render("Click to play again",True,GRAY).get_rect(centerx=W//2,centery=672))

        if self.state == "bet":
            self.bet_sel.draw(surf)
            self.roll_btn.on=self.player.coins>=10
            self.roll_btn.draw(surf)
        elif self.state == "rolling":
            surf.blit(F_MDB.render("Shaking...",True,GOLD),
                      F_MDB.render("Shaking...",True,GOLD).get_rect(centerx=W//2,centery=460))
        self.msg.draw(surf,cx=W//2,cy=672)

# ─────────────────────────────────────────────────────────────────────────────
# Hi-Lo  — bold card display, big choice arrows
# ─────────────────────────────────────────────────────────────────────────────
class HiLoState:
    CW, CH = 110, 158

    def __init__(self, player):
        self.player   = player
        self.back_btn = Btn((20,18,90,36),"< Back",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_SM)
        self.hi_btn   = Btn((W//2-260,338,230,56),"▲  HIGHER",(14,70,30),WINC,tc=WINC,border=WINC,font=F_MDB)
        self.lo_btn   = Btn((W//2+30, 338,230,56),"▼  LOWER", DKRED,RED, tc=WHITE,border=RED, font=F_MDB)
        self.bet_sel  = BetSelector(W//2, 416, player)
        # DEAL sits below BetSelector (bottom of BetSelector = 416+120 = 536)
        self.deal_btn = Btn((W//2-65,548,130,42),"DEAL",GOLD3,GOLD,tc=BLACK,font=F_MDB)
        self.msg      = Msg()
        self.state    = "bet"
        self.c1=self.c2=None
        self.reveal_t = 0.0

    def handle_event(self, event):
        if self.back_btn.clicked(event):
            return "game_over" if self.player.coins <= 0 else "lobby"
        if self.state=="bet":
            self.bet_sel.handle(event)
            if self.deal_btn.clicked(event) and self.player.coins>=10:
                deck=[(r,s) for s in SUITS for r in RANKS]
                random.shuffle(deck)
                self.c1,self.c2=deck[0],deck[1]
                self.state="guess"
                SND.play("card")
        elif self.state=="guess":
            if self.hi_btn.clicked(event): self._resolve("h")
            if self.lo_btn.clicked(event): self._resolve("l")
        elif self.state=="result":
            if event.type==pygame.MOUSEBUTTONDOWN:
                if self.player.coins<=0: return "game_over"
                self.state="bet"
        return None

    def _resolve(self, guess):
        v1,v2=card_val(self.c1[0]),card_val(self.c2[0]); bet=self.bet_sel.value
        SND.play("card")
        if v1==v2:
            self.player.push(); self.msg.show("Equal — Push!  Bet returned.",GOLD)
            SND.play("coin")
        elif (guess=="h" and v2>v1) or (guess=="l" and v2<v1):
            self.player.win(bet); self.msg.show(f"Correct!  +{bet:,} c",WINC)
            SND.play("win")
        else:
            self.player.lose(bet); self.msg.show(f"Wrong!  -{bet:,} c",LOSEC)
            SND.play("lose")
        if self.player.coins<=0: self.player.coins=0
        self.player.save(); self.state="result"; self.reveal_t=0.0

    def update(self, dt):
        self.msg.update(dt)
        if self.state == "result":
            self.reveal_t = min(1.0, self.reveal_t + dt*3)

    def draw(self, surf):
        draw_felt_bg(surf)
        top_bar(surf,"HI-LO",self.player,self.back_btn)

        # Subtitle
        surf.blit(F_MDB.render("Is the next card Higher or Lower?",True,CREAM),
                  F_MDB.render("Is the next card Higher or Lower?",True,CREAM).get_rect(centerx=W//2,centery=108))

        # Cards area
        card_y = 152
        c1_cx  = W//2 - 160
        c2_cx  = W//2 + 50

        if self.state in ("guess","result") and self.c1:
            draw_card(surf,self.c1[0],self.c1[1],c1_cx,card_y,self.CW,self.CH)
            v1_lbl=F_MDB.render(f"Value: {card_val(self.c1[0])}",True,GOLD)
            surf.blit(v1_lbl,v1_lbl.get_rect(centerx=c1_cx+self.CW//2,top=card_y+self.CH+10))

            if self.state=="guess":
                # Hidden card
                draw_card(surf,"","",c2_cx,card_y,self.CW,self.CH,hidden=True)
                q=F_HUGE.render("?",True,GRAY)
                surf.blit(q,q.get_rect(center=(c2_cx+self.CW//2,card_y+self.CH//2)))
            else:
                # Revealed card (squish-in animation)
                squish = min(1.0, self.reveal_t)
                cw_anim = max(4, int(self.CW * squish))
                cx_off  = self.CW//2 - cw_anim//2
                draw_card(surf,self.c2[0],self.c2[1],c2_cx+cx_off,card_y,cw_anim,self.CH)
                if squish > 0.8:
                    v2_lbl=F_MDB.render(f"Value: {card_val(self.c2[0])}",True,GOLD)
                    surf.blit(v2_lbl,v2_lbl.get_rect(centerx=c2_cx+self.CW//2,top=card_y+self.CH+10))

            # Arrow between cards
            ax = W//2 - 12
            ay = card_y + self.CH//2
            pygame.draw.polygon(surf,GOLD,[(ax,ay-28),(ax+24,ay),(ax,ay+28)])
            pygame.draw.polygon(surf,GOLD2,[(ax,ay-28),(ax+24,ay),(ax,ay+28)],2)

        if self.state == "bet":
            self.bet_sel.draw(surf)
            self.deal_btn.on=self.player.coins>=10
            self.deal_btn.draw(surf)
        elif self.state == "guess":
            self.hi_btn.draw(surf)
            self.lo_btn.draw(surf)
            self.bet_sel.draw(surf)
        elif self.state == "result":
            surf.blit(F_SM.render("Click anywhere to play again",True,GRAY),
                      F_SM.render("Click anywhere to play again",True,GRAY).get_rect(centerx=W//2,top=670))

        self.msg.draw(surf,cx=W//2,cy=480)

# ─────────────────────────────────────────────────────────────────────────────
# Coin Flip  — pedestal + arc-trajectory coin
# ─────────────────────────────────────────────────────────────────────────────
class CoinFlipState:
    def __init__(self, player):
        self.player    = player
        self.back_btn  = Btn((20,18,90,36),"< Back",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_SM)
        self.heads_btn = Btn((W//2-240,490,220,60),"HEADS",GOLD3,GOLD,    tc=BLACK,border=GOLD, font=F_LG)
        self.tails_btn = Btn((W//2+20, 490,220,60),"TAILS",PANELB,GOLD2, tc=GOLD, border=GOLD, font=F_LG)
        self.bet_sel   = BetSelector(W//2, 568, player)
        self.msg       = Msg()
        self.state     = "pick"
        self.choice=self.result=None
        self.flip_t=0.0

    def handle_event(self, event):
        if self.back_btn.clicked(event):
            return "game_over" if self.player.coins <= 0 else "lobby"
        if self.state=="pick":
            self.bet_sel.handle(event)
            if self.heads_btn.clicked(event): self._flip("H")
            if self.tails_btn.clicked(event): self._flip("T")
        elif self.state=="result":
            if event.type==pygame.MOUSEBUTTONDOWN:
                if self.player.coins<=0: return "game_over"
                self.state="pick"; self.choice=None
        return None

    def _flip(self, choice):
        self.choice=choice; self.result=random.choice(["H","T"])
        self.flip_t=0.0; self.state="flipping"
        SND.play("flip")

    def update(self, dt):
        self.msg.update(dt)
        if self.state=="flipping":
            self.flip_t+=dt
            if self.flip_t>=1.8: self._resolve()

    def _resolve(self):
        bet=self.bet_sel.value
        if self.choice==self.result:
            self.player.win(bet); self.msg.show(f"{'Heads' if self.result=='H' else 'Tails'}!  Correct!  +{bet:,} c",WINC)
            SND.play("win")
        else:
            self.player.lose(bet); self.msg.show(f"{'Heads' if self.result=='H' else 'Tails'}!  Wrong.  -{bet:,} c",LOSEC)
            SND.play("lose")
        if self.player.coins<=0: self.player.coins=0
        self.player.save(); self.state="result"

    def _draw_pedestal(self, surf, cx, py):
        """Draw a multi-step stone pedestal centred at cx, top at py."""
        for i, (w2,h2,col) in enumerate([
                (100,12,(90,75,55)),(80,10,(110,92,68)),(60,14,(80,65,45))]):
            pygame.draw.rect(surf,col,(cx-w2//2,py+i*10,w2,h2),border_radius=4)
            pygame.draw.rect(surf,(min(255,col[0]+30),min(255,col[1]+24),min(255,col[2]+18)),
                             (cx-w2//2,py+i*10,w2,h2),2,border_radius=4)

    def _draw_coin(self, surf, cx, cy, phase, face):
        """Draw a 3D-looking gold coin. phase 0-1 controls flip squish."""
        squish = abs(math.cos(phase * math.pi * 5))
        if self.state == "result":
            squish = 1.0
        cw = max(6, int(130*squish)); ch = 130

        col_face = GOLD if face=="H" else GOLD2
        col_edge = GOLD3
        col_rim  = (min(255,GOLD[0]+20),min(255,GOLD[1]+20),min(255,GOLD[2]+20))

        # Shadow
        shd = pygame.Surface((cw+20,ch+20),pygame.SRCALPHA)
        pygame.draw.ellipse(shd,(0,0,0,60),(10,16,cw,ch))
        surf.blit(shd,(cx-cw//2-6,cy-ch//2+8))

        # Coin body
        r2 = pygame.Rect(cx-cw//2,cy-ch//2,cw,ch)
        pygame.draw.ellipse(surf,col_face,r2)
        # Metallic ring
        pygame.draw.ellipse(surf,col_rim,r2,4)
        # Inner ring
        if cw>40:
            ir2 = r2.inflate(-20,-20)
            pygame.draw.ellipse(surf,col_edge,ir2,2)
        # Face letter
        if cw>50:
            lbl=F_HUGE.render(face,True,col_edge)
            surf.blit(lbl,lbl.get_rect(center=(cx,cy)))
        # Shine
        if cw>30:
            sh_r=pygame.Rect(cx-cw//4,cy-ch//3,cw//3,ch//5)
            sh_s=pygame.Surface((sh_r.w,sh_r.h),pygame.SRCALPHA)
            pygame.draw.ellipse(sh_s,(255,255,255,55),(0,0,sh_r.w,sh_r.h))
            surf.blit(sh_s,(sh_r.x,sh_r.y))

    def draw(self, surf):
        draw_felt_bg(surf)
        top_bar(surf,"COIN FLIP",self.player,self.back_btn)
        surf.blit(F_MDB.render("Heads or Tails?  Guess right to double your bet.",True,CREAM),
                  F_MDB.render("Heads or Tails?  Guess right to double your bet.",True,CREAM).get_rect(centerx=W//2,centery=108))

        # Coin position: arc trajectory during flip
        coin_base_y = 350
        pedestal_y  = coin_base_y + 66   # top of pedestal

        if self.state in ("flipping","result"):
            phase = min(1.0, self.flip_t/1.8)
            # Arc: coin goes up then comes back down
            arc_h    = 180 * math.sin(phase * math.pi)
            coin_cy  = coin_base_y - int(arc_h)
            face     = self.result if self.state=="result" else ("H" if int(phase*5)%2==0 else "T")
            self._draw_pedestal(surf, W//2, pedestal_y)
            self._draw_coin(surf, W//2, coin_cy, phase, face)
        else:
            # Idle: coin sitting on pedestal, slow wobble
            wobble = math.sin(pygame.time.get_ticks()*0.002)*3
            self._draw_pedestal(surf, W//2, pedestal_y)
            self._draw_coin(surf, W//2, int(coin_base_y+wobble), 0.0, "H")

        if self.state=="pick":
            self.heads_btn.draw(surf); self.tails_btn.draw(surf)
            self.bet_sel.draw(surf)
        elif self.state=="flipping":
            ch_name = "Heads" if self.choice=="H" else "Tails"
            surf.blit(F_MDB.render(f"You called:  {ch_name}  |  Flipping...",True,GOLD),
                      F_MDB.render(f"You called:  {ch_name}  |  Flipping...",True,GOLD).get_rect(centerx=W//2,centery=458))
        elif self.state=="result":
            res=("Heads" if self.result=="H" else "Tails")
            ch2=("Heads" if self.choice=="H" else "Tails")
            surf.blit(F_MDB.render(f"Result: {res}   |  You called: {ch2}",True,CREAM),
                      F_MDB.render(f"Result: {res}   |  You called: {ch2}",True,CREAM).get_rect(centerx=W//2,centery=458))
            surf.blit(F_SM.render("Click anywhere to flip again",True,GRAY),
                      F_SM.render("Click anywhere to flip again",True,GRAY).get_rect(centerx=W//2,centery=484))
        self.msg.draw(surf,cx=W//2,cy=672)

# ─────────────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────────────
class StatsState:
    def __init__(self, player):
        self.player   = player
        self.back_btn = Btn((20,18,90,36),"< Back",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_SM)

    def handle_event(self, event):
        if self.back_btn.clicked(event): return "lobby"
        return None

    def update(self, dt): pass

    def draw(self, surf):
        draw_felt_bg(surf)
        top_bar(surf,"PLAYER STATS",self.player,self.back_btn)
        p=self.player; net=p.stats["won"]-p.stats["lost"]; nc=WINC if net>=0 else LOSEC
        rows=[
            ("Player Name",   p.name,                       WHITE),
            ("Balance",       f"{p.coins:,} c",             GOLD),
            ("Sessions",      str(p.stats["sessions"]),     LGRAY),
            ("Games Played",  str(p.stats["games"]),        LGRAY),
            ("Total Won",     f"+{p.stats['won']:,} c",     WINC),
            ("Total Lost",    f"-{p.stats['lost']:,} c",    LOSEC),
            ("Net P&L",       f"{net:+,} c",                nc),
            ("Biggest Win",   f"{p.stats['biggest_win']:,} c",GOLD),
        ]
        bx,by,bw,bh=W//2-260,108,520,54
        panel(surf,(bx-10,by-10,bw+20,len(rows)*bh+20),PANELB,GOLD,2,12)
        for i,(label,value,vc) in enumerate(rows):
            y2=by+i*bh
            if i%2==0: pygame.draw.rect(surf,(12,30,18),(bx,y2,bw,bh))
            surf.blit(F_MDB.render(label,True,GRAY),(bx+12,y2+bh//2-11))
            vl=F_MDB.render(value,True,vc)
            surf.blit(vl,(bx+bw-vl.get_width()-12,y2+bh//2-11))

# ─────────────────────────────────────────────────────────────────────────────
# Settings  — volume sliders
# ─────────────────────────────────────────────────────────────────────────────
class SettingsState:
    def __init__(self, player):
        self.player   = player
        self.back_btn = Btn((20,18,90,36),"< Back",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_SM)
        self.test_btn = Btn((W//2-75, 540, 150, 46), "► TEST SOUND",
                            GOLD3, GOLD, tc=BLACK, font=F_MDB)
        mid = W // 2
        # Initialise sliders from current SND values
        self.master_sl = Slider(mid, 290, 560, "Master Volume", SND.master)
        self.sfx_sl    = Slider(mid, 420, 560, "SFX Volume",    SND.sfx)

    def handle_event(self, event):
        self.master_sl.handle(event)
        self.sfx_sl.handle(event)
        # Live update while dragging
        SND.master = self.master_sl.value
        SND.sfx    = self.sfx_sl.value
        if self.test_btn.clicked(event):
            SND.play("win")
        if self.back_btn.clicked(event):
            SND.save()
            return "lobby"
        return None

    def update(self, dt): pass

    def draw(self, surf):
        draw_felt_bg(surf)
        top_bar(surf, "SETTINGS", self.player, self.back_btn)

        t = F_TITLE.render("Volume Settings", True, GOLD)
        surf.blit(t, t.get_rect(centerx=W//2, centery=162))
        pygame.draw.line(surf, GOLD3, (W//2-340,204),(W//2+340,204), 1)

        self.master_sl.draw(surf)
        self.sfx_sl.draw(surf)

        # Effective-volume preview bar
        eff = max(0.0, min(1.0, SND.master * SND.sfx))
        bar_x, bar_y, bar_w, bar_h = W//2-260, 498, 520, 14
        pygame.draw.rect(surf,(28,36,46),(bar_x,bar_y,bar_w,bar_h),border_radius=7)
        if eff > 0:
            fc = (int(220*(1-eff)+30*eff), int(60+160*eff), 40)
            pygame.draw.rect(surf, fc,
                             (bar_x, bar_y, int(eff*bar_w), bar_h), border_radius=7)
        pygame.draw.rect(surf,GOLD3,(bar_x,bar_y,bar_w,bar_h),1,border_radius=7)
        lbl = F_SMB.render(f"Effective volume:  {int(eff*100)} %", True, LGRAY)
        surf.blit(lbl, lbl.get_rect(centerx=W//2, top=bar_y+18))

        self.test_btn.draw(surf)

        hint = F_SM.render("Drag the sliders, then press  < Back  to save.", True, GRAY)
        surf.blit(hint, hint.get_rect(centerx=W//2, centery=630))

# ─────────────────────────────────────────────────────────────────────────────
# Game Over
# ─────────────────────────────────────────────────────────────────────────────
class GameOverState:
    def __init__(self, player):
        self.player  = player
        self.anim_t  = 0.0
        cx=W//2
        self.again_btn=Btn((cx-180,560,160,52),"PLAY AGAIN",GOLD3,GOLD,tc=BLACK,font=F_MDB)
        self.quit_btn =Btn((cx+20, 560,160,52),"EXIT",      DKRED,RED, tc=WHITE, font=F_MDB)

    def handle_event(self, event):
        if self.again_btn.clicked(event): return "restart"
        if self.quit_btn.clicked(event):  return "quit"
        return None

    def update(self, dt): self.anim_t+=dt

    def draw(self, surf):
        surf.fill(BG)
        ov=pygame.Surface((W,H),pygame.SRCALPHA)
        ov.fill((80,0,0,85)); surf.blit(ov,(0,0))
        pulse=abs(math.sin(self.anim_t*2.2))
        gc=(int(180+70*pulse),20,20)
        t1=F_TITLE.render("GAME  OVER",True,gc)
        surf.blit(t1,t1.get_rect(centerx=W//2,centery=165))
        t2=F_LG.render(f"You went broke, {self.player.name}.",True,LGRAY)
        surf.blit(t2,t2.get_rect(centerx=W//2,centery=242))
        p=self.player; net=p.stats["won"]-p.stats["lost"]; nc=WINC if net>=0 else LOSEC
        rows=[("Games Played",str(p.stats["games"]),LGRAY),
              ("Total Won",   f"+{p.stats['won']:,} c",WINC),
              ("Total Lost",  f"-{p.stats['lost']:,} c",LOSEC),
              ("Net P&L",     f"{net:+,} c",nc),
              ("Biggest Win", f"{p.stats['biggest_win']:,} c",GOLD)]
        bx,by,bw,bh=W//2-240,295,480,46
        panel(surf,(bx-8,by-8,bw+16,len(rows)*bh+16),PANELB,GOLD3,2,10)
        for i,(label,value,vc) in enumerate(rows):
            y2=by+i*bh
            if i%2==0: pygame.draw.rect(surf,(12,28,16),(bx,y2,bw,bh))
            surf.blit(F_MDB.render(label,True,GRAY),(bx+12,y2+bh//2-11))
            vl=F_MDB.render(value,True,vc)
            surf.blit(vl,(bx+bw-vl.get_width()-12,y2+bh//2-11))
        self.again_btn.draw(surf); self.quit_btn.draw(surf)
        surf.blit(F_SM.render("Start over with 1,000 fresh coins, or exit.",True,GRAY),
                  F_SM.render("Start over with 1,000 fresh coins, or exit.",True,GRAY).get_rect(centerx=W//2,centery=632))

# ─────────────────────────────────────────────────────────────────────────────
# Global sound manager  (created once; used everywhere via SND.play())
# ─────────────────────────────────────────────────────────────────────────────
SND = SoundManager()

# ─────────────────────────────────────────────────────────────────────────────
# State factory
# ─────────────────────────────────────────────────────────────────────────────
def make_state(name, player):
    return {
        "lobby":     lambda: LobbyState(player),
        "slots":     lambda: SlotsState(player),
        "blackjack": lambda: BlackjackState(player),
        "roulette":  lambda: RouletteState(player),
        "dice":      lambda: DiceState(player),
        "hilo":      lambda: HiLoState(player),
        "coinflip":  lambda: CoinFlipState(player),
        "stats":     lambda: StatsState(player),
        "settings":  lambda: SettingsState(player),
        "game_over": lambda: GameOverState(player),
    }[name]()

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def run_name_input():
    ni=NameInputState(); player=None
    while player is None:
        dt=clock.tick(FPS)/1000.0
        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                pygame.quit(); sys.exit()
            result=ni.handle_event(event)
            if result:
                _,name=result
                player=Player(name)
                player.stats["sessions"]=1
                player.save()
        ni.update(dt)
        screen.fill(BG); ni.draw(screen); pygame.display.flip()
    return player


def main():
    saved=Player.load()
    if saved is None:
        player=run_name_input()
    else:
        player=saved
        player.stats["sessions"]=player.stats.get("sessions",0)+1
        player.save()

    state=make_state("game_over" if player.coins<=0 else "lobby",player)

    while True:
        dt=clock.tick(FPS)/1000.0
        for event in pygame.event.get():
            if event.type==pygame.QUIT:
                player.save(); pygame.quit(); sys.exit()
            result=state.handle_event(event)
            if result=="quit":
                player.save(); pygame.quit(); sys.exit()
            elif result=="restart":
                if SAVE_FILE.exists(): SAVE_FILE.unlink()
                player=run_name_input()
                state=make_state("lobby",player)
            elif result=="lobby" and player.coins<=0:
                state=make_state("game_over",player)
            elif result is not None:
                state=make_state(result,player)

        state.update(dt)
        screen.fill(BG); state.draw(screen); pygame.display.flip()


if __name__=="__main__":
    main()
