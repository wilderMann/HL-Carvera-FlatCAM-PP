# HL-Carvera-FlatCAM-PP

Post-processor for the **Makera Carvera** at Happylab. If you mill PCBs with **FlatCAM** or **pcb2gcode**, the G-code
has to be edited before the Carvera can run it. This program does that and merges all files (isolation, drilling,
milled holes, outline) into **one job** for the automatic tool changer.

One program, two ways to use it:

| Start | What you get |
|---|---|
| `python main.py` (double click, or the `.exe`) | **GUI** (German) |
| `python main.py <files> [options]` | **command line** – for scripts, pcb2gcode pipelines, AI agents |

Only the Python standard library is used (tkinter for the GUI), Python ≥ 3.8.

## What it does

- merges several `.nc` / `.ngc` files into one, in the order you choose
- splits every file into **tool blocks** – a FlatCAM drill file with 0.8 / 1.0 / 1.4 mm drills becomes three tools
- gives every physical tool **one ATC slot (1–5)**, automatically or chosen by you; the same tool in several files
  (e.g. pcb2gcode `milldrill` + `outline`, both with the 1 mm mill) gets one slot and **only one tool change**
- tool change as **`T<n>M6` on one line** (Carvera); everything FlatCAM/pcb2gcode put between `T` and `M6` is removed
- removes the **`M0` pause** that FlatCAM and pcb2gcode write after every tool change, plus `M2`, `M9`, zero dwells
  (`G04 P0`), `G91.1`, `G64`
- restarts the spindle after each tool change with **that tool's speed** (`S… M3`), max 15000 rpm
- optional: go to the clearance position at the end (`M496.1`) and load the **dummy tool T6** (Happylab: slot 6
  always holds a dummy tool, the collet should not stay empty); `M30` at the end
- optional: **move the origin** so the job's lower-left corner is X0 Y0 – default for pcb2gcode, whose bottom side
  comes out at negative X; the outline cutter radius is taken into account, so the **board corner** is X0 Y0
- **safety check** of the result (simulation): `T<n>M6`, slots, no M0/M1, rpm ≤ 15000, no cutting with the spindle
  off, no rapid move down into the material, no rapid XY move below Z0, nothing deeper than `--max-depth` (default −2.0 mm, protects the bed), job fits
  the Carvera work area (360 × 240 mm). Problems block saving (GUI asks, CLI needs `--force`)
- **preview** of the tool paths (GUI, and `…_preview.svg` next to the saved file)
- output is plain ASCII; refuses inch files (`G20`), empty files and files that are not G-code

## FlatCAM workflow (Happylab)

FlatCAM always writes `T1` (sometimes `T2` or `T9999`) or – with *Toolchange* switched off – no tool number at all,
and the tool numbers cannot be chosen there. So the workflow is: **one FlatCAM G-code file per job = one tool**
(isolation, drilling, milled holes, cutout), and the **ATC slot and spindle speed are set here**, per file.
Files that use the same tool (e.g. milled holes + cutout with the 2 mm mill) get the same slot automatically and
only one tool change. If FlatCAM's speed field was empty the file only contains a bare `M03`; then the Makera PCB
default is used (drills 10000, mills/V-bit 12000 rpm), marked with `*` and reported – check it.

