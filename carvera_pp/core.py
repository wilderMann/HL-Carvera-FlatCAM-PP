"""Core of the Happylab Carvera post-processor (no GUI code here).

Reads G-code from FlatCAM (default / GRBL-style preprocessors) and pcb2gcode, splits every file into
tool blocks (one block per tool change), lets the caller assign Carvera ATC slots, and writes ONE job that
follows the Carvera / Happylab rules:

  * tool change as ``T<n>M6`` on one line (Carvera ATC), slots 1-5 only, slot 6 = Happylab dummy tool
  * no M0/M1 pauses (FlatCAM and pcb2gcode both stop after every tool change for a manual change)
  * spindle restarted after each tool change with the block's speed, max 15000 rpm
  * end: M5, M496.1 (go to clearance), T6M6 (dummy tool back into the collet), M30

``check()`` simulates the result and reports dangerous mistakes, ``preview_svg()`` draws the tool paths.
"""
import math
import os
import re
from dataclasses import dataclass, field

MAX_RPM = 15000
SLOTS = range(1, 6)          # usable ATC slots
DUMMY_TOOL = 6               # Happylab: slot 6 always holds a dummy tool
GOTO_CLEARANCE = "M496.1"    # Carvera specific: go to clearance position
CARVERA_AREA = (360.0, 240.0)

WORD = re.compile(r"([A-Za-z])\s*([-+]?\d*\.?\d+)")
COMMENT = re.compile(r"\(.*?\)|;.*$")
# pcb2gcode writes its outputs under these names; this is also the machining order
PCB2GCODE_ORDER = ["front.ngc", "back.ngc", "drill.ngc", "milldrill.ngc", "outline.ngc"]


class GCodeError(Exception):
    """Input that cannot be processed safely."""


def code_of(line):
    """Line without comments, stripped, upper case."""
    return COMMENT.sub("", line).strip().upper()


def words(code):
    return {k.upper(): float(v) for k, v in WORD.findall(code)}


def fmt_num(v):
    return f"{v:.4f}".rstrip("0").rstrip(".") if v != int(v) else str(int(v))


@dataclass
class Block:
    """Everything one tool does inside one source file."""
    source: str
    orig_tool: int
    kind: str = "tool"           # vbit | drill | mill | tool (unknown)
    dia: float = None
    rpm: float = None
    feed: float = None           # feed active when the block starts (from the file header)
    lines: list = field(default_factory=list)
    slot: int = None             # assigned ATC slot
    info: str = ""               # tool text from the file (MSG comment)

    @property
    def key(self):
        """Blocks with the same key use the same physical tool."""
        return (self.kind, round(self.dia, 3) if self.dia else self.info or f"T{self.orig_tool}@{self.source}")

    @property
    def label(self):
        names = {"vbit": "Gravierstichel / V-bit", "drill": "Bohrer", "mill": "Fräser", "tool": "Werkzeug"}
        d = f" Ø{fmt_num(self.dia)} mm" if self.dia else ""
        return f"{names.get(self.kind, self.kind)}{d}"

    def depth(self):
        z = [w["Z"] for w in (words(code_of(l)) for l in self.lines) if "Z" in w]
        return min(z) if z else None


