import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class HistoryEntry:
    timestamp: str
    user: str
    assistant: str


@dataclass
class MemorySummary:
    total_conversations: int
    total_facts: int
    latest_interaction: str | None


@dataclass
class UserPreference:
    category: str
    key: str
    value: str
    confidence: float = 0.0
    learned_from: str = "implicit"
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "learned_from": self.learned_from,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "UserPreference":
        return cls(
            category=payload.get("category", ""),
            key=payload.get("key", ""),
            value=payload.get("value", ""),
            confidence=float(payload.get("confidence", 0.0)),
            learned_from=payload.get("learned_from", "implicit"),
            last_updated=payload.get("last_updated", datetime.now().isoformat()),
        )


class MemoryEngine:
    """A reusable memory engine for EchoDesk.

    MemoryEngine stores short-term conversation history and persistent user
    facts in a JSON file under memory/data/. It supports retrieval, summary,
    and context delivery across application runs.
    """

    DEFAULT_DIR = Path(__file__).resolve().parent.parent / "memory" / "data"
    DEFAULT_FILE = "memory.json"
    MAX_HISTORY = 50

    def __init__(self, file_path: str | None = None):
        """Create a memory engine instance.

        Args:
            file_path: Optional custom path to the JSON file used for memory
                persistence. If omitted, memory/data/memory.json is used.
        """
        self.file_path = Path(file_path) if file_path else self.DEFAULT_DIR / self.DEFAULT_FILE
        self._ensure_storage_dir()
        self._payload = self._load_payload()
        print("[Memory] Loaded")

    def remember_fact(self, subject: str, value: str) -> str | None:
        """Store or update a memory fact about the user.

        Args:
            subject: The fact key or subject.
            value: The fact value.

        Returns:
            A human-readable confirmation message, or None when the inputs are
            invalid.
        """
        normalized_subject = self._normalize_subject(subject)
        normalized_value = self._normalize_value(value)

        if not normalized_subject or not normalized_value:
            return None

        existing_index = self._find_fact_index(normalized_subject)
        if existing_index is not None:
            existing = self._payload["facts"][existing_index]
            if existing["value"].strip().lower() == normalized_value.strip().lower():
                return f"I already remember that your {normalized_subject} is {existing['value']}."

            self._payload["facts"][existing_index]["value"] = normalized_value.strip()
            self._payload["facts"][existing_index]["updated_at"] = self._timestamp()
            self._write_payload()
            print("[Memory] Stored Fact")
            return f"I updated your {normalized_subject} to {normalized_value}."

        fact = {
            "subject": normalized_subject,
            "value": normalized_value.strip(),
            "created_at": self._timestamp(),
            "updated_at": self._timestamp(),
        }
        self._payload["facts"].append(fact)
        self._write_payload()
        print("[Memory] Stored Fact")
        return f"I will remember that your {normalized_subject} is {normalized_value}."

    def retrieve_fact(self, subject: str) -> str | None:
        """Retrieve a previously stored fact by subject.

        Args:
            subject: The fact's subject or key.

        Returns:
            A human-readable summary of the fact, or None if no matching fact is
            found.
        """
        normalized_subject = self._normalize_subject(subject)
        index = self._find_fact_index(normalized_subject)
        if index is None:
            return None

        value = self._payload["facts"][index]["value"]
        print("[Memory] Retrieved Fact")
        return f"Your {normalized_subject} is {value}."

    def update_fact(self, subject: str, value: str) -> str | None:
        """Update an existing memory fact.

        Args:
            subject: The existing fact subject.
            value: The updated fact value.

        Returns:
            A human-readable confirmation message, or None if no existing fact
            matches the subject.
        """
        normalized_subject = self._normalize_subject(subject)
        existing_index = self._find_fact_index(normalized_subject)
        if existing_index is None:
            return None

        self._payload["facts"][existing_index]["value"] = self._normalize_value(value)
        self._payload["facts"][existing_index]["updated_at"] = self._timestamp()
        self._write_payload()
        return f"I updated your {normalized_subject} to {value.strip()}."

    def delete_fact(self, subject: str) -> str | None:
        """Delete a stored memory fact.

        Args:
            subject: The subject of the fact to delete.

        Returns:
            A human-readable confirmation message, or None if the fact is not
            found.
        """
        normalized_subject = self._normalize_subject(subject)
        existing_index = self._find_fact_index(normalized_subject)
        if existing_index is None:
            return None

        removed = self._payload["facts"].pop(existing_index)
        self._write_payload()
        return f"I forgot that your {normalized_subject} is {removed['value']}."

    def search_facts(self, keyword: str) -> str | None:
        """Search stored facts by keyword.

        Args:
            keyword: The search keyword.

        Returns:
            A concise summary of matching memory facts, or None if no matches
            were found.
        """
        normalized_keyword = self._normalize_subject(keyword)
        if not normalized_keyword:
            return None

        matches = []
        for fact in self._payload["facts"]:
            if normalized_keyword in fact["subject"] or normalized_keyword in fact["value"].lower():
                matches.append(fact)

        if not matches:
            return None

        if len(matches) == 1:
            fact = matches[0]
            return f"I remember that your {fact['subject']} is {fact['value']}."

        joined = ". ".join(
            f"Your {fact['subject']} is {fact['value']}" for fact in matches[:3]
        )
        return f"I remember several things: {joined}."

    def is_memory_command(self, command: str) -> bool:
        """Detect whether a command should be handled by memory intelligence.

        Args:
            command: The user's raw command.

        Returns:
            True when the command is related to memory storage, retrieval,
            update, deletion, or search.
        """
        if not isinstance(command, str):
            return False

        normalized = command.lower().strip()
        if not normalized:
            return False

        patterns = [
            r"^(?:remember(?: that)?|please remember)\s+",
            r"^(?:update|change|set|modify)\s+",
            r"^(?:forget|forget about|forget that|delete|remove)\s+",
            r"^(?:search memory for|find in memory|find memory|memory search|memory lookup)\s+",
            r"^(?:what is my|what are my|tell me about my|do i have|what do i know about|what do you know about my)\s+",
        ]

        return any(re.match(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    def process_command(self, command: str) -> str | None:
        """Interpret a natural language command to manage user memory.

        Args:
            command: The user's raw command.

        Returns:
            A response string when the command is related to memory management,
            otherwise None.
        """
        if not isinstance(command, str):
            return None

        normalized = command.lower().strip()
        if not normalized:
            return None

        remember_match = self._match_pattern(
            normalized,
            r"^(?:remember(?: that)?|please remember)\s+(?P<subject>.+?)\s+(?:is|are|was|were|to be|=)\s+(?P<value>.+)$",
        )
        if remember_match:
            return self.remember_fact(remember_match.group("subject"), remember_match.group("value"))

        remember_as_match = self._match_pattern(
            normalized,
            r"^(?:remember(?: that)?|please remember)\s+(?P<subject>.+?)\s+as\s+(?P<value>.+)$",
        )
        if remember_as_match:
            return self.remember_fact(remember_as_match.group("subject"), remember_as_match.group("value"))

        update_match = self._match_pattern(
            normalized,
            r"^(?:update|change|set|modify)\s+(?P<subject>.+?)\s+(?:to|as|=)\s+(?P<value>.+)$",
        )
        if update_match:
            subject = update_match.group("subject")
            value = update_match.group("value")
            response = self.update_fact(subject, value)
            if response:
                return response
            return self.remember_fact(subject, value)

        delete_match = self._match_pattern(
            normalized,
            r"^(?:forget|forget about|forget that|delete|remove)\s+(?:about\s+)?(?P<subject>.+)$",
        )
        if delete_match:
            return self.delete_fact(delete_match.group("subject"))

        search_memory_match = self._match_pattern(
            normalized,
            r"^(?:search memory for|find in memory|find memory|memory search|memory lookup)\s+(?P<keyword>.+)$",
        )
        if search_memory_match:
            return self.search_facts(search_memory_match.group("keyword"))

        retrieve_match = self._match_pattern(
            normalized,
            r"^(?:what is my|what are my|tell me about my|do i have|what do i know about|what do you know about my)\s+(?P<subject>.+)$",
        )
        if retrieve_match:
            response = self.retrieve_fact(retrieve_match.group("subject"))
            if response:
                return response
            return self.search_facts(retrieve_match.group("subject"))

        remember_about_match = self._match_pattern(
            normalized,
            r"^(?:what do you remember about me|what do you know about me)\??$",
        )
        if remember_about_match:
            summary = self.summary()
            if summary.total_facts == 0 and summary.total_conversations == 0:
                return "I don't have any memories yet."
            fact_part = (
                f"I remember {summary.total_facts} fact(s)." if summary.total_facts else "I don't have any stored facts yet."
            )
            convo_part = (
                f"I have {summary.total_conversations} recent conversation(s)." if summary.total_conversations else "I don't have any recent conversations."
            )
            return f"{fact_part} {convo_part}"

        return None

    def learn(
        self,
        command: str,
        capability: str | None = None,
        success: bool = True,
        response: str | None = None,
        duration: float | None = None,
    ) -> None:
        if not isinstance(command, str) or not command.strip():
            return

        normalized_command = self._normalize_command(command)
        stats = self._payload.setdefault("command_stats", [])
        command_entry = self._find_command_entry(normalized_command)
        now = self._timestamp()

        if command_entry is None:
            command_entry = {
                "command": command.strip(),
                "normalized": normalized_command,
                "frequency": 1,
                "last_used": now,
                "success_count": 1 if success else 0,
                "fail_count": 0 if success else 1,
                "last_response": response or "",
            }
            stats.append(command_entry)
        else:
            command_entry["frequency"] += 1
            command_entry["last_used"] = now
            command_entry["success_count"] += 1 if success else 0
            command_entry["fail_count"] += 0 if success else 1
            command_entry["last_response"] = response or command_entry.get("last_response", "")

        self._payload["statistics"]["total_commands"] = self._payload["statistics"].get("total_commands", 0) + 1

        if capability:
            counts = self._payload["statistics"].setdefault("capability_counts", {})
            counts[capability] = counts.get(capability, 0) + 1

        if duration is not None and duration > 0:
            self._payload["statistics"]["session_count"] = self._payload["statistics"].get("session_count", 0) + 1
            self._payload["statistics"]["total_duration"] = self._payload["statistics"].get("total_duration", 0.0) + float(duration)

        self._payload["statistics"]["last_active"] = now

        for pref in self._infer_preferences(normalized_command):
            self.remember_preference(
                pref.category,
                pref.key,
                pref.value,
                confidence=pref.confidence,
                learned_from="behavior",
            )

        self._write_payload()

    def remember_preference(
        self,
        category: str,
        key: str,
        value: str,
        confidence: float = 0.5,
        learned_from: str = "explicit",
    ) -> UserPreference | None:
        if not category or not key or not value:
            return None

        category_text = category.strip()
        key_text = key.strip()
        value_text = value.strip()
        now = self._timestamp()

        preferences = self._payload.setdefault("preferences", [])
        index = self._find_preference_index(category_text, key_text)

        if index is not None:
            pref = preferences[index]
            if pref.get("value") == value_text:
                pref["confidence"] = min(1.0, float(pref.get("confidence", 0.0)) + 0.1)
            else:
                pref["value"] = value_text
                pref["confidence"] = float(confidence)
            pref["learned_from"] = learned_from
            pref["last_updated"] = now
            self._write_payload()
            print("[Learning] Preference updated")
            return UserPreference.from_dict(pref)

        new_pref = UserPreference(
            category=category_text,
            key=key_text,
            value=value_text,
            confidence=float(confidence),
            learned_from=learned_from,
            last_updated=now,
        )
        preferences.append(new_pref.to_dict())
        self._write_payload()
        print("[Learning] New preference learned")
        return new_pref

    def get_preferences(self) -> list[UserPreference]:
        return [UserPreference.from_dict(pref) for pref in self._payload.get("preferences", []) if isinstance(pref, dict)]

    def get_statistics(self) -> dict[str, Any]:
        statistics = self._payload.get("statistics", self._default_statistics())
        history = self._payload.get("history", [])
        command_stats = self._payload.get("command_stats", [])
        total_commands = statistics.get("total_commands", sum(item.get("frequency", 0) for item in command_stats))
        session_count = statistics.get("session_count", 0)
        average_session_length = (
            float(statistics.get("total_duration", 0.0)) / session_count
            if session_count > 0
            else 0.0
        )
        capability_counts = statistics.get("capability_counts", {})
        most_used_capability = max(capability_counts, key=capability_counts.get) if capability_counts else None

        return {
            "total_conversations": len(history),
            "total_commands": total_commands,
            "most_used_capability": most_used_capability,
            "average_session_length": average_session_length,
            "last_active": statistics.get("last_active"),
        }

    def get_top_commands(self, limit: int = 20) -> list[dict[str, Any]]:
        stats = self._payload.get("command_stats", [])
        ordered = sorted(stats, key=lambda item: item.get("frequency", 0), reverse=True)
        top = []
        for item in ordered[:limit]:
            frequency = int(item.get("frequency", 0))
            success = int(item.get("success_count", 0))
            fail = int(item.get("fail_count", 0))
            total = frequency if frequency > 0 else 1
            top.append(
                {
                    "command": item.get("command", ""),
                    "frequency": frequency,
                    "last_used": item.get("last_used"),
                    "success_rate": success / total,
                }
            )
        return top

    def recommend(self, limit: int = 3) -> list[str]:
        recommendations: list[str] = []
        preferences = self.get_preferences()
        statistics = self.get_statistics()
        top_commands = self.get_top_commands(3)

        if preferences:
            for pref in preferences[:limit]:
                recommendations.append(
                    f"I noticed you often prefer {pref.value} for {pref.key.lower()}.")

        if top_commands:
            rec = top_commands[0]
            if rec["frequency"] > 1:
                recommendations.append(
                    f"You frequently use the command '{rec['command']}'.")

        if statistics.get("most_used_capability"):
            recommendations.append(
                f"Your most used capability is {statistics['most_used_capability']}.")

        if not recommendations:
            recommendations.append("I have some learning data, but I need more use to offer personalized recommendations.")

        print("[Learning] Recommendation generated")
        return recommendations

    def _infer_preferences(self, normalized_command: str) -> list[UserPreference]:
        preferences: list[UserPreference] = []
        if any(keyword in normalized_command for keyword in ("python", "programming", "code", "function", "class", "debug")):
            preferences.append(
                UserPreference(
                    category="Language",
                    key="Programming Language",
                    value="Python",
                    confidence=0.5,
                )
            )

        if any(keyword in normalized_command for keyword in ("visual studio code", "vscode")):
            preferences.append(
                UserPreference(
                    category="Editor",
                    key="Preferred Editor",
                    value="VS Code",
                    confidence=0.5,
                )
            )

        if any(keyword in normalized_command for keyword in ("google chrome", "chrome")):
            preferences.append(
                UserPreference(
                    category="Browser",
                    key="Preferred Browser",
                    value="Chrome",
                    confidence=0.5,
                )
            )

        if any(keyword in normalized_command for keyword in ("firefox",)):
            preferences.append(
                UserPreference(
                    category="Browser",
                    key="Preferred Browser",
                    value="Firefox",
                    confidence=0.5,
                )
            )

        if any(keyword in normalized_command for keyword in ("dark mode", "dark theme", "theme dark")):
            preferences.append(
                UserPreference(
                    category="Theme",
                    key="Theme",
                    value="Dark",
                    confidence=0.5,
                )
            )
        return preferences

    def _find_command_entry(self, normalized_command: str) -> dict[str, Any] | None:
        for entry in self._payload.get("command_stats", []):
            if entry.get("normalized") == normalized_command:
                return entry
        return None

    def _find_preference_index(self, category: str, key: str) -> int | None:
        for index, pref in enumerate(self._payload.get("preferences", [])):
            if (
                pref.get("category", "").strip().lower() == category.strip().lower()
                and pref.get("key", "").strip().lower() == key.strip().lower()
            ):
                return index
        return None

    def _normalize_command(self, command: str) -> str:
        normalized = command.strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized

    def _load_payload(self) -> dict[str, Any]:
        if not os.path.exists(self.file_path):
            return self._default_payload()

        try:
            with open(self.file_path, "r", encoding="utf-8") as file:
                payload = json.load(file)
        except (json.JSONDecodeError, ValueError, OSError):
            payload = self._default_payload()
            self._write_payload(payload)
            return payload

        if not isinstance(payload, dict):
            payload = self._default_payload()

        if "history" not in payload or not isinstance(payload["history"], list):
            payload["history"] = []

        if "facts" not in payload or not isinstance(payload["facts"], list):
            payload["facts"] = []

        if "preferences" not in payload or not isinstance(payload["preferences"], list):
            payload["preferences"] = []

        if "command_stats" not in payload or not isinstance(payload["command_stats"], list):
            payload["command_stats"] = []

        if "statistics" not in payload or not isinstance(payload["statistics"], dict):
            payload["statistics"] = self._default_statistics()

        return payload

    def _write_payload(self, payload: dict[str, Any] | None = None) -> None:
        payload = payload if payload is not None else self._payload
        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=4)
        self._payload = payload
        print("[Memory] Saved")

    def _default_statistics(self) -> dict[str, Any]:
        return {
            "total_commands": 0,
            "session_count": 0,
            "total_duration": 0.0,
            "last_active": None,
            "capability_counts": {},
        }

    def _default_payload(self) -> dict[str, Any]:
        return {
            "history": [],
            "facts": [],
            "preferences": [],
            "command_stats": [],
            "statistics": self._default_statistics(),
        }

    def _ensure_storage_dir(self) -> None:
        directory = self.file_path.parent
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)

    def add_interaction(self, user: str, assistant: str) -> None:
        """Store a user-assistant interaction in short-term memory."""
        if not isinstance(user, str) or not isinstance(assistant, str):
            return

        entry = {
            "timestamp": self._timestamp(),
            "user": user.strip(),
            "assistant": assistant.strip(),
        }

        self._payload.setdefault("history", [])
        self._payload["history"].append(entry)
        self._payload["history"] = self._payload["history"][-self.MAX_HISTORY:]
        self._write_payload()

    def get_recent_context(self, limit: int = 5) -> list[HistoryEntry]:
        """Return the most recent conversation history entries."""
        history = self._payload.get("history", [])
        entries = history[-limit:]
        return [HistoryEntry(**entry) for entry in entries]

    def summary(self) -> MemorySummary:
        """Return a summary of stored conversations and facts."""
        history = self._payload.get("history", [])
        facts = self._payload.get("facts", [])
        latest_interaction = history[-1]["timestamp"] if history else None
        return MemorySummary(
            total_conversations=len(history),
            total_facts=len(facts),
            latest_interaction=latest_interaction,
        )

    def _normalize_subject(self, subject: str) -> str:
        normalized = subject.strip().lower()
        normalized = re.sub(r"^my\s+", "", normalized)
        normalized = re.sub(r"[?!.]+$", "", normalized)
        normalized = re.sub(r"\s{2,}", " ", normalized)
        return normalized

    def _normalize_value(self, value: str) -> str:
        return value.strip()

    def _find_fact_index(self, subject: str) -> int | None:
        subject = self._normalize_subject(subject)
        for index, fact in enumerate(self._payload["facts"]):
            if self._normalize_subject(fact.get("subject", "")) == subject:
                return index
        return None

    def _match_pattern(self, text: str, pattern: str) -> re.Match[str] | None:
        return re.match(pattern, text, flags=re.IGNORECASE)

    def _timestamp(self) -> str:
        return datetime.now().isoformat()
