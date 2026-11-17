# -*- coding: utf-8 -*-
"""English localization of screening payloads at response time."""

import re

from src.services.screening_i18n import localize_screening_payload
from src.ui_language import set_ui_language, _ui_language

_CJK = re.compile("[一-鿿]")

PAYLOAD = {
    "strategies": [{"name": "放量突破", "description": "成交量放大突破关键阻力位，趋势启动信号"}],
    "route": [{"title": "等待发酵", "description": "暂未获取到明确催化事件，可继续观察涨跌幅、成交额和核心个股联动。"}],
    "summary": "芯片热度 85.0，阶段 加速主升，核心股 中芯国际。",
    "desc": "芯片 当前涨跌幅 3.20%，盘中异动 5 次，高频异动个股为 中芯国际（大笔买入） 当日结构：火箭发射出现 2 次；异动类型 9 出现 1 次。",
    "why_selected": [{"text": "核心因子：value 80.0、momentum 70.0"}, {"text": "已进入当前选股候选结果"}],
    "message": "选股已完成，正在整理 12 条候选",
    "catalyst": "钼价上涨，带动小金属、相关个股发酵。",
    "news_title": "中芯国际放量突破新高",  # free-form data stays as-is
}


def _run(lang):
    token = set_ui_language(lang)
    try:
        return localize_screening_payload(PAYLOAD)
    finally:
        _ui_language.reset(token)


def test_chinese_ui_is_untouched():
    assert _run(None) is PAYLOAD
    assert _run("zh") is PAYLOAD


def test_english_ui_translates_fixed_phrases_and_templates():
    out = _run("en")
    assert out["strategies"][0] == {
        "name": "Volume breakout",
        "description": "Volume expansion breaking key resistance, a trend-start signal",
    }
    assert out["route"][0]["title"] == "Awaiting catalyst"
    assert out["summary"] == "芯片 heat 85.0, stage Accelerating, leaders 中芯国际。"
    assert out["desc"].startswith("芯片 current change 3.20%, 5 intraday moves, most frequent mover: ")
    assert "Rocket launch x2; Move type 9 x1." in out["desc"]
    assert out["why_selected"][0]["text"] == "Top factors: value 80.0, momentum 70.0"
    assert out["why_selected"][1]["text"] == "Included in the current screening results"
    assert out["message"] == "Screening done, organizing 12 candidates"
    assert out["catalyst"].endswith("driving 小金属、相关个股.")
    assert out["news_title"] == PAYLOAD["news_title"]


def test_all_known_strategy_yaml_strings_have_english():
    import glob
    import yaml

    token = set_ui_language("en")
    try:
        for path in glob.glob("src/services/screening/strategies/*.yaml"):
            with open(path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            for key in ("display_name", "description"):
                assert not _CJK.search(localize_screening_payload(data[key])), (path, key)
    finally:
        _ui_language.reset(token)
