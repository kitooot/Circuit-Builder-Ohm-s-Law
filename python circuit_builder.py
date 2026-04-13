"""Launcher for the interactive circuit builder GUI."""

import customtkinter as ctk

from circuit_builder.app import OhmsLawApp


def main() -> None:
    # Initialize and run the Ohm's Law application window.
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    app = OhmsLawApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()