"""Tests: python -m unittest discover -s tests   (no extra packages needed)"""
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from carvera_pp.core import (GCodeError, GCodeFile, Job, Options, check, code_of, cutter_radius,  # noqa: E402
                             load_pcb2gcode_dir, bounds)

FC = os.path.join(ROOT, "tests", "data", "flatcam")              # real FlatCAM 8.993 exports, Toolchange off
FC_TC = os.path.join(ROOT, "tests", "data", "flatcam_toolchange")  # synthetic: FlatCAM default pp WITH tool changes
P2G = os.path.join(ROOT, "tests", "data", "pcb2gcode_ecc83")
FC_FILES = ["Einschulung Carvera-F_Cu.gbr_0.1575_iso3_cnc.nc", "2Einschulung Carvera.drl_cnc.nc",
            "3Einschulung Carvera.drl_mill_cnc.nc", "4Einschulung Carvera-Edge_Cuts.gbr_cutout_cnc.nc"]


def flatcam_job(**opt):
    j = Job([GCodeFile(os.path.join(FC, n)) for n in FC_FILES], Options(**opt))
    j.auto_assign()
    return j


def codes(lines):
    return [code_of(l) for l in lines if code_of(l)]


class FlatCAM(unittest.TestCase):
    """Happylab workflow: one FlatCAM file per tool, no T word in the files."""

    def test_one_file_one_tool(self):
        j = flatcam_job()
        self.assertEqual([len(f.blocks) for f in j.files], [1, 1, 1, 1])
        self.assertEqual([(b.kind, b.dia, b.slot) for b in j.blocks],
                         [("vbit", 0.1575, 1), ("drill", None, 2), ("mill", 2.0, 3), ("mill", 2.0, 3)])

    def test_missing_speed_gets_default_and_is_reported(self):
        j = flatcam_job()
        self.assertEqual([b.rpm for b in j.blocks], [15000, 10000, 12000, 15000])
        self.assertEqual([b.rpm_default for b in j.blocks], [False, True, True, False])
        self.assertEqual(len(j.notes()), 2)

    def test_carvera_rules(self):
        out = flatcam_job().build()
        c = codes(out)
        self.assertEqual([x for x in c if x.startswith("T")], ["T1M6", "T2M6", "T3M6", "T6M6"])  # 2 mm mill once
        self.assertFalse([x for x in c if re.match(r"^M0?[01]\b", x)], "no M0/M1 pauses")
        self.assertFalse([x for x in c if re.fullmatch(r"M0?3", x)], "no bare M03 without speed")
        self.assertEqual(c[-4:], ["M5", "M496.1", "T6M6", "M30"])
        self.assertEqual(check(out)[0], [])

    def test_same_mill_other_speed(self):
        c = codes(flatcam_job().build())
        i = c.index("T3M6")
        self.assertEqual(c[i + 1], "S12000 M3")
        self.assertIn("S15000 M3", c[i + 2:])              # cutout file: speed change, no tool change

    def test_spindle_restarted_after_each_change(self):
        c = codes(flatcam_job().build())
        for i, x in enumerate(c):
            if re.fullmatch(r"T[1-5]M6", x):
                self.assertRegex(c[i + 1], r"^S\d+ M3$")

    def test_options_off(self):
        c = codes(flatcam_job(goto_clearance=False, end_with_dummy=False).build())
        self.assertNotIn("M496.1", c)
        self.assertNotIn("T6M6", c)

    def test_different_tools_in_one_slot_refused(self):
        j = flatcam_job()
        j.blocks[1].slot = 3                               # drill into the 2 mm mill's slot
        with self.assertRaises(GCodeError):
            j.build()

    def test_invalid_slot(self):
        j = flatcam_job()
        j.blocks[0].slot = 6
        with self.assertRaises(GCodeError):
            j.build()

    def test_ascii_output(self):
        "\n".join(flatcam_job().build()).encode("ascii")

    def test_with_toolchange(self):
        """FlatCAM with Toolchange on: T/M6/MSG/M0 block is replaced, each drill gets its own slot."""
        f = GCodeFile(os.path.join(FC_TC, "drill_3tools.nc"))
        self.assertEqual([(b.orig_tool, b.dia, b.rpm) for b in f.blocks], [(1, 0.8, 15000), (2, 1.0, 15000), (3, 1.4, 12000)])
        j = Job([f]); j.auto_assign()
        c = codes(j.build())
        self.assertEqual([x for x in c if x.startswith("T")], ["T1M6", "T2M6", "T3M6", "T6M6"])
        self.assertFalse([x for x in c if re.match(r"^M0?[016]$", x)])

    def test_inch_rejected(self):
        with self.assertRaises(GCodeError):
            GCodeFile("x.nc", text="G20\nT1\nM6\nM03 S1000\nG01 X1 Y1\n")

    def test_not_gcode_rejected(self):
        with self.assertRaises(GCodeError):
            GCodeFile("x.nc", text="hello world\n")


