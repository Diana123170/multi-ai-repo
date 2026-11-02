# 多 AI 协作模型

这份文档解释模板为什么这样设计，以及出问题时怎么处理。规则本身在
[`AGENTS.md`](../AGENTS.md)，机器可读的配置在 [`ai/policy.yml`](../ai/policy.yml)。

## 一句话概括

**控制面和数据面分离。**

- **控制面**：`ai/tasks/*.yml` —— 谁、在哪个分支、改哪些路径、验收标准是什么。
- **数据面**：代码分支和 PR —— 具体怎么改。
- **强制点**：`pr-guard` 在 PR 上逐条校验契约，`ci` 在合并前跑对应轨道的检查。

AI 只读控制面、只写自己契约授权的数据面。它没有权限扩大自己的授权。

## 为什么不是「大家一起往 main 推」

多个 AI 直接对 `main` 提交，会同时出现四个问题：

1. **没有所有权**：两个 AI 都觉得 `utils.ts` 该改，冲突在最后才爆发。
2. **边界模糊**：让它修一个按钮，它顺手重构了半个页面，review 无从下手。
3. **阶段混淆**：原型的临时代码和正式功能混在一个目录，没人说得清哪部分可以删。
4. **不可回滚**：出问题时无法按「任务」回退，只能按文件考古。

双轨 + 契约分别解决 3 和 1、2；squash 合并 + 一任务一 PR 解决 4。

## 双轨模型

| | 原型轨 | 正式轨 |
|---|---|---|
| 目录 | `prototypes/<slug>/` | `apps/` `packages/` `services/` |
| 集成分支 | `proto/<slug>` | `main` |
| 任务分支 | `proto/<slug>/<TASK-ID>` | `feat/<TASK-ID>` 等 |
| 默认 CI | `make proto-check` | `make check` |
| 合并方式 | squash，可自动 | squash + merge queue，必须人审 |
| 评审强度 | 异常时才看 | 每个 PR 都看 |
| 生命周期 | TTL，可整体归档 | 版本化，长期维护 |

### 为什么原型要单独一条主干

原型的价值在于**快速试错**。如果每个原型改动都直接 PR 到 `main`：

- 它会被迫接受正式轨的评审成本，试错速度降到和正式开发一样；
- 半成品会进入主干，正式代码可能不小心依赖它；
- 原型被推翻时，只能从 `main` 里一点点删，而不是丢掉一个分支。

所以原型有自己的集成分支 `proto/<slug>`：多个 AI 的改动先在这里合成一个可演示的整体，
评审通过后再一次性转正。

### 为什么转正必须是一次性搬移

`promote/<slug>` PR 做三件事：`git mv` 代码、把 manifest 标成 `promoted`、写 ADR。
不做「边搬边改」——转正 PR 只允许移动文件，改造留给正式轨任务。

这样出问题时，回滚一个 commit 就能回到转正前；也避免「转正」变成一次大规模重构。

## 契约模型

任务文件字段：

| 字段 | 必填 | 作用 |
|---|---|---|
| `id` | 是 | 任务 ID，PR 描述和提交 trailer 都用它 |
| `title` | 是 | 一句话交付物 |
| `track` | 是 | `formal` / `prototype` |
| `agent` | 是 | 执行者标识，和 PR 里的 `Agent:` 对齐 |
| `base` | 是 | 从哪个分支切 |
| `branch` | 是 | 任务分支名；正式轨 PR 的 head 必须完全一致 |
| `prototype` | prototype 必填 | 所属原型 slug |
| `allowed_paths` | 是 | glob 白名单，空 = 什么都不能改 |
| `forbidden_paths` | 否 | 黑名单，优先级高于白名单 |
| `allow_protected` | 否 | 只有 Planner 任务设为 true |
| `max_changed_lines` | 否 | 覆盖默认行数上限 |
| `acceptance` | 是 | 验收标准，人和 AI 都对照它 |
| `notes` | 否 | 背景与约束 |

校验发生在 PR 上，按模式分：

