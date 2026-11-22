"""Credit tracking — Omni Flash only, per Google AI Pro account.

Rates (user-confirmed, 21 Nov 2026):
  Omni Flash 1.2 at 720p: 3 credits / second
  Veo: 100 credits / 8-sec video — NOT used, do not budget for it.
Accounts: 2 x 1000 starting credits + 50/day each = 2000 + 100/day total.
Always read the Flow cost screen before a run — it is the only authority.

Ledger lives in data/credits.json (local only, never committed with
real balances — see .gitignore; a zeroed example is shipped).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import Config

OMNI_CREDITS_PER_SEC = 3.0
SHORT_TARGET_SEC = 40          # 35-45s Short, 8-10 scenes x 3-4s
LONG_TIER1_CLIPS = 25          # 22-28 planned, budget at 25
LONG_TIER1_CLIP_SEC = 6
LONG_RETAKE_CLIPS = 8
LONG_RETAKE_COST_EACH = 18     # 6s x 3 credits/sec


@dataclass
class CreditEstimate:
    kind: str
    seconds: float
    credits: float
    account: str
    ok: bool
    message: str


class CreditLedger:
    """Simple JSON ledger: {account: {"spent": int, "starting": int}}."""

    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.path = self.config.data_dir / "credits.json"
        self.data = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {a.name: {"spent": 0, "starting": a.starting_credits}
                for a in self.config.accounts}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def balance(self, account: str) -> int:
        row = self.data.get(account, {"spent": 0, "starting": 1000})
        return int(row["starting"]) - int(row["spent"])

    def balances(self) -> dict[str, int]:
        return {a.name: self.balance(a.name) for a in self.config.accounts}

    def total_balance(self) -> int:
        return sum(self.balances().values())

    # -- estimates ------------------------------------------------------
    @staticmethod
    def estimate_short(duration_sec: float = SHORT_TARGET_SEC) -> float:
        """40s Short, all hero clips: 40 x 3 = 120 credits."""
        return duration_sec * OMNI_CREDITS_PER_SEC

    @staticmethod
    def estimate_long(tier1_clips: int = LONG_TIER1_CLIPS,
                      retakes: int = LONG_RETAKE_CLIPS) -> dict:
        primary = tier1_clips * LONG_TIER1_CLIP_SEC * OMNI_CREDITS_PER_SEC
        reserve = retakes * LONG_RETAKE_COST_EACH
        return {"primary": primary, "retake_reserve": reserve,
                "max": primary + reserve}  # 450 + 144 = 594

    def check_before_spend(self, credits: float, account: str = "A") -> CreditEstimate:
        bal = self.balance(account)
        ok = credits <= bal
        msg = (f"OK: {credits:.0f} credits <= {bal} left on account {account}."
               if ok else
               f"STOP: need {credits:.0f} credits but only {bal} left on "
               f"account {account}. Use the other account, wait for the "
               f"+50/day refill, or cut Tier 1 clips (Tier 2/3 cost 0).")
        return CreditEstimate("spend", credits, credits, account, ok, msg)

    def record_spend(self, credits: float, account: str = "A",
                     note: str = "") -> int:
        row = self.data.setdefault(account, {"spent": 0, "starting": 1000})
        row["spent"] = int(row["spent"]) + int(credits)
        if note:
            row.setdefault("notes", []).append(note)
        self.save()
        return self.balance(account)

    def summary(self) -> str:
        lines = ["Credits (Omni Flash 3/sec, 2 accounts x 1000 + 50/day):"]
        for name, bal in self.balances().items():
            lines.append(f"  Account {name}: {bal} left")
        lines.append(f"  Total: {self.total_balance()} left")
        lines.append(f"  One 40s Short: {self.estimate_short():.0f} credits")
        est = self.estimate_long()
        lines.append(f"  One 9-min long-form: {est['primary']:.0f} primary "
                     f"+ {est['retake_reserve']:.0f} reserve = {est['max']:.0f} max")
        return "\n".join(lines)