class GCodeFile:
    """One input file split into tool blocks."""

    def __init__(self, path, text=None):
        self.path = path
        self.name = os.path.basename(path)
        if text is None:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        self.size_kb = round(len(text) / 1024, 2)
        raw = text.splitlines()
        self.line_count = len(raw)
        if not any(l.strip() for l in raw):
            raise GCodeError(f"{self.name}: Datei ist leer / file is empty")
        self.fmt = "pcb2gcode" if "pcb2gcode" in text[:300] else "flatcam" if "FlatCAM" in text[:2000] else "gcode"
        # values FlatCAM writes into its header comments (shown in the GUI)
        self.spindle_speed = self._hdr(text, r"Spindle Speed:\s*([\d.]+)")
        self.feedrate_xy = self._hdr(text, r"Feedrate_XY:\s*([\d.]+)")
        self.feedrate_z = self._hdr(text, r"Feedrate_Z:\s*([\d.]+)")
        self.z_cut = self._hdr(text, r"Z_Cut:\s*(-?[\d.]+)")
        self.is_excellon = bool(re.search(r"Preprocessor Excellon|TOOLS DIAMETER|drill size", text, re.I))
        self.header_dia = self._hdr(text, r"TOOL DIAMETER:\s*([\d.]+)")
        self.blocks = self._split(raw)
        if not self.blocks:
            raise GCodeError(f"{self.name}: keine Werkzeugwechsel / no tool change (T…) and no tool path found")

    @staticmethod
    def _hdr(text, pat):
        m = re.search(pat, text)
        return float(m.group(1)) if m else None

    def _validate(self, n, line):
        code = code_of(line)
        if code and not re.match(r"^(%|[GMTXYZIJKFSPRN][-+.\d\s])", code):
            raise GCodeError(f"{self.name}, Zeile/line {n}: keine G-Code Syntax / not G-code:\n{line.strip()}")
        if re.search(r"\bG20\b", code):
            raise GCodeError(f"{self.name}: Zoll / inch (G20) wird nicht unterstützt - in FlatCAM auf mm stellen")

    def _split(self, raw):
        blocks, cur, rpm, feed, in_tc, after_tc = [], None, None, None, False, False
        has_tc = any(re.match(r"^T\d+", code_of(l)) for l in raw)
        for n, line in enumerate(raw, 1):
            self._validate(n, line)
            code = code_of(line)
            w = words(code)
            if "S" in w:
                rpm = w["S"]
                if cur is not None:
                    cur.rpm = rpm
            if re.match(r"^T\d+", code):                         # ---- start of a tool change
                cur = Block(self.name, int(w["T"]), rpm=rpm, feed=feed)
                blocks.append(cur)
                in_tc = "M6" not in code.replace(" ", "") and not re.search(r"M0?6\b", code)
                after_tc = True
                continue
            if cur is None:
                if not has_tc and re.match(r"^G0*[0-3]\b.*[XYZ]|^[XYZ]", code):   # tool path without any tool change (FlatCAM
                    cur = Block(self.name, 0, rpm=rpm, feed=feed)     # "Toolchange" off): one implicit block
                    blocks.append(cur)
                    after_tc = False
                else:                                            # header: only S and F matter
                    if "F" in w:
                        feed = w["F"]
                    continue
            if line.strip().upper().startswith("(MSG"):
                cur.info = line.strip()[5:].strip(" ,)")
                self._identify(cur)
                continue
            if in_tc:                                            # everything between T and M6 is dropped
                if re.match(r"^M0?6\b", code):
                    in_tc = False
                continue
            if after_tc and re.match(r"^(M0?0|M0?1)\b", code):   # pause directly after the tool change
                continue
            if not code:
                if line.strip().startswith("(") or line.strip().startswith(";"):
                    cur.lines.append(line.rstrip())
                continue
            after_tc = False
            if re.match(r"^(M0?[01256]|M0?[34]|M0?9|M30|G91\.1|G64|T\d+)\b", code) and not re.search(r"[XYZ]", code):
                continue                                         # pauses, spindle, coolant, end, tool words
            if re.match(r"^G0?4\s*P0*(\.0*)?\b", code):          # zero dwells (pcb2gcode)
                continue
            if re.match(r"^(G0*0?\s*)?S[\d.]+$", code) or re.match(r"^G9[04]$|^G2[01]$|^G17$", code):
                continue                                         # mode/speed-only lines: written by us
            if re.match(r"^M0?3\s*S|^S[\d.]+\s*M0?3", code):
                continue
            cur.lines.append(line.rstrip())
        for b in blocks:
            if b.kind == "tool":
                self._identify(b)
        return [b for b in blocks if any(code_of(l) for l in b.lines)]

    def _identify(self, b):
        """Tool kind + diameter from the MSG comment (FlatCAM and pcb2gcode wording)."""
        t = b.info.lower()
        m = re.search(r"(mill diameter|drill size|cutter diameter|tool dia\s*=?)\s*([\d.]+)", t)
        if m:
            b.dia = float(m.group(2))
        elif self.header_dia and not self.is_excellon:
            b.dia = self.header_dia
        if self.fmt == "pcb2gcode":
            b.kind = {"front.ngc": "vbit", "back.ngc": "vbit", "drill.ngc": "drill"}.get(self.name, "mill")
        elif self.is_excellon:
            b.kind = "drill"
        elif b.dia is not None:
            b.kind = "vbit" if b.dia < 0.5 else "mill"