| 检查 | formal | prototype | promote | planning |
|---|---|---|---|---|
| 分支前缀 | ✅ | ✅ | ✅ | ⚠️ 建议 |
| 任务文件存在 | ✅ | 可选 | — | — |
| 分支名与契约一致 | ✅ | ✅ | ✅ | — |
| 路径白名单 | ✅ | ✅（= 原型目录） | ✅ | ✅ |
| 禁止触达 `prototypes/` | ✅ | — | — | — |
| 受保护路径 | ✅ | ✅ | ✅ | — |
| 行数 / 文件数上限 | ✅ | ✅ | 文件数 | 文件数 |
| manifest 状态 | — | ✅ | ✅ | ⚠️ 建议 |
| `approved_by` 留痕 | — | — | ✅ | — |

**关键约束：Worker 不能改自己的任务文件。** `ai/**` 是受保护路径，
只有 `allow_protected: true` 的 Planner 任务能改。想扩边界？让 Planner 开新任务。

## 并发模型：为什么不用锁

一个自然的想法是搞「文件锁」：谁要改哪个目录，先在某个文件里登记。
在这个场景里它弊大于利：

- Git 没有原子锁。两个 AI 同时改 `claims.yml` 本身就是冲突。
- AI 进程会崩、会超时、会被用户打断，锁不会自动释放。
- 引入了一个新的、需要维护的中心状态，比它解决的问题还多。

模板用的是**降低冲突概率 + 在合并点串行化**：

1. **路径所有权**：任务的 `allowed_paths` 尽量不重叠。重叠了就说明任务该拆。
2. **小 PR**：正式轨 ≤ 400 行、≤ 30 个文件；原型轨 ≤ 800 行。半小时能审完的 PR 才合得快。
3. **频繁 rebase**：开工时和 push 前各一次，冲突在小范围内解决。
4. **merge queue**：`main` 上的合并串行执行，冲突在队列里暴露一次，而不是在每个分支里各暴露一次。
5. **squash**：一个任务一个 commit，回滚粒度等于任务粒度。

结果不是「不会冲突」，而是冲突从「文件级、随机的」变成「任务级、可预期的」。
真撞上了，就按下面的手册处理。

## 冲突处理手册

### 标准动作

```bash
git fetch origin
git rebase origin/<base>

# 如果冲突
git status                    # 看哪些文件
# 在 allowed_paths 内：手工解决，保留双方意图
git add <file>
git rebase --continue

# 在 allowed_paths 外，或解不动
git rebase --abort
```

然后在该 PR 里写：

```markdown
## 待确认

与 `origin/main` 在 `apps/billing/...` 冲突，该文件不在本任务 allowed_paths 内。
请 owner 决定由谁处理。
```

### 决策树

1. **冲突文件在你的 `allowed_paths` 内** → 自己解。解完必须跑测试，不能只看「没冲突标记」。
2. **冲突文件不在你的范围内** → 不要解。中止 rebase，升级给人。
3. **冲突在 lockfile / 生成文件** → 不要手改，重新生成（见下一节）。
4. **同一处连续两次 rebase 都冲突** → 停下来。说明你和另一个 AI 在改同一个设计，
   先对齐方案，再决定谁继续。

### 禁止事项

- `git checkout --ours .` / `--theirs .` 整文件覆盖：会静默丢掉别人的改动。
- 为了让 rebase 过去而删除对方的代码。
- 在冲突提交里混入无关修改。

### 建议配置

```bash
git config rerere.enabled true          # 记住冲突解法，重复 rebase 自动复用
git config merge.conflictStyle zdiff3   # 冲突里显示共同祖先，更容易判断意图
git config pull.rebase true
```

## 共享文件与生成文件

这些文件天然会被多个任务同时改，是冲突的主要来源。对策不是「小心一点」，而是结构上避开：

| 文件 | 为什么会冲突 | 对策 |
|---|---|---|
| `package.json` / `pyproject.toml` | 多个任务同时加依赖 | 依赖变更单独开任务；规定只有 `chore/deps-*` 分支能改 |
| lockfile | 任何依赖变更都会整体重写 | 永不手改。冲突时保留一方，删掉 lockfile 重新安装生成 |
| 路由表 / barrel `index.ts` | 每加一个模块都要改一行 | 用脚本自动生成，CI 里校验 `git diff --exit-code` |
| 数据库 migration | 递增序号会撞号 | 用时间戳命名：`20261102_1430_add_coupon.sql` |
| i18n 文案 | 所有人往同一个 json 加 key | 按模块拆文件，构建时合并 |
| CI 配置 / `Makefile` | 每个 AI 都想加检查 | 受保护路径，只有 Planner 任务能改 |

判断标准：**如果一个文件每次加功能都要改，它就不该是手写的。**

