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
  off, no rapid move down into the material, no rapid XY move below Z0, nothing deeper than −2.0 mm (bed), job fits
  the Carvera work area (360 × 240 mm). Problems block saving (GUI asks, CLI needs `--force`)
- **preview** of the tool paths (GUI, and `…_preview.svg` next to the saved file) and estimated cutting time
- output is plain ASCII; refuses inch files (`G20`), empty files and files that are not G-code

## GUI

1. **Öffnen** – FlatCAM files (`.nc`), or **pcb2gcode-Ordner** – the output folder of pcb2gcode.
2. Order the files with **↑ ↓**. Each file lists its tools; select a tool and pick its **Werkzeug-Slot**.
   **Slots automatisch** assigns 1, 2, 3 … in order of use.
3. Check the preview and the status line (**Prüfung: OK**).
4. **Zusammenführen und Speichern** – writes the job and `…_preview.svg` and shows which tool goes into which slot.

## Command line

```bash
python main.py --list isolation.nc drill.nc cutout.nc              # show tools + automatic slots
python main.py isolation.nc drill.nc cutout.nc -o board.nc --preview
python main.py isolation.nc drill.nc cutout.nc --slot vbit=1 --slot drill0.8=2 --slot "drill.nc:T3=4" --slot mill1=5
python main.py --pcb2gcode pcb2gcode_out/ -o board_bottom.nc --preview
```

| Option | |
|---|---|
| `--pcb2gcode DIR` | use `front/back.ngc`, `drill.ngc`, `milldrill.ngc`, `outline.ngc` from DIR, in this order |
| `--slot SPEC` | `FILE:T<n>=<slot>` (tool n of that file) or by tool: `vbit=1`, `drill0.8=2`, `mill1=5` |
| `--keep-tool-numbers` | use the T numbers from the files instead of automatic slots |
| `--origin keep\|lower-left`, `--origin-margin MM` | origin shift (default: lower-left + cutter radius for pcb2gcode, keep for FlatCAM) |
| `--no-clearance`, `--no-dummy` | leave out `M496.1` / `T6M6` at the end |
| `--z-change MM` | retract height before tool changes (default 10) |
| `--max-depth MM` | deepest allowed Z (default 2.0) |
| `--preview` | also write `<output>_preview.svg` |
| `--force` | write even if the safety check fails (exit code stays 2) |

Exit codes: `0` ok, `1` input/usage error (nothing written), `2` safety check failed.

## pcb2gcode

[pcb2gcode](https://github.com/pcb2gcode/pcb2gcode) is a command line CAM for PCBs (it also has an MCP server for AI
assistants). With a configuration for the Happylab tools:

```bash
pcb2gcode --config millproject_carvera --back B_Cu.gbr --drill board.drl --outline Edge_Cuts.gbr --output-dir out
python main.py --pcb2gcode out -o board_bottom.nc --preview
```

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
| `tests/` | unit tests. `tests/data/pcb2gcode_ecc83` = real pcb2gcode output (KiCad demo *ecc83*, bottom side). `tests/data/flatcam` = **synthetic** files written after the templates of FlatCAM 8.994's `default` preprocessor – real FlatCAM exports should be added |

## Changes in 2.0.0

- command line interface next to the GUI, one shared core
- pcb2gcode support (folder input, order, origin, tool detection)
- slots per tool instead of per file (multi-drill FlatCAM files used to end up with one tool number for all drills)
- removes the `M0` pause after tool changes (it was kept before) and other leftovers
- spindle restarted with the right speed after every tool change; one tool change for a repeated tool
- safety check, preview, cutting time, ASCII output, `M30`
