#!/usr/bin/env python3
"""PR 契约校验器 —— 多 AI 双轨协作的守门人。

由 .github/workflows/pr-guard.yml 调用；也可以本地预演：

    BASE_REF=main \
    HEAD_REF=feat/TASK-101 \
    PR_BODY=$'Task: TASK-101\nAgent: claude-code-01' \
    CHANGED_FILES="apps/checkout/a.ts" \
    python3 scripts/check_pr_contract.py

需要 git 时从 origin/<base> 取 diff；测试时可用 CHANGED_FILES（每行一个路径）
和 CHANGED_STATS（每行 added<TAB>deleted<TAB>path）覆盖。

退出码：0 通过，1 违反契约。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("缺少 PyYAML：pip install pyyaml")


# --------------------------------------------------------------------------
# 基础工具
# --------------------------------------------------------------------------

def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def run_git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def resolve_base(root: Path, base: str) -> str | None:
    for ref in (f"origin/{base}", base):
        try:
            run_git(root, "rev-parse", "--verify", "--quiet", ref)
            return ref
        except subprocess.CalledProcessError:
            continue
    return None


def glob_regex(pattern: str) -> re.Pattern:
    """仓库路径 glob：** 跨目录，* 不跨目录。"""
    out = ["^"]
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def matches(path: str, patterns) -> bool:
    return any(glob_regex(p).match(path) for p in (patterns or []))


def format_files(paths: list[str], limit: int = 6) -> str:
    shown = "、".join(f"`{p}`" for p in paths[:limit])
    if len(paths) > limit:
        shown += f" 等共 {len(paths)} 个"
    return shown


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errors


# --------------------------------------------------------------------------
# 输入解析
# --------------------------------------------------------------------------

def changed_files(root: Path, base: str, head: str) -> list[str] | None:
    override = os.environ.get("CHANGED_FILES")
    if override is not None:
        return [line.strip() for line in override.splitlines() if line.strip()]
    ref = resolve_base(root, base)
    if ref is None:
        return None
    out = run_git(
        root,
        "diff",
        "--name-only",
        "--no-renames",
        "--diff-filter=ACMRD",
        # 用 HEAD 而不是分支名：Actions 的 checkout 是 detached HEAD，
        # 本地并不存在 PR 头分支的 ref，用分支名会直接 exit 128。
        f"{ref}...HEAD",
    )
    return [line for line in out.splitlines() if line]


def changed_line_count(root: Path, base: str, head: str) -> int | None:
    override = os.environ.get("CHANGED_STATS")
    if override is not None:
        total = 0
        for line in override.splitlines():
            parts = line.split("\t")
            if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
                total += int(parts[0]) + int(parts[1])
        return total
    ref = resolve_base(root, base)
    if ref is None:
        return None
    out = run_git(root, "diff", "--numstat", "--no-renames", f"{ref}...HEAD")
    total = 0
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            total += int(parts[0]) + int(parts[1])
    return total


TASK_ID_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def parse_task_id(branch: str, body: str) -> str | None:
    m = re.search(r"^\s*Task:\s*([A-Za-z][A-Za-z0-9]*-\d+)", body, re.MULTILINE)
    if m:
        return m.group(1).upper()
    m = TASK_ID_RE.search(branch)
    return m.group(1) if m else None


def parse_agent(body: str) -> str | None:
    m = re.search(r"^\s*Agent:\s*([A-Za-z0-9._-]+)", body, re.MULTILINE)
    return m.group(1) if m else None


def detect_mode(base: str, head: str, files: list[str], policy: dict) -> str:
    branches = policy["branches"]
    trunk = branches["trunk"]
    promote_prefix = branches["promote_prefix"]
    proto_prefix = branches["prototype_prefix"]

    if head.startswith(promote_prefix):
        return "promote"
    if base.startswith(proto_prefix):
        return "prototype"
    if base != trunk:
        return "unsupported"
    # 规划 PR 必须同时满足：用 chore/ 或 plan/ 分支，且只碰契约 / ADR / 原型骨架。
    # 只看文件不看分支的话，feat/* 就能靠「只改 prototypes/」绕过正式轨校验。
    if (
        head.startswith(("chore/", "plan/"))
        and files
        and all(f.startswith(("ai/tasks/", "docs/adr/", "prototypes/")) for f in files)
    ):
        return "planning"
    return "formal"


# --------------------------------------------------------------------------
# 各模式校验
# --------------------------------------------------------------------------

def check_formal(
    root: Path,
    policy: dict,
    report: Report,
    files: list[str],
    base: str,
    head: str,
    body: str,
    task_id: str | None,
) -> None:
    prefixes = policy["branches"]["formal_prefixes"]
    if not head.startswith(tuple(prefixes)):
        report.error(
            f"分支名 `{head}` 不符合正式轨前缀（{', '.join(prefixes)}）。"
            f"例如 `feat/TASK-101`。"
        )

    if not task_id:
        report.error(
            "找不到任务 ID。正式轨 PR 必须有任务契约："
            "先在 `ai/tasks/` 里建文件，并在 PR 描述写 `Task: TASK-xxx`。"
        )
        return

    task_path = root / "ai" / "tasks" / f"{task_id}.yml"
    if not task_path.exists():
        report.error(f"任务文件不存在：`ai/tasks/{task_id}.yml`。")
        return

    task = load_yaml(task_path)
    if task.get("track") != "formal":
        report.error(
            f"`{task_id}` 的 track 是 `{task.get('track')}`，不能走正式轨 PR。"
        )

    expected_branch = task.get("branch")
    if expected_branch and expected_branch != head:
        report.error(
            f"PR 分支 `{head}` 与任务声明 `{expected_branch}` 不一致。"
            "要么切到声明的分支，要么请 Planner 更新任务。"
        )

    agent = parse_agent(body)
    if not agent:
        report.warn("PR 描述里缺少 `Agent:` 行，无法追溯提交者。")
    elif task.get("agent") and agent != task["agent"]:
        report.warn(
            f"PR 的 Agent `{agent}` 与任务声明的 `{task['agent']}` 不一致。"
        )

    allowed = task.get("allowed_paths") or []
    if not allowed:
        report.error(f"`{task_id}` 没有声明 allowed_paths，等于不允许任何改动。")
        return

    outside = [f for f in files if not matches(f, allowed)]
    if outside:
        report.error(
            f"越界修改：{format_files(outside)} 不在 `{task_id}` 的 allowed_paths 内。"
            f"允许范围：{', '.join(f'`{p}`' for p in allowed)}。"
            "请把无关改动拆到另一个任务。"
        )

    forbidden = [f for f in files if matches(f, task.get("forbidden_paths"))]
    if forbidden:
        report.error(f"命中了 forbidden_paths：{format_files(forbidden)}。")

    proto_root = policy["workspace"]["prototype_root"]
    leaked = [f for f in files if f.startswith(proto_root)]
    if leaked:
        report.error(
            f"正式轨 PR 不能修改 `{proto_root}`：{format_files(leaked)}。"
            "原型代码请先在原型轨验证，再走 promote 转正。"
        )

    protected = [f for f in files if matches(f, policy["protected_paths"])]
    if protected and not task.get("allow_protected"):
        report.error(
            f"修改了受保护路径：{format_files(protected)}。"
            "只有声明 `allow_protected: true` 的 Planner 任务才能改这些文件。"
        )

    limits = policy["tracks"]["formal"]
    max_lines = task.get("max_changed_lines") or limits["max_changed_lines"]
    size = changed_line_count(root, base, head)
    if size is not None and size > max_lines:
        report.error(
            f"改动 {size} 行，超过上限 {max_lines} 行。请拆分任务后重新提交。"
        )
    if len(files) > limits["max_files"]:
        report.error(
            f"改动 {len(files)} 个文件，超过上限 {limits['max_files']} 个。请拆分任务。"
        )

    if size is not None:
        report.note(f"改动规模：{size} 行 / {len(files)} 个文件（上限 {max_lines} 行）。")


def check_prototype(
    root: Path,
    policy: dict,
    report: Report,
    files: list[str],
    base: str,
    head: str,
    body: str,
) -> None:
    proto_prefix = policy["branches"]["prototype_prefix"]
    slug = base[len(proto_prefix):].strip("/")
    if not slug or "/" in slug:
        report.error(f"无法从 base 分支 `{base}` 解析原型 slug。")
        return

    manifest_path = root / "prototypes" / slug / "prototype.yaml"
    if not manifest_path.exists():
        report.error(
            f"原型 `{slug}` 缺少身份证：`prototypes/{slug}/prototype.yaml`。"
        )
        return

    manifest = load_yaml(manifest_path)
    status = manifest.get("status")
    if status not in ("designing", "validating", "approved"):
        report.error(
            f"原型状态是 `{status}`，不能再在原型轨修改。"
            "已转正的原型请走正式轨任务；已归档的原型请先重新激活。"
        )

    expected_prefix = f"{proto_prefix}{slug}/"
    if not head.startswith(expected_prefix):
        report.error(
            f"原型轨分支必须是 `{expected_prefix}<TASK-ID>`，当前是 `{head}`。"
        )

    if not manifest.get("target"):
        report.warn(
            "prototype.yaml 没有填 `target`，转正时不知道该搬到哪个正式目录。"
        )

    agent = parse_agent(body)
    agents = manifest.get("agents") or []
    if agent and agents and agent not in agents:
        report.warn(
            f"Agent `{agent}` 不在原型的 agents 列表里，"
            "如果它是新加入的，请让 Planner 更新 manifest。"
        )

    allowed = [f"prototypes/{slug}/**"]
    outside = [f for f in files if not matches(f, allowed)]
    if outside:
        report.error(
            f"原型轨只能改 `prototypes/{slug}/`：{format_files(outside)} 越界。"
            "需要改正式代码请走 promote 或正式轨任务。"
        )

    limit = policy["tracks"]["prototype"]["max_changed_lines"]
    size = changed_line_count(root, base, head)
    if size is not None and size > limit:
        report.error(f"改动 {size} 行，超过原型轨上限 {limit} 行。")


def check_promote(
    root: Path,
    policy: dict,
    report: Report,
    files: list[str],
    head: str,
) -> None:
    prefix = policy["branches"]["promote_prefix"]
    slug = head[len(prefix):].strip("/")
    if not slug:
        report.error(f"无法从分支 `{head}` 解析原型 slug。")
        return

    manifest_path = root / "prototypes" / slug / "prototype.yaml"
    if not manifest_path.exists():
        report.error(f"找不到 `prototypes/{slug}/prototype.yaml`。")
        return

    manifest = load_yaml(manifest_path)
    status = manifest.get("status")
    min_status = policy["promote"]["min_status"]
    if status not in (min_status, "promoted"):
        report.error(
            f"原型状态是 `{status}`，只有 `{min_status}` 的原型才能转正。"
            "请先完成评审并在 manifest 里记录 approved_by。"
        )

    if not manifest.get("approved_by"):
        report.error(
            "prototype.yaml 缺少 `approved_by`。转正必须有人明确批准并留痕。"
        )

    target = (manifest.get("target") or "").strip("/")
    if not target:
        report.error("prototype.yaml 缺少 `target`，不知道该搬到哪。")
        return

    code_roots = tuple(policy["workspace"]["code_roots"])
    if not target.startswith(code_roots):
        report.error(
            f"`target`（{target}）必须落在正式代码目录之下：{', '.join(code_roots)}。"
        )

    allowed = [f"prototypes/{slug}/**", f"{target}/**", "docs/adr/**"]
    outside = [f for f in files if not matches(f, allowed)]
    if outside:
        report.error(
            f"转正 PR 只能动原型目录、目标目录和 ADR：{format_files(outside)} 越界。"
        )

    if not any(f.startswith(f"{target}/") for f in files):
        report.error(f"没有向 `{target}/` 搬移任何文件，这不像一次转正。")

    limit = policy["promote"]["max_files"]
    if len(files) > limit:
        report.error(f"转正涉及 {len(files)} 个文件，超过上限 {limit}。")


def check_planning(
    root: Path,
    policy: dict,
    report: Report,
    files: list[str],
    head: str,
    body: str,
) -> None:
    """规划 PR：只加任务契约、ADR，或初始化一个新原型。"""
    if not head.startswith(("chore/", "plan/")):
        report.warn(
            f"规划 PR 建议使用 `chore/` 或 `plan/` 前缀，当前是 `{head}`。"
        )

    if not parse_agent(body):
        report.warn("规划 PR 建议在描述里写 `Planner:` 或 `Agent:`。")

    for path in files:
        if path.endswith("/prototype.yaml") and path.startswith("prototypes/"):
            manifest = load_yaml(root / path)
            if manifest.get("status") != "designing":
                report.warn(
                    f"新原型 `{path}` 的初始状态是 `{manifest.get('status')}`，"
                    "建议从 `designing` 开始。"
                )

    limit = policy["tracks"]["formal"]["max_files"]
    if len(files) > limit:
        report.error(f"规划 PR 涉及 {len(files)} 个文件，超过上限 {limit}。")


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------

def emit(report: Report, mode: str, files: list[str]) -> int:
    icon = "✅ 通过" if report.ok else "❌ 未通过"
    print(f"PR 契约检查：{icon}（模式：{mode}，改动 {len(files)} 个文件）")

    for note in report.notes:
        print(f"  · {note}")
    for warning in report.warnings:
        print(f"::warning::{warning}")
    for error in report.errors:
        print(f"::error::{error}")

    summary = [f"## PR 契约检查：{icon}", ""]
    summary.append(f"- 模式：`{mode}`")
    summary.append(f"- 改动文件：{len(files)} 个")
    summary.append("")

    if report.errors:
        summary.append("### 必须修复")
        summary.extend(f"- {e}" for e in report.errors)
        summary.append("")
    if report.warnings:
        summary.append("### 提醒")
        summary.extend(f"- {w}" for w in report.warnings)
        summary.append("")
    if report.ok:
        summary.append("边界校验通过，可以进入 review。")
        summary.append("")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        Path(summary_path).write_text("\n".join(summary), encoding="utf-8")

    return 0 if report.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", default=str(Path(__file__).resolve().parents[1]), help="仓库根目录"
    )
    args = parser.parse_args()
    root = Path(args.root).resolve()

    base = os.environ.get("BASE_REF", "").strip()
    head = os.environ.get("HEAD_REF", "").strip()
    body = os.environ.get("PR_BODY", "") or ""

    report = Report()
    if not base or not head:
        report.error("环境变量 BASE_REF / HEAD_REF 未设置。")
        return emit(report, "unknown", [])

    policy_path = root / "ai" / "policy.yml"
    if not policy_path.exists():
        report.error("缺少 `ai/policy.yml`。")
        return emit(report, "unknown", [])

    policy = load_yaml(policy_path)
    files = changed_files(root, base, head)
    if files is None:
        report.error(
            f"无法计算改动文件：`origin/{base}` 不存在，或当前目录不是完整 git 仓库。"
        )
        return emit(report, "unknown", [])

    if not files:
        report.error("PR 没有改动任何文件（diff 为空），请确认分支和目标分支是否正确。")
        return emit(report, "empty", [])

    mode = detect_mode(base, head, files, policy)
    task_id = parse_task_id(head, body)

    if mode == "formal":
        check_formal(root, policy, report, files, base, head, body, task_id)
    elif mode == "prototype":
        check_prototype(root, policy, report, files, base, head, body)
    elif mode == "promote":
        check_promote(root, policy, report, files, head)
    elif mode == "planning":
        check_planning(root, policy, report, files, head, body)
    else:
        report.error(
            f"不支持的目标分支 `{base}`。合法目标是 `main` 或 `proto/<slug>`。"
        )

    return emit(report, mode, files)


if __name__ == "__main__":
    sys.exit(main())
