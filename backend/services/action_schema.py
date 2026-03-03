"""
Action protocol parser and risk classifier.
Parses Gemini's text output into structured Action objects.
"""
from __future__ import annotations

import json
import re
import logging
from typing import Any

from models.schemas import Action, ActionType, ActionTarget, RiskLevel

logger = logging.getLogger(__name__)

# ─── Prompt hint injected into Gemini system prompt ──────────────────────────

def action_to_prompt_hint() -> str:
    return """
When you need to take an action on the user's computer, output it as a JSON block wrapped in triple backticks with the "action" label:

```action
{
  "action_type": "click",
  "target": {
    "type": "button",
    "label": "Send",
    "x": 450,
    "y": 320,
    "confidence": 0.95
  },
  "parameters": {},
  "risk_level": "high",
  "confidence": 0.95,
  "narration": "Clicking the Send button to send the email",
  "requires_confirmation": true,
  "undo_strategy": "open drafts and restore email"
}
```

Valid action_types: click, type, scroll, navigate, open_app, key_combo, drag, screenshot, search_web, read_clipboard, write_clipboard, wait

For type actions, include "text" in parameters: {"text": "Hello world"}
For scroll actions, include "direction" ("up"/"down") and "amount" (pixels) in parameters.
For key_combo actions, include "keys" list in parameters: {"keys": ["ctrl", "c"]}
For navigate actions, include "url" in parameters.
For open_app actions, include "app_name" in parameters.
For wait actions, include "duration_ms" in parameters.

Risk levels: low (navigation/scroll), medium (file writes, form typing), high (sends/submits), critical (delete/purchase/irreversible)

Always set requires_confirmation: true for high and critical risk actions.
Always narrate what you're doing in the narration field.
You can output multiple action blocks in sequence for multi-step tasks.
"""


# ─── Parser ──────────────────────────────────────────────────────────────────

ACTION_BLOCK_RE = re.compile(
    r"```action\s*\n(.*?)\n```",
    re.DOTALL | re.IGNORECASE,
)

