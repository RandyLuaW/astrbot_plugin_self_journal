# 更新日志

所有重要变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [1.0.0] - 2026-10-20

### 新增

- 首个公开版本。
- `write_journal` / `read_journal` / `edit_journal` / `drop_journal` — 写、读、改、弃用
- `/journal` 指令，人工查看
- 注入块显式声明归属，避免被误读成用户自述
- 钩子用负 priority，追加在其他记忆注入之后，位置稳定
- 每小时 / 每天写入条数上限，防止刷屏式写日记

