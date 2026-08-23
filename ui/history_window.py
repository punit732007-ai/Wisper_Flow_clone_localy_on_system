"""
LocalWhisper Pro — History Window
Searchable transcript viewer with 1-click copy, deletion, and AI re-processing.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pyperclip
from typing import Optional
from config import config
from core.history_manager import history_manager
from core.ai_refiner import ai_refiner


class HistoryWindow:
    """Transcript archive and search interface."""

    def __init__(self, parent_root: tk.Tk):
        self.parent = parent_root
        self.win: Optional[tk.Toplevel] = None
        self._selected_entry_id: Optional[str] = None

    def show(self) -> None:
        """Create or focus the history window."""
        if self.win is not None and self.win.winfo_exists():
            self.win.lift()
            self.win.focus_force()
            return

        self.win = tk.Toplevel(self.parent)
        self.win.title("LocalWhisper Pro — Transcript History")
        self.win.geometry("700x520")
        self.win.minsize(600, 400)
        self.win.configure(bg="#1e1e2e")

        # Top search bar
        search_frame = tk.Frame(self.win, bg="#181825", padx=12, pady=10)
        search_frame.pack(fill="x")

        tk.Label(search_frame, text="🔍 Search:", bg="#181825", fg="#cdd6f4", font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        search_entry = tk.Entry(search_frame, textvariable=self.search_var, bg="#11111b", fg="#cdd6f4", font=("Segoe UI", 10), insertbackground="#cdd6f4", width=36)
        search_entry.pack(side="left", fill="x", expand=True, padx=(0, 12))

        clear_all_btn = tk.Button(
            search_frame, text="Clear All", bg="#313244", fg="#f38ba8",
            activebackground="#45475a", font=("Segoe UI", 8),
            command=self._clear_all,
        )
        clear_all_btn.pack(side="right")

        # Main Paned View: Left = list, Right = full detail
        paned = tk.PanedWindow(self.win, orient="horizontal", bg="#1e1e2e", sashrelief="flat", sashwidth=4)
        paned.pack(fill="both", expand=True, padx=12, pady=10)

        # Left Listbox frame
        left_frame = tk.Frame(paned, bg="#1e1e2e")
        paned.add(left_frame, width=280)

        self.entry_listbox = tk.Listbox(
            left_frame, bg="#181825", fg="#cdd6f4", selectbackground="#45475a",
            selectforeground="#89b4fa", font=("Segoe UI", 9), borderwidth=0, highlightthickness=0,
        )
        self.entry_listbox.pack(fill="both", expand=True, side="left")
        self.entry_listbox.bind("<<ListboxSelect>>", self._on_entry_selected)

        scrollbar = tk.Scrollbar(left_frame, orient="vertical", command=self.entry_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.entry_listbox.config(yscrollcommand=scrollbar.set)

        # Right Detail frame
        right_frame = tk.Frame(paned, bg="#181825", padx=12, pady=12)
        paned.add(right_frame, width=400)

        self.meta_lbl = tk.Label(right_frame, text="Select an entry from the list", bg="#181825", fg="#89b4fa", font=("Segoe UI Semibold", 9), anchor="w")
        self.meta_lbl.pack(fill="x", pady=(0, 6))

        self.detail_text = tk.Text(
            right_frame, bg="#11111b", fg="#cdd6f4", insertbackground="#cdd6f4",
            font=("Segoe UI", 10), wrap="word", borderwidth=0, padx=8, pady=8,
        )
        self.detail_text.pack(fill="both", expand=True, pady=(0, 10))

        # Action Buttons
        btn_bar = tk.Frame(right_frame, bg="#181825")
        btn_bar.pack(fill="x")

        self.copy_btn = tk.Button(
            btn_bar, text="📋 Copy Text", bg="#89b4fa", fg="#11111b",
            activebackground="#b4befe", font=("Segoe UI Semibold", 9),
            padx=10, pady=3, relief="flat", command=self._copy_selected,
        )
        self.copy_btn.pack(side="left", padx=(0, 8))

        self.re_refine_btn = tk.Button(
            btn_bar, text="🔄 Re-refine with Mode...", bg="#313244", fg="#cdd6f4",
            activebackground="#45475a", font=("Segoe UI", 8),
            command=self._re_refine_popup,
        )
        self.re_refine_btn.pack(side="left", padx=(0, 8))

        self.del_btn = tk.Button(
            btn_bar, text="🗑️ Delete", bg="#313244", fg="#f38ba8",
            activebackground="#45475a", font=("Segoe UI", 8),
            command=self._delete_selected,
        )
        self.del_btn.pack(side="right")

        self._refresh_list()

    # ── Helpers ───────────────────────────────────────────────────

    def _refresh_list(self) -> None:
        query = self.search_var.get().strip() if hasattr(self, "search_var") else ""
        self._current_entries = history_manager.get_entries(limit=100, search_query=query)

        self.entry_listbox.delete(0, "end")
        for e in self._current_entries:
            snippet = e.get("refined_text", "")[:28].replace("\n", " ")
            mode_badge = e.get("mode_name", "Smart")
            date_time = e.get("date_str", "")[5:16]  # MM-DD HH:MM
            self.entry_listbox.insert("end", f"[{mode_badge}] {date_time} — {snippet}...")

        if self._current_entries:
            self.entry_listbox.selection_set(0)
            self._show_entry(self._current_entries[0])
        else:
            self.meta_lbl.config(text="No transcript history found.")
            self.detail_text.delete("1.0", "end")

    def _on_search_changed(self, *args) -> None:
        self._refresh_list()

    def _on_entry_selected(self, event=None) -> None:
        sel = self.entry_listbox.curselection()
        if sel and sel[0] < len(self._current_entries):
            entry = self._current_entries[sel[0]]
            self._show_entry(entry)

    def _show_entry(self, entry: dict) -> None:
        self._selected_entry_id = entry.get("id")
        mode = entry.get("mode_name", "")
        dur = entry.get("duration_sec", 0.0)
        wc = entry.get("word_count", 0)
        dt = entry.get("date_str", "")

        self.meta_lbl.config(text=f"📅 {dt}  |  🎯 {mode}  |  ⏱️ {dur}s  |  📝 {wc} words")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", entry.get("refined_text", ""))

    def _copy_selected(self) -> None:
        text = self.detail_text.get("1.0", "end").strip()
        if text:
            pyperclip.copy(text)
            messagebox.showinfo("Copied", "Transcript copied to clipboard!")

    def _delete_selected(self) -> None:
        if self._selected_entry_id:
            history_manager.delete_entry(self._selected_entry_id)
            self._refresh_list()

    def _clear_all(self) -> None:
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear all transcript history?"):
            history_manager.clear_history()
            self._refresh_list()

    def _re_refine_popup(self) -> None:
        if not self._selected_entry_id:
            return

        entry = next((e for e in self._current_entries if e.get("id") == self._selected_entry_id), None)
        if not entry:
            return

        raw_text = entry.get("raw_text", "")
        if not raw_text:
            raw_text = entry.get("refined_text", "")

        # Popup mode selector
        modes = config.all_modes
        mode_keys = list(modes.keys())

        dlg = tk.Toplevel(self.win)
        dlg.title("Select Mode for Re-refinement")
        dlg.geometry("320x160")
        dlg.configure(bg="#1e1e2e")

        tk.Label(dlg, text="Choose Dictation Mode:", bg="#1e1e2e", fg="#cdd6f4", font=("Segoe UI", 9)).pack(pady=(12, 4))
        sel_mode = tk.StringVar(value="pro")
        combo = ttk.Combobox(dlg, textvariable=sel_mode, values=mode_keys, state="readonly", width=20)
        combo.pack(pady=4)

        def _do_refine():
            target_mode = sel_mode.get()
            dlg.destroy()
            self.detail_text.delete("1.0", "end")
            self.detail_text.insert("1.0", "Re-refining with AI...")

            def _worker():
                # Temporarily switch mode for refinement
                orig_mode = config.get("current_mode", "smart")
                config.set("current_mode", target_mode, auto_save=False)
                new_text = ai_refiner.refine(raw_text, entry.get("language", "en"))
                config.set("current_mode", orig_mode, auto_save=False)

                if self.win and self.win.winfo_exists():
                    self.win.after(0, lambda: self._update_detail(new_text))

            import threading
            threading.Thread(target=_worker, daemon=True).start()

        tk.Button(dlg, text="Re-refine Now", bg="#89b4fa", fg="#11111b", command=_do_refine).pack(pady=12)

    def _update_detail(self, text: str) -> None:
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", text)
