#!/usr/bin/env python3
"""盘点过期原型，写进一个长期 issue。

由 .github/workflows/housekeeping.yml 每周触发，也可以本地手动跑
（需要 gh 已登录，或设置 GH_TOKEN）：

    python3 scripts/report_expired.py --dry-run   # 只打印，不调 gh
    python3 scripts/report_expired.py
"""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML：pip install pyyaml")

ROOT = Path(__file__).resolve().parents[1]
TITLE = "[housekeeping] 过期原型盘点"


def gh(*args: str) -> str:
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise SystemExit("找不到 gh CLI，请安装或改用 --dry-run。")
    if result.returncode != 0:
        raise SystemExit(f"gh 调用失败：{result.stderr.strip()}")
    return result.stdout


def collect_expired(today: datetime.date) -> list[tuple[str, str, str, str]]:
    expired: list[tuple[str, str, str, str]] = []
    for manifest_path in sorted((ROOT / "prototypes").glob("*/prototype.yaml")):
        if manifest_path.parent.name.startswith("_"):
            continue  # 跳过 _template
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        if data.get("status") in ("promoted", "archived"):
            continue
        expires = data.get("expires")
        if not expires:
            continue
        if isinstance(expires, str):
            try:
                expires = datetime.date.fromisoformat(expires)
            except ValueError:
                continue
        if expires < today:
            expired.append(
                (
                    manifest_path.parent.name,
                    str(data.get("status", "?")),
                    expires.isoformat(),
                    str(data.get("owner", "?")),
                )
            )
    return expired


def build_body(expired: list[tuple[str, str, str, str]]) -> str:
    if not expired:
        return "本周没有过期原型 🎉"
    rows = "\n".join(
        f"| `{slug}` | {status} | {when} | {owner} |"
        for slug, status, when, owner in expired
    )
    return (
        "每周自动盘点。以下原型已过 `expires`，但仍处于设计状态。\n\n"
        "请 owner 决定：继续（更新 `expires`）或归档（`status: archived`）。\n\n"
        "| 原型 | 状态 | 过期日 | Owner |\n"
        "|---|---|---|---|\n"
        f"{rows}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印报告，不调用 gh")
    args = parser.parse_args()

    today = datetime.date.today()
    expired = collect_expired(today)
    body = build_body(expired)
    print(f"发现 {len(expired)} 个过期原型")

    if args.dry_run:
        print()
        print(body)
        return 0

    issues = json.loads(
        gh("issue", "list", "--state", "open", "--limit", "100", "--json", "number,title")
    )
    existing = next((item for item in issues if item["title"] == TITLE), None)

    if existing:
        gh("issue", "comment", str(existing["number"]), "--body", body)
        print(f"已追加到 issue #{existing['number']}")
    else:
        gh("issue", "create", "--title", TITLE, "--body", body)
        print("已创建盘点 issue")

    return 0


if __name__ == "__main__":
    sys.exit(main())
