#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Casino Royale — Pygame Edition"""

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
BG      = (12,  18,  30)
FELT    = (22,  36,  54)
PANEL   = (18,  26,  38)
PANELB  = (28,  38,  54)
GOLD    = (88,  204, 255)
GOLD2   = (64,  140, 215)
GOLD3   = (45,   95, 155)
WHITE   = (238, 243, 248)
CREAM   = (220, 230, 240)
RED     = (240, 110, 110)
DKRED   = (170,  55,  55)
BLACK   = (18,  24,  34)
GRAY    = (120, 135, 150)
LGRAY   = (175, 190, 205)
WINC    = (70, 220, 145)
LOSEC   = (230,  90,  90)
BLUE    = (75, 145, 255)
DKBLUE  = (40,  65, 125)
ROULRED = (220,  90,  90)
DARKGRN = (15,  95,  60)

# ── Fonts ─────────────────────────────────────────────────────────────────────
_f      = "arial"
F_TITLE = pygame.font.SysFont(_f, 64, bold=True)
F_LG    = pygame.font.SysFont(_f, 36, bold=True)
F_MDB   = pygame.font.SysFont(_f, 22, bold=True)
F_MD    = pygame.font.SysFont(_f, 18)
F_SM    = pygame.font.SysFont(_f, 16)
F_SMB   = pygame.font.SysFont(_f, 16, bold=True)
F_XS    = pygame.font.SysFont(_f, 13)
F_HUGE  = pygame.font.SysFont(_f, 76, bold=True)

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
        self.card_back = 0
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

        # Button click
        self._snds["click"] = _make_snd(
            lambda t, p: s(650, t) * math.exp(-t * 70) * 0.65, 0.06)

        # Coin clink — metallic harmonics
        self._snds["coin"] = _make_snd(
            lambda t, p: (s(1100,t)*0.5 + s(1650,t)*0.3 + s(550,t)*0.2)
                         * math.exp(-t * 14), 0.22)

        # Card swish — noise burst + tonal sweep
        self._snds["card"] = _make_snd(
            lambda t, p: (
                random.uniform(-1,1) * math.exp(-t*20) * 0.65
                + s(900-700*p, t) * math.exp(-t*28) * 0.30
            ) * 0.90, 0.12)

        # Dice — sharp crack + decelerating tumble
        self._snds["dice"] = _make_snd(
            lambda t, p: (
                random.uniform(-1,1) * abs(math.sin(t*(26-14*p))) * (1-p*0.55) * 0.75
                + s(180, t) * math.exp(-t*38) * 0.45
            ), 0.48)

        # Coin-flip — metallic ring harmonics + light whoosh
        self._snds["flip"] = _make_snd(
            lambda t, p: (
                s(1300,t)*math.exp(-t*2.2)*0.42
                + s(2600,t)*math.exp(-t*3.5)*0.22
                + s(3900,t)*math.exp(-t*5.0)*0.12
                + random.uniform(-1,1)*math.sin(math.pi*p)*0.18
            ) * 0.88, 1.1)

        # Roulette spin — rattling whir that decelerates
        self._snds["spin"] = _make_snd(
            lambda t, p: (
                random.uniform(-1,1) * abs(math.sin(p2*9*(1-p)**0.6*t)) * 0.68
                + s(120+380*(1-p)**1.2, t) * (1-p) * 0.28
            ) * (0.85 - p*0.35), 1.9)

        # Reel stop — mechanical thud/snap
        self._snds["reel_stop"] = _make_snd(
            lambda t, p: (
                s(110,t)*math.exp(-t*28)*0.55
                + random.uniform(-1,1)*math.exp(-t*32)*0.38
            ), 0.13)

        # Reel tick — quick click as symbols scroll past
        self._snds["tick"] = _make_snd(
            lambda t, p: (
                s(1400,t)*math.exp(-t*90)*0.40
                + random.uniform(-1,1)*math.exp(-t*100)*0.20
            ) * 0.55, 0.035)

        # Small win — C E G C5 arpeggio with chord finish
        _wn = [261.63, 329.63, 392.0, 523.25]
        def _win(t, p):
            i = min(3, int(p*4)); lp = p*4-i
            base = (s(_wn[i],t) + s(_wn[i]*2,t)*0.18) * math.sin(math.pi*lp) * 0.65
            if i == 3:
                base += (s(329.63,t)*0.12 + s(392.0,t)*0.10) * math.exp(-lp*2.5) * 0.5
            return base
        self._snds["win"] = _make_snd(_win, 0.90)

        # Jackpot — fast fanfare + triumphant chord finale
        _jp = [261.63, 329.63, 392.0, 523.25, 659.25, 783.99]
        def _jackpot(t, p):
            i = min(5, int(p*6)); lp = p*6-i
            base = (s(_jp[i],t)*0.62 + s(_jp[i]*2,t)*0.22) * math.sin(math.pi*lp)
            if p > 0.70:
                extra = (p-0.70)/0.30
                base += (s(523.25,t)*0.18 + s(392.0,t)*0.14) * math.sin(math.pi*extra) * 0.7
            return base
        self._snds["jackpot"] = _make_snd(_jackpot, 1.55)

        # Lose — descending minor with added bass weight
        _ln = [392.0, 311.13, 261.63, 220.0]
        def _lose(t, p):
            i = min(3, int(p*4)); lp = p*4-i
            return (s(_ln[i],t)*0.55 + s(_ln[i]*0.5,t)*0.25) * math.sin(math.pi*lp) * (1-p*0.45) * 0.72
        self._snds["lose"] = _make_snd(_lose, 0.88)

    # ── persistence ───────────────────────────────────────────────────────────
    def _load(self):
        try:
            if self._SETTINGS.exists():
                d = json.loads(self._SETTINGS.read_text())
                self.master    = float(d.get("master", 0.7))
                self.sfx       = float(d.get("sfx",    1.0))
                self.card_back = int(d.get("card_back", 0))
                self.card_back = max(0, min(len(CARD_BACK_STYLE_NAMES) - 1, self.card_back))
        except Exception:
            pass

    def save(self):
        try:
            self._SETTINGS.write_text(
                json.dumps({"master": self.master,
                            "sfx": self.sfx,
                            "card_back": self.card_back}, indent=2))
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
CARD_BACK_STYLE_NAMES = ["Classic", "Diamonds", "Stripes", "Dots", "Checkerboard"]

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
        self.display_coins = float(coins)
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

    def update(self, dt):
        if self.display_coins != self.coins:
            diff = self.coins - self.display_coins
            direction = 1 if diff > 0 else -1
            speed = max(120.0, abs(diff) * 2.5)
            step = min(abs(diff), speed * dt)
            self.display_coins += direction * step
            if abs(self.coins - self.display_coins) < 0.5:
                self.display_coins = float(self.coins)

    def save(self):
        SAVE_FILE.write_text(json.dumps(
            {"name":self.name,"coins":self.coins,"stats":self.stats}, indent=2))

    @staticmethod
    def load():
        if SAVE_FILE.exists():
            try:
                d = json.loads(SAVE_FILE.read_text())
                p = Player(d["name"], d["coins"])
                p.display_coins = float(d["coins"])
                p.stats = {**p.stats, **d.get("stats",{})}
                return p
            except: pass
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Drawing helpers
# ─────────────────────────────────────────────────────────────────────────────
def txt(font, text, color=WHITE):
    return font.render(str(text), True, color)

def panel(surf, rect, bg=PANEL, border=GOLD, bw=2, r=14):
    x,y,w,h = rect
    s = pygame.Surface((w,h), pygame.SRCALPHA)
    pygame.draw.rect(s, (*bg, 240), (0,0,w,h), border_radius=r)
    pygame.draw.rect(s, (255,255,255,18), (1,1,w-2,h-2), 1, border_radius=r)
    surf.blit(s, (x,y))
    if bw:
        pygame.draw.rect(surf, border, (x,y,w,h), bw, border_radius=r)

