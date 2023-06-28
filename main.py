import tkinter as tk
from tkinter import filedialog
import re

class GCodeFile:
    def __init__(self, file_path):
        self.file_path = file_path
        self.name = file_path.split("/")[-1]
        self.size = self.get_file_size()
        self.line_count = 0
        self.tool = ""
        self.spindle_speed = ""
        self.feedrate_xy = ""
        self.feedrate_z = ""
        self.z_cut = ""
        self.gcode_content = ""
        self.analyze_file()

    def get_file_size(self):
        return round((len(open(self.file_path).read()) / 1024), 2)

    def analyze_file(self):
        with open(self.file_path, "r") as file:
            gcode_lines = file.readlines()
            self.line_count = len(gcode_lines)
            for line in gcode_lines:
                if line.startswith("T"):
                    self.tool = re.search(r"T(\d+)", line).group(1)
                elif re.search(r"Spindle Speed:\s*([\d.-]+)", line):
                    self.spindle_speed = re.search(r"Spindle Speed:\s*([\d.-]+)", line).group(1)
                elif re.search(r"Feedrate_XY:\s*([\d.-]+)", line):
                    self.feedrate_xy = re.search(r"Feedrate_XY:\s*([\d.-]+)", line).group(1)
                elif re.search(r"Feedrate_Z:\s*([\d.-]+)", line):
                    self.feedrate_z = re.search(r"Feedrate_Z:\s*([\d.-]+)", line).group(1)
                elif re.search(r"Z_Cut:\s*(-[\d.]+)", line):
                    self.z_cut = re.search(r"Z_Cut:\s*(-[\d.]+)", line).group(1)
                if line.startswith("T"):
                    if "M6" not in line:
                        self.gcode_content += line.replace("\n","M6\n")
                elif line.startswith("M6"):
                    pass
                else:
                    self.gcode_content += line
class GCodeAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.file_list = []
        self.selected_file = None
        self.file_listbox = None
        self.details_frame = None
        self.name_label = None
        self.size_label = None
        self.line_count_label = None
        self.order_label = None
        self.spindle_speed_label = None
        self.feedrate_xy_label = None
        self.feedrate_z_label = None
        self.z_cut_label = None
        self.tool_label = None
        self.tool_var = None
        self.tool_dropdown = None
        self.open_button = None
        self.close_button = None
        self.move_up_button = None
        self.move_down_button = None
        self.merge_button = None
        self.create_gui()

    def create_gui(self):
        self.root.title("Happylab Carvera GCode Merger")
        self.file_listbox = tk.Listbox(self.root)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_selected)

        self.details_frame = tk.Frame(self.root)
        self.details_frame.pack(side=tk.LEFT, fill=tk.BOTH, padx=10, pady=10)

        self.name_label = tk.Label(self.details_frame, text="Name:")
        self.name_label.pack(anchor=tk.W)
        self.size_label = tk.Label(self.details_frame, text="Größe (KB):")
        self.size_label.pack(anchor=tk.W)
        self.line_count_label = tk.Label(self.details_frame, text="Anzahl der Zeilen:")
        self.line_count_label.pack(anchor=tk.W)
        self.order_label = tk.Label(self.details_frame, text="Reihenfolge:")
        self.order_label.pack(anchor=tk.W)
        self.spindle_speed_label = tk.Label(self.details_frame, text="Spindel Drehzahl (RPM):")
        self.spindle_speed_label.pack(anchor=tk.W)
        self.feedrate_xy_label = tk.Label(self.details_frame, text="Vorschub XY (mm/min):")
        self.feedrate_xy_label.pack(anchor=tk.W)
        self.feedrate_z_label = tk.Label(self.details_frame, text="Vorschub Z (mm/min):")
        self.feedrate_z_label.pack(anchor=tk.W)
        self.z_cut_label = tk.Label(self.details_frame, text="Schnitttiefe (mm):")
        self.z_cut_label.pack(anchor=tk.W)
        self.tool_label = tk.Label(self.details_frame, text="Werkzeug:")
        self.tool_label.pack(anchor=tk.W)

        self.tool_var = tk.StringVar(self.root)
        self.tool_dropdown = tk.OptionMenu(self.details_frame, self.tool_var, *range(1, 7), command=self.on_tool_selected)
        self.tool_dropdown.pack(anchor=tk.W)
        self.tool_dropdown.configure(state="disabled")

        self.open_button = tk.Button(self.root, text="Öffnen", command=self.open_files)
        self.open_button.pack(pady=10)
        self.close_button = tk.Button(self.root, text="Schließen", command=self.close_file)
        self.close_button.pack(pady=10)
        self.move_up_button = tk.Button(self.root, text="↑", command=self.move_file_up)
        self.move_up_button.pack(pady=5)
        self.move_down_button = tk.Button(self.root, text="↓", command=self.move_file_down)
        self.move_down_button.pack(pady=5)
        self.merge_button = tk.Button(self.root, text="Zusammenführen und Speichern", command=self.merge_and_save)
        self.merge_button.pack(pady=10)

    def open_files(self):
        file_paths = filedialog.askopenfilenames(filetypes=[("GCode Files", "*.nc")])
        for file_path in file_paths:
            gcode_file = GCodeFile(file_path)
            self.file_list.append(gcode_file)
            self.file_listbox.insert(tk.END, gcode_file.name)

    def close_file(selfs):

        self.selected_file = None

    def on_file_selected(self, event):
        selected_index = self.file_listbox.curselection()
        if selected_index:
            self.selected_file = self.file_list[selected_index[0]]
            self.display_file_details()

    def display_file_details(self):
        self.name_label.config(text="Name: " + self.selected_file.name)
        self.size_label.config(text="Größe (KB): " + str(self.selected_file.size))
        self.line_count_label.config(text="Anzahl der Zeilen: " + str(self.selected_file.line_count))
        self.order_label.config(text="Reihenfolge: " + str(self.file_list.index(self.selected_file) + 1))
        self.spindle_speed_label.config(text="Spindel Drehzahl (RPM): " + str(self.selected_file.spindle_speed))
        self.feedrate_xy_label.config(text="Vorschub XY (mm/min): " + str(self.selected_file.feedrate_xy))
        self.feedrate_z_label.config(text="Vorschub Z (mm/min): " + str(self.selected_file.feedrate_z))
        self.z_cut_label.config(text="Schnitttiefe (mm): " + str(self.selected_file.z_cut))
        self.tool_var.set(self.selected_file.tool)
        self.tool_dropdown.configure(state="normal")

    def on_tool_selected(self, tool):
        self.selected_file.tool = tool

    def move_file_up(self):
        selected_index = self.file_listbox.curselection()
        if selected_index and selected_index[0] > 0:
            self.file_list.insert(selected_index[0] - 1, self.file_list.pop(selected_index[0]))
            self.file_listbox.delete(0, tk.END)
            for file in self.file_list:
                self.file_listbox.insert(tk.END, file.name)
            self.file_listbox.selection_clear(0, tk.END)
            self.file_listbox.selection_set(selected_index[0] - 1)
            self.selected_file = self.file_list[selected_index[0] - 1]
            self.display_file_details()

    def move_file_down(self):
        selected_index = self.file_listbox.curselection()
        if selected_index and selected_index[0] < len(self.file_list) - 1:
            self.file_list.insert(selected_index[0] + 1, self.file_list.pop(selected_index[0]))
            self.file_listbox.delete(0, tk.END)
            for file in self.file_list:
                self.file_listbox.insert(tk.END, file.name)
            self.file_listbox.selection_clear(0, tk.END)
            self.file_listbox.selection_set(selected_index[0] + 1)
            self.selected_file = self.file_list[selected_index[0] + 1]
            self.display_file_details()

    def goToHome(self):
        coord_x = 351.200
        coord_y = 175.000
        coord_z = 122.000
        movement = "M5\n"
        movement += "G00 Z" + str(coord_z) + "\n"
        movement += "G00 X" + str(coord_x) + " G00 Y" + str(coord_y) + "\n"
        return movement

    def changeT6(self):
        return "T6M6\n"
    def merge_and_save(self):
        merged_content = ""
        for file in self.file_list:
            merged_content += re.sub(r"T\d+", "T" + str(file.tool), file.gcode_content)
        merged_content += str(self.goToHome())
        merged_content += str(self.changeT6())
        save_path = filedialog.asksaveasfilename(filetypes=[("GCode Files", "*.nc")])
        with open(save_path, "w") as file:
            file.write(merged_content)

root = tk.Tk()
app = GCodeAnalyzerApp(root)
root.mainloop()
