# Notes for AI agents / developers

Happylab post-processor: FlatCAM / pcb2gcode G-code -> one Makera Carvera job. User-facing docs: README.md.

## Layout
- `main.py` – entry point. Arguments -> `carvera_pp/cli.py`, none -> `carvera_pp/gui.py` (tkinter, German UI).
- `carvera_pp/core.py` – everything else: `GCodeFile` (parse + split into tool `Block`s), `Job` (slots, build),
  `check()` (simulation), `toolpaths()` / `preview_svg()`. No GUI code in core. Standard library only (PyInstaller).

## Rules that must not break (tests cover them)
- Tool change exactly `T<n>M6` on one line, then `S<rpm> M3`. Slots 1-5 only; 6 = Happylab dummy tool, loaded at the end.
- End: `M5`, `M496.1` (clearance), `T6M6`, `M30`. No `M0`/`M1` anywhere. Max 15000 rpm. Output ASCII only.
- Happylab FlatCAM workflow: **one file = one tool**, FlatCAM "Toolchange" is off -> files have NO `T` word and
  often a bare `M03` without speed. Slot and rpm are set per file in this tool (GUI / `--slot FILE=N`, `--rpm FILE=RPM`).
  Missing speed -> `DEFAULT_RPM` (Makera PCB presets), flagged `rpm_default`, reported – never silently.
- Files WITH several tool changes (pcb2gcode `drill.ngc`, FlatCAM Toolchange on) are split per tool.
- Different tools in one slot -> error. Same tool (kind + diameter) in consecutive blocks -> one tool change.
- Do NOT show cutting time estimates (user decision: tool changes + auto-leveling make them misleading).
  Cutting path length and deepest Z are fine.

## Tests
`python -m unittest discover -s tests` (CI: .github/workflows/tests.yml, Ubuntu + Windows).
`tests/data/flatcam` = real FlatCAM 8.993 exports, `tests/data/pcb2gcode_ecc83` = real pcb2gcode output,
`tests/data/flatcam_toolchange` = synthetic (FlatCAM default preprocessor with Toolchange on).
GUI check without clicking: create `App(tk.Tk())`, `app._add([...])`, screenshot with `import -window`.

## Branches
`cli-gui-pcb2gcode` = v2.0.0 rewrite (CLI + GUI + pcb2gcode), not merged into `master` yet.