@dataclass
class Options:
    goto_clearance: bool = True
    end_with_dummy: bool = True
    origin: str = "keep"         # keep | lower-left
    origin_margin: float = 0.0   # added to the lower-left shift (e.g. outline cutter radius)
    z_change: float = 10.0       # retract height before every tool change
    max_depth: float = 2.0       # deepest allowed Z below 0 (bed protection), board 1.6 + extra


class Job:
    """Ordered list of files -> one Carvera program."""

    def __init__(self, files=None, options=None):
        self.files = list(files or [])
        self.options = options or Options()

    @property
    def blocks(self):
        return [b for f in self.files for b in f.blocks]

    def auto_assign(self, keep_numbers=False):
        """Give every physical tool one ATC slot (1-5) in order of first use."""
        slots = {}
        for b in self.blocks:
            if keep_numbers and b.orig_tool in SLOTS:
                b.slot = b.orig_tool
                continue
            if b.key not in slots:
                slots[b.key] = len(slots) + 1
            b.slot = slots[b.key]
        return slots

    def problems_before_build(self):
        probs = []
        for b in self.blocks:
            if b.slot not in SLOTS:
                probs.append(f"{b.source} T{b.orig_tool} ({b.label}): Slot {b.slot} ungültig - nur 1-5 (6 = Dummy)")
            if b.rpm is None:
                probs.append(f"{b.source} T{b.orig_tool}: keine Spindeldrehzahl gefunden / no spindle speed")
            elif b.rpm > MAX_RPM:
                probs.append(f"{b.source} T{b.orig_tool}: S{b.rpm:.0f} > {MAX_RPM} rpm (Carvera max)")
        used = {}
        for b in self.blocks:
            if b.slot in SLOTS and b.kind != "tool":
                used.setdefault(b.slot, {})[b.key] = b.label
        for s, keys in used.items():
            if len(keys) > 1:
                probs.append(f"Slot {s} ist für verschiedene Werkzeuge vergeben: {', '.join(sorted(keys.values()))}")
        return probs

    def _shift(self):
        if self.options.origin != "lower-left":
            return 0.0, 0.0
        b = bounds([l for bl in self.blocks for l in bl.lines], feed_only=True)
        if not b:
            return 0.0, 0.0
        m = self.options.origin_margin
        return -(b[0] + m), -(b[1] + m)

    def build(self, title=""):
        """Return the merged program as list of lines. Raises GCodeError on problems that make it unsafe."""
        probs = self.problems_before_build()
        if probs:
            raise GCodeError("\n".join(probs))
        dx, dy = self._shift()
        o = self.options
        out = [f"( Happylab Carvera job{' - ' + title if title else ''} )", "( Werkzeuge / tool rack: )"]
        seen = {}
        for b in self.blocks:
            seen.setdefault(b.slot, b)
        out += [f"(   T{s} = {b.label} )" for s, b in sorted(seen.items())]
        if o.end_with_dummy:
            out.append(f"(   T{DUMMY_TOOL} = Dummy, wird am Ende eingewechselt )")
        if dx or dy:
            out.append(f"( Nullpunkt verschoben um X{dx:+.3f} Y{dy:+.3f}: X0 Y0 = linke untere Ecke )")
        out.append("G90 G94 G17 G21")
        cur_slot, cur_rpm = None, None
        for b in self.blocks:
            out += ["", f"( {b.source}: {b.label} - T{b.orig_tool} -> T{b.slot} )"]
            if b.slot != cur_slot:
                if cur_slot is not None:
                    out.append("M5")
                out += [f"G00 Z{o.z_change:.3f}", f"T{b.slot}M6", f"S{b.rpm:.0f} M3"]
                cur_slot, cur_rpm = b.slot, b.rpm
            elif b.rpm != cur_rpm:
                out.append(f"S{b.rpm:.0f} M3")
                cur_rpm = b.rpm
            if b.feed:
                out.append(f"G01 F{fmt_num(b.feed)}")
            out += [shift_line(l, dx, dy) for l in b.lines] if (dx or dy) else list(b.lines)
        out += ["", f"G00 Z{o.z_change:.3f}", "M5"]
        if o.goto_clearance:
            out.append(GOTO_CLEARANCE)
        if o.end_with_dummy:
            out += ["( Happylab: Dummy-Werkzeug zurück in die Spannzange )", f"T{DUMMY_TOOL}M6"]
        out.append("M30")
        return [ascii_line(l) for l in out]


ASCII = str.maketrans({"Ø": "D", "ø": "d", "ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss",
                       "–": "-", "→": "->", "°": "deg"})


