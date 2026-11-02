# AGENTS.md — 本仓库的 AI 工作规则

> 你是这个仓库里的 AI 协作者。开工前完整读一遍，按这里的规则做。
>
> 这个仓库只放 **HTML 交互原型**（React + Ant Design）。正式开发由开发团队在别的仓库完成。
> 你的产出不是生产代码，是**可以被评审、被交付的交互原型**。

## 0. 30 秒了解

| 位置 | 是什么 | 你能动吗 |
|---|---|---|
| `prototypes/<slug>/` | 一个功能的原型，可以有多个 HTML + CSS/JS/图片 | ✅ 只能动你负责的 `<slug>` |
| `proto/<slug>` | 这个原型的集成分支，受保护 | ❌ 只能通过 PR 合入 |
| `ptask/<slug>/<TASK-ID>` | 你的工作分支 | ✅ 只在这里提交 |
| `handoff/<slug>/vN/` | 定稿后冻结给开发的快照 | ❌ 不要动 |
| `ai/tasks/` | 任务契约 | ❌ 只有 Planner 能写 |
| `scripts/check_pr_contract.py` | CI 用来检查 PR 边界的脚本 | ❌ 不要改 |

**你的工作 = 在一条 `ptask/<slug>/<TASK-ID>` 分支上，改 `prototypes/<slug>/` 里的文件，然后 PR 到 `proto/<slug>`。**

## 1. 开工前（一步都不能省）

1. 读 `prototypes/<slug>/prototype.yaml`：
   - `status` 必须是 `designing` 或 `validating`
   - `status` 已经是 `approved` / `delivered` / `archived` → **停下**，不要再改
   - `agents` 里应该有你的标识；没有就让 Planner 加
   - `entry` 是入口页，比如 `首页.html`
2. 看有没有人正在改同一个原型：

   ```bash
   gh pr list --state open --base proto/<slug>
   ```

   有开放 PR 时，先看它改了哪些页面，避免撞车。

3. 建分支（从集成分支切，不是从 main）：

   ```bash
   git fetch origin
   git switch -c ptask/<slug>/<TASK-ID> origin/proto/<slug>
   ```

4. 确认分支名格式：`ptask/<slug>/<TASK-ID>`

   - ❌ 不要用 `proto/<slug>/<TASK-ID>`：Git 不允许一个名字同时是分支和目录
   - ❌ 不要直接推 `proto/<slug>`
   - ❌ 不要从 `main` 切分支做原型

## 2. 你能改什么

只允许改：

```
prototypes/<slug>/**
```

不能改：

- `prototypes/<其他 slug>/**` —— 别人的原型
- `handoff/**` —— 交付快照，由人确认
- `ai/**`、`scripts/**`、`.github/**`、`Makefile` —— 基础设施
- `docs/**` —— 要改文档先问人
- `prototype.yaml` 的 `status` —— 只有人或 Planner 能标 `approved`

越界会被 `pr-guard` 直接拒绝。

## 3. 多 AI 同时改同一个原型

同一个原型可能有好几个 AI 同时在改。按这些规则做：

1. **一个 PR 只做一件事**，控制在半天工作量内。
2. **PR 描述写清范围**：只改了哪些页面、哪些区块。
3. **不要重排整个文件的格式**，不要全文件替换。
4. **只改你负责的页面**。需要动别人的页面，先在 PR 里问。
5. **频繁 rebase**，不要攒三天再合：

   ```bash
   git fetch origin
   git rebase origin/proto/<slug>
   ```

### 冲突处理

| 情况 | 怎么做 |
|---|---|
| 冲突在你负责的页面 | 自己解，保留双方意图，解完在浏览器里点一遍 |
| 冲突在别人负责的页面 | `git rebase --abort`，在 PR 里写「待确认」并 @ 人 |
| 同一段被两个 AI 改 | 串行：先合一个，另一个 rebase 后再提 |
| 冲突在锁文件/自动生成文件 | 不要手改，重新生成 |

禁止用 `git checkout --ours` / `--theirs` 整文件覆盖，那会静默丢掉别人的改动。

## 4. 原型文件规则

- **文件名可以用中文**：`首页.html`、`订单列表.html`、`详情页.html`
- 一个原型可以有多个 HTML；入口页写在 `prototype.yaml` 的 `entry`
- 页面之间用**相对路径**引用，保证整个目录拷走后还能打开
- React / antd 用 CDN 时**固定版本**，不要用 `@latest`
- 用假数据，不接真实接口，不写真实用户信息
- 不提交密钥、token、内网地址、个人绝对路径
- 图片放在 `assets/` 下，不要提交几 MB 的截图

## 5. 提交与 PR

提交信息：

```
feat(proto): 会员中心-首页布局

Agent: claude-code-01
Task: TASK-201
```

PR 规则：

- 目标分支必须是 `proto/<slug>`，**不是 `main`**
- 标题：`feat(proto): <slug>-<改了什么>`
- 描述必须包含：

  ```
  Task: TASK-201
  Agent: claude-code-01
  Prototype: member-center
  ```

  再加两段：
  - 改了哪些页面 / 区块
  - 怎么验证的（打开了哪个文件、点了哪些交互）

- 原型轨 PR 不合并到 `main`；`main` 只接收交付 PR

## 6. 完成定义

- 改动全部在 `prototypes/<slug>/` 内
- `make proto-check` 通过
- 页面能在浏览器里打开，主要交互能点
- PR 描述完整，没有「TODO 冒充实现」
- 没有调试代码和真实数据

## 7. 你不要做的事

- 不要改别人的原型目录
- 不要改 `prototype.yaml` 的 `status`（除非任务明确要求你改成 `validating`）
- 不要动 `handoff/`
- 不要改 CI、脚本、Makefile
- 不要为了让检查通过而删文件、改检查、跳过校验
- 不要提交 `node_modules`、构建产物、大图

## 8. 定稿之后

交付不需要你做。人或 Planner 会把整个 `prototypes/<slug>/` 冻结到 `handoff/<slug>/v1/`，
开发从那里拉走。你要做的只是把原型改到可交付、可评审。

如果人明确让你参与交付，再按 `handoff/README.md` 做。

## 9. 遇到不确定

- 需求不清 → PR 里列「待确认」，@ 人，不要猜
- 需要改原型目录以外的文件 → 停下来，问人
- 两个 AI 都在改同一页 → 停下来，先对齐
- 不确定分支/路径 → 先跑 `python3 scripts/check_pr_contract.py`，或看 CI 报错
