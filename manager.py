"""
Command Vault Manager
A GUI for managing the Command Vault database.
Launch via: python manager.py
Or from Flow Launcher: cv :manage
"""

import os
import sqlite3
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault.db")
ACCENT = "#3B82F6"
BG = "#1E1E2E"
SURFACE = "#2A2A3E"
SURFACE2 = "#313145"
FG = "#CDD6F4"
FG_DIM = "#6C7086"
GREEN = "#A6E3A1"
RED = "#F38BA8"
YELLOW = "#F9E2AF"
BORDER = "#45475A"


# ── Database helpers ──────────────────────────────────────────────────────────

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def fetch_all(search="", category="All"):
    with db() as con:
        conditions = []
        params = []
        if search:
            like = f"%{search}%"
            conditions.append(
                "(title LIKE ? OR command LIKE ? OR description LIKE ? OR tags LIKE ?)"
            )
            params += [like, like, like, like]
        if category and category != "All":
            conditions.append("category = ?")
            params.append(category)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return con.execute(
            f"SELECT * FROM commands {where} "
            "ORDER BY is_favorite DESC, category, subcategory, title",
            params,
        ).fetchall()


def fetch_categories():
    with db() as con:
        rows = con.execute(
            "SELECT DISTINCT category FROM commands ORDER BY category"
        ).fetchall()
        return ["All"] + [r["category"] for r in rows]


def insert_command(data: dict) -> int:
    with db() as con:
        cur = con.execute(
            "INSERT INTO commands(category,subcategory,title,command,"
            "description,tags,is_favorite) VALUES(?,?,?,?,?,?,?)",
            (
                data["category"], data["subcategory"], data["title"],
                data["command"], data["description"], data["tags"],
                1 if data["is_favorite"] else 0,
            ),
        )
        con.commit()
        return cur.lastrowid


def update_command(cmd_id: int, data: dict):
    with db() as con:
        con.execute(
            "UPDATE commands SET category=?,subcategory=?,title=?,command=?,"
            "description=?,tags=?,is_favorite=?,updated_at=datetime('now') "
            "WHERE id=?",
            (
                data["category"], data["subcategory"], data["title"],
                data["command"], data["description"], data["tags"],
                1 if data["is_favorite"] else 0,
                cmd_id,
            ),
        )
        con.commit()


def delete_command(cmd_id: int):
    with db() as con:
        con.execute("DELETE FROM commands WHERE id=?", (cmd_id,))
        con.commit()


def toggle_favorite(cmd_id: int):
    with db() as con:
        con.execute(
            "UPDATE commands SET is_favorite=CASE WHEN is_favorite=1 THEN 0 ELSE 1 END "
            "WHERE id=?",
            (cmd_id,),
        )
        con.commit()


# ── Edit / Add Dialog ─────────────────────────────────────────────────────────