## 一次任务的完整时序

```
Planner                Worker A              Worker B              GitHub
   │                      │                     │                    │
   ├─ 写 TASK-101.yml ────┼─────────────────────┼───────────────────►│ 规划 PR
   │                      │                     │                    ├─ pr-guard: planning
   │                      │                     │                    ├─ 人审 + 合并
   │                      │                     │                    │
   │                      ├─ bootstrap TASK-101 │                    │
   │                      ├─ 改 allowed_paths   │                    │
   │                      ├─ push ──────────────┼───────────────────►│ PR -> main
   │                      │                     │                    ├─ pr-guard: formal
   │                      │                     │                    ├─ ci: full
   │                      │                     │                    ├─ 人审 approve
   │                      │                     │                    ├─ merge queue
   │                      │                     │                    │
   │                      │                     ├─ 同一时刻做 TASK-102│
   │                      │                     ├─ 路径不重叠        │
   │                      │                     ├─ push ─────────────┼──► PR -> proto/x
   │                      │                     │                    ├─ pr-guard: prototype
   │                      │                     │                    ├─ ci: light
   │                      │                     │                    ├─ automerge 标签 → 自动合并
```

要点：两个 Worker 可以完全并行，因为它们的 `allowed_paths` 不重叠，
且合并到不同目标分支。真正的串行只发生在同一个目标分支的合并上。

## 接入一个新的 AI

每个 AI 都要满足：

1. **独立的工作副本**。不要多个 agent 共享一个 clone —— `.git/index.lock` 会让它们互相阻塞。
   同一台机器上用 `git worktree add ../work-agent-b <branch>`，或者干脆各自 clone。
2. **独立的身份**。每个 agent 一个 GitHub App / bot 账号 / fine-grained PAT。
   共享 token 会让审计、限流、权限回收全部混在一起。
3. **能读到规则**。Claude Code 用 `CLAUDE.md`；其他工具把 `AGENTS.md` 放进系统提示或首轮上下文。
4. **开工跑 bootstrap**：

   ```bash
   git clone git@github.com:YOUR_ORG/YOUR_REPO.git work-agent-b
   cd work-agent-b
   scripts/ai-bootstrap.sh TASK-102
   ```

5. **并发上限**。一个 agent 同时最多 1–2 个开放 PR。开太多，rebase 成本会指数上升。

## 人管什么

| 角色 | 做什么 | 不做什么 |
|---|---|---|
| Planner | 拆任务、写契约、排优先级、维护 `prototype.yaml` | 不写实现 |
| Reviewer | 正式轨 PR 的 approve；原型转正的批准 | 不手工 merge 绕过队列 |
| Owner | 决定原型的生死（续期 / 归档 / 转正） | 不让 AI 自己决定 |

三个「不要」：

- 不要因为 CI 红就关掉检查。
- 不要为了让某个 AI 通过而放宽它的 `allowed_paths`——应该拆任务。
- 不要手工 `git push --force` 到 `main` 或 `proto/*`。

## 失败模式

| 现象 | 大概率原因 | 处理 |
|---|---|---|
| PR 一直红，提示分支不一致 | PR head 与任务 `branch` 不符 | 切到正确分支，或让 Planner 改契约 |
| 两个 AI 反复冲突 | `allowed_paths` 重叠 | 拆任务，或在契约里明确各自的文件 |
| 自动合并不生效 | 没开 repo auto-merge / 没打 `automerge` 标签 | 检查 Settings 和标签 |
| 原型转正后还能改 | 有人改了 `prototype.yaml` 的 status | 恢复 `promoted`，改动走正式轨 |
| rebase 越来越痛苦 | 任务太大、活得太久 | 拆成半天粒度的任务，尽早合并 |
| CI 时快时慢 | 原型和正式用同一套检查 | 检查 `detect-scope.sh` 是否把所有改动都判成了 formal |

## 扩缩容

| 规模 | 建议 |
|---|---|
| 1–3 个 AI | 单仓库即可；重点是把 `AGENTS.md` 写清楚 |
| 4–8 个 AI | 路径所有权变关键；任务粒度减到半天；开始用 merge queue |
| 8 个以上 | 考虑按域拆仓（每个域一套 `policy.yml`），或引入中心调度器分配任务 |

拆仓的信号：`allowed_paths` 已经很难切成不重叠的块，或者一个 PR 的 CI 时间超过 30 分钟。
