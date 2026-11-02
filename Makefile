# 本仓库只放单文件 HTML 原型；正式开发在开发团队那边进行。
# 原型检查不依赖 npm，CI 直接用 Python 标准库跑。
#
# 以后如果正式代码也放进本仓库，在 check 里接上 lint / test / build。

.PHONY: check proto-check

## 正式轨：交付 PR 也跑同一套基础检查
check: proto-check

## 原型轨：检查所有 prototypes/*/index.html
proto-check:
	python3 scripts/check_prototypes.py
