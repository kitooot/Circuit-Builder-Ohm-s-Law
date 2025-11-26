"""Launcher for the interactive circuit builder GUI."""

import tkinter as tk

from circuit_builder.app import OhmsLawApp


def main() -> None:
    root = tk.Tk()
    app = OhmsLawApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()