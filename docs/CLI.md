# Command line reference

`main.py` runs as a **command line tool** when it gets arguments, and as the GUI without arguments.
The binaries behave the same way: Linux one-file binary, Windows `…-cli.exe`.

```
python main.py [FILES ...] [--pcb2gcode DIR] [-o OUTPUT] [options]
```

The input files are G-code from **FlatCAM** or **pcb2gcode**. The output is **one** Carvera job (`.nc`, ASCII) that
follows the Happylab rules, plus an optional SVG preview.

---

## 1. Inputs

| Input | How it is used |
|---|---|
| `FILES ...` | G-code files (`.nc`, `.ngc`, `.gcode`), machined **in the order given** |
| `--pcb2gcode DIR` | pcb2gcode output folder. Uses `front.ngc` or `back.ngc`, `drill.ngc`, `milldrill.ngc`, `outline.ngc` in this order (missing files are skipped). FILES given as well come after them. |

The format is recognised per file (FlatCAM header / pcb2gcode header / generic). Each file is split into **tool blocks**:

- **FlatCAM with *Toolchange* off** (the Happylab workflow) has no `T` word, so **one file = one tool**.
  The tool is identified from the file name and comments (`iso` → V-bit, `drl` → drill, `drl_mill` / `cutout` → mill).
- **Files with tool changes** (pcb2gcode `drill.ngc`, FlatCAM with Toolchange on) are split into one block per tool.
  The tool size comes from `(MSG, Change tool bit to …)` / `Tool Dia` comments.

These files are refused (exit 1): inch files (`G20`), empty files, non-G-code files.

## 2. Options

| Option | Default | Meaning |
|---|---|---|
| `-o, --output FILE` | `carvera_job.nc` next to the first input (`carvera.nc` in DIR for `--pcb2gcode`) | output file |
| `--slot WHAT=N` | automatic | ATC slot **1–5** (6 is the Happylab dummy). Can be repeated. See §3 for WHAT. |
| `--rpm WHAT=RPM` | from the file | spindle speed. Needed when FlatCAM wrote a bare `M03`. Can be repeated. |
| `--keep-tool-numbers` | off | use the file's own T numbers (1–5) as slots instead of numbering automatically |
| `--origin keep\|lower-left` | `lower-left` with `--pcb2gcode`, else `keep` | shift X/Y so the job's lower-left lies at X0 Y0 (§4) |
| `--origin-margin MM` | outline cutter radius (pcb2gcode), else 0 | where the lowest path point lands: at **X = −MM, Y = −MM** (§4) |
| `--no-clearance` | off | leave out `M496.1` (go to clearance position) at the end |
| `--no-dummy` | off | leave out `T6M6` (load dummy tool) at the end |
| `--z-change MM` | 10 | retract height before every tool change |
| `--max-depth MM` | 2.0 | deepest allowed Z below 0. Drilling at −2.1 needs `--max-depth 2.2`. |
| `--list` | | only print the tool table (with automatic slots) and exit. Nothing is written. |
| `--preview` | off | also write `<output>_preview.svg` |
| `--force` | off | write the file even if the safety check fails (exit code is still 2) |
| `-q, --quiet` | off | no report. Problems still go to stderr. |
| `--version` | | print the version |

## 3. `WHAT` in `--slot` / `--rpm`

| WHAT | Matches | Example |
|---|---|---|
| file name | all tools of that file (path or base name) | `--slot drill.nc=2` |
| `file:T<n>` | tool `T<n>` of a file that has several tools | `--slot drill.ngc:T3=4` |
| `vbit`, `drill`, `mill`, `tool` + optional diameter | every block of that kind (and size) | `--slot drill0.8=2`, `--slot mill2=3`, `--rpm vbit=12000` |

A WHAT that matches nothing is an error (exit 1). Use `--list` to see the file names and `T` references.

Rules:
- every physical tool (kind + diameter) gets **one** slot;
- **different tools in one slot are an error**;
- the same tool in consecutive blocks (for example pcb2gcode `milldrill` and `outline` with the 1 mm mill) causes
  **only one** tool change.

## 4. Origin

pcb2gcode writes bottom-side jobs at negative X. With `--origin lower-left`, the job is moved so that

```
lowest X of all paths  →  X = −margin
lowest Y of all paths  →  Y = −margin
```

The default margin is the **outline cutter radius**. The outline path runs one radius outside the board edge, so the
**board's lower-left corner** becomes X0 Y0.

**Board inside a bigger blank**: to make the corner of the blank X0 Y0 and keep the clamps clear, use a **negative**
margin:

```bash
# 2 mm outline mill (r = 1): board edge 10 mm from the blank corner -> lowest path at 9 mm -> margin = -9
python main.py --pcb2gcode out -o board.nc --origin-margin=-9
```

Write a negative value as `--origin-margin=-9`, with `=`. Otherwise argparse reads `-9` as an option.

`--origin keep` leaves the coordinates as they are. That is the default for FlatCAM files, where the origin is set
in FlatCAM.

## 5. What is written

