"""Small, validated runtime configuration shared by software modules."""

import json
from copy import deepcopy
from pathlib import Path


DEFAULTS = {
    "confusion": {
        "emotion_weight": 0.60,
        "pulse_weight": 0.40,
        "attentive_max": 0.25,
        "confused_min": 0.60,
        "checkin_threshold": 0.60,
        "checkin_sustained_seconds": 3,
        "checkin_cooldown_seconds": 45,
    },
    "pulse": {"resting_bpm": 70, "elevated_bpm": 110, "valid_min": 35, "valid_max": 220},
    "glove_logging": {"enabled": True, "flush_every_rows": 30},
    "ui": {"require_login": False},
}


def _merge(base, override):
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config():
    path = Path(__file__).with_name("runtime_config.json")
    if not path.exists():
        return deepcopy(DEFAULTS)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        return _merge(DEFAULTS, loaded)
    except (OSError, ValueError, TypeError) as exc:
        print(f"[Config] Using defaults; could not read {path.name}: {exc}")
        return deepcopy(DEFAULTS)


CONFIG = load_config()


def setting(section, key):
    return CONFIG[section][key]
