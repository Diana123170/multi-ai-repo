#!/usr/bin/env bash
# 每个 AI 开工前运行：同步主干、建任务分支、设置提交模板。
#
#   scripts/ai-bootstrap.sh TASK-101
#
# 幂等：分支已存在时直接切过去，不会重建。
set -euo pipefail

task_id="${1:-}"
if [[ -z "$task_id" ]]; then
  echo "用法: scripts/ai-bootstrap.sh <TASK-ID>" >&2
  exit 2
fi

root="$(git rev-parse --show-toplevel)"
cd "$root"

meta="$(
  python3 - "$task_id" <<'PY'
import pathlib
import sys

import yaml

task_id = sys.argv[1]
path = pathlib.Path("ai/tasks") / f"{task_id}.yml"
if not path.exists():
    print(f"任务文件不存在: {path}", file=sys.stderr)
    raise SystemExit(1)

task = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
for key in ("base", "branch", "agent"):
    if not task.get(key):
        print(f"任务文件缺少字段: {key}", file=sys.stderr)
        raise SystemExit(1)

print(f'BASE="{task["base"]}"')
print(f'BRANCH="{task["branch"]}"')
print(f'AGENT="{task["agent"]}"')
print('ALLOWED="' + " | ".join(task.get("allowed_paths") or []) + '"')
PY
)" || { echo "读取任务失败，终止。" >&2; exit 1; }

eval "$meta"

git fetch origin "$BASE" --prune || true

if ! git show-ref --verify --quiet "refs/remotes/origin/$BASE"; then
  echo "❌ 目标分支 origin/$BASE 不存在。" >&2
  if [[ "$BASE" == proto/* ]]; then
    echo "   新原型需要先建集成分支：GitHub 仓库页 → 分支下拉 → 从 main 新建 $BASE。" >&2
  fi
  exit 1
fi

if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
  git switch "$BRANCH"
elif git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  git switch --track "origin/$BRANCH"
else
  git switch -c "$BRANCH" "origin/$BASE"
fi

git config commit.template .gitmessage
git config rerere.enabled true
git config merge.conflictStyle zdiff3
git config pull.rebase true

cat <<EOF
✅ 就绪

  Agent   : $AGENT
  Branch  : $BRANCH
  Base    : origin/$BASE
  Scope   : $ALLOWED

开工前请再读一遍 AGENTS.md，并在 PR 描述里填写 Task / Agent。
EOF
