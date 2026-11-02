#!/usr/bin/env python3
"""检查 prototypes/ 下的 HTML 原型。

一个原型可以是一个 HTML，也可以是**一个目录里的多个 HTML + 资源文件**，
文件名可以是中文。只依赖 Python 标准库，CI 里直接跑。

规则：
- 每个原型目录必须有 prototype.yaml，status 合法
- status = designing 时，可以还没有 HTML（只警告）
- status = validating / approved / delivered 时，目录里至少要有一个 .html
- 如果 manifest 里写了 `entry: 首页.html`，这个文件必须存在
- 每个 HTML 都要有 doctype、html/head/body/title，且不能是空壳
- React / antd 引用只给警告，不阻断
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_STATUS = {"designing", "validating", "approved", "delivered", "archived"}
HTML_REQUIRED_STATUS = {"validating", "approved", "delivered"}


def read_field(manifest: Path, key: str) -> str | None:
    if not manifest.exists():
        return None
    pattern = re.compile(rf"\s*{re.escape(key)}:\s*(.+)")
    for line in manifest.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1).strip().strip("'\"")
    return None


def check_html(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
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
        manifest = directory / "prototype.yaml"
        status = read_field(manifest, "status")
        entry = read_field(manifest, "entry")
        html_files = sorted(p for p in directory.rglob("*.html") if p.is_file())
        errors: list[str] = []
        warnings: list[str] = []

        if status is None:
            errors.append("缺少 prototype.yaml，或其中没有 status")
        elif status not in ALLOWED_STATUS:
            errors.append(f"status 不合法：{status}")

        if not html_files:
            if status == "designing":
                warnings.append("还没有 HTML 文件（designing 阶段允许）")
            else:
                errors.append("目录里没有任何 .html 文件")

        if entry and not (directory / entry).exists():
            errors.append(f"entry 指向的文件不存在：{entry}")

        for html in html_files:
            html_errors, html_warnings = check_html(html)
            rel = html.relative_to(directory)
            errors.extend(f"{rel}: {item}" for item in html_errors)
            warnings.extend(f"{rel}: {item}" for item in html_warnings)

        if errors:
            failed = True
            print(f"❌ {directory.name}")
            for item in errors:
                print(f"   - {item}")
        else:
            count = f"{len(html_files)} 个 HTML" if html_files else "暂无 HTML"
            print(f"✅ {directory.name}（{status}，{count}）")
        for item in warnings:
            print(f"   ⚠️  {item}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
