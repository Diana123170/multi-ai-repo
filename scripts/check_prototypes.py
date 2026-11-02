#!/usr/bin/env python3
"""检查 prototypes/ 下的单文件 HTML 原型。

只依赖 Python 标准库，CI 里直接跑，不需要 npm / pip install。

规则：
- 每个原型目录必须有 prototype.yaml，status 合法
- status = designing 时，可以还没有 index.html（只警告）
- status = validating / approved / delivered 时，必须有 index.html
- index.html 要有 doctype、html/head/body/title，且不能是空壳
- React / antd 引用只给警告，不阻断
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_STATUS = {"designing", "validating", "approved", "delivered", "archived"}
HTML_REQUIRED_STATUS = {"validating", "approved", "delivered"}


def read_status(manifest: Path) -> str | None:
    if not manifest.exists():
        return None
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*status:\s*(\S+)", line)
        if match:
            return match.group(1).strip("'\"")
    return None


def check_html(index: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    text = index.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()

    if "<!doctype html" not in lower:
        errors.append("缺少 <!DOCTYPE html>")
    for tag in ("<html", "<head", "<body", "<title"):
        if tag not in lower:
            errors.append(f"缺少 {tag}>")
    if len(text) < 500:
        errors.append(f"文件太小（{len(text)} 字符），可能不是完整原型")
    if "react" not in lower:
        warnings.append("没有发现 React 引用")
    if "antd" not in lower and "ant-design" not in lower:
        warnings.append("没有发现 antd 引用")
    return errors, warnings


def main() -> int:
    prototypes_dir = ROOT / "prototypes"
    if not prototypes_dir.exists():
        print("没有 prototypes/ 目录，跳过")
        return 0

    dirs = sorted(
        p for p in prototypes_dir.iterdir() if p.is_dir() and not p.name.startswith("_")
    )
    if not dirs:
        print("还没有原型目录，跳过")
        return 0

    failed = False
    for directory in dirs:
        status = read_status(directory / "prototype.yaml")
        index = directory / "index.html"
        errors: list[str] = []
        warnings: list[str] = []

        if status is None:
            errors.append("缺少 prototype.yaml，或其中没有 status")
        elif status not in ALLOWED_STATUS:
            errors.append(f"status 不合法：{status}")

        if not index.exists():
            if status == "designing":
                warnings.append("还没有 index.html（designing 阶段允许）")
            else:
                errors.append("缺少 index.html")
        else:
            html_errors, html_warnings = check_html(index)
            errors.extend(html_errors)
            warnings.extend(html_warnings)

        if errors:
            failed = True
            print(f"❌ {directory.name}")
            for item in errors:
                print(f"   - {item}")
        else:
            print(f"✅ {directory.name}（{status}）")
        for item in warnings:
            print(f"   ⚠️  {item}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