def top_bar(surf, title, player, back_btn):
    pygame.draw.rect(surf, PANELB, (0, 0, W, 80))
    pygame.draw.line(surf, GOLD2, (0,80),(W,80), 2)
    pygame.draw.line(surf, GOLD, (0,76),(W,76), 1)
    back_btn.draw(surf)
    s = txt(F_LG, title, WHITE)
    surf.blit(s, s.get_rect(centerx=W//2, centery=40))
    display_balance = int(round(player.display_coins))
    b = txt(F_MD, f"Balance:  {display_balance:,} c", LGRAY)
    surf.blit(b, b.get_rect(right=W-30, centery=40))

def draw_card_back(surf, x, y, w, h, style=0):
    r = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surf, DKBLUE, r, border_radius=12)
    pygame.draw.rect(surf, BLUE, r, 2, border_radius=12)
    inset = pygame.Rect(x+8, y+8, w-16, h-16)
    pygame.draw.rect(surf, (14, 28, 52), inset, border_radius=10)
    if style == 0:
        for i in range(x+14, x+w-14, 12):
            pygame.draw.line(surf, (55,100,170), (i, y+14), (i, y+h-14), 2)
    elif style == 1:
        for ix in range(x+16, x+w-16, 18):
            for iy in range(y+16, y+h-16, 18):
                pygame.draw.circle(surf, (70,120,200), (ix, iy), 4)
    elif style == 2:
        for i in range(y+14, y+h-14, 12):
            pygame.draw.line(surf, (55,100,170), (x+14, i), (x+w-14, i), 2)
    elif style == 3:  # Dots
        for ix in range(x+14, x+w-14, 18):
            for iy in range(y+14, y+h-14, 18):
                pygame.draw.circle(surf, (100,150,230), (ix, iy), 3)
    else:  # style == 4, Checkerboard
        sq_size = 12
        for ix in range(x+12, x+w-12, sq_size):
            for iy in range(y+12, y+h-12, sq_size):
                if ((ix - x) // sq_size + (iy - y) // sq_size) % 2 == 0:
                    pygame.draw.rect(surf, (35, 60, 95), (ix, iy, sq_size, sq_size))
    pygame.draw.rect(surf, BLUE, r, 2, border_radius=12)


def draw_card(surf, rank, suit, x, y, w=72, h=104, hidden=False):
    r = pygame.Rect(x, y, w, h)
    if hidden:
        draw_card_back(surf, x, y, w, h, getattr(SND, 'card_back', 0))
        return
    # Card shadow
    shd = pygame.Surface((w+8, h+8), pygame.SRCALPHA)
    pygame.draw.rect(shd, (0, 0, 0, 100), (0, 0, w+8, h+8), border_radius=8)
    surf.blit(shd, (x+2, y+2))
    # Card body
    pygame.draw.rect(surf, (252, 252, 250), r, border_radius=8)
    pygame.draw.rect(surf, (200, 200, 195), r, 2, border_radius=8)
    # Card edge highlight
    pygame.draw.line(surf, (255, 255, 255, 120), (x+4, y+4), (x+w-4, y+4), 1)
    
    color = RED if suit in RED_S else BLACK
    sym   = SUIT_SYM[suit]
    # Top-left corner
    rl = F_SMB.render(rank, True, color)
    sl = F_XS.render(sym,  True, color)
    surf.blit(rl, (x+4, y+3))
    surf.blit(sl, (x+4, y+3+rl.get_height()))
    # Center symbol - larger
    cs = F_LG.render(sym, True, color)
    surf.blit(cs, cs.get_rect(centerx=x+w//2, centery=y+h//2))
    # Bottom-right corner - inverted
    rr = F_SMB.render(rank, True, color)
    sr = F_XS.render(sym,  True, color)
    surf.blit(rr, (x+w-4-rr.get_width(), y+h-3-rr.get_height()-sr.get_height()))
    surf.blit(sr, (x+w-4-sr.get_width(), y+h-3-sr.get_height()))

def draw_die(surf, value, x, y, size=80):
    r = pygame.Rect(x, y, size, size)
    # 3D effect: bottom/right shadow face - more pronounced
    pygame.draw.rect(surf, (140, 130, 110), (x+size//8, y+size//8, size, size), border_radius=14)
    # Main face - cleaner white
    pygame.draw.rect(surf, (248, 248, 245), r, border_radius=14)
    # Border - darker for contrast
    pygame.draw.rect(surf, (120, 115, 100), r, 3, border_radius=14)
    # Top edge highlight
    pygame.draw.line(surf, (255, 255, 255, 150), (x+8, y+4), (x+size-8, y+4), 2)
    # Dots with better appearance
    for fx, fy in DICE_DOTS[value-1]:
        dot_x = int(x + fx*size)
        dot_y = int(y + fy*size)
        dot_radius = max(7, size//11)
        # Dot shadow
        pygame.draw.circle(surf, (100, 100, 100), (dot_x+2, dot_y+2), dot_radius)
        # Dot body
        pygame.draw.circle(surf, (20, 20, 20), (dot_x, dot_y), dot_radius)
        # Dot highlight
        pygame.draw.circle(surf, (80, 80, 80), (dot_x-2, dot_y-2), dot_radius//2)

def draw_glow(surf, cx, cy, color, radii=None):
    if radii is None:
        radii = [(180,8),(120,16),(70,28),(35,45)]
    for r, a in radii:
        s = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*color, a), (r, r), r)
        surf.blit(s, (cx-r, cy-r))

def draw_felt_bg(surf):
    """Modern casino table background with improved depth and styling."""
    surf.fill(BG)
    # Radial glow rings for depth
    ring = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.circle(ring, (100, 220, 255, 30), (W//2, H//2), 500)
    pygame.draw.circle(ring, (100, 220, 255, 15), (W//2, H//2), 380)
    pygame.draw.circle(ring, (255, 255, 255, 8), (W//2, H//2), 280)
    surf.blit(ring, (0, 0))
    # Table rails with better styling
    rails = pygame.Rect(40, 80, W-80, H-140)
    pygame.draw.rect(surf, (25, 80, 120), rails, border_radius=26)
    pygame.draw.rect(surf, (40, 100, 140), rails, 3, border_radius=26)
    pygame.draw.rect(surf, (50, 120, 160), rails.inflate(-12, -12), 2, border_radius=22)
    # Inner felt area with subtle texture
    felt_area = rails.inflate(-40, -40)
    pygame.draw.rect(surf, (30, 110, 60), felt_area, border_radius=20)
    # Subtle scanlines for texture
    for y in range(felt_area.top, felt_area.bottom, 8):
        pygame.draw.line(surf, (255, 255, 255, 3), (felt_area.left, y), (felt_area.right, y), 1)
    # Edge highlights
    pygame.draw.rect(surf, (255, 255, 255, 15), felt_area, 1, border_radius=20)

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
    # Outer wood rim - more polished
    pygame.draw.circle(surf, (36, 20, 8), (cx, cy), r+16)
    pygame.draw.circle(surf, (70, 45, 15), (cx, cy), r+12, 8)
    pygame.draw.circle(surf, (110, 75, 28), (cx, cy), r+5, 4)
    # Number pockets with improved colors
    for i, num in enumerate(WHEEL_NUMS):
        a1 = i * seg + angle - math.pi/2
        a2 = (i+1)*seg + angle - math.pi/2
        col = (20, 140, 50) if num==0 else (200, 30, 30) if num in RED_NUMS else (10, 10, 10)
        pts = [(cx, cy)]
        for s in range(8):
            a = a1 + (a2-a1)*s/7
            pts.append((int(cx+r*math.cos(a)), int(cy+r*math.sin(a))))
        pygame.draw.polygon(surf, col, pts)
        # Pocket divider - brighter
        pygame.draw.line(surf, (85, 60, 25),
            (int(cx + 0.46*r*math.cos(a1)), int(cy + 0.46*r*math.sin(a1))),
            (int(cx + r     *math.cos(a1)), int(cy + r     *math.sin(a1))), 2)
    # Clean outer edge - chrome effect
    pygame.draw.circle(surf, (110, 80, 35), (cx, cy), r, 4)
    # Inner felt with better depth
    ir = int(r * 0.44)
    pygame.draw.circle(surf, (14, 70, 35), (cx, cy), ir)
    pygame.draw.circle(surf, (18, 90, 45), (cx, cy), int(ir*0.84))
    # Spokes - more visible
    for s in range(8):
        sa = s * math.pi/4 + angle
        pygame.draw.line(surf, (70, 50, 20),
            (cx, cy),
            (int(cx+ir*math.cos(sa)), int(cy+ir*math.sin(sa))), 3)
    # Center hub with shine
    pygame.draw.circle(surf, (35, 20, 8), (cx, cy), int(r*0.13))
    pygame.draw.circle(surf, (240, 200, 100), (cx, cy), int(r*0.1), 2)
    pygame.draw.circle(surf, GOLD, (cx, cy), int(r*0.075))
    pygame.draw.circle(surf, (255, 255, 255, 200), (cx-3, cy-3), int(r*0.045))

def draw_roulette_ball(surf, cx, cy, r, angle):
    orbit = r - 16
    bx = int(cx + orbit * math.cos(angle))
    by = int(cy + orbit * math.sin(angle))
    # Shadow
    pygame.draw.circle(surf, (0, 0, 0, 100), (bx+3, by+3), 10)
    # Ball body with shine
    pygame.draw.circle(surf, (20, 20, 20), (bx, by), 10)
    pygame.draw.circle(surf, (240, 240, 240), (bx, by), 8)
    pygame.draw.circle(surf, WHITE, (bx, by), 6)
    pygame.draw.circle(surf, (200, 200, 200), (bx-3, by-3), 4)

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
        bg  = self.hover if hot else (self.bg if self.on else (40, 48, 62))
        if hot:
            glow = pygame.Surface((self.rect.w+22, self.rect.h+22), pygame.SRCALPHA)
            pygame.draw.rect(glow, (*self.border, 32), glow.get_rect(), border_radius=self.r+12)
            surf.blit(glow, (self.rect.x-11, self.rect.y-11))
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
        self.pop_t = 0.4   # start fully settled

    def show(self, text, color=WHITE, dur=2.2):
        self.text  = text
        self.color = color
        self.timer = dur
        self.pop_t = 0.0   # reset pop-in

    def update(self, dt):
        if self.timer > 0:
            self.timer -= dt
        if self.pop_t < 0.4:
            self.pop_t += dt

    def draw(self, surf, cx=W//2, cy=H-60):
        if self.timer <= 0 or not self.text:
            return
        alpha  = min(255, int(255 * min(self.timer, 0.4) / 0.4))
        base   = F_LG.render(self.text, True, self.color)
        pop_p  = min(1.0, self.pop_t / 0.22)
        scale  = 1.0 + 0.40 * (1.0 - pop_p) ** 2
        if scale > 1.01:
            nw = max(1, int(base.get_width()  * scale))
            nh = max(1, int(base.get_height() * scale))
            s  = pygame.transform.smoothscale(base, (nw, nh))
        else:
            s = base
        tmp = pygame.Surface(s.get_size(), pygame.SRCALPHA)
        tmp.fill((0, 0, 0, 0))
        tmp.blit(s, (0, 0))
        tmp.set_alpha(alpha)
        surf.blit(tmp, tmp.get_rect(centerx=cx, centery=cy))

# ─────────────────────────────────────────────────────────────────────────────
# Win particles  — spinning gold coins that burst out on wins
# ─────────────────────────────────────────────────────────────────────────────
class Particle:
    _COLORS = [GOLD, GOLD2, (255, 230, 60), (255, 200, 10), (240, 178, 20)]

    def __init__(self, x, y):
        ang        = random.uniform(-math.pi, 0)
        speed      = random.uniform(90, 340)
        self.x     = float(x)
        self.y     = float(y)
        self.vx    = math.cos(ang) * speed * random.uniform(0.6, 1.4)
        self.vy    = math.sin(ang) * speed
        self.color = random.choice(self._COLORS)
        self.life  = random.uniform(0.65, 1.35)
        self.maxl  = self.life
        self.r     = random.randint(5, 10)
        self.spin  = random.uniform(-9, 9)
        self.phase = random.uniform(0, math.pi)

    def update(self, dt):
        self.x    += self.vx * dt
        self.y    += self.vy * dt
        self.vy   += 650 * dt
        self.vx   *= (1 - 1.2 * dt)
        self.life -= dt
        self.phase += self.spin * dt
        return self.life > 0

    def draw(self, surf):
        alpha  = max(0, int(255 * self.life / self.maxl))
        squish = abs(math.cos(self.phase))
        cw     = max(2, int(self.r * 2 * squish))
        ch     = self.r * 2
        ps     = pygame.Surface((cw + 2, ch + 2), pygame.SRCALPHA)
        pygame.draw.ellipse(ps, (*self.color, alpha), (1, 1, max(1, cw), ch))
        surf.blit(ps, (int(self.x) - cw // 2 - 1, int(self.y) - ch // 2 - 1))


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
        self.symbols      = random.choices(S_NAMES, weights=S_WEIGHTS, k=30)
        self.offset       = 0.0
        self.speed        = 0.0
        self.spinning     = False
        self.stopped      = True
        self.stop_ms      = 0
        self.target       = None
        self.bounce_t     = 0.0
        self.bounce_amp   = 0.0
        self.just_stopped = False

    def spin(self, target_sym, stop_ms):
        self.target   = target_sym
        self.speed    = 1800.0
        self.spinning = True
        self.stopped  = False
        self.stop_ms  = stop_ms
        self.symbols  = self.symbols + random.choices(S_NAMES, weights=S_WEIGHTS, k=60)
        self.offset   = 0.0

    def update(self, dt):
        if self.bounce_amp > 0:
            self.bounce_t  += dt
            self.bounce_amp = max(0.0, 10.0 * math.exp(-self.bounce_t * 18)
                                       * abs(math.cos(self.bounce_t * 22)))
        if not self.spinning: return
        self.offset += self.speed * dt
        if pygame.time.get_ticks() >= self.stop_ms:
            ci = (int(self.offset / SYM_H) + 1) % len(self.symbols)
            self.symbols[ci]  = self.target
            self.offset       = int(self.offset / SYM_H) * float(SYM_H)
            self.spinning     = False
            self.stopped      = True
            self.bounce_t     = 0.0
            self.bounce_amp   = 10.0
            self.just_stopped = True

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
        surf.blit(rsurf, (x, y + int(self.bounce_amp)))
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
        for i, (offset, tint) in enumerate([(-36, BLUE), (0, GOLD), (36, RED)]):
            s = F_LG.render("7", True, tint)
            surf.blit(s, s.get_rect(centerx=cx+offset, centery=cy-4))
        for offset in [-42, -18, 6, 30]:
            pygame.draw.rect(surf, (255,255,255, 40), (cx+offset, cy+32, 8, 4), border_radius=2)

    elif game_key == "blackjack":
        card1 = pygame.Rect(cx-34, cy-22, 46, 70)
        card2 = pygame.Rect(cx-16, cy-10, 46, 70)
        pygame.draw.rect(surf, (248,248,244), card1, border_radius=12)
        pygame.draw.rect(surf, (192,192,192), card1, 2, border_radius=12)
        pygame.draw.rect(surf, (232,232,228), card2, border_radius=12)
        pygame.draw.rect(surf, (170,170,170), card2, 2, border_radius=12)
        surf.blit(F_SMB.render("A", True, BLACK), (card1.x+6, card1.y+6))
        surf.blit(F_XS.render(SUIT_SYM["S"], True, BLACK), (card1.x+6, card1.y+28))
        surf.blit(F_MD.render(SUIT_SYM["S"], True, BLACK), F_MD.render(SUIT_SYM["S"], True, BLACK).get_rect(center=(card1.centerx+2, card1.centery)))
        surf.blit(F_SMB.render("K", True, RED), (card2.x+8, card2.y+8))
        surf.blit(F_XS.render(SUIT_SYM["H"], True, RED), (card2.x+8, card2.y+30))
        surf.blit(F_MD.render(SUIT_SYM["H"], True, RED), F_MD.render(SUIT_SYM["H"], True, RED).get_rect(center=(card2.centerx+2, card2.centery)))
        pygame.draw.circle(surf, GOLD, (cx+18, cy+28), 14)
        pygame.draw.circle(surf, (255,255,255,150), (cx+14, cy+24), 7)
        surf.blit(F_SMB.render("21", True, BLACK), F_SMB.render("21", True, BLACK).get_rect(center=(cx+18, cy+28)))

    elif game_key == "roulette":
        R = 38
        pygame.draw.circle(surf, (28,28,34), (cx,cy), R)
        for i in range(18):
            a1 = math.radians(i*20)
            a2 = math.radians(i*20 + 10)
            color = ROULRED if i % 2 == 0 else (35,35,35)
            pygame.draw.polygon(surf, color, [
                (cx,cy),
                (cx+int(R*math.cos(a1)), cy+int(R*math.sin(a1))),
                (cx+int(R*math.cos(a2)), cy+int(R*math.sin(a2))) ] )
        pygame.draw.circle(surf, (18,18,18), (cx,cy), 16)
        pygame.draw.circle(surf, GOLD, (cx,cy), 6)
        pygame.draw.circle(surf, (255,255,255,150), (cx+26, cy-8), 5)

    elif game_key == "dice":
        for ox, oy, val in [(-22,-10,5), (10,4,2)]:
            dx, dy = cx+ox, cy+oy
            pygame.draw.rect(surf, CREAM, (dx,dy,38,38), border_radius=10)
            pygame.draw.rect(surf, GRAY, (dx,dy,38,38), 2, border_radius=10)
            for fx, fy in DICE_DOTS[val-1]:
                pygame.draw.circle(surf, BLACK, (int(dx+fx*38), int(dy+fy*38)), 4)
        pygame.draw.line(surf, (255,255,255,100), (cx-10, cy+22), (cx+20, cy+22), 2)

    elif game_key == "hilo":
        pygame.draw.rect(surf, (40,120,220), (cx-24, cy-34, 24, 48), border_radius=6)
        pygame.draw.rect(surf, (220,75,75), (cx+4, cy+2, 24, 36), border_radius=6)
        pygame.draw.polygon(surf, WHITE, [(cx-13,cy-38),(cx-21,cy-24),(cx-5,cy-24)])
        pygame.draw.polygon(surf, WHITE, [(cx+28,cy+38),(cx+20,cy+24),(cx+36,cy+24)])
        surf.blit(F_SMB.render("H", True, WHITE), (cx-21, cy-24))
        surf.blit(F_SMB.render("L", True, WHITE), (cx+9, cy+16))

    elif game_key == "coinflip":
        pygame.draw.circle(surf, (205,170,70), (cx-8,cy), 30)
        pygame.draw.circle(surf, (245,225,125), (cx-8,cy), 22)
        pygame.draw.circle(surf, (205,170,70), (cx+14,cy+4), 24)
        pygame.draw.circle(surf, (240,220,115), (cx+14,cy+4), 18)
        pygame.draw.circle(surf, (255,255,255,150), (cx-18, cy-10), 8)
        pygame.draw.circle(surf, (255,255,255,120), (cx+18, cy+2), 6)
        surf.blit(F_MDB.render("H", True, BLACK), F_MDB.render("H", True, BLACK).get_rect(center=(cx-8,cy)))
        surf.blit(F_MDB.render("T", True, BLACK), F_MDB.render("T", True, BLACK).get_rect(center=(cx+14,cy+4)))


def draw_cabinet(surf, x, y, game_key, game_name, game_desc, hovered, can_afford=True):
    w, h  = CAB_W, CAB_H
    base_color = GAME_COLORS[game_key]
    tick  = pygame.time.get_ticks()
    pulse = 0.80 + abs(math.sin(tick * 0.004)) * 0.20
    color = tuple(int(c * pulse) for c in base_color)
    if not can_afford:
        color = tuple(int(c * 0.45) for c in color)
    shd = pygame.Surface((w+12, h+12), pygame.SRCALPHA)
    pygame.draw.rect(shd, (0,0,0,90), (0,0,w+12,h+12), border_radius=18)
    surf.blit(shd, (x+6, y+6))
    body_c = PANELB if not hovered else (34, 46, 66)
    if not can_afford:
        body_c = tuple(int(c * 0.7) for c in body_c)
    pygame.draw.rect(surf, body_c, (x,y,w,h), border_radius=18)
    pygame.draw.rect(surf, color, (x,y,w,52), border_top_left_radius=18, border_top_right_radius=18)
    pygame.draw.rect(surf, (*WHITE, 20), (x+12, y+12, w-24, 28), border_radius=12)
    if hovered:
        overlay = pygame.Surface((w-40, 28), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        surf.blit(overlay, (x+20, y+14))
    title = F_MDB.render(game_name, True, WHITE if hovered else LGRAY)
    surf.blit(title, title.get_rect(centerx=x+w//2, centery=y+26))
    scr_x, scr_y = x+18, y+70
    scr_w, scr_h = w-36, 108
    panel(surf, (scr_x, scr_y, scr_w, scr_h), PANEL, GOLD3, 1, 14)
    _draw_cabinet_icon(surf, game_key, scr_x, scr_y, scr_w, scr_h)
    desc_bg = pygame.Surface((w-44, 28), pygame.SRCALPHA)
    desc_bg.fill((0, 0, 0, 150))
    desc_y = y + h - 44
    surf.blit(desc_bg, (x+22, desc_y))
    dl = F_XS.render(game_desc, True, WHITE if hovered else LGRAY)
    surf.blit(dl, dl.get_rect(centerx=x+w//2, centery=desc_y+14))
    led_y   = y + h - 12
    phase   = (tick // 450) % 3
    n_leds  = 7
    led_gap = (w - 76) // n_leds
    for i in range(n_leds):
        lx2  = x + 34 + i * led_gap
        rect = pygame.Rect(lx2, led_y, 14, 6)
        if can_afford:
            alpha = 180 if hovered else 80
            glow = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            glow.fill((*color, alpha if (i+phase)%2==0 else alpha//2))
            surf.blit(glow, rect.topleft)
        else:
            pygame.draw.rect(surf, (40,45,55), rect, border_radius=3)
    border_c = GOLD if hovered else (65, 100, 150)
    pygame.draw.rect(surf, border_c, (x,y,w,h), 2, border_radius=18)
    if hovered:
        glow = pygame.Surface((w-16,h-16), pygame.SRCALPHA)
        pygame.draw.rect(glow, (*color, 30), (0,0,w-16,h-16), border_radius=16)
        surf.blit(glow, (x+8,y+8))
    if can_afford:
        draw_glow(surf, x + w//2, y + h//2, color, [(90,6),(50,12),(25,20)])


def draw_lobby_bg(surf):
    surf.fill(BG)
    for i, alpha in enumerate([18, 14, 10]):
        glow = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.circle(glow, (88, 204, 255, alpha), (W//2, H//2-80), 420 - i*120)
        surf.blit(glow, (0,0))
    vignette = pygame.Surface((W, H), pygame.SRCALPHA)
    pygame.draw.rect(vignette, (0,0,0,100), (0,0,W,H), border_radius=0)
    surf.blit(vignette, (0,0))
    pygame.draw.line(surf, GOLD2, (0, 120), (W, 120), 1)
    for x in range(0, W, 80):
        pygame.draw.line(surf, (255,255,255,8), (x, 0), (x, H), 1)
    for y in range(0, H, 80):
        pygame.draw.line(surf, (255,255,255,8), (0, y), (W, y), 1)


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
        display_balance = int(round(self.player.display_coins))
        bal = F_MDB.render(
            f"{self.player.name}   |   Balance:  {display_balance:,} c",
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
            draw_cabinet(surf, rect.x, rect.y, key, name, desc, hovered, self.player.coins >= 10)

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
        self.bet_sel     = BetSelector(_M_CX, 448, player)
        self.back_btn    = Btn((20,18,90,36),"< Back",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_SM)
        self.state       = "idle"
        self.result      = []
        self._bet_placed = 0
        self._win_flash    = 0.0
        self._particles    = []
        self._flash_t      = 0.0
        self._tick_timer   = 0.0
        # Lever
        self.lever_y       = 0.0   # 0=up, 1=down
        self.lever_anim    = "idle"
        self.lever_t       = 0.0
        self._lever_grabbed = False
        # Auto spin
        self.auto_spins   = 0
        self.auto_btns    = [
            Btn((W-250, 340, 80, 40), "5x", PANELB, GOLD2, tc=GOLD, font=F_SM),
            Btn((W-250, 390, 80, 40), "10x", PANELB, GOLD2, tc=GOLD, font=F_SM),
            Btn((W-250, 440, 80, 40), "25x", PANELB, GOLD2, tc=GOLD, font=F_SM),
        ]

    # ── lever helpers ──────────────────────────────────────────────────────────
    def _lever_ball_pos(self):
        y = _LEV_UP_Y + self.lever_y * (_LEV_DOWN_Y - _LEV_UP_Y)
        return (_LEV_X, int(y))

    def _can_spin(self):
        return self.player.coins >= self.bet_sel.value and self.player.coins >= 10

    def _trigger_spin(self):
        SND.play("spin")
        self._do_spin()
        self.lever_anim = "returning"
        self.lever_t    = 0.0

    # ── handle ────────────────────────────────────────────────────────────────
    def handle_event(self, event):
        if self.back_btn.clicked(event):
            return "game_over" if self.player.coins <= 0 else "lobby"

        # Auto spin buttons
        if self.state in ("idle", "result") and not self._lever_grabbed:
            for i, btn in enumerate(self.auto_btns):
                if btn.clicked(event):
                    spins = [5, 10, 25][i]
                    if self.player.coins >= self.bet_sel.value * spins:
                        self.auto_spins = spins
                        self._do_spin()
                    break

        # Grab lever on mouse-down near the ball
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            bx, by = self._lever_ball_pos()
            if (math.hypot(event.pos[0]-bx, event.pos[1]-by) <= _LEV_R + 20
                    and self.state in ("idle", "result")
                    and self._can_spin()):
                self._lever_grabbed = True

        # Release lever
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._lever_grabbed:
                self._lever_grabbed = False
                if self.lever_y >= 0.92:
                    if self.state == "result":
                        self.state = "idle"
                    self._trigger_spin()
                else:
                    self.lever_anim = "returning"

        if self.state == "idle":
            if not self._lever_grabbed:
                self.bet_sel.handle(event)
        elif self.state == "result":
            if (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
                    and not self._lever_grabbed):
                if self.player.coins <= 0:
                    return "game_over"
                self.state = "idle"
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
        self._flash_t   = max(0.0, self._flash_t - dt)
        for r in self.reels:
            r.update(dt)
            if r.just_stopped:
                SND.play("reel_stop")
                r.just_stopped = False
        self._particles = [p for p in self._particles if p.update(dt)]
        if self.state == "spinning" and all(r.stopped for r in self.reels):
            self._resolve()

        # Reel tick sounds while spinning
        if self.state == "spinning":
            n_still = sum(1 for r in self.reels if r.spinning)
            interval = 0.07 + 0.04 * max(0, 3 - n_still)
            self._tick_timer -= dt
            if self._tick_timer <= 0:
                SND.play("tick")
                self._tick_timer = interval
        else:
            self._tick_timer = 0.0

        # Lever drag: track mouse while button is held
        if self._lever_grabbed:
            my = pygame.mouse.get_pos()[1]
            raw = (my - _LEV_UP_Y) / (_LEV_DOWN_Y - _LEV_UP_Y)
            self.lever_y = max(0.0, min(1.0, raw))
            # Auto-trigger when dragged all the way down
            if self.lever_y >= 1.0 and self.state in ("idle", "result"):
                self._lever_grabbed = False
                if self.state == "result":
                    self.state = "idle"
                self._trigger_spin()
        elif self.lever_anim == "returning":
            # Spring-back: accelerates as it returns to top
            self.lever_y = max(0.0, self.lever_y - dt * (2.0 + self.lever_y * 7.0))
            if self.lever_y < 0.01:
                self.lever_y    = 0.0
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
            self._flash_t   = 0.28
            for _ in range(80):
                self._particles.append(Particle(_M_CX + random.randint(-220, 220), 300))
        elif a == b or b == c or a == c:
            self.player.push()
            self.msg.show("Two matching — push!  Bet returned.", GOLD)
            SND.play("coin")
            self._win_flash = 1.0
            for _ in range(28):
                self._particles.append(Particle(_M_CX + random.randint(-80, 80), 340))
        else:
            self.player.lose(bet)
            self.msg.show(f"No match  —  -{bet:,} c", LOSEC)
            SND.play("lose")
        if self.player.coins <= 0: self.player.coins = 0
        self.player.save()
        self.bet_sel.bet = max(10, min(self.bet_sel.bet, self.player.coins))
        # Auto spin chaining
        if self.auto_spins > 0:
            if self.player.coins >= self.bet_sel.value:
                self.auto_spins -= 1
                self._do_spin()
            else:
                self.auto_spins = 0
        self.state = "result"

    # ── draw helpers ──────────────────────────────────────────────────────────
    def _draw_machine_body(self, surf):
        mx, my, mw, mh = _M_X, _M_Y, _M_W, _M_H
        # Drop shadow
        shd = pygame.Surface((mw+16, mh+16), pygame.SRCALPHA)
        pygame.draw.rect(shd, (0,0,0,140), (0,0,mw+16,mh+16), border_radius=20)
        surf.blit(shd, (mx+4, my+4))
        # Outer shell gradient effect
        pygame.draw.rect(surf, (20,24,36), (mx, my, mw, mh), border_radius=18)
        pygame.draw.rect(surf, (50,65,100), (mx, my, mw, mh), 3, border_radius=18)
        # Inner panel with depth
        pygame.draw.rect(surf, (32,40,56), (mx+8, my+8, mw-16, mh-16), border_radius=14)
        # Side chrome rails - more polished
        for sx2 in [mx+16, mx+mw-22]:
            pygame.draw.rect(surf, (100,115,145), (sx2, my+50, 12, mh-90), border_radius=6)
            pygame.draw.rect(surf, (180,195,215), (sx2+2, my+50, 4, mh-90), border_radius=3)
        # Bottom panel - coin return area
        bpy = my+mh-52
        pygame.draw.rect(surf, (18, 22, 32), (mx, bpy, mw, 52), border_radius=18)
        pygame.draw.rect(surf, (40, 52, 80), (mx+10, bpy+8, mw-20, 36), border_radius=14)
        csx, csy = mx+mw//2-28, bpy+18
        pygame.draw.rect(surf, (12, 16, 24), (csx, csy, 56, 14), border_radius=8)
        pygame.draw.rect(surf, (120, 170, 255), (csx, csy, 56, 14), 2, border_radius=8)
        surf.blit(F_XS.render("INSERT COIN", True, GOLD),
                  F_XS.render("INSERT COIN", True, GOLD).get_rect(centerx=mx+mw//2, centery=csy+7))

    def _draw_marquee(self, surf):
        mx, my, mw = _M_X, _M_Y, _M_W
        mh_q = 62
        # Marquee background - darker gradient effect
        block = pygame.Rect(mx, my, mw, mh_q)
        pygame.draw.rect(surf, (22, 28, 40), block, border_top_left_radius=18, border_top_right_radius=18)
        pygame.draw.rect(surf, (45, 65, 110), block, 2, border_top_left_radius=18, border_top_right_radius=18)
        # Horizontal scanlines for vintage feel
        sh = pygame.Surface((mw, mh_q), pygame.SRCALPHA)
        for i in range(5):
            pygame.draw.line(sh, (255, 255, 255, 8), (0, 12 + i*11), (mw, 12 + i*11), 1)
        surf.blit(sh, (mx, my))
        # Title text with better styling
        tl = F_LG.render("SLOT MACHINE", True, (255, 250, 200))
        surf.blit(tl, tl.get_rect(centerx=mx+mw//2, centery=my+mh_q//2))
        # Animated LED lights - more vibrant
        tick = pygame.time.get_ticks()
        phase = (tick//200) % 3
        n_led = 24
        lgap = (mw-48)//n_led
        for i in range(n_led):
            lx2 = mx+24+i*lgap+lgap//2
            # Cycling color animation
            led_state = (i + phase) % 3
            if led_state == 0:
                lc = ROULRED
            elif led_state == 1:
                lc = GOLD
            else:
                lc = (60, 150, 255)
            pygame.draw.circle(surf, lc, (lx2, my+mh_q-10), 6)
            pygame.draw.circle(surf, (255, 255, 255, 120), (lx2-2, my+mh_q-12), 2)

    def _draw_reel_window(self, surf):
        rw_total = 3*REEL_W + 2*20
        rx = _M_CX - rw_total//2
        ry = 150
        bw2 = rw_total+40
        bh2 = REEL_H+40
        # Outer bezel - chrome effect
        pygame.draw.rect(surf, (16, 20, 28), (rx-20, ry-20, bw2, bh2), border_radius=16)
        pygame.draw.rect(surf, (60, 90, 150), (rx-20, ry-20, bw2, bh2), 3, border_radius=16)
        pygame.draw.rect(surf, (100, 130, 180), (rx-18, ry-18, bw2-4, bh2-4), 1, border_radius=14)
        # Inner dark recess with depth
        pygame.draw.rect(surf, (8, 10, 16), (rx-14, ry-14, bw2-12, bh2-12), border_radius=12)
        pygame.draw.rect(surf, (20, 30, 50), (rx-14, ry-14, bw2-12, bh2-12), 1, border_radius=12)
        # Reels
        for i, reel in enumerate(self.reels):
            reel.draw(surf, rx+i*(REEL_W+20), ry)
        # Glass overlay - stronger reflective effect
        glass = pygame.Surface((bw2-12, bh2-12), pygame.SRCALPHA)
        pygame.draw.rect(glass, (200, 230, 255, 12), (0, 0, bw2-12, bh2-12), border_radius=10)
        pygame.draw.line(glass, (200, 230, 255, 40), (0, 20), (bw2-12, 20), 2)
        surf.blit(glass, (rx-14, ry-14))
        # PAY label with improved arrows
        py_cy = ry + REEL_H//2
        pay_lbl = F_XS.render("PAY", True, GOLD)
        surf.blit(pay_lbl, (rx-50, py_cy-8))
        pygame.draw.polygon(surf, GOLD, [(rx-48, py_cy), (rx-36, py_cy-8), (rx-36, py_cy+8)])
        # Win-flash glow on payline - brighter
        if self._win_flash > 0:
            pulse = abs(math.sin(self._win_flash * 10))
            glow_s = pygame.Surface((bw2, SYM_H+16), pygame.SRCALPHA)
            ga = int(100 * pulse)
            pygame.draw.rect(glow_s, (255, 220, 50, ga), (0, 0, bw2, SYM_H+16), border_radius=8)
            surf.blit(glow_s, (rx-20, ry+SYM_H-8))
            # Bright border on payline frame
            bc = (int(220+35*pulse), int(180+35*pulse), 0)
            pygame.draw.rect(surf, bc, (rx-6, ry+SYM_H-4, bw2-8, SYM_H+8), 4)

    def _draw_paytable(self, surf):
        px, py = _M_X+20, 148
        pw, ph = 200, 400
        # Panel with better styling
        pygame.draw.rect(surf, (16, 22, 36), (px-2, py-2, pw+4, ph+4), border_radius=10)
        pygame.draw.rect(surf, (20, 28, 42), (px, py, pw, ph), border_radius=10)
        pygame.draw.rect(surf, (80, 120, 200), (px, py, pw, ph), 2, border_radius=10)
        # Header
        hdr = F_SMB.render("PAYTABLE", True, (255, 240, 150))
        surf.blit(hdr, hdr.get_rect(centerx=px+pw//2, top=py+10))
        pygame.draw.line(surf, (100, 140, 200), (px+10, py+34), (px+pw-10, py+34), 2)
        # Payout rows with better styling
        for i, (name, col, pay, _) in enumerate(SLOT_DEFS):
            y2 = py+45+i*50
            # Color swatch - larger and better styled
            pygame.draw.rect(surf, col, (px+10, y2+2, 20, 20), border_radius=4)
            pygame.draw.rect(surf, (200, 200, 200), (px+10, y2+2, 20, 20), 1, border_radius=4)
            # Text with better contrast
            surf.blit(F_SM.render(name, True, col), (px+36, y2))
            payout_txt = F_XS.render(f"x3 = {pay}x", True, (200, 220, 255))
            surf.blit(payout_txt, (px+36, y2+18))

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

        # HOLD & PULL hint
        if self.lever_anim == "idle" and self.state == "idle" and not self._lever_grabbed:
            pulse = abs(math.sin(pygame.time.get_ticks()*0.003))
            hc = (int(180+75*pulse),int(140+60*pulse),0)
            ht = F_XS.render("HOLD & PULL", True, hc)
            surf.blit(ht, ht.get_rect(centerx=bx,top=by+_LEV_R+6))
        elif self._lever_grabbed:
            pct = int(self.lever_y * 100)
            hc2 = (int(100+155*(self.lever_y)), int(200-150*(self.lever_y)), 0)
            ht2 = F_XS.render(f"{'RELEASE!' if self.lever_y>=0.92 else f'{pct}%'}", True, hc2)
            surf.blit(ht2, ht2.get_rect(centerx=bx, top=by+_LEV_R+6))

    def draw(self, surf):
        surf.fill(BG)
        for tx in range(0,W,64):
            pygame.draw.line(surf, (255,255,255,10), (tx,80), (tx,H), 1)
        for ty in range(80,H,64):
            pygame.draw.line(surf, (255,255,255,10), (0,ty), (W,ty), 1)
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
            surf.blit(hint, hint.get_rect(centerx=_M_CX, top=576))
            # Auto spin buttons
            for btn in self.auto_btns:
                btn.draw(surf)
            if self.auto_spins > 0:
                auto_text = F_SM.render(f"Auto spins left: {self.auto_spins}", True, GOLD)
                surf.blit(auto_text, auto_text.get_rect(centerx=W-190, top=490))
        elif self.state == "spinning":
            s = F_LG.render("Spinning...", True, GOLD)
            surf.blit(s, s.get_rect(centerx=_M_CX, centery=512))
        elif self.state == "result":
            self.bet_sel.draw(surf)
            s = F_SM.render("Pull lever or click to spin again", True, GRAY)
            surf.blit(s, s.get_rect(centerx=_M_CX, top=576))
            # Auto spin buttons
            for btn in self.auto_btns:
                btn.draw(surf)
            if self.auto_spins > 0:
                auto_text = F_SM.render(f"Auto spins left: {self.auto_spins}", True, GOLD)
                surf.blit(auto_text, auto_text.get_rect(centerx=W-190, top=490))
        for p in self._particles:
            p.draw(surf)
        if self._flash_t > 0:
            fa  = int(200 * (self._flash_t / 0.28))
            fov = pygame.Surface((W, H), pygame.SRCALPHA)
            fov.fill((255, 255, 200, min(200, fa)))
            surf.blit(fov, (0, 0))
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
            draw_card_back(surf, rx2, ry2, 62, 86, SND.card_back)
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

        self.msg.draw(surf, cx=cx, cy=660)

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
        self.spin_btn  = Btn((220, 592, 160, 44), "SPIN",
                             GOLD3, GOLD, tc=BLACK, font=F_MDB)
        # BetSelector left-panel-centred
        self.bet_sel   = BetSelector(300, 468, player)
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
        # Settling phase
        self.settle_t      = 0.0
        self.settle_start  = 0.0
        self.settle_target = 0.0
        self.settle_dur    = 1.2

        self.type_btns = []
        for i,(key,label,pays) in enumerate(ROUL_BETS):
            col=i%2; row=i//2
            x=28+col*282; y=82+row*40
            self.type_btns.append((key,
                Btn((x,y,268,34),label,PANELB,GOLD2,tc=LGRAY,border=GOLD3,font=F_SM)))

        self.num_btns = []
        for n in range(37):
            nc=n%13; nr=n//13
            x=20+nc*44; y=338+nr*36
            self.num_btns.append(Btn((x,y,40,30),str(n),
                bg=ROULRED if n in RED_NUMS else (PANEL if n>0 else DARKGRN),
                hover=GOLD2,tc=WHITE,font=F_SMB,border=GOLD3))

    def handle_event(self, event):
        if self.back_btn.clicked(event):
            return "game_over" if self.player.coins <= 0 else "lobby"
        if self.state in ("pick","pick_num","bet"):
            for key,btn in self.type_btns:
                if btn.clicked(event):
                    self.sel_type = key
                    if key == "number":
                        self.state = "pick_num"
                    else:
                        self.state = "bet"
                        self.pick_num = 0  # reset if changing away from number
            if self.state == "pick_num":
                for n,btn in enumerate(self.num_btns):
                    if btn.clicked(event):
                        self.pick_num = n
                        self.state = "bet"
            if self.state == "bet":
                self.bet_sel.handle(event)
                if self.spin_btn.clicked(event):
                    self.bet_locked = self.bet_sel.value   # lock bet NOW
                    self.result     = random.randint(0,36)
                    self.spin_anim  = 0.0
                    self.ball_vis   = True
                    self.state      = "spinning"
                    SND.play("spin")
        elif self.state == "result":
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.player.coins <= 0: return "game_over"
                self.state = "pick"
                self.sel_type = None
                self.ball_vis = False
        return None

    def update(self, dt):
        self.msg.update(dt)
        if self.state == "spinning":
            self.spin_anim += dt
            wheel_spd = max(0.0, 12.0 * math.exp(-self.spin_anim * 2.1))
            ball_spd  = max(0.0, 18.0 * math.exp(-self.spin_anim * 1.55))
            self.wheel_angle -= wheel_spd * dt
            self.ball_angle  += ball_spd  * dt
            # Start settling once ball speed drops to ~3 rad/s (still visibly moving)
            if ball_spd <= 3.2 and self.spin_anim >= 0.5:
                self._start_settling()

        elif self.state == "settling":
            self.settle_t += dt
            progress = min(1.0, self.settle_t / self.settle_dur)
            # Quadratic ease-out: initial speed matches spinning hand-off velocity
            ease = progress * (2.0 - progress)
            self.ball_angle = self.settle_start + (self.settle_target - self.settle_start) * ease
            if progress >= 1.0:
                self._resolve()

        elif self.state not in ("result",):
            # Idle slow drift while picking a bet
            self.wheel_angle -= 0.35 * dt

    def _start_settling(self):
        """Freeze wheel; compute pocket target with velocity-matched deceleration."""
        self.state        = "settling"
        self.settle_t     = 0.0
        self.settle_start = self.ball_angle

        # Ball speed at this exact moment — used to set initial settling speed
        v0 = max(0.1, 18.0 * math.exp(-self.spin_anim * 1.55))

        n_pockets = len(WHEEL_NUMS)
        seg = 2.0 * math.pi / n_pockets
        try:
            idx = WHEEL_NUMS.index(self.result)
        except ValueError:
            idx = 0

        pocket_screen = idx * seg + self.wheel_angle - math.pi / 2 + seg * 0.5

        # Minimum forward travel to reach the pocket
        base_diff = (pocket_screen - self.settle_start) % (2.0 * math.pi)
        if base_diff < 0.25:          # nearly grazed it — add a full lap
            base_diff += 2.0 * math.pi

        # With quadratic ease-out (p*(2-p)), distance = v0 * T / 2
        # → T = 2 * diff / v0.  Clamp T to [0.8, 2.8] s.
        T_MIN, T_MAX = 0.8, 2.8
        min_diff = v0 * T_MIN / 2
        max_diff = v0 * T_MAX / 2

        diff = base_diff
        # Add full laps until diff is at least min_diff (looks natural)
        while diff < min_diff:
            diff += 2.0 * math.pi
        # If still over max, clamp T and let the ball overshoot by <2π
        if diff > max_diff:
            diff = base_diff
            while diff < min_diff:
                diff += 2.0 * math.pi

        self.settle_dur    = max(T_MIN, min(T_MAX, 2.0 * diff / v0))
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
            panel(surf,(12,326,576,126),PANELB,GOLD3,1)
            for n,btn in enumerate(self.num_btns):
                btn.bw=2 if n==self.pick_num else 1
                btn.border=GOLD if n==self.pick_num else GOLD3
                btn.draw(surf)

        if self.state=="bet":
            if self.sel_type:
                info=next((l for k,l,_ in ROUL_BETS if k==self.sel_type),"")
                s=F_SMB.render(f"Bet on:  {info}",True,GOLD)
                surf.blit(s, s.get_rect(left=28,top=282))
                if self.sel_type=="number":
                    surf.blit(F_MDB.render(f"Number:  {self.pick_num}",True,CREAM),
                              (28,304))
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
        self.roll_btn = Btn((W//2-70,622,140,46),"ROLL DICE",GOLD3,GOLD,tc=BLACK,font=F_MDB)
        self.bet_sel  = BetSelector(W//2, 480, player)
        self.msg      = Msg()
        self.state    = "pick"
        self.sel      = None
        self.d1=self.d2=1
        self.anim_t=0.0; self.anim_d1=1; self.anim_d2=1
        self.cup_tilt      = 0.0  # 0=upright, 1=fully tipped
        self.dice_bounce_t = 0.0
        self.dice_bounce_y = 0.0

        self.bet_btns=[]
        for i,(key,label,pays) in enumerate(DICE_BETS_DEF):
            col=i%2; row=i//2
            x=W//2-300+col*308; y=82+row*66
            self.bet_btns.append((key,
                Btn((x,y,292,54),f"{label}   pays {pays}:1",
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
        if self.dice_bounce_y > 0:
            self.dice_bounce_t += dt
            self.dice_bounce_y  = max(0.0, 28.0 * math.exp(-self.dice_bounce_t * 14)
                                          * abs(math.cos(self.dice_bounce_t * 18)))
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
        self.player.save()
        self.state         = "result"
        self.dice_bounce_t = 0.0
        self.dice_bounce_y = 28.0

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

        # Shadow - more pronounced
        shd_pts = [(p[0]+5, p[1]+5) for p in cup_pts]
        shd_s = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.polygon(shd_s, (0, 0, 0, 100), shd_pts)
        surf.blit(shd_s, (0, 0))

        # Cup body with better colors - leather-like
        pygame.draw.polygon(surf, (85, 75, 60), cup_pts)
        pygame.draw.polygon(surf, (110, 95, 70), cup_pts, 4)
        # Top rim - chrome effect
        pygame.draw.line(surf, (160, 165, 180), tl, tr, 6)
        pygame.draw.line(surf, (130, 135, 150), tl, tr, 3)
        # Bottom rim band - more defined
        pygame.draw.line(surf, (130, 120, 90), bl, br, 5)
        # Handle nub - improved
        handle_top = rot(cx+cw_bot//2+12, cy-12)
        handle_bot = rot(cx+cw_bot//2+12, cy+8)
        pygame.draw.line(surf, (130, 120, 100), br, handle_top, 10)
        pygame.draw.line(surf, (130, 120, 100), br, handle_bot, 10)
        pygame.draw.line(surf, (160, 150, 120), br, handle_top, 4)

    def draw(self, surf):
        draw_felt_bg(surf)
        top_bar(surf,"DICE DUEL",self.player,self.back_btn)

        for key,btn in self.bet_btns:
            btn.tc=GOLD if key==self.sel else LGRAY
            btn.bg=(18,60,30) if key==self.sel else PANELB
            btn.draw(surf)

        # Cup and dice area
        cup_cx, cup_cy = W//2, 370
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
            by_off = int(self.dice_bounce_y)
            draw_die(surf,self.d1,W//2-130,dice_y + by_off,92)
            draw_die(surf,self.d2,W//2+38, dice_y + by_off,92)
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
                      F_MDB.render("Shaking...",True,GOLD).get_rect(centerx=W//2,centery=474))
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

        self.msg.draw(surf,cx=W//2,cy=660)

# ─────────────────────────────────────────────────────────────────────────────
# Coin Flip  — pedestal + arc-trajectory coin
# ─────────────────────────────────────────────────────────────────────────────
class CoinFlipState:
    def __init__(self, player):
        self.player    = player
        self.back_btn  = Btn((20,18,90,36),"< Back",PANELB,GOLD2,tc=GOLD,border=GOLD2,font=F_SM)
        self.heads_btn = Btn((W//2-240,480,220,54),"HEADS",GOLD3,GOLD,    tc=BLACK,border=GOLD, font=F_LG)
        self.tails_btn = Btn((W//2+20, 480,220,54),"TAILS",PANELB,GOLD2, tc=GOLD, border=GOLD, font=F_LG)
        self.bet_sel   = BetSelector(W//2, 550, player)
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
        # Base shadow
        shadow = pygame.Surface((120, 40), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 80), (0, 0, 120, 40))
        surf.blit(shadow, (cx-60, py+40))
        
        for i, (w2, h2, col) in enumerate([
                (100, 14, (95, 80, 60)),
                (80, 12, (115, 95, 70)),
                (60, 16, (85, 70, 50))]):
            # Pedestal step with shadow
            pygame.draw.rect(surf, (60, 50, 30), (cx-w2//2+2, py+i*10+2, w2, h2), border_radius=5)
            # Main step
            pygame.draw.rect(surf, col, (cx-w2//2, py+i*10, w2, h2), border_radius=5)
            # Bright top edge
            pygame.draw.rect(surf, (min(255, col[0]+40), min(255, col[1]+30), min(255, col[2]+20)),
                             (cx-w2//2, py+i*10, w2, h2), 3, border_radius=5)

    def _draw_coin(self, surf, cx, cy, phase, face):
        """Draw a 3D-looking gold coin. phase 0-1 controls flip squish."""
        squish = abs(math.cos(phase * math.pi * 5))
        if self.state == "result":
            squish = 1.0
        cw = max(8, int(130*squish)); ch = 130

        col_face = (220, 180, 80) if face=="H" else (200, 160, 60)
        col_edge = (180, 140, 40)
        col_rim  = (240, 210, 130)
        col_dark = (100, 80, 20)

        # Shadow - more pronounced
        shd = pygame.Surface((cw+24, ch+24), pygame.SRCALPHA)
        pygame.draw.ellipse(shd, (0, 0, 0, 120), (12, 18, cw, ch))
        surf.blit(shd, (cx-cw//2-8, cy-ch//2+10))

        # Coin body with gradient effect
        r2 = pygame.Rect(cx-cw//2, cy-ch//2, cw, ch)
        pygame.draw.ellipse(surf, col_dark, r2)
        pygame.draw.ellipse(surf, col_face, r2.inflate(-6, -6))
        # Metallic rim - brighter
        pygame.draw.ellipse(surf, col_rim, r2, 5)
        # Inner ring - darker edge
        if cw > 40:
            ir2 = r2.inflate(-22, -22)
            pygame.draw.ellipse(surf, col_edge, ir2, 3)
        # Face letter - improved visibility
        if cw > 50:
            lbl = F_HUGE.render(face, True, col_dark)
            surf.blit(lbl, lbl.get_rect(center=(cx, cy)))
        # Shine - multiple highlights for metallic effect
        if cw > 30:
            # Main shine
            sh_r = pygame.Rect(cx-cw//5, cy-ch//3, cw//3, ch//6)
            sh_s = pygame.Surface((sh_r.w, sh_r.h), pygame.SRCALPHA)
            pygame.draw.ellipse(sh_s, (255, 255, 255, 80), (0, 0, sh_r.w, sh_r.h))
            surf.blit(sh_s, (sh_r.x, sh_r.y))
            # Secondary shine
            if cw > 50:
                sh_r2 = pygame.Rect(cx+cw//8, cy+ch//6, cw//4, ch//8)
                sh_s2 = pygame.Surface((sh_r2.w, sh_r2.h), pygame.SRCALPHA)
                pygame.draw.ellipse(sh_s2, (255, 255, 255, 40), (0, 0, sh_r2.w, sh_r2.h))
                surf.blit(sh_s2, (sh_r2.x, sh_r2.y))

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
        self.test_btn = Btn((W//2-75, 670, 150, 46), "► TEST SOUND",
                            GOLD3, GOLD, tc=BLACK, font=F_MDB)
        mid = W // 2
        # Initialise sliders from current SND values
        self.master_sl = Slider(mid, 290, 560, "Master Volume", SND.master)
        self.sfx_sl    = Slider(mid, 420, 560, "SFX Volume",    SND.sfx)
        self.card_back_idx = SND.card_back
        self.card_back_btn = Btn((mid-200, 520, 400, 50), f"Card Back: {CARD_BACK_STYLE_NAMES[SND.card_back]}", PANELB, GOLD2, tc=GOLD, border=GOLD2, font=F_MDB)

    def handle_event(self, event):
        self.master_sl.handle(event)
        self.sfx_sl.handle(event)
        # Live update while dragging
        SND.master = self.master_sl.value
        SND.sfx    = self.sfx_sl.value
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pass  # removed card_back_rects
        if self.card_back_btn.clicked(event):
            SND.card_back = (SND.card_back + 1) % len(CARD_BACK_STYLE_NAMES)
            self.card_back_btn.label = f"Card Back: {CARD_BACK_STYLE_NAMES[SND.card_back]}"
            SND.play("click")
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

        # Card back selection
        mid = W // 2
        self.card_back_btn.draw(surf)
        preview_rect = pygame.Rect(mid + 210, 520, 80, 50)
        pygame.draw.rect(surf, PANELB, preview_rect, border_radius=8)
        pygame.draw.rect(surf, GOLD3, preview_rect, 2, border_radius=8)
        draw_card_back(surf, preview_rect.x + 5, preview_rect.y + 5, preview_rect.w - 10, preview_rect.h - 10, SND.card_back)

        self.test_btn.draw(surf)

        hint = F_SM.render("Drag the sliders, then press  < Back  to save.", True, GRAY)
        surf.blit(hint, hint.get_rect(centerx=W//2, centery=715))

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
# Screen transition  — fade-to-black between every state change
# ─────────────────────────────────────────────────────────────────────────────
class Transition:
    FADE_OUT = 0.20   # seconds to go black
    FADE_IN  = 0.26   # seconds to clear from black

    def __init__(self):
        self.phase   = "idle"   # "out" | "in" | "idle"
        self._t      = 0.0
        self.pending = None
        self._surf   = pygame.Surface((W, H))
        self._surf.fill((0, 0, 0))

    @property
    def busy(self):
        return self.phase != "idle"

    def start(self, result):
        if self.phase == "idle":          # don't interrupt an ongoing fade
            self.phase   = "out"
            self._t      = 0.0
            self.pending = result

    def update(self, dt):
        if self.phase == "idle":
            return None
        self._t += dt
        if self.phase == "out" and self._t >= self.FADE_OUT:
            self.phase = "in"
            self._t    = 0.0
            return self.pending           # caller creates new state NOW
        if self.phase == "in" and self._t >= self.FADE_IN:
            self.phase = "idle"
        return None

    def draw(self, surf):
        if self.phase == "idle":
            return
        if self.phase == "out":
            a = int(255 * min(1.0, self._t / self.FADE_OUT))
        else:
            a = int(255 * max(0.0, 1.0 - self._t / self.FADE_IN))
        self._surf.set_alpha(a)
        surf.blit(self._surf, (0, 0))


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

    state = make_state("game_over" if player.coins<=0 else "lobby", player)
    trans = Transition()

    while True:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                player.save(); SND.save(); pygame.quit(); sys.exit()
            if trans.busy:
                continue          # block input while fading
            result = state.handle_event(event)
            if result == "quit":
                player.save(); SND.save(); pygame.quit(); sys.exit()
            elif result is not None:
                if result == "lobby" and player.coins <= 0:
                    trans.start("game_over")
                else:
                    trans.start(result)

        switch = trans.update(dt)
        if switch is not None:
            if switch == "restart":
                if SAVE_FILE.exists(): SAVE_FILE.unlink()
                player = run_name_input()
                state  = make_state("lobby", player)
            elif switch == "lobby" and player.coins <= 0:
                state = make_state("game_over", player)
            else:
                state = make_state(switch, player)

        state.update(dt)
        player.update(dt)
        screen.fill(BG)
        state.draw(screen)
        trans.draw(screen)
        pygame.display.flip()


if __name__=="__main__":
    main()
