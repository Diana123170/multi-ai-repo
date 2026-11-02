#!/usr/bin/env python3
"""原型转正：把 prototypes/<slug>/ 的实现搬到正式目录。

默认只打印计划（dry-run），加 --apply 才真正建分支、移动文件、提交。

    python3 scripts/promote.py checkout-redesign
    python3 scripts/promote.py checkout-redesign --apply

转正前必须满足：

1. `prototype.yaml` 的 status 是 `approved`（在 `proto/<slug>` 上）
2. 有 `approved_by`（人批准留痕）
3. `target` 指向 apps/ packages/ services/ 之下
4. 工作区干净，且 `proto/<slug>` 已推到远端

转正分支基于 `proto/<slug>` 而不是 main —— 原型代码只存在于集成分支上。
脚本只负责「搬」和「留痕」，不做代码改造；转正后的重构走正式轨任务。
"""
from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML：pip install pyyaml")

ROOT = Path(__file__).resolve().parents[1]
CODE_ROOTS = ("apps/", "packages/", "services/")


def git(*args: str, check: bool = True) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=check, capture_output=True, text=True
    ).stdout.strip()


def git_try(*args: str) -> str | None:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else None


def fail(message: str) -> int:
    print(f"❌ {message}", file=sys.stderr)
    return 1


def resolve_base(slug: str) -> str | None:
    """转正分支的基点：优先远端原型分支。"""
    for ref in (f"origin/proto/{slug}", f"proto/{slug}"):
        if git_try("rev-parse", "--verify", ref):
            return ref
    return None


def read_manifest(base_ref: str, slug: str) -> dict | None:
    raw = git_try("show", f"{base_ref}:prototypes/{slug}/prototype.yaml")
    if raw is None:
        return None
    return yaml.safe_load(raw) or {}


def list_entries(base_ref: str, slug: str) -> list[str]:
    """列出原型目录下要搬移的顶层条目（排除 manifest）。"""
    raw = git_try("ls-tree", "--name-only", base_ref, f"prototypes/{slug}/")
    if raw is None:
        return []
    return [
        line
        for line in raw.splitlines()
        if line and line != f"prototypes/{slug}/prototype.yaml"
    ]


def next_adr_number(adr_dir: Path) -> int:
    numbers = []
    for path in adr_dir.glob("*.md"):
        match = re.match(r"(\d{4})-", path.name)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def adr_body(number: int, slug: str, target: str, today: datetime.date) -> str:
    return f"""# ADR {number:04d}：{slug} 转正

- 状态：已接受
- 日期：{today.isoformat()}
- 原型：`prototypes/{slug}/`
- 转正位置：`{target}/`

## 背景

（由 scripts/promote.py 生成，请补充：为什么这个原型要转正、验证了什么。）

## 决策

将 `prototypes/{slug}/` 的实现迁入 `{target}/`，此后按正式轨维护：
全量 CI、代码评审、版本化发布。

## 后果

- 新增的正式代码纳入全量测试与安全扫描
- 原型目录保留 `prototype.yaml` 作为决策记录，不再包含实现
- 后续改动不再享受原型轨的自动合并
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug", help="原型 slug，例如 checkout-redesign")
    parser.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run）")
    parser.add_argument("--no-adr", action="store_true", help="不生成 ADR 文件")
    args = parser.parse_args()

    slug = args.slug.strip("/")

    # 尽量拿到最新的原型分支；没有远端时退回本地
    git_try("fetch", "origin", "--prune", "--quiet")

    base_ref = resolve_base(slug)
    if base_ref is None:
        return fail(
            f"找不到原型集成分支 `proto/{slug}`（本地或远端）。"
            "新原型请先在 GitHub 上从 main 创建该分支。"
        )

    manifest = read_manifest(base_ref, slug)
    if manifest is None:
        return fail(f"`{base_ref}` 上没有 `prototypes/{slug}/prototype.yaml`。")

    status = manifest.get("status")
    if status == "promoted":
        return fail(f"原型 `{slug}` 已经转正过了。")
    if status != "approved":
        return fail(
            f"原型状态是 `{status}`，只有 `approved` 才能转正。"
            "先在原型分支上写 approved_by / approved_at 并推送。"
        )
    if not manifest.get("approved_by"):
        return fail("manifest 缺少 `approved_by`，转正必须有人批准并留痕。")

    target = (manifest.get("target") or "").strip("/")
    if not target:
        return fail("manifest 缺少 `target`，不知道该搬到哪里。")
    if not target.startswith(CODE_ROOTS):
        return fail(f"`target` 必须落在 {', '.join(CODE_ROOTS)} 之下，当前是 `{target}`。")

    entries = list_entries(base_ref, slug)
    if not entries:
        return fail(f"`prototypes/{slug}/` 里没有可搬移的内容（只有 manifest）。")

    if git("status", "--porcelain"):
        return fail("工作区不干净，先提交或 stash 再转正。")

    today = datetime.date.today()
    adr_dir = ROOT / "docs" / "adr"
    adr_path = None
    if not args.no_adr:
        decision_adr = manifest.get("decision_adr")
        adr_path = (
            ROOT / decision_adr
            if decision_adr
            else adr_dir / f"{next_adr_number(adr_dir):04d}-{slug}.md"
        )

    print(f"原型    : {slug}")
    print(f"基点    : {base_ref}")
    print(f"状态    : {status}（approved_by: {manifest.get('approved_by')}）")
    print(f"目标    : {target}/")
    print("将移动：")
    for entry in entries:
        name = entry[len(f"prototypes/{slug}/"):]
        print(f"  {entry}  ->  {target}/{name}")
    if adr_path:
        print(f"将写入  : {adr_path.relative_to(ROOT)}")
    print(f"将更新  : prototypes/{slug}/prototype.yaml -> status: promoted")

    if not args.apply:
        print()
        print("这是 dry-run。确认无误后加 --apply 执行。")
        return 0

    branch = f"promote/{slug}"
    if git_try("rev-parse", "--verify", branch) is not None:
        return fail(f"分支 `{branch}` 已存在，先删掉或复用它。")

    git("switch", "-c", branch, base_ref)

    target_dir = ROOT / target
    if target_dir.exists() and any(target_dir.iterdir()):
        return fail(f"`{target}/` 已存在且非空，转正会覆盖。请人工确认后再处理。")
    target_dir.mkdir(parents=True, exist_ok=True)

    for entry in entries:
        name = entry[len(f"prototypes/{slug}/"):]
        git("mv", entry, f"{target}/{name}")

    manifest_path = ROOT / "prototypes" / slug / "prototype.yaml"
    manifest["status"] = "promoted"
    manifest["promoted_to"] = target
    manifest["promoted_at"] = today.isoformat()
    if adr_path:
        manifest["decision_adr"] = str(adr_path.relative_to(ROOT))
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    if adr_path and not adr_path.exists():
        adr_path.parent.mkdir(parents=True, exist_ok=True)
        match = re.match(r"(\d{4})-", adr_path.name)
        number = int(match.group(1)) if match else next_adr_number(adr_dir)
        adr_path.write_text(adr_body(number, slug, target, today), encoding="utf-8")

    git("add", "-A")
    git(
        "commit",
        "-m",
        f"chore(proto): 转正 {slug} -> {target}\n\nAgent: promote-script\nTask: {slug}",
    )

    print()
    print("✅ 已在本地完成转正提交。接下来：")
    print(f"  git push -u origin {branch}")
    print(
        f"  gh pr create --base main --title 'chore(proto): 转正 {slug}' "
        f"--body 'Prototype: {slug}'"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