Only if a file really contains several tool changes (pcb2gcode's `drill.ngc`, FlatCAM with Toolchange on) it is
split into its tools, each with its own slot.

## GUI

1. **Öffnen** – FlatCAM files (`.nc`), or **pcb2gcode-Ordner** – the output folder of pcb2gcode.
2. Order the files with **↑ ↓**. Select a file and set its **Werkzeug-Slot** and **Drehzahl** (a file with several
   tools shows them below it). **Slots automatisch** assigns 1, 2, 3 … in order of use.
3. Check the preview and the status line (**Prüfung: OK**).
4. **Zusammenführen und Speichern** – writes the job and `…_preview.svg` and shows which tool goes into which slot.

## Command line

```bash
python main.py --list isolation.nc drill.nc cutout.nc              # show tools + automatic slots
python main.py isolation.nc drill.nc cutout.nc -o board.nc --preview
python main.py iso.nc drill.nc drill_mill.nc cutout.nc --slot drill.nc=2 --slot drill_mill.nc=3 --rpm drill.nc=10000
python main.py --pcb2gcode pcb2gcode_out/ -o board_bottom.nc --preview --max-depth 2.2
```

| Option | |
|---|---|
| `--pcb2gcode DIR` | use `front/back.ngc`, `drill.ngc`, `milldrill.ngc`, `outline.ngc` from DIR, in this order |
| `-o FILE`, `--preview` | output file, plus `<output>_preview.svg` |
| `--list` | only show the tool table with the automatic slots |
| `--slot WHAT=N` | slot for a file (`drill.nc=2`), one tool of a file (`drill.ngc:T3=4`) or a tool kind/size (`vbit=1`, `drill0.8=2`, `mill2=3`) |
| `--rpm WHAT=RPM` | spindle speed, same WHAT as `--slot` (for files where FlatCAM wrote no speed) |
| `--keep-tool-numbers` | use the T numbers from the files instead of automatic slots |
| `--origin keep\|lower-left`, `--origin-margin MM` | origin shift: the lowest path point lands at −MM. Default: the board corner is X0 Y0 for pcb2gcode, keep for FlatCAM. Negative values move the job into a blank. |
| `--no-clearance`, `--no-dummy` | leave out `M496.1` / `T6M6` at the end |
| `--z-change MM`, `--max-depth MM` | retract height before tool changes (10), deepest allowed Z (2.0; drilling at −2.1 needs 2.2) |
| `--force`, `-q`, `--version` | write even if the check fails (exit code stays 2), quiet, version |

Exit codes: `0` ok, `1` input/usage error (nothing written), `2` safety check failed.
**Full reference** (inputs, WHAT syntax, origin, output format, safety check, errors): [docs/CLI.md](docs/CLI.md).
**AI agents** that use the tool: read [AGENTS.md](AGENTS.md).

## pcb2gcode

[pcb2gcode](https://github.com/pcb2gcode/pcb2gcode) is a command line CAM for PCBs (it also has an MCP server for AI
assistants). [`examples/millproject_carvera`](examples/millproject_carvera) holds the settings for the Happylab tools
that were checked on the machine:

```bash
pcb2gcode --config examples/millproject_carvera --back B_Cu.gbr --drill board.drl --outline Edge_Cuts.gbr --output-dir out
python main.py --pcb2gcode out -o board_bottom.nc --preview --max-depth 2.2
```

## Tested on the Carvera (Happylab, November 2026)

The pcb2gcode route was milled on the Happylab Carvera: a single-sided THT board, and a calibration board with
isolation at three depths, measured with calipers and a 3D scanner (RaptorX).

| | Setting | Result |
|---|---|---|
| Isolation, 30° V-bit (Sorotec LGS.0030) | Z −0.10, `mill-diameters=0.25mm`, 2 passes, 12000 rpm, F500 | copper edges at the design within ±0.03 mm; real gap ≈ 0.35 mm |
| Isolation depth | Z −0.05 / −0.15 | −0.05 does not cut through the copper everywhere; −0.15 is no wider |
| Drills 0.8 / 1.0 mm | Z −2.1 (`--max-depth 2.2`) | all holes through (−1.7 was not enough) |
| Outline | 2 mm diamond corn mill, Z −1.7, 0.3 mm per pass, 4 tabs | ok |
| Z / auto-leveling | | measured depths within ±0.01 mm of nominal |

Design rules from this: track and copper clearance **≥ 0.25 mm**, pads ≥ 0.5 mm, holes ≥ 0.8 mm.

## Install / build

```bash
python main.py                         # from source (Linux: needs python3-tkinter for the GUI)
python -m unittest discover -s tests   # tests
./setup_linux.sh                       # one-file binary with PyInstaller (GUI without args, CLI with args)
setup_win.bat                          # Windows: GUI .exe (windowed) + "-cli" .exe (console)
```
On Windows the windowed GUI `.exe` cannot print to a console – use the `-cli` `.exe` for the command line.

## Project layout

| Path | |
|---|---|
| `main.py` | entry point: arguments → CLI, none → GUI |
| `carvera_pp/core.py` | parsing, tool blocks, Carvera rules, check, preview (no GUI code) |
| `carvera_pp/cli.py`, `carvera_pp/gui.py` | the two front ends |
| `docs/CLI.md` | full command line reference |
| `AGENTS.md` | how AI agents use the tool (commands, checks, what to report, machine data) |
| `examples/millproject_carvera` | pcb2gcode configuration for the Happylab tools, checked on the machine |
| `tests/` | unit tests. `tests/data/pcb2gcode_ecc83` = real pcb2gcode output (KiCad demo *ecc83*, bottom side). `tests/data/flatcam` = real FlatCAM 8.993 exports (Einschulung board, Toolchange off). `tests/data/flatcam_toolchange` = synthetic file after FlatCAM's `default` preprocessor with Toolchange on |

## Development

Core logic in `carvera_pp/core.py` (no GUI code), front ends in `cli.py` / `gui.py`, only the Python standard
library. Run the tests before every commit: `python -m unittest discover -s tests` (also run by GitHub Actions on
Ubuntu and Windows). Rules that must not break and notes for developers / coding agents: [CLAUDE.md](CLAUDE.md).
Agents that only *use* the tool: [AGENTS.md](AGENTS.md).

## Changes in 2.0.0

- command line interface next to the GUI, one shared core
- pcb2gcode support (folder input, order, origin, tool detection)
- **inserts the tool change for FlatCAM files without `T` word** (Toolchange off): before, such files were merged
  without any tool change (see the old `kombi.nc`: no `T…M6` at all)
- slot + spindle speed per file; missing speed (`M03` without `S`) gets a default and is reported
- files with several tool changes are split per tool (FlatCAM Toolchange on, pcb2gcode drill files)
- removes the `M0` pause after tool changes (it was kept before) and other leftovers
- spindle restarted with the right speed after every tool change; one tool change for a repeated tool
- safety check, preview, ASCII output, `M30`
- documentation: full CLI reference (`docs/CLI.md`), agent guide (`AGENTS.md`), checked pcb2gcode config (`examples/`)
