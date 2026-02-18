"""
Command Vault Manager  —  GUI editor for vault.db
Launch: python manager.py  |  Flow Launcher: cv :manage
"""

import json
import os
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vault.db")

# ── Palette ───────────────────────────────────────────────────────────────────
BG        = "#1E1E2E"
SIDEBAR   = "#181825"
SURFACE   = "#313244"
SURFACE2  = "#45475A"
FG        = "#CDD6F4"
FG_DIM    = "#6C7086"
FG_MUTED  = "#45475A"
ACCENT    = "#89B4FA"
ACCENT_DK = "#1D6FED"
GREEN     = "#A6E3A1"
RED       = "#F38BA8"
YELLOW    = "#F9E2AF"
PEACH     = "#FAB387"
BORDER    = "#313244"

CATEGORY_ICONS = {
    "Cisco":   "󰒍",   # fallback to text if font missing
    "Linux":   "",
    "Proxmox": "󰒋",
    "Ansible": "⚙",
    "Default": "▸",
}
CATEGORY_COLORS = {
    "Cisco":   "#89B4FA",
    "Linux":   "#A6E3A1",
    "Proxmox": "#FAB387",
    "Ansible": "#F38BA8",
    "Default": "#CDD6F4",
}

# ── DB helpers ────────────────────────────────────────────────────────────────
def _db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con

def fetch_categories():
    with _db() as con:
        rows = con.execute("SELECT category, COUNT(*) as cnt FROM commands GROUP BY category ORDER BY category").fetchall()
        total = con.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    return total, rows

def fetch_commands(search="", category=None, favorites_only=False):
    with _db() as con:
        conditions, params = [], []
        if search:
            like = f"%{search}%"
            conditions.append("(title LIKE ? OR command LIKE ? OR description LIKE ? OR tags LIKE ?)")
            params += [like, like, like, like]
        if category:
            conditions.append("category = ?")
            params.append(category)
        if favorites_only:
            conditions.append("is_favorite = 1")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return con.execute(
            f"SELECT * FROM commands {where} ORDER BY is_favorite DESC, category, subcategory, title",
            params
        ).fetchall()

def insert_cmd(d):
    with _db() as con:
        cur = con.execute(
            "INSERT INTO commands(category,subcategory,title,command,description,tags,is_favorite) VALUES(?,?,?,?,?,?,?)",
            (d["category"], d["subcategory"], d["title"], d["command"], d["description"], d["tags"], 1 if d["is_favorite"] else 0)
        )
        con.commit()
        return cur.lastrowid

def update_cmd(cmd_id, d):
    with _db() as con:
        con.execute(
            "UPDATE commands SET category=?,subcategory=?,title=?,command=?,description=?,tags=?,is_favorite=?,updated_at=datetime('now') WHERE id=?",
            (d["category"], d["subcategory"], d["title"], d["command"], d["description"], d["tags"], 1 if d["is_favorite"] else 0, cmd_id)
        )
        con.commit()

def delete_cmd(cmd_id):
    with _db() as con:
        con.execute("DELETE FROM commands WHERE id=?", (cmd_id,))
        con.commit()

def toggle_fav(cmd_id):
    with _db() as con:
        con.execute("UPDATE commands SET is_favorite=CASE WHEN is_favorite=1 THEN 0 ELSE 1 END WHERE id=?", (cmd_id,))
        con.commit()

# ── Toast notification ────────────────────────────────────────────────────────
class Toast(tk.Toplevel):
    def __init__(self, parent, message, color=GREEN):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=SURFACE)

        tk.Label(self, text=f"  {message}  ", bg=SURFACE, fg=color,
                 font=("Segoe UI", 10), pady=10, padx=8).pack()

        # Position bottom-right of parent
        parent.update_idletasks()
        x = parent.winfo_rootx() + parent.winfo_width() - 320
        y = parent.winfo_rooty() + parent.winfo_height() - 70
        self.geometry(f"+{x}+{y}")
        self.after(2000, self.destroy)