JSON_OBJECT_RE = re.compile(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', re.DOTALL)


def parse_gemini_response(text: str) -> list[Action]:
    """
    Parse Gemini text output and extract Action objects.
    Looks for ```action ... ``` blocks first, then falls back to
    bare JSON objects containing 'action_type'.
    """
    actions: list[Action] = []

    # 1. Try explicit ```action blocks
    for match in ACTION_BLOCK_RE.finditer(text):
        raw = match.group(1).strip()
        action = _parse_action_json(raw)
        if action:
            actions.append(action)

    # 2. Fallback: look for bare JSON objects with action_type field
    if not actions:
        for match in JSON_OBJECT_RE.finditer(text):
            raw = match.group(0)
            if '"action_type"' in raw or "'action_type'" in raw:
                action = _parse_action_json(raw)
                if action:
                    actions.append(action)

    return actions


def _parse_action_json(raw: str) -> Action | None:
    try:
        data: dict[str, Any] = json.loads(raw)
        return _dict_to_action(data)
    except json.JSONDecodeError:
        # Try to fix common JSON issues
        fixed = _fix_json(raw)
        if fixed:
            try:
                data = json.loads(fixed)
                return _dict_to_action(data)
            except json.JSONDecodeError:
                pass
    except Exception as e:
        logger.warning(f"Failed to parse action JSON: {e} | raw: {raw[:200]}")
    return None


def _dict_to_action(data: dict[str, Any]) -> Action | None:
    try:
        # Normalize action_type
        raw_type = data.get("action_type", "").lower().replace("-", "_")
        try:
            action_type = ActionType(raw_type)
        except ValueError:
            logger.warning(f"Unknown action_type: {raw_type}")
            return None

        # Parse target
        target = None
        if "target" in data and data["target"]:
            t = data["target"]
            if isinstance(t, dict):
                target = ActionTarget(
                    type=t.get("type", "coordinate"),
                    label=t.get("label"),
                    selector=t.get("selector"),
                    x=t.get("x"),
                    y=t.get("y"),
                    width=t.get("width"),
                    height=t.get("height"),
                    confidence=float(t.get("confidence", 0.9)),
                )

        # Parse risk level
        raw_risk = data.get("risk_level", "low").lower()
        try:
            risk_level = RiskLevel(raw_risk)
        except ValueError:
            risk_level = RiskLevel.low

        action = Action(
            action_type=action_type,
            target=target,
            parameters=data.get("parameters", {}),
            risk_level=risk_level,
            confidence=float(data.get("confidence", 0.9)),
            narration=data.get("narration", ""),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            undo_strategy=data.get("undo_strategy"),
            agent_source=data.get("agent_source", "phantom_core"),
        )
        # Override requires_confirmation for high/critical if not set
        if action.risk_level in (RiskLevel.high, RiskLevel.critical):
            action.requires_confirmation = True

        return action
    except Exception as e:
        logger.warning(f"Failed to construct Action from dict: {e}")
        return None


def _fix_json(raw: str) -> str | None:
    """Attempt basic JSON repair: trailing commas, single-quoted keys/values.

    Only replaces single quotes used as JSON delimiters (keys and string values
    at field boundaries). Apostrophes inside string content — e.g. "don't" —
    are preserved because they are not at a key or value boundary.
    """
    # Remove trailing commas before } or ]
    fixed = re.sub(r",\s*([\]}])", r"\1", raw)
    # Replace single-quoted keys: {'key': ...} → {"key": ...}
    fixed = re.sub(r"'([^'\n]*?)'(\s*:)", r'"\1"\2', fixed)
    # Replace single-quoted string values (after : or [ boundaries)
    fixed = re.sub(r"([:,\[]\s*)'([^'\n]*?)'", r'\1"\2"', fixed)
    return fixed


# ─── Risk classifier ─────────────────────────────────────────────────────────

_HIGH_RISK_LABELS = {
    "send", "submit", "confirm", "save", "upload",
    "post", "publish", "share", "sign in", "log in", "login",
    "checkout", "pay", "purchase", "buy", "order",
    "sign", "authorize",
}

_CRITICAL_RISK_LABELS = {
    "delete", "remove", "clear", "erase", "wipe", "destroy",
    "uninstall", "format", "reset", "terminate", "kill",
    "drop", "purge", "revoke", "cancel subscription",
}

_CRITICAL_KEY_COMBOS = {
    frozenset(["ctrl", "shift", "delete"]),
    frozenset(["shift", "delete"]),
}

_HIGH_KEY_COMBOS = {
    frozenset(["ctrl", "w"]),
    frozenset(["alt", "f4"]),
    frozenset(["ctrl", "shift", "w"]),
}


def risk_score(action: Action) -> RiskLevel:
    """
    Re-classify action risk based on action type and parameters/target.
    Used by SafetyAgent to override Gemini's self-reported risk level.
    """
    label = (action.target.label or "").lower() if action.target else ""
    params = action.parameters

    if action.action_type == ActionType.key_combo:
        keys = frozenset(k.lower() for k in params.get("keys", []))
        if keys in _CRITICAL_KEY_COMBOS:
            return RiskLevel.critical
        if keys in _HIGH_KEY_COMBOS:
            return RiskLevel.high

    if action.action_type == ActionType.click:
        for word in _CRITICAL_RISK_LABELS:
            if word in label:
                return RiskLevel.critical
        for word in _HIGH_RISK_LABELS:
            if word in label:
                return RiskLevel.high

    if action.action_type == ActionType.navigate:
        url = params.get("url", "")
        if any(kw in url for kw in ["checkout", "payment", "delete", "remove"]):
            return RiskLevel.high

    if action.action_type == ActionType.type:
        # Typing in password-like fields
        selector = (action.target.selector or "").lower() if action.target else ""
        target_type = (action.target.type or "").lower() if action.target else ""
        if "password" in selector or "password" in label or target_type == "password":
            return RiskLevel.high

    # Return the action's own risk level if no override triggered
    return action.risk_level