def ascii_line(line):
    """The Carvera controller gets plain ASCII (comments from us contain umlauts / Ø)."""
    return line.translate(ASCII).encode("ascii", "replace").decode("ascii")


def shift_line(line, dx, dy):
    m = re.match(r"^([^(;]*)(.*)$", line)
    code, com = m.group(1), m.group(2)

    def f(mo):
        a = mo.group(1).upper()
        if a == "X":
            return f"X{float(mo.group(2)) + dx:.4f}"
        if a == "Y":
            return f"Y{float(mo.group(2)) + dy:.4f}"
        return mo.group(0)
    return WORD.sub(f, code).rstrip() + (" " + com.strip() if com.strip() else "")


def bounds(lines, feed_only=False):
    xs, ys, g = [], [], None
    for l in lines:
        c = code_of(l)
        gm = re.match(r"^G0*(\d)\b", c)
        if gm:
            g = gm.group(1)
        if feed_only and g == "0":
            continue
        w = words(c)
        if "X" in w: xs.append(w["X"])
        if "Y" in w: ys.append(w["Y"])
    return (min(xs), min(ys), max(xs), max(ys)) if xs and ys else None


def check(lines, max_depth=2.0, area=CARVERA_AREA):
    """Simulate the program; return (problems, stats). Only the dangerous mistakes."""
    probs, stats = [], {"tools": [], "zmin": 0.0, "feed_mm": 0.0, "time_min": 0.0}
    x = y = z = None
    spindle, tool, g, f = False, None, None, None
    for n, line in enumerate(lines, 1):
        c = code_of(line)
        if not c:
            continue
        w = words(c)
        if re.match(r"^T\d+", c):
            if not re.fullmatch(r"T\d+M0?6", c.replace(" ", "")):
                probs.append(f"Zeile {n}: Werkzeugwechsel nicht als 'T<n>M6': {line}")
            tool = int(w["T"])
            if tool not in SLOTS and tool != DUMMY_TOOL:
                probs.append(f"Zeile {n}: Werkzeug {tool} außerhalb 1-6")
            stats["tools"].append(tool)
            spindle = False
            continue
        if re.search(r"\bM0?[01]\b", c):
            probs.append(f"Zeile {n}: Programmpause M0/M1")
        if re.search(r"\bM0?3\b", c):
            spindle = True
        if re.search(r"\bM0?5\b", c):
            spindle = False
        if "S" in w and w["S"] > MAX_RPM:
            probs.append(f"Zeile {n}: S{w['S']:.0f} > {MAX_RPM}")
        if "F" in w:
            f = w["F"]
        gm = re.match(r"^G0*(\d)\b", c)
        if gm:
            g = gm.group(1)
        nx, ny, nz = w.get("X", x), w.get("Y", y), w.get("Z", z)
        moving = any(k in w for k in "XYZ")
        if moving and tool is None and ("X" in w or "Y" in w or (nz is not None and nz < 0)):
            probs.append(f"Zeile {n}: Bewegung vor dem ersten Werkzeugwechsel")
        if moving and nz is not None and nz < 0 and not spindle:
            probs.append(f"Zeile {n}: unter Z0 mit stehender Spindel")
        if moving and g == "0" and "Z" in w and nz < 0 and (z is None or nz < z - 1e-6):
            probs.append(f"Zeile {n}: Eilgang (G0) nach unten ins Material Z{nz}")
        if moving and g == "0" and ("X" in w or "Y" in w) and z is not None and z < 0:
            probs.append(f"Zeile {n}: Eilgang XY im Material (Z{z})")
        if nz is not None and nz < -max_depth - 1e-6:
            probs.append(f"Zeile {n}: Z{nz} tiefer als -{max_depth} mm (Opferplatte/Bett!)")
        if moving and g in ("1", "2", "3") and None not in (x, y, z):
            d = math.dist((x, y, z), (nx, ny, nz))
            if g in ("2", "3") and (nx, ny) == (x, y) and ("I" in w or "J" in w):   # full circle / helix
                d = math.hypot(2 * math.pi * math.hypot(w.get("I", 0), w.get("J", 0)), nz - z)
            stats["feed_mm"] += d
            if f:
                stats["time_min"] += d / f
        if nz is not None:
            stats["zmin"] = min(stats["zmin"], nz)
        x, y, z = nx, ny, nz
    b = bounds(lines)
    if b and (b[2] - b[0] > area[0] or b[3] - b[1] > area[1]):
        probs.append(f"Job ist {b[2]-b[0]:.0f} x {b[3]-b[1]:.0f} mm groß - größer als der Carvera Arbeitsbereich")
    return probs[:50], stats


