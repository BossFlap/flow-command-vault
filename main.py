"""
CommandVault - Flow Launcher Plugin
A 1Password-style command launcher with categories, fuzzy search,
favorites, and template variable support.

Author: Filip Ristevski
License: MIT
"""

import os
import re
import sqlite3
import subprocess
from typing import Any

from flowlauncher import FlowLauncher  # type: ignore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PLUGIN_DIR, "vault.db")
ICON = "Images/icon.png"
ICON_STAR = "Images/icon_star.png"
ICON_TEMPLATE = "Images/icon_template.png"

VAR_PATTERN = re.compile(r"\{([a-zA-Z0-9_]+)\}")
PYTHON_EXE = os.path.join(PLUGIN_DIR, "python_path.txt")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def _icon(row) -> str:
    if row["is_favorite"]:
        if os.path.exists(os.path.join(PLUGIN_DIR, ICON_STAR)):
            return ICON_STAR
    return ICON


def _fts_ok(con: sqlite3.Connection) -> bool:
    try:
        con.execute("SELECT 1 FROM commands_fts LIMIT 1")
        return True
    except sqlite3.Error:
        return False


def _search(query: str) -> list:
    query = (query or "").strip()
    with _db() as con:
        if not query:
            # No query: show favorites first, then all (limited)
            return con.execute(
                "SELECT * FROM commands "
                "ORDER BY is_favorite DESC, category ASC, subcategory ASC, title ASC "
                "LIMIT 50"
            ).fetchall()

        if _fts_ok(con):
            # FTS5: tokenize safely
            fts_q = " OR ".join(
                f'"{t}"' for t in re.split(r"\s+", query) if t
            )
            try:
                rows = con.execute(
                    "SELECT c.* FROM commands_fts f "
                    "JOIN commands c ON c.id = f.rowid "
                    "WHERE commands_fts MATCH ? "
                    "ORDER BY c.is_favorite DESC, rank "
                    "LIMIT 50",
                    (fts_q,),
                ).fetchall()
                if rows:
                    return rows
            except sqlite3.Error:
                pass  # fall through to LIKE

        # Fallback: LIKE search across all relevant columns
        like = f"%{query}%"
        return con.execute(
            "SELECT * FROM commands "
            "WHERE title LIKE ? OR command LIKE ? OR description LIKE ? "
            "   OR tags LIKE ? OR category LIKE ? OR subcategory LIKE ? "
            "ORDER BY is_favorite DESC, category ASC, subcategory ASC, title ASC "
            "LIMIT 50",
            (like, like, like, like, like, like),
        ).fetchall()


def _format_title(row) -> str:
    parts = [row["category"]]
    if row["subcategory"]:
        parts.append(row["subcategory"])
    parts.append(row["title"])
    fav = "\u2605 " if row["is_favorite"] else ""
    return fav + " \u203a ".join(parts)


def _format_subtitle(row) -> str:
    cmd = row["command"]
    desc = row["description"] or ""
    has_vars = bool(VAR_PATTERN.search(cmd))
    template_hint = "  [template]" if has_vars else ""
    if desc:
        return f"{cmd}   \u2014   {desc}{template_hint}"
    return f"{cmd}{template_hint}"


