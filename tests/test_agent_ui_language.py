# -*- coding: utf-8 -*-
"""English UI localization of ask-stock agent text."""

from pathlib import Path

from src.agent.skills.base import load_skill_from_yaml
from src.agent.runner import _THINKING_TOOL_LABELS, _THINKING_TOOL_LABELS_EN
from api.v1.endpoints.agent import TOOL_DISPLAY_NAMES, TOOL_DISPLAY_NAMES_EN, _skill_name
from src.ui_language import set_ui_language, _ui_language

STRATEGIES = sorted(Path(__file__).resolve().parents[1].glob("strategies/*.yaml"))


def test_tool_label_maps_cover_same_tools():
    assert TOOL_DISPLAY_NAMES.keys() == TOOL_DISPLAY_NAMES_EN.keys()
    assert _THINKING_TOOL_LABELS.keys() == _THINKING_TOOL_LABELS_EN.keys()


def test_all_strategies_have_english_name_and_description():
    assert len(STRATEGIES) == 15
    token = set_ui_language("en")
    try:
        for path in STRATEGIES:
            skill = load_skill_from_yaml(path)
            assert skill.description_en, path.name
            assert _skill_name(skill).isascii(), path.name
    finally:
        _ui_language.reset(token)


def test_skill_name_is_unchanged_for_chinese_ui():
    skill = load_skill_from_yaml(STRATEGIES[0])
    assert _skill_name(skill) == skill.display_name