def toolpaths(lines):
    """Segments for drawing: list of (tool, kind, data). kind: feed | rapid -> ((x0,y0),(x1,y1));
    hole -> (x, y); arc -> (cx, cy, r)."""
    out, x, y, tool, g = [], None, None, 0, None
    for line in lines:
        c = code_of(line)
        if not c:
            continue
        w = words(c)
        if re.match(r"^T\d+", c):
            tool = int(w["T"])
            continue
        gm = re.match(r"^G0*(\d)\b", c)
        if gm:
            g = gm.group(1)
        nx, ny = w.get("X", x), w.get("Y", y)
        if g in ("2", "3") and ("I" in w or "J" in w) and x is not None:
            i, j = w.get("I", 0.0), w.get("J", 0.0)
            out.append((tool, "arc", (x + i, y + j, math.hypot(i, j))))
        elif "Z" in w and w["Z"] < -0.5 and "X" not in w and "Y" not in w and x is not None:
            out.append((tool, "hole", (x, y)))
        if x is not None and nx is not None and (nx, ny) != (x, y) and g not in ("2", "3"):
            out.append((tool, "rapid" if g == "0" else "feed", ((x, y), (nx, ny))))
        x, y = nx, ny
    return out


TOOL_COLORS = {1: "#1565c0", 2: "#c62828", 3: "#ef6c00", 4: "#6a1b9a", 5: "#2e7d32", 6: "#555555"}


def preview_svg(lines, path):
    segs = toolpaths(lines)
    b = bounds(lines) or (0, 0, 10, 10)
    m = 3
    x0, y0, W, H = b[0] - m, b[1] - m, b[2] - b[0] + 2 * m, b[3] - b[1] + 2 * m
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.3f} {-(y0 + H):.3f} {W:.3f} {H:.3f}" '
         f'width="{W * 8:.0f}" height="{H * 8:.0f}"><rect x="{x0}" y="{-(y0 + H)}" width="{W}" height="{H}" fill="#fff"/>',
         '<g transform="scale(1,-1)">']
    for t, kind, d in segs:
        col = TOOL_COLORS.get(t, "#000")
        if kind == "rapid":
            s.append(f'<path d="M{d[0][0]:.3f},{d[0][1]:.3f}L{d[1][0]:.3f},{d[1][1]:.3f}" stroke="#bbb" stroke-width="0.05"/>')
        elif kind == "feed":
            s.append(f'<path d="M{d[0][0]:.3f},{d[0][1]:.3f}L{d[1][0]:.3f},{d[1][1]:.3f}" stroke="{col}" '
                     f'stroke-width="0.2" stroke-linecap="round"/>')
        elif kind == "hole":
            s.append(f'<circle cx="{d[0]:.3f}" cy="{d[1]:.3f}" r="0.4" fill="{col}"/>')
        elif kind == "arc":
            s.append(f'<circle cx="{d[0]:.3f}" cy="{d[1]:.3f}" r="{d[2]:.3f}" fill="none" stroke="{col}" stroke-width="0.25"/>')
    s.append("</g></svg>")
    with open(path, "w") as fh:
        fh.write("\n".join(s))


def load_pcb2gcode_dir(d):
    """The .ngc files pcb2gcode wrote into one output folder, in machining order."""
    files = [os.path.join(d, n) for n in PCB2GCODE_ORDER if os.path.exists(os.path.join(d, n))]
    if not files:
        raise GCodeError(f"{d}: keine pcb2gcode Dateien (front/back/drill/milldrill/outline.ngc)")
    out = []
    for p in files:
        try:
            out.append(GCodeFile(p))
        except GCodeError as e:
            raise GCodeError(f"{e}\n(pcb2gcode hat für {os.path.basename(p)} keinen Pfad erzeugt - Log prüfen)")
    return out


def cutter_radius(files):
    """Outline cutter radius from pcb2gcode's outline.ngc (to put the board corner, not the path, at X0 Y0)."""
    for f in files:
        if f.name == "outline.ngc":
            for b in f.blocks:
                if b.dia:
                    return b.dia / 2
    return 0.0
