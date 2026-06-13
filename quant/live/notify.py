"""Trade/event notifications.

Always prints to the console; if ``ALERT_WEBHOOK_URL`` is set in ``.env`` it also
POSTs to that URL. The payload includes both ``text`` (Slack) and ``content``
(Discord) keys so a standard incoming webhook from either works unchanged.
Uses stdlib ``urllib`` — no extra dependency.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import List


class Notifier:
    def notify(self, title: str, message: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    def notify(self, title: str, message: str) -> None:
        print(f"[ALERT] {title}: {message}")


class WebhookNotifier(Notifier):
    def __init__(self, url: str, timeout: float = 5.0):
        self.url = url
        self.timeout = timeout

    def notify(self, title: str, message: str) -> None:
        text = f"**{title}** — {message}"
        data = json.dumps({"text": text, "content": text}).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=data, headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req, timeout=self.timeout)
        except Exception as exc:  # never let a notification crash trading
            print(f"! webhook notify failed: {exc}")


class MultiNotifier(Notifier):
    def __init__(self, notifiers: List[Notifier]):
        self.notifiers = notifiers

    def notify(self, title: str, message: str) -> None:
        for n in self.notifiers:
            n.notify(title, message)


def build_notifier() -> Notifier:
    """Console always; add a webhook if ALERT_WEBHOOK_URL is configured."""
    notifiers: List[Notifier] = [ConsoleNotifier()]
    url = os.getenv("ALERT_WEBHOOK_URL")
    if url:
        notifiers.append(WebhookNotifier(url))
    return MultiNotifier(notifiers)
