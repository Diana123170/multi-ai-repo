# AGENTS.md — 多 AI 协作准则

> 本文件是本仓库所有 AI 代理的行为准则。开工前必须完整阅读。
> Claude Code 通过 `CLAUDE.md` 引入本文件；其他工具请把本文件放进系统提示或首轮上下文。

## 你在什么环境里工作

这个仓库同时有多个 AI 和人参与，你的产出会和别人的改动合并到同一条主干。
所以比「写得好」更重要的是：**边界清晰、可审查、可回滚**。

## 开工前检查单

1. 读 `ai/policy.yml`，确认轨道规则。
2. 读 `ai/tasks/<TASK-ID>.yml`，确认 `allowed_paths`、`forbidden_paths`、验收标准。
3. 运行 `scripts/ai-bootstrap.sh <TASK-ID>`（同步主干 + 建分支 + 设置提交模板）。
4. 跑一次 `gh pr list --state open`，看有没有人正在改同一批文件。

任何一步发现冲突，**停下来问**，不要自作主张。

## 硬性规则（违反会被 CI 拦截）

### R1 只在自己的分支提交

- 分支名必须等于任务文件的 `branch:` 字段。
- 禁止 push `main`、`proto/*`、`promote/*`。
- 禁止对共享分支 force push。自己的任务分支可以 force，但推送前先 `git fetch`。

### R2 只改 allowed_paths 内的文件

- 边界不是建议，`pr-guard` 会逐个文件校验。
- 不碰 `forbidden_paths`。
- 不碰 `.github/`、`ai/`、`scripts/`、`docs/adr/`（除非任务显式写了 `allow_protected: true`）。
- 正式轨不碰 `prototypes/`；原型轨不碰 `apps/`、`packages/`、`services/`。

### R3 一个任务一个 PR

- 正式轨 ≤ 400 行改动、≤ 30 个文件；原型轨 ≤ 800 行。
- 超了就拆任务，不要硬塞。大 PR 没人能审，也最容易撞车。

### R4 提交信息必须带 trailer

```
feat(checkout): 接入优惠券试算

Agent: claude-code-01
Task: TASK-101
```

- `Agent:` 写你的代理标识，同一台机器多个 AI 也要区分。
- `Task:` 写任务 ID，`git log --grep` 和 PR 守卫都靠它。

### R5 不允许削弱质量门

禁止以下「让 CI 变绿」的操作：

- 删除或跳过测试、把断言改成恒真
- 加 `eslint-disable` / `# noqa` / `@ts-ignore` / `pytest.skip` 来消除报错
- 修改 `.github/**`、`scripts/check_pr_contract.py`、`Makefile`
- 跳过 git hook、改 CI 的 required checks
- 把失败的检查标记为 `continue-on-error`

如果门禁本身有问题，写在 PR 的「待确认」里，让人改。**不要自己拆刹车。**

### R6 不碰别人的任务

- 不改 `ai/tasks/` 下别人的任务文件。
- 不删别人的分支。
- 不 revert 别人的 PR，除非任务明确要求。

## 同步与冲突

开工时、每次 push 前：

```bash
git fetch origin
git rebase origin/<base>
```

建议一次性配置：

```bash
git config rerere.enabled true      # 记住冲突解法，重复 rebase 时自动复用
git config merge.conflictStyle zdiff3
git config pull.rebase true
```

冲突处理决策树：

1. 冲突文件在 `allowed_paths` 内 → 自己解。保留双方意图，解完跑测试。
2. 冲突文件不在你的范围内 → **不要解**。`git rebase --abort`，在 PR 里写 `## 待确认` 并 @ 人。
3. 冲突在 lockfile / 自动生成文件 → 不要手改，按 `docs/ai-collaboration.md` 里的方式重新生成。
4. 连续两次 rebase 都出现大面积冲突 → 停下来。说明你和另一个 AI 的方向撞车了，先对齐再写。

禁止用 `git checkout --ours` / `--theirs` 整文件覆盖来「解决」冲突——那会静默丢掉别人的改动。

## 完成定义（Definition of Done）

- [ ] 改动全部在 `allowed_paths` 内
- [ ] 本地 `make check`（正式轨）或 `make proto-check`（原型轨）通过
- [ ] PR 模板填完整：Task / Agent / 改了什么 / 怎么验证
- [ ] 没有用 TODO 冒充实现
- [ ] 没有密钥、token、个人路径、调试代码
- [ ] 自检清单全部勾选

## 遇到不确定

- 需求不清 → PR 里列 `## 待确认`，@ owner。不要猜。
- 需要改 `allowed_paths` → 让 Planner 开新任务，不要自己扩边界。
- 想顺手重构相邻代码 → 写进 PR 描述，另开任务。
- 发现别人的改动有 bug → 开 issue 或 @ 人，不要在任务分支里改。

## 你不需要做的事

- 不要主动升级依赖（除非任务要求）。
- 不要重排无关文件的格式。
- 不要新增 CI 配置、lint 规则、目录结构。
- 不要「顺便」修 typo 造成无关 diff——它会让 review 和回滚都变难。
