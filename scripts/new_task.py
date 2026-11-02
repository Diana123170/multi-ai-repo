#!/usr/bin/env python3
"""生成任务契约文件。

正式轨：
    python3 scripts/new_task.py --id TASK-103 --track formal \\
      --agent claude-code-01 --title "优惠券接口" \\
      --path 'apps/checkout/**' --path 'packages/payments/**'

原型轨：
    python3 scripts/new_task.py --id TASK-104 --track prototype \\
      --prototype checkout-redesign --agent codex-02 \\
      --title "新版布局" --path 'prototypes/checkout-redesign/**'

生成的只是本地文件，记得开一个规划 PR 合并到 main 之后，Worker 才能开工。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML：pip install pyyaml")

ROOT = Path(__file__).resolve().parents[1]
TASK_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*-\d+$")

HEADER = """\
# 任务契约：由 scripts/new_task.py 生成。
# 修改 allowed_paths 等于扩大授权范围，需要评审。
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, help="任务 ID，例如 TASK-103")
    parser.add_argument("--title", required=True)
    parser.add_argument("--track", choices=["formal", "prototype"], required=True)
    parser.add_argument("--agent", required=True, help="执行任务的 AI 标识")
    parser.add_argument(
        "--path",
        action="append",
        dest="paths",
        default=[],
        help="allowed_paths，可重复；glob 写法，** 跨目录",
    )
    parser.add_argument("--prototype", help="原型 slug（prototype 轨必填）")
    parser.add_argument("--base", help="默认 main 或 proto/<slug>")
    parser.add_argument("--branch", help="默认 feat/<ID> 或 proto/<slug>/<ID>")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的任务文件")
    args = parser.parse_args()

    task_id = args.id.upper()
    if not TASK_ID_RE.match(task_id):
        return fail(f"任务 ID 格式不对：{task_id}，应形如 TASK-103")

    if args.track == "prototype":
        if not args.prototype:
            return fail("prototype 轨必须用 --prototype 指定原型 slug")
        default_base = f"proto/{args.prototype}"
        default_branch = f"proto/{args.prototype}/{task_id}"
        if not args.paths:
            args.paths = [f"prototypes/{args.prototype}/**"]
    else:
        default_base = "main"
        default_branch = f"feat/{task_id}"
        if not args.paths:
            return fail("formal 轨必须用 --path 声明至少一个 allowed_paths")

    task = {
        "id": task_id,
        "title": args.title,
        "track": args.track,
        "agent": args.agent,
        "base": args.base or default_base,
        "branch": args.branch or default_branch,
    }
    if args.track == "prototype":
        task["prototype"] = args.prototype
    task.update(
        {
            "allowed_paths": args.paths,
            "forbidden_paths": [],
            "allow_protected": False,
            "acceptance": ["make check 通过"],
            "notes": "",
        }
    )

    out = ROOT / "ai" / "tasks" / f"{task_id}.yml"
    if out.exists() and not args.force:
        return fail(f"{out.relative_to(ROOT)} 已存在。确认要覆盖请加 --force")

    body = yaml.safe_dump(task, allow_unicode=True, sort_keys=False)
    out.write_text(HEADER + body, encoding="utf-8")

    print(f"已生成 {out.relative_to(ROOT)}")
    print()
    print("接下来：")
    print(f"  1. 编辑验收标准和 notes")
    print(f"  2. git switch -c chore/{task_id}-plan")
    print(f"  3. git add {out.relative_to(ROOT)} && git commit -m 'chore(task): {task_id}'")
    print(f"  4. git push -u origin chore/{task_id}-plan")
    print(f"  5. gh pr create --base main --title 'chore(task): {task_id}' --body 'Planner: <你>'")
    print()
    print(f"合并后 Worker 执行：scripts/ai-bootstrap.sh {task_id}")
    return 0


def fail(message: str) -> int:
    print(f"错误：{message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
