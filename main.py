"""Happylab FlatCAM-Carvera Postprozessor.

Without arguments (double click, windowed .exe): starts the GUI.
With arguments: command line tool, see  python main.py --help
"""
import sys


def run():
    if len(sys.argv) > 1 and sys.argv[1] != "--gui":
        from carvera_pp.cli import main
        sys.exit(main())
    try:
        from carvera_pp.gui import main
    except ImportError as e:   # e.g. Python without tkinter on a server
        sys.exit(f"GUI not available ({e}). Use the command line: python main.py --help")
    main()


if __name__ == "__main__":
    run()
