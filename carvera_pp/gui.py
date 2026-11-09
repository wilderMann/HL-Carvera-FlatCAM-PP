"""tkinter GUI (used when main.py is started without arguments, e.g. double click / windowed .exe)."""
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import APP_NAME, VERSION
from .core import (GCodeError, GCodeFile, Job, Options, SLOTS, TOOL_COLORS, bounds, check, cutter_radius,
                   load_pcb2gcode_dir, preview_svg, toolpaths, DUMMY_TOOL)


class App:
    def __init__(self, root):
        self.root = root
        self.job = Job()
        self.lines = []
        self.var_home = tk.IntVar(value=1)
        self.var_tool6 = tk.IntVar(value=1)
        self.var_origin = tk.IntVar(value=0)
        self.var_slot = tk.StringVar()
        self.var_rpm = tk.StringVar()
        self.selected = None              # (file_index, block_index or None)
        self._build_gui()
        self.refresh()

    # ------------------------------------------------------------------ layout
    def _build_gui(self):
        r = self.root
        r.title(f"{APP_NAME} v{VERSION}")
        r.minsize(980, 560)
        left = ttk.Frame(r, padding=8)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(r, padding=8)
        right.pack(side=tk.LEFT, fill=tk.BOTH)

        cols = ("tool", "rpm", "depth", "slot")
        self.tree = ttk.Treeview(left, columns=cols, height=16, selectmode="browse")
        for c, t, w in (("#0", "Datei / Reihenfolge", 230), ("tool", "Werkzeug", 190), ("rpm", "Drehzahl", 70),
                        ("depth", "Tiefe mm", 70), ("slot", "Slot", 50)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, anchor=tk.W if c in ("#0", "tool") else tk.E)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        bar = ttk.Frame(left)
        bar.pack(fill=tk.X, pady=6)
        for text, cmd in (("Öffnen", self.open_files), ("pcb2gcode-Ordner", self.open_p2g_dir),
                          ("Entfernen", self.remove_file), ("↑", lambda: self.move(-1)), ("↓", lambda: self.move(1)),
                          ("Slots automatisch", self.auto_slots)):
            ttk.Button(bar, text=text, command=cmd).pack(side=tk.LEFT, padx=2)

        det = ttk.LabelFrame(left, text="Details", padding=6)
        det.pack(fill=tk.X)
        self.details = ttk.Label(det, text="", justify=tk.LEFT, font=("TkFixedFont", 9))
        self.details.pack(side=tk.LEFT, anchor=tk.NW)
        sl = ttk.Frame(det)
        sl.pack(side=tk.RIGHT, anchor=tk.NE)
        ttk.Label(sl, text="Werkzeug-Slot (ATC):").pack(anchor=tk.W)
        self.slot_box = ttk.Combobox(sl, textvariable=self.var_slot, values=[str(s) for s in SLOTS], width=5,
                                     state="disabled")
        self.slot_box.pack(anchor=tk.W)
        self.slot_box.bind("<<ComboboxSelected>>", self.on_slot)
        ttk.Label(sl, text="Drehzahl (RPM):").pack(anchor=tk.W, pady=(6, 0))
        self.rpm_box = ttk.Spinbox(sl, textvariable=self.var_rpm, from_=1000, to=15000, increment=1000, width=7,
                                   state="disabled", command=self.on_rpm)
        self.rpm_box.pack(anchor=tk.W)
        self.rpm_box.bind("<Return>", self.on_rpm)
        self.rpm_box.bind("<FocusOut>", self.on_rpm)

        self.canvas = tk.Canvas(right, width=440, height=320, bg="white", highlightthickness=1,
                                highlightbackground="#999")
        self.canvas.pack()
        self.legend = ttk.Label(right, text="", justify=tk.LEFT)
        self.legend.pack(anchor=tk.W, pady=4)
        opts = ttk.LabelFrame(right, text="Optionen", padding=6)
        opts.pack(fill=tk.X)
        ttk.Checkbutton(opts, text="Endposition anfahren (M496.1)", variable=self.var_home,
                        command=self.refresh).pack(anchor=tk.W)
        ttk.Checkbutton(opts, text=f"Mit Werkzeug {DUMMY_TOOL} (Dummy) enden", variable=self.var_tool6,
                        command=self.refresh).pack(anchor=tk.W)
        ttk.Checkbutton(opts, text="Nullpunkt nach links unten verschieben", variable=self.var_origin,
                        command=self.refresh).pack(anchor=tk.W)
        self.status = ttk.Label(right, text="", justify=tk.LEFT, wraplength=440)
        self.status.pack(anchor=tk.W, pady=6, fill=tk.X)
        ttk.Button(right, text="Zusammenführen und Speichern", command=self.save).pack(fill=tk.X, pady=4)

    # ------------------------------------------------------------------ data
    def _add(self, files):
        self.job.files += files
        if any(f.fmt == "pcb2gcode" for f in files):
            self.var_origin.set(1)
        self.job.auto_assign()
        self.refresh()

    def open_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("G-Code", "*.nc *.ngc *.gcode *.tap *.cnc"), ("Alle", "*")])
        files = []
        for p in paths:
            try:
                files.append(GCodeFile(p))
            except (GCodeError, OSError) as e:
                messagebox.showerror("Fehler", str(e))
        self._add(files)

    def open_p2g_dir(self):
        d = filedialog.askdirectory(title="pcb2gcode Ausgabeordner")
        if d:
            try:
                self._add(load_pcb2gcode_dir(d))
            except GCodeError as e:
                messagebox.showerror("Fehler", str(e))

    def remove_file(self):
        if self.selected is None:
            messagebox.showinfo("Fehler", "Keine Datei ausgewählt!")
            return
        self.job.files.pop(self.selected[0])
        self.selected = None
        self.refresh()

    def move(self, d):
        if self.selected is None:
            return
        i, j = self.selected[0], self.selected[0] + d
        if 0 <= j < len(self.job.files):
            fs = self.job.files
            fs[i], fs[j] = fs[j], fs[i]
            self.selected = (j, None)
            self.refresh()

    def auto_slots(self):
        self.job.auto_assign()
        self.refresh()

    def on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        parts = sel[0].split(":")
        self.selected = (int(parts[1]), int(parts[2]) if len(parts) > 2 else None)
        self.show_details()

    def _sel_block(self):
        if self.selected is None:
            return None
        f = self.job.files[self.selected[0]]
        if self.selected[1] is not None:
            return f.blocks[self.selected[1]]
        return f.blocks[0] if len(f.blocks) == 1 else None

    def on_rpm(self, _=None):
        b = self._sel_block()
        if b is None:
            return
        try:
            v = float(self.var_rpm.get())
        except ValueError:
            return
        if v != b.rpm:
            b.rpm, b.rpm_default = v, False
            self.refresh()

    def on_slot(self, _):
        b = self._sel_block()
        if b is not None:
            b.slot = int(self.var_slot.get())
            self.refresh()

    # ------------------------------------------------------------------ view
    def show_details(self):
        if self.selected is None:
            self.details.config(text="")
            self.slot_box.config(state="disabled")
            self.rpm_box.config(state="disabled")
            return
        f = self.job.files[self.selected[0]]
        v = lambda x: "-" if x is None else f"{x:g}"
        txt = (f"Name: {f.name}   ({f.fmt})\nGröße: {f.size_kb} KB   Zeilen: {f.line_count}   "
               f"Reihenfolge: {self.selected[0] + 1}\n")
        if f.fmt == "flatcam":
            txt += (f"Spindel: {v(f.spindle_speed)} RPM   Vorschub XY: {v(f.feedrate_xy)}   "
                    f"Vorschub Z: {v(f.feedrate_z)}   Schnitttiefe: {v(f.z_cut)} mm\n")
        b = self._sel_block()
        if b is not None:
            src = f"in Datei {b.tool_ref}" if b.orig_tool else "ganze Datei = ein Werkzeug"
            txt += (f"Werkzeug: {b.label} ({src})   Tiefe: {v(b.depth())} mm\n"
                    + ("Drehzahl stand NICHT in der Datei - Standardwert, bitte prüfen!\n" if b.rpm_default else "")
                    + b.info)
            self.var_slot.set(str(b.slot or ""))
            self.var_rpm.set(f"{b.rpm:.0f}" if b.rpm else "")
            self.slot_box.config(state="readonly")
            self.rpm_box.config(state="normal")
        else:
            txt += "Mehrere Werkzeuge in dieser Datei - zum Ändern ein Werkzeug auswählen."
            self.slot_box.config(state="disabled")
            self.rpm_box.config(state="disabled")
        self.details.config(text=txt)

    def _options(self):
        is_p2g = any(f.fmt == "pcb2gcode" for f in self.job.files)
        return Options(goto_clearance=bool(self.var_home.get()), end_with_dummy=bool(self.var_tool6.get()),
                       origin="lower-left" if self.var_origin.get() else "keep",
                       origin_margin=cutter_radius(self.job.files) if is_p2g else 0.0)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        def vals(b):
            d = b.depth()
            return (b.label, (f"{b.rpm:.0f}" + ("*" if b.rpm_default else "")) if b.rpm else "-",
                    f"{d:.3f}" if d is not None else "-", f"T{b.slot}" if b.slot else "-")
        for i, f in enumerate(self.job.files):
            if len(f.blocks) == 1:            # normal FlatCAM case: one file = one tool -> one row
                self.tree.insert("", tk.END, iid=f"f:{i}", text=f"{i + 1}. {f.name}", values=vals(f.blocks[0]))
                continue
            fid = self.tree.insert("", tk.END, iid=f"f:{i}", text=f"{i + 1}. {f.name}", open=True)
            for k, b in enumerate(f.blocks):
                self.tree.insert(fid, tk.END, iid=f"b:{i}:{k}", text=f"   {b.tool_ref}", values=vals(b))
        if self.selected is not None and self.selected[0] < len(self.job.files):
            iid = f"f:{self.selected[0]}" if self.selected[1] is None else f"b:{self.selected[0]}:{self.selected[1]}"
            if self.tree.exists(iid):
                self.tree.selection_set(iid)
        else:
            self.selected = None
        self.show_details()
        self.job.options = self._options()
        self.lines, msg = [], ""
        if self.job.files:
            try:
                self.lines = self.job.build()
                probs, st = check(self.lines, self.job.options.max_depth)
                notes = self.job.notes()
                msg = (f"Prüfung: {'OK' if not probs else 'FEHLER'}   Schnittweg {st['feed_mm'] / 1000:.2f} m, "
                       f"ca. {st['time_min']:.0f} min, tiefste Z {st['zmin']:.2f}")
                if probs:
                    msg += "\n" + "\n".join(probs[:6])
                if notes:
                    msg += "\n* " + "\n* ".join(notes)
            except GCodeError as e:
                msg = "Nicht speicherbar:\n" + str(e)
        ok = msg.startswith("Prüfung: OK")
        self.status.config(text=msg, foreground="#c62828" if not ok else "#e65100" if "\n* " in msg else "#2e7d32")
        self.draw()

    def draw(self):
        c = self.canvas
        c.delete("all")
        rack = {}
        for b in self.job.blocks:
            rack.setdefault(b.slot, b.label)
        self.legend.config(text="  ".join(f"T{s}: {lab}" for s, lab in sorted(rack.items()) if s))
        if not self.lines:
            c.create_text(220, 160, text="Dateien öffnen …", fill="#999")
            return
        b = bounds(self.lines)
        if not b:
            return
        W, H = int(c["width"]), int(c["height"])
        sc = min((W - 20) / max(b[2] - b[0], 1e-3), (H - 20) / max(b[3] - b[1], 1e-3))
        X = lambda x: 10 + (x - b[0]) * sc
        Y = lambda y: H - 10 - (y - b[1]) * sc
        if self.var_origin.get():
            c.create_line(X(0) - 8, Y(0), X(0) + 8, Y(0), fill="#000")
            c.create_line(X(0), Y(0) - 8, X(0), Y(0) + 8, fill="#000")
        for t, kind, d in toolpaths(self.lines):
            col = TOOL_COLORS.get(t, "#000")
            if kind == "feed":
                c.create_line(X(d[0][0]), Y(d[0][1]), X(d[1][0]), Y(d[1][1]), fill=col)
            elif kind == "hole":
                c.create_oval(X(d[0]) - 2, Y(d[1]) - 2, X(d[0]) + 2, Y(d[1]) + 2, fill=col, outline=col)
            elif kind == "arc":
                r = d[2] * sc
                c.create_oval(X(d[0]) - r, Y(d[1]) - r, X(d[0]) + r, Y(d[1]) + r, outline=col)

    def save(self):
        if not self.job.files:
            messagebox.showinfo("Fehler", "Keine Dateien geladen!")
            return
        try:
            lines = self.job.build()
        except GCodeError as e:
            messagebox.showerror("Nicht speicherbar", str(e))
            return
        probs, st = check(lines, self.job.options.max_depth)
        if probs and not messagebox.askyesno("Prüfung fehlgeschlagen",
                                             "\n".join(probs[:10]) + "\n\nTrotzdem speichern? (nicht empfohlen)",
                                             icon="warning", default="no"):
            return
        path = filedialog.asksaveasfilename(defaultextension=".nc", filetypes=[("G-Code", "*.nc")],
                                            initialfile="carvera_job.nc")
        if not path:
            return
        with open(path, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        preview_svg(lines, os.path.splitext(path)[0] + "_preview.svg")
        rack = {}
        for b in self.job.blocks:
            rack.setdefault(b.slot, b.label)
        messagebox.showinfo("Gespeichert", f"{path}\n\nWerkzeuge einsetzen:\n" +
                            "\n".join(f"  T{s}: {lab}" for s, lab in sorted(rack.items())) +
                            (f"\n  T{DUMMY_TOOL}: Dummy" if self.var_tool6.get() else "") +
                            f"\n\nca. {st['time_min']:.0f} min Schnittzeit. Auto-Leveling verwenden und beobachten!")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
