# apps/ —— 正式开发的应用

这里放**已经转正、要对用户负责**的代码。

- 只能通过正式轨任务修改：分支 `feat/<TASK-ID>`，PR 到 `main`，必须人审。
- 不能引用 `prototypes/` 里的任何代码。
- 每次改动都要有测试；CI 跑全量。

一个原型转正后会落到 `apps/<target>/`，通过 `scripts/promote.py` 完成，不要手工搬。
