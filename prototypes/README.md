# prototypes/ —— 设计中的原型

这里放**还在被推翻的东西**：视觉稿、交互验证、假数据 demo、技术选型试验。
判断标准只有一条：**它现在是否需要对用户负责？** 不需要，就放这里。

## 什么可以放进来

- 还没定稿的页面布局、交互流程
- 用假数据跑通的概念验证
- 两三个方案并行对比
- 一次性的脚本、脚手架

## 什么不能放进来

- 已经被正式功能引用的代码
- 需要长期维护的公共库
- 线上配置、密钥、真实用户数据
- 数据库 migration（原型的库可以随时重建）

## 新建一个原型

1. 复制模板并填写 manifest：

   ```bash
   git switch main && git pull
   git switch -c chore/bootstrap-<slug>
   mkdir -p prototypes/<slug>
   cp prototypes/_template/prototype.yaml prototypes/<slug>/
   cp prototypes/_template/README.md prototypes/<slug>/
   # 编辑 prototype.yaml：status: designing，写清 target 和 expires
   git add prototypes/<slug>
   git commit -m "chore(proto): 初始化 <slug>"
   git push -u origin chore/bootstrap-<slug>
   gh pr create --base main --title "chore(proto): 初始化 <slug>" --body "Planner: <你>"
   ```

2. PR 合并后，在 GitHub 上从 `main` 新建集成分支 `proto/<slug>`
   （Branches 下拉框 → New branch）。

3. 给每个执行任务建一份契约，指定 `base: proto/<slug>`：

   ```bash
   python3 scripts/new_task.py --id TASK-201 --track prototype \
     --prototype <slug> --agent claude-code-01 \
     --title "第一版布局" --path 'prototypes/<slug>/**'
   ```

4. AI 开工：

   ```bash
   scripts/ai-bootstrap.sh TASK-201
   ```

## 生命周期

| 状态 | 含义 | 谁能改 |
|---|---|---|
| `designing` | 还在做，方向随时可能推翻 | 原型轨任务 |
| `validating` | 方案基本定了，在验证边界情况 | 原型轨任务 |
| `approved` | 评审通过，可以转正 | 只能改 manifest 记录批准 |
| `promoted` | 已搬进正式目录 | 不能改，去正式轨 |
| `archived` | 放弃或长期搁置 | 不能改 |

状态只前进不后退。要重新激活一个 archived 原型，请新建一个 slug 并说明关系。

## 转正

评审通过后：

```bash
# 1. 在原型分支上记录批准，并推送到远端
git switch proto/<slug>
# 编辑 prototype.yaml：status: approved、approved_by、approved_at
git add prototypes/<slug>/prototype.yaml
git commit -m "chore(proto): 批准 <slug> 转正"
git push

# 2. 本地 dry-run，看看会搬哪些东西
#    转正分支基于 proto/<slug>，不是 main
python3 scripts/promote.py <slug>

# 3. 执行：建 promote/<slug> 分支、git mv、更新 manifest、写 ADR、提交
python3 scripts/promote.py <slug> --apply

# 4. 推上去开 PR，走正式轨评审
git push -u origin promote/<slug>
gh pr create --base main --title "chore(proto): 转正 <slug>" --body "Prototype: <slug>"
```

转正 PR 合并后，`prototypes/<slug>/` 只留 `prototype.yaml` 作为决策记录。

## 过期清理

`expires` 到期且仍在设计中的原型，每周会被 `housekeeping` workflow 汇总到一个 issue 里。
owner 需要二选一：更新 `expires` 继续，或改成 `archived` 收摊。

原型不是仓库的资产，**是成本**。该删就删。
