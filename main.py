import tkinter as tk
from tkinter import filedialog, messagebox
import re

END_TOOL = '6'
ENDPOINT_COORD = {'x':348,'y':175.000,'z':122.000}  # Deprecated, only Using Z.
GOTO_CLEARANCE = "M496.1"   # GoTo Clearance, is carvera specific code

APP_NAME = 'Happylab FlatCAM-Carvera Postprozessor'
VERSION = '1.0.1'

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

    def is_gcode(self,line):
        pattern = [r"^G\d.*$"]          # Line starts with G and a digit
        pattern.append(r"^M\d.*$")      # Line starts with M and a digit
        pattern.append(r"^T\d.*$")      # Line starts with T and a digit
        pattern.append(r"^\(.*$")       # Line starts with (
        pattern.append(r"^\s*$")        # Line is Empty or has only spaces and tabs
        for pat in pattern:
            if re.match(pat, line):
                return True
        return False

    def analyze_file(self):
        with open(self.file_path, "r") as file:
            gcode_lines = file.readlines()
            self.line_count = len(gcode_lines)
            if self.line_count == 0:
                raise EOFError("Input File ist leer!")
            for line in gcode_lines:
                if not self.is_gcode(line):
                    raise SyntaxError("Diese Zeile hat falsche Syntax:\n" + str(line))        #Raise error! this is no gcode!
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
        self.checkbox_home = None
        self.checkbox_home_var = tk.BooleanVar()
        self.checkbox_home_var = tk.IntVar(value=1)     # Damit Checkbox standart aktiviert ist
        self.checkbox_tool = None
        self.checkbox_tool_var = tk.BooleanVar()
        self.checkbox_tool_var = tk.IntVar(value=1)     # Damit Checkbox standart aktiviert ist
        self.messagebox = None
        self.create_gui()

    def create_gui(self):
        self.root.title(str(APP_NAME)+' v'+str(VERSION))
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
        self.close_button = tk.Button(self.root, text="Entfernen", command=self.close_file)
        self.close_button.pack(pady=10)
        self.move_up_button = tk.Button(self.root, text="↑", command=self.move_file_up)
        self.move_up_button.pack(pady=5)
        self.move_down_button = tk.Button(self.root, text="↓", command=self.move_file_down)
        self.move_down_button.pack(pady=5)
        self.checkbox_home = tk.Checkbutton(self.root, text="Enposition anfahren", variable=self.checkbox_home_var)
        self.checkbox_home.pack(pady=10)
        self.checkbox_tool = tk.Checkbutton(self.root, text="Mit Werkzeug 6 enden", variable=self.checkbox_tool_var)
        self.checkbox_tool.pack(pady=10)
        self.merge_button = tk.Button(self.root, text="Zusammenführen und Speichern", command=self.merge_and_save)
        self.merge_button.pack(pady=10)

    def open_files(self):
        file_paths = filedialog.askopenfilenames(filetypes=[("GCode Files", "*.nc")])
        for file_path in file_paths:
            try:
                gcode_file = GCodeFile(file_path)
            except SyntaxError as error:
                print(str(error))
                messagebox.showinfo("Fehler", str(error))
            except EOFError as error:
                messagebox.showinfo("Fehler", str(error))
            else:
                self.file_list.append(gcode_file)
                self.file_listbox.insert(tk.END, gcode_file.name)

    def close_file(self):
        try:
            selected_index = self.file_listbox.curselection()   # get selected index
            self.file_list.pop(selected_index[0])               # remove entry with index
        except IndexError:
            messagebox.showinfo("Fehler", "Kein File ausgewählt!")
        else:
            self.selected_file = None                           # clear selected file
            self.file_listbox.delete(0, tk.END)                 # delete box
            for file in self.file_list:                         # populate box again
                self.file_listbox.insert(tk.END, file.name)
            self.file_listbox.selection_clear(0, tk.END)        # clear selection in box
            self.display_file_details_dummy()                   # draw details without value

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

    def display_file_details_dummy(self):   # function for drawing details without values
        self.name_label.config(text="Name: ")
        self.size_label.config(text="Größe (KB): ")
        self.line_count_label.config(text="Anzahl der Zeilen: ")
        self.order_label.config(text="Reihenfolge: ")
        self.spindle_speed_label.config(text="Spindel Drehzahl (RPM): ")
        self.feedrate_xy_label.config(text="Vorschub XY (mm/min): ")
        self.feedrate_z_label.config(text="Vorschub Z (mm/min): ")
        self.z_cut_label.config(text="Schnitttiefe (mm): ")
        self.tool_var.set(6)
        self.tool_dropdown.configure(state="normal")

    def on_tool_selected(self, tool):
        self.selected_file.tool = tool

    def move_file_up(self):
        selected_index = self.file_listbox.curselection()
        if selected_index and selected_index[0] > 0:        # check if not first in list
            self.file_list.insert(selected_index[0] - 1, self.file_list.pop(selected_index[0]))     # remove and insert above
            self.file_listbox.delete(0, tk.END)     # delete box and refresh it.
            for file in self.file_list:
                self.file_listbox.insert(tk.END, file.name)
            self.file_listbox.selection_clear(0, tk.END)
            self.file_listbox.selection_set(selected_index[0] - 1)      # select moved entry
            self.selected_file = self.file_list[selected_index[0] - 1]  # load selected file
            self.display_file_details()                                 # display details

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
        movement = "M5\n"
        movement += GOTO_CLEARANCE + "\n"                         # using command from machine "GoTo Clearance"
        return movement

    def changeT6(self):
        return "T" + str(END_TOOL) + "M6\n"
    def merge_and_save(self):
        merged_content = ""
        for file in self.file_list:
            merged_content += re.sub(r"T\d+", "T" + str(file.tool), file.gcode_content)
        if self.checkbox_home_var.get():
            merged_content += str(self.goToHome())
        if self.checkbox_tool_var.get():
            merged_content += str(self.changeT6())
        save_path = filedialog.asksaveasfilename(filetypes=[("GCode Files", "*.nc")])
        with open(save_path, "w") as file:
            file.write(merged_content)

root = tk.Tk()
app = GCodeAnalyzerApp(root)
root.mainloop()
