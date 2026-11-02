# CLAUDE.md

本仓库所有 AI 代理的统一规则写在 `AGENTS.md`，开工前先完整阅读。

@AGENTS.md

## Claude Code 额外说明

- 开工先跑 `scripts/ai-bootstrap.sh <TASK-ID>`，不要手工建分支。
- 不要使用 `--dangerously-skip-permissions` 之外的方式绕过路径限制；真正的边界由 `pr-guard` 在服务端校验。
- 长任务请在自己的任务分支上小步提交，不要攒一个大提交。
