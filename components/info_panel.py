"""
components/info_panel.py
------------------------
右侧信息栏：公式 / 更新规则 / 参数 / 动态刷新值 / 收敛提示。

槽位（自上而下，y 坐标从 layouts.constants 取）：
    formula  - 主公式
    rule     - 更新规则 / 推导
    param    - 参数（如 α=0.25）
    value    - 动态刷新值（θ_t = ...） ← 唯一一个会被 update() 替换
    result   - 收敛 / 总结

调用方决定每个槽位的内容、颜色、字号。

用法：
    panel = InfoPanel()
    panel.set_formula(r"L(\theta)=(\theta-2)^2", color=BLUE)
    panel.set_rule(r"\theta_{t+1}=\theta_t-\alpha\nabla L")
    panel.set_param(r"\alpha=0.25", color=YELLOW)
    panel.set_value(rf"\theta_0={x0:.2f}", color=YELLOW)

    self.play(*panel.write_anims_for(["formula", "rule", "param", "value"]),
              run_time=1.5)

    # 迭代过程中刷新当前值：
    new_anims = panel.update_value(rf"\theta_1={x1:.2f}", color=YELLOW)
    self.play(*new_anims, run_time=0.4)
"""

from __future__ import annotations

from typing import Dict, List, Optional

from manim import (
    Animation,
    FadeIn,
    FadeOut,
    MathTex,
    Text,
    VGroup,
    WHITE,
    Write,
)

from layouts.constants import (
    FONT_ZH,
    FS_BODY,
    FS_FORMULA,
    FS_FORMULA_BIG,
    FS_PARAM,
    FS_VALUE,
    INFO_FORMULA_Y,
    INFO_PANEL_X,
    INFO_PARAM_Y,
    INFO_RESULT_Y,
    INFO_RULE_Y,
    INFO_VALUE_Y,
)


_SLOT_Y = {
    "formula": INFO_FORMULA_Y,
    "rule": INFO_RULE_Y,
    "param": INFO_PARAM_Y,
    "value": INFO_VALUE_Y,
    "result": INFO_RESULT_Y,
}

_SLOT_DEFAULT_FS = {
    "formula": FS_FORMULA_BIG,
    "rule": FS_FORMULA,
    "param": FS_PARAM,
    "value": FS_VALUE,
    "result": FS_BODY,
}


class InfoPanel:
    def __init__(self, x: float = INFO_PANEL_X) -> None:
        self.x = x
        self._slots: Dict[str, Optional[object]] = {
            "formula": None,
            "rule": None,
            "param": None,
            "value": None,
            "result": None,
        }

    # --------------------------------------------------------
    # 设置槽位（构造 mobject，不播放动画）
    # --------------------------------------------------------
    def _make_math(self, slot: str, tex: str, color, font_size: Optional[int]) -> MathTex:
        fs = font_size or _SLOT_DEFAULT_FS[slot]
        m = MathTex(tex, font_size=fs, color=color)
        m.move_to([self.x, _SLOT_Y[slot], 0])
        return m

    def _make_text(self, slot: str, text: str, color, font_size: Optional[int]) -> Text:
        fs = font_size or _SLOT_DEFAULT_FS[slot]
        m = Text(text, font=FONT_ZH, font_size=fs, color=color)
        m.move_to([self.x, _SLOT_Y[slot], 0])
        return m

    def set_formula(self, tex: str, color=WHITE, font_size: Optional[int] = None) -> "InfoPanel":
        self._slots["formula"] = self._make_math("formula", tex, color, font_size)
        return self

    def set_rule(self, tex: str, color=WHITE, font_size: Optional[int] = None) -> "InfoPanel":
        self._slots["rule"] = self._make_math("rule", tex, color, font_size)
        return self

    def set_param(self, tex: str, color=WHITE, font_size: Optional[int] = None) -> "InfoPanel":
        self._slots["param"] = self._make_math("param", tex, color, font_size)
        return self

    def set_value(self, tex: str, color=WHITE, font_size: Optional[int] = None) -> "InfoPanel":
        self._slots["value"] = self._make_math("value", tex, color, font_size)
        return self

    def set_result_zh(self, text: str, color=WHITE, font_size: Optional[int] = None) -> "InfoPanel":
        """收敛/总结提示用中文（Pango Text）。"""
        self._slots["result"] = self._make_text("result", text, color, font_size)
        return self

    def set_result_math(self, tex: str, color=WHITE, font_size: Optional[int] = None) -> "InfoPanel":
        self._slots["result"] = self._make_math("result", tex, color, font_size)
        return self

    # --------------------------------------------------------
    # 动画工厂
    # --------------------------------------------------------
    def write_anims_for(self, slot_names: List[str]) -> List[Animation]:
        """对指定槽位生成出场动画（Write）。槽位必须已 set_xxx。"""
        anims: List[Animation] = []
        for s in slot_names:
            mob = self._slots.get(s)
            if mob is None:
                continue
            anims.append(Write(mob))
        return anims

    def fadein_anims_for(self, slot_names: List[str]) -> List[Animation]:
        anims: List[Animation] = []
        for s in slot_names:
            mob = self._slots.get(s)
            if mob is None:
                continue
            anims.append(FadeIn(mob))
        return anims

    def update_value(
        self, tex: str, color=WHITE, font_size: Optional[int] = None
    ) -> List[Animation]:
        """把 value 槽位换成新内容，返回 [FadeOut(old), FadeIn(new)]。"""
        old = self._slots["value"]
        new = self._make_math("value", tex, color, font_size)
        self._slots["value"] = new
        anims: List[Animation] = []
        if old is not None:
            anims.append(FadeOut(old))
        anims.append(FadeIn(new))
        return anims

    def fadeout_anims(self) -> List[Animation]:
        return [FadeOut(m) for m in self._slots.values() if m is not None]

    # --------------------------------------------------------
    # 视图
    # --------------------------------------------------------
    @property
    def group(self) -> VGroup:
        return VGroup(*[m for m in self._slots.values() if m is not None])

    def get(self, slot: str):
        """读取某槽位 mobject（动画里要替换/隐藏时用）。"""
        return self._slots.get(slot)
