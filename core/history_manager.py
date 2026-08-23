"""
LocalWhisper Pro — History Manager
Persists and searches transcript records in ~/.localwhisper/history.json.
"""

import json
import time
import uuid
import threading
from typing import List, Dict, Any, Optional
from config import HISTORY_FILE


class HistoryManager:
    """Thread-safe transcript history database."""

    def __init__(self):
        self._lock = threading.Lock()
        self._entries: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> None:
        """Load history entries from disk."""
        with self._lock:
            if HISTORY_FILE.exists():
                try:
                    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                        self._entries = json.load(f)
                except Exception as e:
                    print(f"[History] Error loading history: {e}")
                    self._entries = []
            else:
                self._entries = []

    def save(self) -> None:
        """Persist entries to disk."""
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[History] Error saving history: {e}")

    def add_entry(
        self,
        raw_text: str,
        refined_text: str,
        mode_key: str,
        mode_name: str,
        duration_sec: float,
        language: str = "en",
        model_name: str = "",
    ) -> Dict[str, Any]:
        """Record a newly completed dictation."""
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "date_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            "raw_text": raw_text.strip(),
            "refined_text": refined_text.strip(),
            "mode_key": mode_key,
            "mode_name": mode_name,
            "duration_sec": round(duration_sec, 2),
            "word_count": len(refined_text.split()),
            "language": language,
            "model_name": model_name,
        }

        with self._lock:
            # Prepend to list (most recent first)
            self._entries.insert(0, entry)
            # Limit stored history to last 500 items
            if len(self._entries) > 500:
                self._entries = self._entries[:500]
            self.save()

        return entry

    def get_entries(self, limit: int = 100, search_query: str = "") -> List[Dict[str, Any]]:
        """Retrieve history entries with optional search filter."""
        with self._lock:
            if not search_query.strip():
                return list(self._entries[:limit])
            
            q = search_query.lower()
            filtered = [
                e for e in self._entries
                if q in e.get("refined_text", "").lower()
                or q in e.get("raw_text", "").lower()
                or q in e.get("mode_name", "").lower()
            ]
            return filtered[:limit]

    def delete_entry(self, entry_id: str) -> bool:
        """Delete a single history entry by ID."""
        with self._lock:
            initial_len = len(self._entries)
            self._entries = [e for e in self._entries if e.get("id") != entry_id]
            if len(self._entries) < initial_len:
                self.save()
                return True
        return False

    def clear_history(self) -> None:
        """Wipe all saved history."""
        with self._lock:
            self._entries.clear()
            self.save()


history_manager = HistoryManager()