# ── Command dialog ────────────────────────────────────────────────────────────
class CommandDialog(tk.Toplevel):
    def __init__(self, parent, title="Add Command", data=None, prefill_category=None):
        super().__init__(parent)
        self.title(title)
        self.result = None
        self.configure(bg=BG)
        self.geometry("700x560")
        self.minsize(600, 500)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        px = parent.winfo_rootx() + parent.winfo_width() // 2 - 350
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - 280
        self.geometry(f"+{max(0,px)}+{max(0,py)}")

        d = data or {}
        if prefill_category and not d.get("category"):
            d["category"] = prefill_category

        self._build(d)
        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<Control-Return>", lambda _: self._save())
        self.wait_window()

    def _field(self, parent, label, var=None, multiline=False, height=4):
        tk.Label(parent, text=label, bg=BG, fg=FG_DIM,
                 font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(10, 2))
        if multiline:
            w = tk.Text(parent, height=height, bg=SURFACE, fg=FG,
                        insertbackground=FG, relief="flat",
                        font=("Consolas", 11), wrap="none",
                        highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=ACCENT, padx=8, pady=6)
            w.pack(fill="x")
            return w
        e = tk.Entry(parent, textvariable=var, bg=SURFACE, fg=FG,
                     insertbackground=FG, relief="flat", font=("Segoe UI", 11),
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT)
        e.pack(fill="x", ipady=7)
        return e

    def _build(self, d):
        # Header bar
        header = tk.Frame(self, bg=SURFACE, padx=20, pady=14)
        header.pack(fill="x")
        tk.Label(header, text=self.title(), bg=SURFACE, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Label(header, text="Ctrl+Enter to save  ·  Esc to cancel",
                 bg=SURFACE, fg=FG_DIM, font=("Segoe UI", 9)).pack(side="right")

        body = tk.Frame(self, bg=BG, padx=24, pady=10)
        body.pack(fill="both", expand=True)

        # Row: category + subcategory
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x")
        left = tk.Frame(row, bg=BG)
        left.pack(side="left", fill="x", expand=True, padx=(0, 10))
        right = tk.Frame(row, bg=BG)
        right.pack(side="left", fill="x", expand=True)

        self.v_cat = tk.StringVar(value=d.get("category", ""))
        self.v_sub = tk.StringVar(value=d.get("subcategory", "") or "")
        tk.Label(left, text="Category  *", bg=BG, fg=FG_DIM, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(10,2))
        tk.Entry(left, textvariable=self.v_cat, bg=SURFACE, fg=FG,
                 insertbackground=FG, relief="flat", font=("Segoe UI", 11),
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(fill="x", ipady=7)
        tk.Label(right, text="Subcategory", bg=BG, fg=FG_DIM, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(10,2))
        tk.Entry(right, textvariable=self.v_sub, bg=SURFACE, fg=FG,
                 insertbackground=FG, relief="flat", font=("Segoe UI", 11),
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(fill="x", ipady=7)

        self.v_title = tk.StringVar(value=d.get("title", ""))
        self._field(body, "Title  *", self.v_title)

        tk.Label(body, text="Command  *   (use {variable} for templates)",
                 bg=BG, fg=FG_DIM, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(10, 2))
        self.t_cmd = tk.Text(body, height=4, bg=SURFACE, fg=FG,
                             insertbackground=FG, relief="flat",
                             font=("Consolas", 11), wrap="none",
                             highlightthickness=1, highlightbackground=BORDER,
                             highlightcolor=ACCENT, padx=8, pady=6)
        self.t_cmd.pack(fill="x")
        self.t_cmd.insert("1.0", d.get("command", ""))

        self.v_desc = tk.StringVar(value=d.get("description", "") or "")
        self._field(body, "Description   (shown as subtitle in Flow Launcher)", self.v_desc)

        self.v_tags = tk.StringVar(value=d.get("tags", "") or "")
        self._field(body, "Tags   (comma-separated  ·  e.g. vlan,l2,cisco)", self.v_tags)

        # Favorite checkbox
        self.v_fav = tk.BooleanVar(value=bool(d.get("is_favorite", 0)))
        fav = tk.Frame(body, bg=BG)
        fav.pack(fill="x", pady=(12, 0))
        tk.Checkbutton(fav, text="  Mark as favorite  ★",
                       variable=self.v_fav, bg=BG, fg=YELLOW,
                       activebackground=BG, activeforeground=YELLOW,
                       selectcolor=SURFACE, font=("Segoe UI", 10),
                       relief="flat", cursor="hand2").pack(side="left")

        # Buttons
        btn_row = tk.Frame(self, bg=SURFACE, padx=20, pady=14)
        btn_row.pack(fill="x")
        tk.Button(btn_row, text="Cancel", command=self.destroy,
                  bg=SURFACE2, fg=FG_DIM, activebackground=BORDER,
                  relief="flat", font=("Segoe UI", 10), padx=18, pady=8,
                  cursor="hand2", bd=0).pack(side="right", padx=(6,0))
        tk.Button(btn_row, text="Save Command", command=self._save,
                  bg=ACCENT, fg="#1E1E2E", activebackground=ACCENT_DK,
                  relief="flat", font=("Segoe UI", 10, "bold"), padx=22, pady=8,
                  cursor="hand2", bd=0).pack(side="right")

    def _save(self):
        cat   = self.v_cat.get().strip()
        title = self.v_title.get().strip()
        cmd   = self.t_cmd.get("1.0", "end").strip()
        if not cat or not title or not cmd:
            messagebox.showwarning("Missing fields",
                "Category, Title and Command are required.", parent=self)
            return
        self.result = {
            "category":    cat,
            "subcategory": self.v_sub.get().strip(),
            "title":       title,
            "command":     cmd,
            "description": self.v_desc.get().strip(),
            "tags":        self.v_tags.get().strip(),
            "is_favorite": self.v_fav.get(),
        }
        self.destroy()

# ── Main window ───────────────────────────────────────────────────────────────
class VaultManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Command Vault")
        self.geometry("1160x700")
        self.minsize(900, 560)
        self.configure(bg=BG)

        self._active_category = None  # None = All
        self._favs_only = False
        self._sort_col = "category"
        self._sort_rev = False

        self._setup_style()
        self._build()
        self.refresh_sidebar()
        self.refresh_table()

        self.bind("<Control-n>", lambda _: self.cmd_add())
        self.bind("<Delete>",    lambda _: self.cmd_delete())
        self.bind("<Return>",    lambda _: self.cmd_edit())
        self.bind("<F5>",        lambda _: self.full_refresh())

    # ── Style ────────────────────────────────────────────────────────────────
    def _setup_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview",
            background=BG, foreground=FG, rowheight=38,
            fieldbackground=BG, borderwidth=0, font=("Segoe UI", 10))
        s.configure("Treeview.Heading",
            background=SIDEBAR, foreground=FG_DIM,
            borderwidth=0, font=("Segoe UI", 9, "bold"), relief="flat")
        s.map("Treeview",
            background=[("selected", SURFACE)],
            foreground=[("selected", FG)])
        s.configure("Vertical.TScrollbar",
            background=SIDEBAR, troughcolor=SIDEBAR, borderwidth=0,
            arrowcolor=FG_DIM, relief="flat")
        s.configure("Horizontal.TScrollbar",
            background=SIDEBAR, troughcolor=SIDEBAR, borderwidth=0,
            arrowcolor=FG_DIM, relief="flat")

    # ── Layout ───────────────────────────────────────────────────────────────
    def _build(self):
        # ── Top bar ──────────────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=SIDEBAR, pady=0)
        topbar.pack(fill="x")

        # Logo
        logo = tk.Frame(topbar, bg=SIDEBAR, padx=20, pady=12)
        logo.pack(side="left")
        tk.Label(logo, text="⚡", bg=SIDEBAR, fg=ACCENT,
                 font=("Segoe UI", 16)).pack(side="left")
        tk.Label(logo, text=" Command Vault", bg=SIDEBAR, fg=FG,
                 font=("Segoe UI", 13, "bold")).pack(side="left")

        # Search bar
        search_wrap = tk.Frame(topbar, bg=SIDEBAR, padx=16, pady=10)
        search_wrap.pack(side="left", fill="x", expand=True)

        search_bg = tk.Frame(search_wrap, bg=SURFACE, highlightbackground=BORDER,
                             highlightthickness=1)
        search_bg.pack(fill="x")
        tk.Label(search_bg, text=" 🔍 ", bg=SURFACE, fg=FG_DIM,
                 font=("Segoe UI", 11)).pack(side="left")
        self.v_search = tk.StringVar()
        self.v_search.trace_add("write", lambda *_: self.refresh_table())
        tk.Entry(search_bg, textvariable=self.v_search, bg=SURFACE, fg=FG,
                 insertbackground=FG, relief="flat", font=("Segoe UI", 11),
                 bd=0).pack(side="left", fill="x", expand=True, ipady=8, padx=(0,8))

        # Action buttons
        btn_bar = tk.Frame(topbar, bg=SIDEBAR, padx=12, pady=8)
        btn_bar.pack(side="right")

        def tbtn(text, cmd, fg_col=FG, bg_col=SURFACE2, bold=False):
            f = ("Segoe UI", 10, "bold") if bold else ("Segoe UI", 10)
            return tk.Button(btn_bar, text=text, command=cmd,
                             bg=bg_col, fg=fg_col, activebackground=SURFACE,
                             activeforeground=FG, relief="flat", font=f,
                             padx=14, pady=7, cursor="hand2", bd=0)

        tbtn("+ Add", self.cmd_add, fg_col="#1E1E2E", bg_col=ACCENT, bold=True).pack(side="left", padx=3)
        tbtn("✎ Edit", self.cmd_edit).pack(side="left", padx=3)
        tbtn("⧉ Duplicate", self.cmd_duplicate).pack(side="left", padx=3)
        tbtn("★", self.cmd_fav, fg_col=YELLOW).pack(side="left", padx=3)
        tbtn("✕", self.cmd_delete, fg_col=RED).pack(side="left", padx=3)

        # Import / Export
        ie_frame = tk.Frame(topbar, bg=SIDEBAR, padx=4, pady=8)
        ie_frame.pack(side="right")
        tbtn("↑ Export", self.cmd_export, fg_col=FG_DIM).pack(side="left", padx=2)
        tbtn("↓ Import", self.cmd_import, fg_col=FG_DIM).pack(side="left", padx=2)

        # ── Main area: sidebar + table ────────────────────────────────────────
        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = tk.Frame(main, bg=SIDEBAR, width=200)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        tk.Label(self.sidebar, text="CATEGORIES", bg=SIDEBAR, fg=FG_MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w",
                 padx=16, pady=12).pack(fill="x")

        self.sidebar_frame = tk.Frame(self.sidebar, bg=SIDEBAR)
        self.sidebar_frame.pack(fill="both", expand=True)

        # Divider
        tk.Frame(main, bg=BORDER, width=1).pack(side="left", fill="y")

        # Table area
        right = tk.Frame(main, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        cols = ("fav", "category", "subcategory", "title", "command", "description", "tags")
        self.tree = ttk.Treeview(right, columns=cols, show="headings",
                                 selectmode="browse")

        col_cfg = {
            "fav":         ("★",           38,  False),
            "category":    ("Category",    120, False),
            "subcategory": ("Subcategory", 110, False),
            "title":       ("Title",       210, True),
            "command":     ("Command",     310, True),
            "description": ("Description", 200, True),
            "tags":        ("Tags",        140, False),
        }
        for col, (heading, width, stretch) in col_cfg.items():
            self.tree.heading(col, text=heading,
                              command=lambda c=col: self._sort(c))
            self.tree.column(col, width=width, stretch=stretch, anchor="w",
                             minwidth=30)

        vsb = ttk.Scrollbar(right, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(right, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.tree.tag_configure("fav",  foreground=YELLOW)
        self.tree.tag_configure("even", background="#252535")
        self.tree.bind("<Double-1>", lambda _: self.cmd_edit())

        # ── Status bar ────────────────────────────────────────────────────────
        status = tk.Frame(self, bg=SIDEBAR, pady=7, padx=16)
        status.pack(fill="x")
        self.lbl_status = tk.Label(status, text="", bg=SIDEBAR, fg=FG_DIM,
                                   font=("Segoe UI", 9))
        self.lbl_status.pack(side="left")
        tk.Label(status,
                 text="Ctrl+N  Add    Enter  Edit    Del  Delete    F5  Refresh",
                 bg=SIDEBAR, fg=FG_MUTED, font=("Segoe UI", 9)).pack(side="right")

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _sidebar_btn(self, text, count, tag, active=False):
        color = CATEGORY_COLORS.get(tag, CATEGORY_COLORS["Default"])
        bg = SURFACE if active else SIDEBAR
        fg = FG if active else FG_DIM

        row = tk.Frame(self.sidebar_frame, bg=bg, cursor="hand2")
        row.pack(fill="x")

        # Left accent bar for active
        accent = tk.Frame(row, bg=ACCENT if active else SIDEBAR, width=3)
        accent.pack(side="left", fill="y")

        inner = tk.Frame(row, bg=bg, padx=12, pady=9)
        inner.pack(side="left", fill="x", expand=True)

        tk.Label(inner, text=text, bg=bg, fg=fg,
                 font=("Segoe UI", 10), anchor="w").pack(side="left")
        tk.Label(inner, text=str(count), bg=bg, fg=FG_MUTED,
                 font=("Segoe UI", 9)).pack(side="right")

        def on_click(t=tag):
            if t == "__favs__":
                self._favs_only = not self._favs_only
                self._active_category = None
            elif t is None:
                self._active_category = None
                self._favs_only = False
            else:
                self._active_category = t
                self._favs_only = False
            self.refresh_sidebar()
            self.refresh_table()

        for w in (row, inner, accent):
            w.bind("<Button-1>", lambda e, t=tag: on_click(t))

    def refresh_sidebar(self):
        for w in self.sidebar_frame.winfo_children():
            w.destroy()

        total, cats = fetch_categories()
        favs_count = len(fetch_commands(favorites_only=True))

        self._sidebar_btn("All commands", total, None,
                          active=(self._active_category is None and not self._favs_only))
        self._sidebar_btn("★  Favorites", favs_count, "__favs__",
                          active=self._favs_only)

        if cats:
            tk.Frame(self.sidebar_frame, bg=BORDER, height=1).pack(fill="x", pady=6)

        for row in cats:
            cat = row["category"]
            icon = CATEGORY_ICONS.get(cat, CATEGORY_ICONS["Default"])
            self._sidebar_btn(f"  {cat}", row["cnt"], cat,
                              active=(self._active_category == cat and not self._favs_only))

    # ── Table ─────────────────────────────────────────────────────────────────
    def refresh_table(self, *_):
        search = self.v_search.get()
        rows = fetch_commands(
            search=search,
            category=self._active_category,
            favorites_only=self._favs_only,
        )

        sel_id = self._selected_id()
        self.tree.delete(*self.tree.get_children())

        for i, r in enumerate(rows):
            fav  = "★" if r["is_favorite"] else ""
            tags = ("fav",) if r["is_favorite"] else ("even",) if i % 2 == 0 else ()
            self.tree.insert("", "end", iid=str(r["id"]),
                values=(fav, r["category"], r["subcategory"] or "",
                        r["title"],
                        r["command"].replace("\n", " ↵ "),
                        r["description"] or "",
                        r["tags"] or ""),
                tags=tags)

        # Restore selection
        if sel_id:
            try:
                self.tree.selection_set(str(sel_id))
                self.tree.see(str(sel_id))
            except tk.TclError:
                pass

        total_all = fetch_commands()
        cat_label = f"  ›  {self._active_category}" if self._active_category else ("  ›  Favorites" if self._favs_only else "")
        self.lbl_status.config(
            text=f"{len(rows)} shown{cat_label}   /   {len(total_all)} total"
        )

    def full_refresh(self):
        self.refresh_sidebar()
        self.refresh_table()

    def _selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _sort(self, col):
        rows = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        rev = (self._sort_col == col) and not self._sort_rev
        rows.sort(reverse=rev)
        for idx, (_, k) in enumerate(rows):
            self.tree.move(k, "", idx)
        self._sort_col = col
        self._sort_rev = rev

    # ── Actions ───────────────────────────────────────────────────────────────
    def cmd_add(self):
        dlg = CommandDialog(self, "Add Command",
                            prefill_category=self._active_category)
        if dlg.result:
            insert_cmd(dlg.result)
            self.full_refresh()
            Toast(self, f"Added: {dlg.result['title']}", GREEN)

    def cmd_edit(self):
        cmd_id = self._selected_id()
        if not cmd_id:
            return
        with _db() as con:
            row = con.execute("SELECT * FROM commands WHERE id=?", (cmd_id,)).fetchone()
        if not row:
            return
        dlg = CommandDialog(self, "Edit Command", dict(row))
        if dlg.result:
            update_cmd(cmd_id, dlg.result)
            self.full_refresh()
            Toast(self, f"Saved: {dlg.result['title']}", ACCENT)

    def cmd_duplicate(self):
        cmd_id = self._selected_id()
        if not cmd_id:
            return
        with _db() as con:
            row = dict(con.execute("SELECT * FROM commands WHERE id=?", (cmd_id,)).fetchone())
        row["title"] += " (copy)"
        row["is_favorite"] = 0
        new_id = insert_cmd(row)
        self.full_refresh()
        try:
            self.tree.selection_set(str(new_id))
            self.tree.see(str(new_id))
        except tk.TclError:
            pass
        Toast(self, "Duplicated", PEACH)

    def cmd_delete(self):
        cmd_id = self._selected_id()
        if not cmd_id:
            return
        with _db() as con:
            row = con.execute("SELECT title FROM commands WHERE id=?", (cmd_id,)).fetchone()
        if not row:
            return
        if messagebox.askyesno("Delete command",
                f"Delete \"{row['title']}\"?\n\nThis cannot be undone.",
                parent=self, icon="warning"):
            delete_cmd(cmd_id)
            self.full_refresh()
            Toast(self, "Deleted", RED)

    def cmd_fav(self):
        cmd_id = self._selected_id()
        if not cmd_id:
            return
        toggle_fav(cmd_id)
        self.full_refresh()
        try:
            self.tree.selection_set(str(cmd_id))
            self.tree.see(str(cmd_id))
        except tk.TclError:
            pass

    # ── Import / Export ───────────────────────────────────────────────────────
    def cmd_export(self):
        path = filedialog.asksaveasfilename(
            title="Export commands",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
            initialfile="command_vault_export.json",
        )
        if not path:
            return
        rows = fetch_commands(
            search=self.v_search.get(),
            category=self._active_category,
            favorites_only=self._favs_only,
        )
        data = [
            {k: row[k] for k in ("category","subcategory","title","command","description","tags","is_favorite")}
            for row in rows
        ]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        Toast(self, f"Exported {len(data)} commands", GREEN)

    def cmd_import(self):
        path = filedialog.askopenfilename(
            title="Import commands",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("Expected a JSON array")
        except Exception as e:
            messagebox.showerror("Import failed", str(e), parent=self)
            return

        count = 0
        for entry in data:
            try:
                insert_cmd({
                    "category":    entry.get("category", "Imported"),
                    "subcategory": entry.get("subcategory", ""),
                    "title":       entry.get("title", "Untitled"),
                    "command":     entry.get("command", ""),
                    "description": entry.get("description", ""),
                    "tags":        entry.get("tags", ""),
                    "is_favorite": entry.get("is_favorite", 0),
                })
                count += 1
            except Exception:
                pass

        self.full_refresh()
        Toast(self, f"Imported {count} commands", GREEN)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = VaultManager()
    app.mainloop()
