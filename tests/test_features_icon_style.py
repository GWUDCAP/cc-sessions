import contextlib
import os
import sys
import tempfile
import types
from pathlib import Path

# Ensure shared_state locates an isolated project root before modules import it
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="cc-sessions-test-"))
os.environ.setdefault("CLAUDE_PROJECT_DIR", str(_TEST_ROOT))

# Ensure the project package can be imported without installation
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

PYTHON_DIR = PROJECT_ROOT / "cc_sessions" / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from hooks.shared_state import EnabledFeatures, IconStyle
from cc_sessions.python.api import config_commands


def _make_config(icon_style):
    features = types.SimpleNamespace(
        branch_enforcement=True,
        task_detection=True,
        auto_ultrathink=True,
        icon_style=icon_style,
        context_warnings=types.SimpleNamespace(warn_85=True, warn_90=True),
    )
    return types.SimpleNamespace(features=features)


def test_normalize_icon_style_aliases():
    style, changed, recognized = EnabledFeatures.normalize_icon_style("nerd-fonts")
    assert style is IconStyle.NERD_FONTS
    assert changed is True
    assert recognized is True

    style, changed, recognized = EnabledFeatures.normalize_icon_style("emoji")
    assert style is IconStyle.EMOJI
    assert changed is False
    assert recognized is True

    style, changed, recognized = EnabledFeatures.normalize_icon_style(False)
    assert style is IconStyle.ASCII
    assert changed is True
    assert recognized is True

    style, _, recognized = EnabledFeatures.normalize_icon_style("bogus")
    assert style is IconStyle.NERD_FONTS
    assert recognized is False


def test_handle_features_set_accepts_alias(monkeypatch):
    config = _make_config(IconStyle.EMOJI)

    @contextlib.contextmanager
    def fake_edit():
        yield config

    monkeypatch.setattr(config_commands, "edit_config", fake_edit)

    message = config_commands.handle_features_command(["set", "icon_style", "nerd-fonts"])
    assert config.features.icon_style is IconStyle.NERD_FONTS
    assert "nerd_fonts" in message


def test_handle_features_toggle_handles_strings(monkeypatch):
    config = _make_config("emoji")

    @contextlib.contextmanager
    def fake_edit():
        yield config

    monkeypatch.setattr(config_commands, "edit_config", fake_edit)
    monkeypatch.setattr(config_commands, "load_config", lambda: config)

    message = config_commands.handle_features_command(["toggle", "icon_style"])
    assert config.features.icon_style is IconStyle.ASCII
    assert "emoji" in message.lower()
    assert "ascii" in message.lower()