**Job file** (ASCII):
```
( Happylab Carvera job - back.ngc, drill.ngc, milldrill.ngc, outline.ngc )
( Werkzeuge / tool rack: )
(   T1 = Gravierstichel / V-bit D0.25 mm )
...
G90 G94 G17 G21
( back.ngc: Gravierstichel / V-bit D0.25 mm - T1 -> T1 )
G00 Z10.000
T1M6
S12000 M3
...                       (moves of the block, cleaned: no M0/M2/M9/G04 P0/G91.1/G64)
M5
M496.1                    (clearance, unless --no-clearance)
T6M6                      (dummy tool, unless --no-dummy)
M30
```

- The tool change is always `T<n>M6` on one line, followed by `S<rpm> M3` for that tool.
- The speed is at most 15000 rpm. Where a file has no speed, the Makera PCB default is used (drill 10000, mill and V-bit 12000), marked with `*` in the table.

**Preview** (`--preview`): `<output>_preview.svg` shows the tool paths in tool colours (T1 blue, T2 red, T3 orange,
T4 purple, T5 green). Drill holes are dots, helical milled holes are circles.

## 6. Report on stdout

```
   #  file              T  tool                           rpm   depth slot
   1  back.ngc         T1  Gravierstichel / V-bit Ø0.  12000   -0.100   T1
   2  drill.ngc        T1  Bohrer Ø0.8 mm              10000   -2.100   T2
   3  drill.ngc        T2  Bohrer Ø1 mm                10000   -2.100   T3
   4  outline.ngc      T1  Fräser Ø2 mm                12000   -1.700   T4
  T '-' = file without tool change = one tool (FlatCAM 'Toolchange' off)

Tool rack:
  T1: Gravierstichel / V-bit Ø0.25 mm
  T2: Bohrer Ø0.8 mm
  T3: Bohrer Ø1 mm
  T4: Fräser Ø2 mm
  T6: dummy tool (loaded at the end)

Origin: lower-left (margin 1 mm)
Cutting distance 3.99 m, deepest Z -2.100
Check: OK
Written: /path/board_bottom.nc
Preview: /path/board_bottom_preview.svg
```

Lines that are stable for scripts:
- `Tool rack:` with the indented `T<n>: <tool>` lines;
- `Check: OK` or `Check: FAILED` (followed by `  !! <problem>` lines);
- `Written: <path>`;
- `Preview: <path>`;
- `Note: …` for hints, for example a default rpm.

No cutting time is printed on purpose. Tool changes and auto-leveling make such estimates misleading.

## 7. Safety check

The finished program is simulated before it is written:

- `T<n>M6` on one line, slots 1–5 (6 only for the final dummy), no different tools in one slot;
- no `M0` / `M1`, rpm ≤ 15000, no cutting while the spindle is off;
- no rapid move (`G0`) down into the material, and no rapid XY move below Z0;
- nothing deeper than `--max-depth`;
- the job fits the Carvera work area (360 × 240 mm).

If a problem is found, nothing is written (exit 2) unless `--force` is given.

## 8. Exit codes

| Code | Meaning | File written? |
|---|---|---|
| 0 | ok | yes |
| 1 | input or usage error: file missing or unreadable, inch (`G20`), empty, not G-code, WHAT matches nothing, slot conflict or slot outside 1–5, rpm > 15000 | no |
| 2 | safety check failed | no; yes with `--force` |

## 9. Examples

```bash
# FlatCAM (Toolchange off, one file per tool): look first, then set slots and missing speeds
python main.py --list iso.nc drill.nc drill_mill.nc cutout.nc
python main.py iso.nc drill.nc drill_mill.nc cutout.nc -o board.nc --preview \
       --slot iso.nc=1 --slot drill.nc=2 --slot drill_mill.nc=3 --slot cutout.nc=3 --rpm drill.nc=10000

# pcb2gcode, single-sided THT board (bottom copper, mirrored), drills to -2.1
pcb2gcode --config millproject_carvera --back B_Cu.gbr --drill board.drl --outline Edge_Cuts.gbr --output-dir out
python main.py --pcb2gcode out -o board_bottom.nc --preview --max-depth 2.2

# same, origin = corner of a 65 x 100 blank, board edge 10 mm in (2 mm outline mill)
python main.py --pcb2gcode out -o board_bottom.nc --preview --max-depth 2.2 --origin-margin=-9

# fix slots by tool type instead of by file
python main.py --pcb2gcode out -o b.nc --slot vbit=1 --slot drill0.8=2 --slot drill1=3 --slot mill2=4
```

## 10. Common errors

| Message | Fix |
|---|---|
| `Slot 6 ungültig - nur 1-5 (6 = Dummy)` (exit 1) | more than 5 different tools. Use the same mill for milled holes and outline, or leave out a drill size. |
| `Slot N ist für verschiedene Werkzeuge vergeben: …` (exit 1) | two different tools are in the same slot. Check with `--list` and change `--slot`. |
| `--slot X=…: no matching file/tool (see --list)` (exit 1) | WHAT does not match. Copy the name or `T` reference from `--list`. |
| `Zeile n: Z-2.1 tiefer als -2.0 mm (Opferplatte/Bett!)` (exit 2) | drills or outline are deeper than `--max-depth`. Raise it on purpose (`--max-depth 2.2`), never use `--force` for this. |
| `* no spindle speed in the file` | FlatCAM wrote `M03` without `S`. The default is used. Check it or set `--rpm FILE=…`. |
