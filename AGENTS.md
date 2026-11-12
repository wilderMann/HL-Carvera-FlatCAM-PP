# Using the post-processor as an AI agent

This file is for agents (Claude Code, other LLM tools, scripts) that **use** this post-processor to make G-code for
the Happylab Makera Carvera. Notes for changing the code itself are in [CLAUDE.md](CLAUDE.md). The full option reference
is in [docs/CLI.md](docs/CLI.md).

The tool is a plain command line program, standard library only:
`python3 main.py ...` (or the `…-cli` binary). There is no network and no state between runs.

## 1. Decide which input you have

| The user has … | Do |
|---|---|
| a **KiCad board** | export Gerbers + drill file (`kicad-cli pcb export gerbers` / `drill`), then pcb2gcode (row below) |
| **Gerbers** from any EDA tool | `pcb2gcode --config millproject_carvera …`, then `main.py --pcb2gcode DIR` |
| **FlatCAM G-code files** (one per tool, Happylab workflow) | `main.py --list FILES`, then `main.py FILES --slot … --rpm …` |
| an existing **pcb2gcode output folder** | `main.py --pcb2gcode DIR` |

Don't write your own CAM code. pcb2gcode does the CAM; this tool only adapts the G-code to the Carvera. pcb2gcode
has its own MCP server (`pcb2gcode --mcp`) if your client supports MCP.

## 2. Standard commands

```bash
# pcb2gcode route (single-sided board, copper on the bottom = mirrored; use --front for top copper)
pcb2gcode --config examples/millproject_carvera --back B_Cu.gbr --drill board.drl --outline Edge_Cuts.gbr --output-dir p2g
python3 main.py --pcb2gcode p2g -o board_bottom.nc --preview --max-depth 2.2

# FlatCAM route
python3 main.py --list iso.nc drill.nc cutout.nc            # 1. look
python3 main.py iso.nc drill.nc cutout.nc -o board.nc --preview --slot ... --rpm ...   # 2. build
```

`examples/millproject_carvera` holds the pcb2gcode settings that were checked on the real machine (§5).

## 3. Check every run (mandatory)

1. **The exit code is 0 and the output contains `Check: OK`.** Exit 1 = input problem, exit 2 = safety check
   failed. **Never hand a file to the user that failed, and never use `--force` on your own.** Explain the
   `!! …` lines and fix the cause, or ask the user.
2. **Read the pcb2gcode log** if pcb2gcode was used:
   - `rounded to` – holes made bigger or smaller (vias 0.3 → 0.8 mm!). Tell the user.
   - `hasn't been able to fulfill all clearance requirements` – copper too close for the V-bit. Short circuits are
     possible. Show `contentions_*.svg` and suggest more clearance in the design.
   - `unconnected loop` – the outline isn't closed, so the job is **incomplete**. Fix it before going on.
3. **Look at the preview SVG.** Check that every pad has isolation, holes sit on pads, the outline goes all the way
   around with tabs, and the board is mirrored for bottom copper.
4. **Check the tool table.** At most 5 tools (slots 1–5). Any rpm marked `*` (default, not from the file) needs a
   decision: check it, or set `--rpm`.

## 4. Tell the user

- **The output path** of the `.nc` and the preview.
- **The tool rack**: which tool goes into which slot, from the `Tool rack:` lines. Slot 6 always holds the dummy
  tool.
- **Any warnings** from steps 2–4 above.
- **The origin.** X0 Y0 is the board's lower-left corner by default. If you used `--origin-margin`, give the exact
  offset to the blank corner.
- **Machine steps:**
  1. Load the tools as listed.
  2. Fix the blank with the copper side up.
  3. Set the work origin.
  4. Turn on **Auto-Leveling** (the isolation is only 0.1 mm deep).
- **Don't give cutting time estimates.** That's a user decision: tool changes and auto-leveling make them wrong.
  Cutting path length and deepest Z are fine. If the user explicitly asks for a time, give it as a rough range and
  say what it leaves out.

## 5. Machine data checked on the Carvera (Happylab, 2026-11)

| What | Value | Why |
|---|---|---|
| V-bit | Sorotec VHM Frässtichel 30° (LGS.0030), 12000 rpm, F500, plunge F200 | Happylab tool, Makera "Single Flute Engraving 30°" PCB preset |
| Isolation | `zwork=-0.10`, `mill-diameters=0.25mm`, `isolation-width=0.44mm` (2 passes) | calibration board + 3D scan: copper edges at design ±0.03 mm. Z-0.05 doesn't cut through the copper everywhere. Z-0.15 gives no gain. |
| Real isolation gap | about 0.35 mm (the 2nd pass cuts less) | 3D scan |
| Smallest copper gap that can be isolated | about 0.25 mm. Design clearance should be ≥ 0.25 mm (tracks), ≥ 0.5 mm (pads). | groove width |
| Drills | 0.8 / 1.0 / 1.4 mm, `zdrill=-2.1` (1.6 board + drill tip + margin), 10000 rpm, F200 → run this tool with `--max-depth 2.2` | −1.7 left holes closed. −2.1: all holes through. |
| Outline | 2 mm diamond corn mill, `zcut=-1.7`, 0.3 mm per pass, 12000 rpm, F500, 4 tabs | Makera PCB preset. Use the 1 mm mill if the board also has milled holes ≥ 1.55 mm (otherwise 6 tools > 5 slots). |
| Spindle | ≤ 15000 rpm | Carvera max |

If the user has a different bit or material, suggest milling a calibration board first: a few 10 mm squares
isolated at 2–3 depths. Measure them with calipers or a 3D scan, then adjust `mill-diameters`.

## 6. Common pitfalls

- **More than 5 tools.** For example V-bit, three drill sizes, 1 mm mill for holes and a 2 mm outline mill. Use one mill
  for both milled holes and outline, or drop a drill size (pcb2gcode `drills-available`).
- **Blank bigger than the board.** To put the job inside the blank (away from the clamps) with X0 Y0 at the blank's
  corner, use a **negative** `--origin-margin=-(edge distance − cutter radius)`, for example `=-9` for a 10 mm
  edge with a 2 mm mill. Then check the extents in the G-code.
- **FlatCAM files without speed.** A bare `M03` gets the Makera default (`*` in the table). FlatCAM files are often
  15000 rpm, which is the machine maximum. Don't change speeds without the user.
- **Inch files are refused.** Ask the user to set FlatCAM to mm.
- **pcb2gcode with KiCad outlines** needs line ends joined within 25 µm. Stock pcb2gcode uses 2.5 µm, so the outline
  can come out empty. Use the patched build or check for `unconnected loop`. If Edge.Cuts uses several line widths,
  give all apertures the same width.
- **Big dense boards with copper pours** can make pcb2gcode use > 12 GB RAM. Run one board at a time.
