"""
template_dialog.py — standalone template variable prompt
Called by main.py as a subprocess.

Usage:
    python template_dialog.py <command_json>

Reads JSON from argv[1]: {"command": "...", "title": "..."}
Prints filled command to stdout, or exits with code 1 on cancel.
"""

import json
import re
import sys
import tkinter as tk
from tkinter import font as tkfont

# ── Palette (matches manager.py) ──────────────────────────────────────────────
BG      = "#1E1E2E"
SURFACE = "#313244"
SURFACE2= "#45475A"
FG      = "#CDD6F4"
FG_DIM  = "#6C7086"
ACCENT  = "#89B4FA"
YELLOW  = "#F9E2AF"
GREEN   = "#A6E3A1"
RED     = "#F38BA8"
BORDER  = "#313244"

VAR_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def highlight_command(text_widget: tk.Text, command: str):
    """Insert command text with {variables} highlighted in yellow."""
    text_widget.config(state="normal")
    text_widget.delete("1.0", "end")

    last = 0
    for m in VAR_PATTERN.finditer(command):
        if m.start() > last:
            text_widget.insert("end", command[last:m.start()], "plain")
        text_widget.insert("end", m.group(0), "var")
        last = m.end()
    if last < len(command):
        text_widget.insert("end", command[last:], "plain")

    text_widget.config(state="disabled")


def run(command: str, title: str) -> str | None:
    """Show dialog, return filled command or None on cancel."""
    vars_found = list(dict.fromkeys(VAR_PATTERN.findall(command)))
    if not vars_found:
        return command

    root = tk.Tk()
    root.title("Command Vault — Template")
    root.configure(bg=BG)
    root.resizable(False, False)
    root.attributes("-topmost", True)

    # Center on screen
    root.update_idletasks()
    w, h = 560, 160 + len(vars_found) * 72
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    result = {"value": None}

    # ── Header ────────────────────────────────────────────────────────────────
    header = tk.Frame(root, bg=SURFACE, padx=20, pady=12)
    header.pack(fill="x")
    tk.Label(header, text="✎  Fill in template variables",
             bg=SURFACE, fg=FG, font=("Segoe UI", 12, "bold")).pack(side="left")
    tk.Label(header, text=title, bg=SURFACE, fg=FG_DIM,
             font=("Segoe UI", 9)).pack(side="right", padx=(0, 4))

    # ── Command preview ───────────────────────────────────────────────────────
    preview_frame = tk.Frame(root, bg=BG, padx=20, pady=10)
    preview_frame.pack(fill="x")
    tk.Label(preview_frame, text="Command", bg=BG, fg=FG_DIM,
             font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")

    preview = tk.Text(preview_frame, height=2, bg=SURFACE, fg=FG,
                      font=("Consolas", 10), relief="flat", wrap="word",
                      padx=10, pady=8, state="disabled",
                      highlightthickness=1, highlightbackground=BORDER)
    preview.tag_configure("plain", foreground=FG)
    preview.tag_configure("var",   foreground=YELLOW, font=("Consolas", 10, "bold"))
    preview.pack(fill="x")
    highlight_command(preview, command)

    # ── Variable inputs ───────────────────────────────────────────────────────
    vars_frame = tk.Frame(root, bg=BG, padx=20, pady=4)
    vars_frame.pack(fill="x")
    entries: dict[str, tk.StringVar] = {}

    for i, var in enumerate(vars_found):
        row = tk.Frame(vars_frame, bg=BG)
        row.pack(fill="x", pady=6)

        tk.Label(row, text=f"{var}", bg=BG, fg=ACCENT,
                 font=("Consolas", 10, "bold"), width=18, anchor="w").pack(side="left")

        sv = tk.StringVar()
        entries[var] = sv
        e = tk.Entry(row, textvariable=sv, bg=SURFACE, fg=FG,
                     insertbackground=FG, relief="flat",
                     font=("Consolas", 11),
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT)
        e.pack(side="left", fill="x", expand=True, ipady=7, padx=(8, 0))

        # Focus first field
        if i == 0:
            e.focus_set()

        # Update preview on type
        def on_type(*_, v=var, sv=sv):
            filled = command
            for k, s in entries.items():
                val = s.get() or f"{{{k}}}"
                filled = filled.replace(f"{{{k}}}", val)
            highlight_command(preview, filled)
        sv.trace_add("write", on_type)

    # ── Buttons ───────────────────────────────────────────────────────────────
    btn_row = tk.Frame(root, bg=SURFACE, padx=20, pady=12)
    btn_row.pack(fill="x", side="bottom")

    def on_cancel():
        result["value"] = None
        root.destroy()

    def on_ok():
        filled = command
        for var, sv in entries.items():
            filled = filled.replace(f"{{{var}}}", sv.get())
        result["value"] = filled
        root.destroy()

    tk.Button(btn_row, text="Cancel", command=on_cancel,
              bg=SURFACE2, fg=FG_DIM, activebackground=BORDER,
              relief="flat", font=("Segoe UI", 10),
              padx=18, pady=7, cursor="hand2", bd=0).pack(side="right", padx=(6,0))

    tk.Button(btn_row, text="Copy Command", command=on_ok,
              bg=ACCENT, fg="#1E1E2E", activebackground="#6BA3F5",
              relief="flat", font=("Segoe UI", 10, "bold"),
              padx=22, pady=7, cursor="hand2", bd=0).pack(side="right")

    tk.Label(btn_row, text="Enter to confirm  ·  Esc to cancel",
             bg=SURFACE, fg=FG_DIM, font=("Segoe UI", 8)).pack(side="left")

    root.bind("<Return>", lambda _: on_ok())
    root.bind("<Escape>", lambda _: on_cancel())
    root.protocol("WM_DELETE_WINDOW", on_cancel)

    root.mainloop()
    return result["value"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)

    try:
        payload = json.loads(sys.argv[1])
        command = payload["command"]
        title   = payload.get("title", "")
    except (json.JSONDecodeError, KeyError):
        sys.exit(1)

    filled = run(command, title)
    if filled is None:
        sys.exit(1)

    print(filled, end="")
    sys.exit(0)
