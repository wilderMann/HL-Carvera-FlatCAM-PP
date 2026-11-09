"""Command line interface. Used when main.py is called with arguments (scripts, agents, pcb2gcode pipelines)."""
import argparse
import os
import re
import sys

from . import APP_NAME, VERSION
from .core import (GCodeError, GCodeFile, Job, Options, check, cutter_radius, load_pcb2gcode_dir,
                   preview_svg, DUMMY_TOOL)

EPILOG = """examples:
  FlatCAM files, in this order, automatic ATC slots:
    main.py isolation.nc drill.nc cutout.nc -o board.nc
  pcb2gcode output folder (order + origin handled automatically):
    main.py --pcb2gcode out_dir -o board_bottom.nc --preview
  show the tools first, then fix slots:
    main.py --list isolation.nc drill.nc cutout.nc
    main.py isolation.nc drill.nc cutout.nc --slot vbit=1 --slot drill0.8=2 --slot "drill.nc:T3=4" --slot mill1=5

exit codes: 0 ok, 1 input/usage error, 2 safety check failed (nothing written unless --force)
"""


def parse_slot(spec):
    m = re.fullmatch(r"(?:(?P<file>[^:]+):T(?P<t>\d+)|(?P<kind>vbit|drill|mill|tool)(?P<dia>[\d.]*))=(?P<slot>\d+)", spec)
    if not m:
        raise argparse.ArgumentTypeError(f"bad --slot '{spec}' (use FILE:T<n>=<slot> or drill0.8=<slot> / vbit=<slot>)")
    return m.groupdict()


def apply_slots(job, specs):
    for sp in specs:
        hit = 0
        for b in job.blocks:
            if sp["file"]:
                ok = b.source == os.path.basename(sp["file"]) and b.orig_tool == int(sp["t"])
            else:
                ok = b.kind == sp["kind"] and (not sp["dia"] or (b.dia is not None and abs(b.dia - float(sp["dia"])) < 1e-3))
            if ok:
                b.slot = int(sp["slot"])
                hit += 1
        if not hit:
            raise GCodeError(f"--slot {sp}: no matching tool")


def table(job):
    rows = [f"  {'#':>2}  {'file':24} {'tool':>4} {'what':28} {'rpm':>6} {'depth':>7} {'slot':>4}"]
    for i, b in enumerate(job.blocks, 1):
        d = b.depth()
        rows.append(f"  {i:>2}  {b.source[:24]:24} T{b.orig_tool:<3} {b.label[:28]:28} {b.rpm or 0:>6.0f} "
                    f"{d if d is not None else 0:>7.3f} {('T' + str(b.slot)) if b.slot else '-':>4}")
    return "\n".join(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="main.py", description=f"{APP_NAME} v{VERSION} - FlatCAM/pcb2gcode G-code -> "
                                 "one Makera Carvera job (Happylab rules)", epilog=EPILOG,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="G-code files in machining order (.nc/.ngc/.gcode)")
    ap.add_argument("--pcb2gcode", metavar="DIR", help="use all pcb2gcode outputs in DIR (front/back, drill, milldrill, outline)")
    ap.add_argument("-o", "--output", help="output file (default: carvera_job.nc next to the first input)")
    ap.add_argument("--slot", action="append", type=parse_slot, default=[], metavar="SPEC",
                    help="set ATC slot: FILE:T<n>=<slot>, or by tool: vbit=1, drill0.8=2, mill1=5 (repeatable)")
    ap.add_argument("--keep-tool-numbers", action="store_true", help="use the T numbers from the files (1-5) instead of auto")
    ap.add_argument("--origin", choices=["keep", "lower-left"], help="lower-left: shift X/Y so the job starts at X0 Y0 "
                    "(default: lower-left for --pcb2gcode, keep otherwise)")
    ap.add_argument("--origin-margin", type=float, help="extra shift for lower-left (default: outline cutter radius for pcb2gcode)")
    ap.add_argument("--no-clearance", action="store_true", help=f"do not go to clearance position (M496.1) at the end")
    ap.add_argument("--no-dummy", action="store_true", help=f"do not load the dummy tool T{DUMMY_TOOL} at the end")
    ap.add_argument("--z-change", type=float, default=10.0, help="retract height before tool changes (default 10)")
    ap.add_argument("--max-depth", type=float, default=2.0, help="deepest allowed cut below Z0 in mm (default 2.0)")
    ap.add_argument("--list", action="store_true", help="only list the tools found (with automatic slots) and exit")
    ap.add_argument("--preview", action="store_true", help="also write <output>_preview.svg")
    ap.add_argument("--force", action="store_true", help="write the output even if the safety check fails")
    ap.add_argument("-q", "--quiet", action="store_true")
    ap.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    a = ap.parse_args(argv)

    say = (lambda *x: None) if a.quiet else print
    try:
        files = []
        if a.pcb2gcode:
            files += load_pcb2gcode_dir(a.pcb2gcode)
        files += [GCodeFile(p) for p in a.files]
        if not files:
            ap.error("no input files (give files or --pcb2gcode DIR)")
        is_p2g = any(f.fmt == "pcb2gcode" for f in files)
        origin = a.origin or ("lower-left" if is_p2g else "keep")
        margin = a.origin_margin if a.origin_margin is not None else (cutter_radius(files) if is_p2g else 0.0)
        job = Job(files, Options(goto_clearance=not a.no_clearance, end_with_dummy=not a.no_dummy, origin=origin,
                                 origin_margin=margin, z_change=a.z_change, max_depth=a.max_depth))
        job.auto_assign(keep_numbers=a.keep_tool_numbers)
        apply_slots(job, a.slot)
        if a.list:
            print(table(job))
            return 0
        lines = job.build(title=", ".join(f.name for f in files))
    except (GCodeError, OSError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    probs, st = check(lines, max_depth=a.max_depth)
    out = a.output or os.path.join(os.path.dirname(os.path.abspath(a.pcb2gcode or files[0].path)),
                                   "carvera.nc" if a.pcb2gcode else "carvera_job.nc")
    say(table(job))
    say(f"\nTool rack:" )
    seen = {}
    for b in job.blocks:
        seen.setdefault(b.slot, b.label)
    for s, lab in sorted(seen.items()):
        say(f"  T{s}: {lab}")
    if not a.no_dummy:
        say(f"  T{DUMMY_TOOL}: dummy tool (loaded at the end)")
    say(f"\nOrigin: {origin}" + (f" (margin {margin:g} mm)" if origin == "lower-left" else ""))
    say(f"Cutting distance {st['feed_mm'] / 1000:.2f} m, ~{st['time_min']:.0f} min without rapids/tool changes, "
        f"deepest Z {st['zmin']:.3f}")
    say("Check: " + ("OK" if not probs else "FAILED"))
    for p in probs:
        print("  !! " + p, file=sys.stderr if a.quiet else sys.stdout)
    if probs and not a.force:
        say("Nothing written (use --force to write anyway).")
        return 2
    with open(out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    say(f"Written: {out}")
    if a.preview:
        pv = os.path.splitext(out)[0] + "_preview.svg"
        preview_svg(lines, pv)
        say(f"Preview: {pv}")
    return 2 if probs else 0
