# 三个占位 target 是模板里最需要你先改的地方。
# CI 的 light / full 两个 job 分别调用 proto-check 和 check。

.PHONY: check proto-check lint test contract

## 正式轨：CI 的 full job 会跑这个
check: lint test

## 原型轨：CI 的 light job 会跑这个，保持轻量
proto-check: lint
	@echo "[proto] TODO: 换成原型的最小校验（构建 / 冒烟），不要跑全量测试"

## TODO: 换成真实命令，例如 `npx eslint .` / `ruff check .`
lint:
	@echo "[lint] TODO: 尚未配置 lint 命令"

## TODO: 换成真实命令，例如 `npm test` / `pytest -q`
test:
	@echo "[test] TODO: 尚未配置测试命令"

## 本地预演 PR 守卫
contract:
	python3 scripts/check_pr_contract.py
