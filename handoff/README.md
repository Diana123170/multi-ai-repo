# handoff/ —— 已交付开发的原型

每个评审通过的原型，在这里留一份**冻结快照**和交接信息。
开发从这里拉走，不再回看 `prototypes/`（那边会继续改，容易看错版本）。

## 目录结构

```
handoff/<slug>/
├── v1/                 # 冻结的整个原型目录（所有 HTML + 资源）
│   ├── 首页.html
│   ├── 订单列表.html
│   └── assets/...
├── handoff.yaml        # 交接元数据
└── README.md           # 给开发看的说明
```

> 一个原型可能是多个 HTML + JS/CSS/图片。**复制整个 `prototypes/<slug>/` 目录**，
> 不要只复制 `index.html`，否则页面之间的相对链接会断。

## 交付流程

1. 在 `proto/<slug>` 分支上把 `prototype.yaml` 改成 `approved`，填写 `approved_by` / `approved_at`
2. 新建分支 `handoff/<slug>`
3. 把整个 `prototypes/<slug>/` 复制到 `handoff/<slug>/v1/`（保留目录结构）
4. 复制 `handoff/_template/` 里的两个文件，填好
5. 提 PR 到 `main`
6. 合并后，开发从 `handoff/<slug>/v1/index.html` 取

## 原型继续改怎么办

- 小改动：在 `proto/<slug>` 上改，改完重新走一次交付，生成 `v2/`
- 大改方向：当成新原型，换一个 slug

**不要在 `handoff/` 里直接改 HTML。** 它是冻结的快照，改了就和原型对不上了。

## 开发进度怎么跟

改 `handoff/<slug>/handoff.yaml` 的 `status`：

| 状态 | 含义 |
|---|---|
| `in-development` | 开发已接手 |
| `ready-for-qa` | 开发完成，待验收 |
| `released` | 已上线 |
| `on-hold` | 暂停 |

每次状态变更走一个小 PR，这样仓库里能看到「哪些原型在开发中、哪些已上线」。