class CommandDialog(tk.Toplevel):
    def __init__(self, parent, title="Add Command", data=None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.resizable(True, True)
        self.configure(bg=BG)
        self.geometry("680x540")
        self.minsize(560, 480)

        # Center on parent
        self.transient(parent)
        self.grab_set()
        px = parent.winfo_rootx() + parent.winfo_width() // 2 - 340
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - 270
        self.geometry(f"+{px}+{py}")

        self._build(data or {})
        self.wait_window()

    def _label(self, parent, text):
        tk.Label(
            parent, text=text, bg=BG, fg=FG_DIM,
            font=("Segoe UI", 9), anchor="w"
        ).pack(fill="x", pady=(8, 2))

    def _entry(self, parent, var, placeholder=""):
        e = tk.Entry(
            parent, textvariable=var, bg=SURFACE2, fg=FG,
            insertbackground=FG, relief="flat", font=("Segoe UI", 11),
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        e.pack(fill="x", ipady=6)
        return e

    def _build(self, data):
        # ── Scrollable body ────────────────────────────────────────────
        body = tk.Frame(self, bg=BG, padx=24, pady=16)
        body.pack(fill="both", expand=True)

        # Row 1: category + subcategory
        row1 = tk.Frame(body, bg=BG)
        row1.pack(fill="x")
        col1 = tk.Frame(row1, bg=BG)
        col1.pack(side="left", fill="x", expand=True, padx=(0, 8))
        col2 = tk.Frame(row1, bg=BG)
        col2.pack(side="left", fill="x", expand=True)

        self.v_cat = tk.StringVar(value=data.get("category", ""))
        self.v_sub = tk.StringVar(value=data.get("subcategory", ""))
        tk.Label(col1, text="Category *", bg=BG, fg=FG_DIM, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(0,2))
        self._entry(col1, self.v_cat)
        tk.Label(col2, text="Subcategory", bg=BG, fg=FG_DIM, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(0,2))
        self._entry(col2, self.v_sub)

        # Title
        self.v_title = tk.StringVar(value=data.get("title", ""))
        self._label(body, "Title *")
        self._entry(body, self.v_title)

        # Command (multiline)
        tk.Label(body, text="Command *  (use {var} for templates)", bg=BG, fg=FG_DIM, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(8,2))
        self.t_cmd = tk.Text(
            body, height=4, bg=SURFACE2, fg=FG, insertbackground=FG,
            relief="flat", font=("Consolas", 11),
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT, wrap="none",
        )
        self.t_cmd.pack(fill="x", ipady=4)
        self.t_cmd.insert("1.0", data.get("command", ""))

        # Description
        self.v_desc = tk.StringVar(value=data.get("description", ""))
        self._label(body, "Description")
        self._entry(body, self.v_desc)

        # Tags
        self.v_tags = tk.StringVar(value=data.get("tags", ""))
        self._label(body, "Tags  (comma-separated, e.g. vlan,l2,ccna)")
        self._entry(body, self.v_tags)

        # Favorite
        self.v_fav = tk.BooleanVar(value=bool(data.get("is_favorite", 0)))
        fav_frame = tk.Frame(body, bg=BG)
        fav_frame.pack(fill="x", pady=(12, 0))
        tk.Checkbutton(
            fav_frame, text="  Mark as favorite  ★", variable=self.v_fav,
            bg=BG, fg=YELLOW, activebackground=BG, activeforeground=YELLOW,
            selectcolor=SURFACE2, font=("Segoe UI", 10),
        ).pack(side="left")

        # ── Buttons ────────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=BG, padx=24, pady=12)
        btn_row.pack(fill="x")

        tk.Button(
            btn_row, text="Cancel", command=self.destroy,
            bg=SURFACE2, fg=FG_DIM, activebackground=BORDER,
            relief="flat", font=("Segoe UI", 10), padx=20, pady=8,
            cursor="hand2",
        ).pack(side="right", padx=(6, 0))

        tk.Button(
            btn_row, text="Save", command=self._save,
            bg=ACCENT, fg="white", activebackground="#2563EB",
            relief="flat", font=("Segoe UI", 10, "bold"), padx=24, pady=8,
            cursor="hand2",
        ).pack(side="right")

        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<Control-Return>", lambda _: self._save())

    def _save(self):
        cat = self.v_cat.get().strip()
        title = self.v_title.get().strip()
        cmd = self.t_cmd.get("1.0", "end").strip()
        if not cat or not title or not cmd:
            messagebox.showwarning("Missing fields", "Category, Title and Command are required.", parent=self)
            return
        self.result = {
            "category": cat,
            "subcategory": self.v_sub.get().strip(),
            "title": title,
            "command": cmd,
            "description": self.v_desc.get().strip(),
            "tags": self.v_tags.get().strip(),
            "is_favorite": self.v_fav.get(),
        }
        self.destroy()


# ── Main Window ───────────────────────────────────────────────────────────────

class VaultManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Command Vault Manager")
        self.geometry("1100x680")
        self.minsize(800, 500)
        self.configure(bg=BG)
        self._setup_style()
        self._build()
        self.refresh()
        # Keyboard shortcuts
        self.bind("<Control-n>", lambda _: self.cmd_add())
        self.bind("<Delete>", lambda _: self.cmd_delete())
        self.bind("<F5>", lambda _: self.refresh())
        self.bind("<Return>", lambda _: self.cmd_edit())

    def _setup_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview",
            background=SURFACE, foreground=FG,
            rowheight=34, fieldbackground=SURFACE,
            borderwidth=0, font=("Segoe UI", 10),
        )
        style.configure("Treeview.Heading",
            background=SURFACE2, foreground=FG_DIM,
            borderwidth=0, font=("Segoe UI", 9, "bold"),
        )
        style.map("Treeview",
            background=[("selected", ACCENT)],
            foreground=[("selected", "white")],
        )
        style.configure("TCombobox",
            fieldbackground=SURFACE2, background=SURFACE2,
            foreground=FG, selectbackground=ACCENT,
        )
        style.map("TCombobox",
            fieldbackground=[("readonly", SURFACE2)],
            foreground=[("readonly", FG)],
        )

    def _build(self):
        # ── Top bar ────────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=SURFACE2, pady=10, padx=16)
        topbar.pack(fill="x")

        # App title
        tk.Label(
            topbar, text="⚡ Command Vault", bg=SURFACE2, fg=FG,
            font=("Segoe UI", 14, "bold"),
        ).pack(side="left", padx=(0, 24))

        # Search
        self.v_search = tk.StringVar()
        self.v_search.trace_add("write", lambda *_: self.refresh())
        search_frame = tk.Frame(topbar, bg=SURFACE2)
        search_frame.pack(side="left", fill="x", expand=True)
        tk.Label(search_frame, text="🔍", bg=SURFACE2, fg=FG_DIM, font=("Segoe UI", 11)).pack(side="left", padx=(0,4))
        tk.Entry(
            search_frame, textvariable=self.v_search,
            bg=SURFACE, fg=FG, insertbackground=FG,
            relief="flat", font=("Segoe UI", 11),
            highlightthickness=1, highlightbackground=BORDER,
            highlightcolor=ACCENT,
        ).pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 16))

        # Category filter
        tk.Label(topbar, text="Category:", bg=SURFACE2, fg=FG_DIM, font=("Segoe UI", 10)).pack(side="left")
        self.v_cat_filter = tk.StringVar(value="All")
        self.cat_combo = ttk.Combobox(
            topbar, textvariable=self.v_cat_filter,
            state="readonly", width=14, font=("Segoe UI", 10),
        )
        self.cat_combo.pack(side="left", padx=(6, 16))
        self.cat_combo.bind("<<ComboboxSelected>>", lambda _: self.refresh())

        # ── Action buttons ─────────────────────────────────────────────
        def btn(parent, text, cmd, color=SURFACE2, fg_col=FG):
            return tk.Button(
                parent, text=text, command=cmd,
                bg=color, fg=fg_col, activebackground=BORDER,
                relief="flat", font=("Segoe UI", 10), padx=14, pady=6,
                cursor="hand2",
            )

        btn(topbar, "+ Add  (Ctrl+N)", self.cmd_add, ACCENT, "white").pack(side="left", padx=2)
        btn(topbar, "✎ Edit  (Enter)", self.cmd_edit).pack(side="left", padx=2)
        btn(topbar, "⧉ Duplicate", self.cmd_duplicate).pack(side="left", padx=2)
        btn(topbar, "★ Favorite", self.cmd_fav, SURFACE2, YELLOW).pack(side="left", padx=2)
        btn(topbar, "✕ Delete  (Del)", self.cmd_delete, SURFACE2, RED).pack(side="left", padx=2)

        # ── Table ──────────────────────────────────────────────────────
        table_frame = tk.Frame(self, bg=BG)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(8, 0))

        cols = ("fav", "category", "subcategory", "title", "command", "description", "tags")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")

        col_cfg = {
            "fav":         ("★",           36,  False),
            "category":    ("Category",   110,  True),
            "subcategory": ("Subcategory", 110, True),
            "title":       ("Title",       200,  True),
            "command":     ("Command",     300,  True),
            "description": ("Description", 220,  True),
            "tags":        ("Tags",        140,  True),
        }
        for col, (heading, width, stretch) in col_cfg.items():
            self.tree.heading(col, text=heading, command=lambda c=col: self._sort(c))
            self.tree.column(col, width=width, stretch=stretch, anchor="w")

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", lambda _: self.cmd_edit())
        self.tree.tag_configure("fav", foreground=YELLOW)

        # ── Status bar ─────────────────────────────────────────────────
        statusbar = tk.Frame(self, bg=SURFACE2, pady=6, padx=16)
        statusbar.pack(fill="x")
        self.lbl_status = tk.Label(statusbar, text="", bg=SURFACE2, fg=FG_DIM, font=("Segoe UI", 9))
        self.lbl_status.pack(side="left")
        tk.Label(
            statusbar,
            text="Ctrl+N Add   Enter Edit   Del Delete   F5 Refresh",
            bg=SURFACE2, fg=FG_DIM, font=("Segoe UI", 9),
        ).pack(side="right")

        self._sort_col = None
        self._sort_rev = False

    # ── Data ──────────────────────────────────────────────────────────────────

    def refresh(self, *_):
        search = self.v_search.get()
        cat = self.v_cat_filter.get()

        # Update category list
        cats = fetch_categories()
        self.cat_combo["values"] = cats
        if cat not in cats:
            self.v_cat_filter.set("All")
            cat = "All"

        rows = fetch_all(search, cat)
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            fav = "★" if r["is_favorite"] else ""
            tags = (self.tree.insert(
                "", "end",
                iid=str(r["id"]),
                values=(fav, r["category"], r["subcategory"] or "", r["title"],
                        r["command"].replace("\n", " ↵ "),
                        r["description"] or "", r["tags"] or ""),
                tags=("fav",) if r["is_favorite"] else (),
            ))

        total_all = len(fetch_all())
        shown = len(rows)
        self.lbl_status.config(
            text=f"{shown} commands shown  /  {total_all} total"
        )

    def _selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _sort(self, col):
        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        rev = self._sort_col == col and not self._sort_rev
        rows.sort(reverse=rev)
        for i, (_, k) in enumerate(rows):
            self.tree.move(k, "", i)
        self._sort_col = col
        self._sort_rev = rev

    # ── Actions ───────────────────────────────────────────────────────────────

    def cmd_add(self):
        dlg = CommandDialog(self, "Add Command")
        if dlg.result:
            insert_command(dlg.result)
            self.refresh()

    def cmd_edit(self):
        cmd_id = self._selected_id()
        if not cmd_id:
            return
        with db() as con:
            row = con.execute("SELECT * FROM commands WHERE id=?", (cmd_id,)).fetchone()
        if not row:
            return
        dlg = CommandDialog(self, "Edit Command", dict(row))
        if dlg.result:
            update_command(cmd_id, dlg.result)
            self.refresh()

    def cmd_duplicate(self):
        cmd_id = self._selected_id()
        if not cmd_id:
            return
        with db() as con:
            row = con.execute("SELECT * FROM commands WHERE id=?", (cmd_id,)).fetchone()
        if not row:
            return
        data = dict(row)
        data["title"] = data["title"] + " (copy)"
        data["is_favorite"] = 0
        insert_command(data)
        self.refresh()

    def cmd_delete(self):
        cmd_id = self._selected_id()
        if not cmd_id:
            return
        with db() as con:
            row = con.execute("SELECT title FROM commands WHERE id=?", (cmd_id,)).fetchone()
        if not row:
            return
        if messagebox.askyesno(
            "Delete command",
            f"Delete \"{row['title']}\"?\n\nThis cannot be undone.",
            parent=self, icon="warning",
        ):
            delete_command(cmd_id)
            self.refresh()

    def cmd_fav(self):
        cmd_id = self._selected_id()
        if not cmd_id:
            return
        toggle_favorite(cmd_id)
        self.refresh()
        # Re-select the same row if it's still visible
        try:
            self.tree.selection_set(str(cmd_id))
            self.tree.see(str(cmd_id))
        except tk.TclError:
            pass


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = VaultManager()
    app.mainloop()
