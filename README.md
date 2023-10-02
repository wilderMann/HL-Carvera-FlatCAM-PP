# HL-Carvera-FlatCAM-PP
This application acts as a postprocessor for the Makera Carvera. If you are using FlatCAM to cnc PCBs, you have to edit the gcode manually. This postprocessor does that for you.

What this program does:
- merge multiple .nc files into one
- fix the tool-change-M6 error, by removing everything between T# and M6
- set a different tool for each file, when merging the gcode will be modified with the selected tool
- Optional: inserting code at the end, so when all jobs are finished goto clearance position
- Optional: inserting code at the end to perform a toolchange to tool 6, so the machine will not be without a tool for long period of time