class Pcb2gcode(unittest.TestCase):
    def setUp(self):
        self.files = load_pcb2gcode_dir(P2G)
        self.job = Job(self.files, Options(origin="lower-left", origin_margin=cutter_radius(self.files)))
        self.job.auto_assign()

    def test_order_and_tools(self):
        self.assertEqual([f.name for f in self.files], ["back.ngc", "drill.ngc", "milldrill.ngc", "outline.ngc"])
        self.assertEqual(sorted({b.slot for b in self.job.blocks}), [1, 2, 3, 4, 5])
        mills = [b for b in self.job.blocks if b.kind == "mill"]
        self.assertEqual({b.slot for b in mills}, {5})   # milldrill + outline share the 1 mm mill

    def test_origin_is_board_corner(self):
        out = self.job.build()
        b = bounds(out, feed_only=True)
        self.assertAlmostEqual(b[0], -0.5, places=3)     # outline path = board edge - cutter radius
        self.assertAlmostEqual(b[1], -0.5, places=3)
        self.assertAlmostEqual(b[2] - 0.5, 52.07, places=2)   # ecc83 board width in KiCad

    def test_check_ok_and_no_pcb2gcode_leftovers(self):
        out = self.job.build()
        self.assertEqual(check(out)[0], [])
        c = codes(out)
        self.assertFalse([x for x in c if re.match(r"^(G0?4 P0|G91\.1|M0\b|M2\b|M9\b)", x)])
        self.assertEqual(len([x for x in c if x == "T5M6"]), 1)  # one change for milldrill + outline


class Check(unittest.TestCase):
    def test_detects_problems(self):
        bad = ["T1", "M6", "S20000 M3", "G00 Z-1", "M0", "G01 Z-3 F100"]
        probs = check(bad)[0]
        text = "\n".join(probs)
        for needle in ("T<n>M6", "Eilgang", "M0/M1", "20000", "tiefer"):
            self.assertIn(needle, text)


class CLI(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, os.path.join(ROOT, "main.py"), *args], capture_output=True, text=True)

    def test_flatcam_cli(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "job.nc")
            r = self.run_cli(*[os.path.join(FC, n) for n in FC_FILES], "-o", out, "--preview",
                             "--rpm", "2Einschulung Carvera.drl_cnc.nc=12000")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(os.path.exists(out) and os.path.exists(os.path.join(d, "job_preview.svg")))
            with open(out) as fh:
                self.assertEqual(fh.read().count("S12000 M3"), 2)

    def test_pcb2gcode_cli(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli("--pcb2gcode", P2G, "-o", os.path.join(d, "b.nc"))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("Check: OK", r.stdout)

    def test_slot_per_file_and_conflict(self):
        files = [os.path.join(FC, n) for n in FC_FILES]
        r = self.run_cli(*files, "--slot", "2Einschulung Carvera.drl_cnc.nc=5", "--list")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r"2Einschulung Carvera.drl_cnc.nc .* T5")
        r = self.run_cli(*files, "--slot", "2Einschulung Carvera.drl_cnc.nc=1", "-o", os.devnull)
        self.assertEqual(r.returncode, 1)
        self.assertIn("verschiedene Werkzeuge", r.stderr)


if __name__ == "__main__":
    unittest.main()
