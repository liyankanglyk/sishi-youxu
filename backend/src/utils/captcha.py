"""图形验证码生成与校验（骨架阶段，纯 CPU 计算）。

为什么放在 utils 而不是 service：
- 不依赖 DB / Redis，仅生成 SVG 和比较答案
- 答案持久化由调用方决定（一般存 Redis，TTL 5 分钟）
"""
from __future__ import annotations

import base64
import random
import string
from typing import Tuple

# 字符集：去掉容易混淆的 0/O/1/l/I
_CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def generate_captcha(length: int = 4) -> Tuple[str, str]:
    """生成图形验证码。

    返回 `(answer, svg_base64)`：
    - `answer`：答案（不区分大小写比较时调用方做 `.upper()`）
    - `svg_base64`：SVG 图片的 base64 编码（不含 data: 前缀）
    """
    answer = "".join(random.choices(_CHARS, k=length))

    # 生成 SVG（120x40，加干扰线 / 干扰点）
    width, height = 120, 40
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#f8fafc"/>'
    ]

    # 干扰线
    for _ in range(3):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        color = random.choice(["#cbd5e1", "#94a3b8", "#fbbf24"])
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="1"/>'
        )

    # 干扰点
    for _ in range(20):
        cx = random.randint(0, width)
        cy = random.randint(0, height)
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="1" fill="#64748b"/>'
        )

    # 字符
    char_width = width // (length + 1)
    for i, ch in enumerate(answer):
        x = char_width * (i + 1) - 8
        y = random.randint(22, 30)
        font_size = random.randint(20, 24)
        rotate = random.randint(-15, 15)
        color = random.choice(["#1e293b", "#0f172a", "#1d4ed8", "#b91c1c"])
        parts.append(
            f'<text x="{x}" y="{y}" font-size="{font_size}" '
            f'font-family="monospace" font-weight="bold" '
            f'fill="{color}" transform="rotate({rotate} {x} {y})">{ch}</text>'
        )

    parts.append("</svg>")
    svg = "".join(parts)
    svg_b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return answer, svg_b64


def captcha_data_uri(svg_b64: str) -> str:
    """包装成 data URI，方便前端直接放到 `<img src>`。"""
    return f"data:image/svg+xml;base64,{svg_b64}"


__all__ = ["generate_captcha", "captcha_data_uri"]