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

CATEGORY_PREFIX = {
    "Cisco":   "[C]",
    "Linux":   "[L]",
    "Proxmox": "[P]",
    "Ansible": "[A]",
}


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


_OPERATORS = {
    # category
    "cat": "category", "c": "category", "category": "category",
    # subcategory
    "sub": "subcategory", "s": "subcategory", "subcategory": "subcategory",
    # tag
    "tag": "tag", "t": "tag",
    # favorites
    "fav": "favorites", "f": "favorites", "favorite": "favorites", "favorites": "favorites",
}

def _parse_query(raw: str) -> tuple[str, dict]:
    """
    Split a raw query into plain text + operator filters.

    Examples:
        "cat:cisco vlan"      → ("vlan", {"category": "cisco"})
        "fav: show mac"       → ("show mac", {"favorites": True})
        "tag:ccna sub:vlan"   → ("", {"tag": "ccna", "subcategory": "vlan"})
    """
    filters: dict = {}
    plain_tokens: list[str] = []

    for token in raw.split():
        if ":" in token:
            key, _, val = token.partition(":")
            key = key.lower().strip()
            val = val.strip()
            op = _OPERATORS.get(key)
            if op == "favorites":
                filters["favorites"] = True
            elif op and val:
                filters[op] = val
            else:
                plain_tokens.append(token)
        else:
            plain_tokens.append(token)

    return " ".join(plain_tokens), filters


def _search(query: str) -> list:
    raw = (query or "").strip()
    plain, filters = _parse_query(raw)

    with _db() as con:
        conditions: list[str] = []
        params: list = []

        # ── Operator filters ──────────────────────────────────────────────
        if filters.get("favorites"):
            conditions.append("is_favorite = 1")
        if cat := filters.get("category"):
            conditions.append("category LIKE ?")
            params.append(f"%{cat}%")
        if sub := filters.get("subcategory"):
            conditions.append("subcategory LIKE ?")
            params.append(f"%{sub}%")
        if tag := filters.get("tag"):
            conditions.append("tags LIKE ?")
            params.append(f"%{tag}%")

        # ── Plain text search ─────────────────────────────────────────────
        if plain:
            if _fts_ok(con) and not filters:
                # FTS5 only when no operator filters (avoids JOIN complexity)
                fts_q = " OR ".join(f'"{t}"' for t in plain.split() if t)
                try:
                    rows = con.execute(
                        "SELECT c.* FROM commands_fts f "
                        "JOIN commands c ON c.id = f.rowid "
                        "WHERE commands_fts MATCH ? "
                        + (("AND " + " AND ".join(conditions)) if conditions else "")
                        + " ORDER BY c.is_favorite DESC, rank LIMIT 50",
                        [fts_q] + params,
                    ).fetchall()
                    if rows:
                        return rows
                except sqlite3.Error:
                    pass

            # LIKE fallback
            like = f"%{plain}%"
            text_cond = (
                "(title LIKE ? OR command LIKE ? OR description LIKE ? "
                " OR tags LIKE ? OR category LIKE ? OR subcategory LIKE ?)"
            )
            conditions.append(text_cond)
            params += [like, like, like, like, like, like]

        # ── Build final query ─────────────────────────────────────────────
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return con.execute(
            f"SELECT * FROM commands {where} "
            "ORDER BY is_favorite DESC, category ASC, subcategory ASC, title ASC "
            "LIMIT 50",
            params,
        ).fetchall()


def _format_title(row) -> str:
    cat    = row["category"]
    sub    = row["subcategory"] or ""
    title  = row["title"]
    prefix = CATEGORY_PREFIX.get(cat, f"[{cat[0].upper()}]")
    fav    = "\u2605 " if row["is_favorite"] else ""
    if sub:
        return f"{fav}{prefix}  {sub}  \u203a  {title}"
    return f"{fav}{prefix}  {title}"


def _format_subtitle(row) -> str:
    cmd  = row["command"].replace("\n", "  \u21b5  ")  # show newlines as ↵
    desc = row["description"] or ""
    has_vars = bool(VAR_PATTERN.search(cmd))
    hints = []
    if has_vars:
        hints.append("\u270e template")       # ✎ template
    if desc:
        hints.append(desc)
    suffix = "   \u00b7   ".join(hints)       # ·
    return f"{cmd}   {suffix}" if suffix else cmd


def _set_clipboard(text: str) -> None:
    """Copy text to Windows clipboard using clip.exe."""
    p = subprocess.Popen(
        ["clip"],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    p.communicate(text.encode("utf-16-le"))


def _expand_template(command: str, title: str) -> str:
    """Show a proper tkinter dialog to fill in {variable} placeholders."""
    if not VAR_PATTERN.search(command):
        return command

    import sys
    import json as _json

    dialog = os.path.join(PLUGIN_DIR, "template_dialog.py")
    payload = _json.dumps({"command": command, "title": title})

    try:
        result = subprocess.run(
            [sys.executable, dialog, payload],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and result.stdout:
            return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return command  # fallback: return unchanged if dialog was cancelled


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
                    "SubTitle": (
                        "cv [text]  ·  cat:cisco  ·  sub:vlan  ·  tag:ccna  ·  fav:  ·  :manage"
                    ),
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

        fav_label = "\u2605  Remove from favorites" if row["is_favorite"] else "\u2606  Add to favorites"
        cmd_preview = row["command"][:80] + ("…" if len(row["command"]) > 80 else "")

        return [
            {
                "Title": "Copy command",
                "SubTitle": cmd_preview,
                "IcoPath": ICON,
                "JsonRPCAction": {
                    "method": "copy_command",
                    "parameters": [cmd_id, row["title"]],
                    "dontHideAfterAction": False,
                },
            },
            {
                "Title": fav_label,
                "SubTitle": "Favorites appear first on empty query",
                "IcoPath": ICON_STAR,
                "JsonRPCAction": {
                    "method": "toggle_favorite",
                    "parameters": [cmd_id],
                    "dontHideAfterAction": True,
                },
            },
            {
                "Title": "\u270e  Edit in Manager",
                "SubTitle": "Open the GUI editor for this command",
                "IcoPath": ICON,
                "JsonRPCAction": {
                    "method": "open_manager",
                    "parameters": [],
                    "dontHideAfterAction": True,
                },
            },
            {
                "Title": "\ud83d\udcc2  Open vault folder",
                "SubTitle": PLUGIN_DIR,
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
