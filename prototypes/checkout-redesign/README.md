# checkout-redesign

示例原型。验证结算页的两种布局：

- `?variant=one-page`：单页结算
- `?variant=stepper`：分步结算

## 要验证什么

两种布局在「填写 → 确认 → 支付」三步上的流失差异（用埋点模拟数据）。

## 现在到哪一步

`designing` —— 只有静态布局，没有接真实接口。

## 约束

- 不接真实支付
- 不改 `apps/checkout/`，所有代码留在本目录
- 定稿后走 `scripts/promote.py` 转正