def _set_clipboard(text: str) -> None:
    """Copy text to Windows clipboard using clip.exe."""
    p = subprocess.Popen(
        ["clip"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    p.communicate(text.encode("utf-16-le"))


def _prompt_variable(var_name: str, command_title: str) -> str:
    """Show a small PowerShell InputBox for a template variable."""
    script = (
        "Add-Type -AssemblyName Microsoft.VisualBasic; "
        f'[Microsoft.VisualBasic.Interaction]::InputBox('
        f'"Enter value for: {var_name}", '
        f'"Command Vault \u2014 {command_title}", "")'
    )
    try:
        result = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return result.strip()
    except subprocess.CalledProcessError:
        return ""


def _expand_template(command: str, title: str) -> str:
    """Replace {var} placeholders interactively."""
    vars_found = VAR_PATTERN.findall(command)
    if not vars_found:
        return command

    seen: dict[str, str] = {}
    for var in vars_found:
        if var not in seen:
            seen[var] = _prompt_variable(var, title)

    for k, v in seen.items():
        command = command.replace("{" + k + "}", v)
    return command


def _toggle_favorite(cmd_id: int) -> None:
    with _db() as con:
        con.execute(
            "UPDATE commands "
            "SET is_favorite = CASE WHEN is_favorite=1 THEN 0 ELSE 1 END, "
            "    updated_at = datetime('now') "
            "WHERE id = ?",
            (cmd_id,),
        )
        con.commit()


# ---------------------------------------------------------------------------
# Plugin class
# ---------------------------------------------------------------------------
class CommandVault(FlowLauncher):

    def query(self, query: str) -> list[dict[str, Any]]:
        # Special command: open the GUI manager
        if query.strip() in (":manage", ":manager", ":edit", ":gui"):
            return [
                {
                    "Title": "Open Command Vault Manager",
                    "SubTitle": "Add, edit, delete and organize your commands in a GUI",
                    "IcoPath": ICON,
                    "JsonRPCAction": {
                        "method": "open_manager",
                        "parameters": [],
                        "dontHideAfterAction": True,
                    },
                }
            ]

        rows = _search(query)
        if not rows:
            return [
                {
                    "Title": "No commands found",
                    "SubTitle": "cv [keyword]  —  empty shows favorites  |  cv :manage opens GUI editor",
                    "IcoPath": ICON,
                    "JsonRPCAction": {
                        "method": "noop",
                        "parameters": [],
                        "dontHideAfterAction": True,
                    },
                }
            ]

        results = []
        for r in rows:
            results.append(
                {
                    "Title": _format_title(r),
                    "SubTitle": _format_subtitle(r),
                    "IcoPath": _icon(r),
                    "JsonRPCAction": {
                        "method": "copy_command",
                        "parameters": [r["id"], r["title"]],
                        "dontHideAfterAction": False,
                    },
                    "ContextData": r["id"],
                }
            )
        return results

    def context_menu(self, data: Any) -> list[dict[str, Any]]:
        cmd_id = int(data) if data else None
        if not cmd_id:
            return []

        with _db() as con:
            row = con.execute(
                "SELECT * FROM commands WHERE id = ?", (cmd_id,)
            ).fetchone()

        if not row:
            return []

        fav_label = "Remove from favorites" if row["is_favorite"] else "Add to favorites"

        return [
            {
                "Title": "Copy command",
                "SubTitle": row["command"],
                "IcoPath": ICON,
                "JsonRPCAction": {
                    "method": "copy_command",
                    "parameters": [cmd_id, row["title"]],
                    "dontHideAfterAction": False,
                },
            },
            {
                "Title": fav_label,
                "SubTitle": "Toggle \u2605 favorite status",
                "IcoPath": ICON_STAR,
                "JsonRPCAction": {
                    "method": "toggle_favorite",
                    "parameters": [cmd_id],
                    "dontHideAfterAction": True,
                },
            },
            {
                "Title": "Open vault location",
                "SubTitle": DB_PATH,
                "IcoPath": ICON,
                "JsonRPCAction": {
                    "method": "open_vault_folder",
                    "parameters": [],
                    "dontHideAfterAction": True,
                },
            },
        ]

    # ---- Actions -----------------------------------------------------------

    def copy_command(self, cmd_id: int, title: str) -> None:
        with _db() as con:
            row = con.execute(
                "SELECT * FROM commands WHERE id = ?", (cmd_id,)
            ).fetchone()
        if not row:
            return
        cmd = _expand_template(row["command"], title)
        _set_clipboard(cmd)

    def toggle_favorite(self, cmd_id: int) -> None:
        _toggle_favorite(cmd_id)

    def open_vault_folder(self) -> None:
        subprocess.Popen(["explorer", PLUGIN_DIR])

    def open_manager(self) -> None:
        import sys
        manager = os.path.join(PLUGIN_DIR, "manager.py")
        subprocess.Popen(
            [sys.executable, manager],
            creationflags=subprocess.DETACHED_PROCESS,
        )

    def noop(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    CommandVault()
