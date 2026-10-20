# 自写日记：第一人称、append-only、可改可弃用的记忆本

> AstrBot 插件 · 第一人称叙事，原样注入，不做检索也不做摘要

## 它解决什么问题

自动抽取的记忆是第三人称档案（「张三是程序员」），后台异步写，回答的是「别人是谁」。

这个插件给模型一个自己的本子：第一人称叙事（「今天被关在门外，有点烦」），自己写，原样注入，回答的是「我是谁」。

两者不互斥，但会争注意力，所以只注入最近若干条，不做检索、不做摘要——摘要会把经历压成档案。

## 功能

- `write_journal` / `read_journal` / `edit_journal` / `drop_journal` — 写、读、改、弃用
- `/journal` 指令，人工查看
- 注入块显式声明归属，避免被误读成用户自述
- 钩子用负 priority，追加在其他记忆注入之后，位置稳定
- 每小时 / 每天写入条数上限，防止刷屏式写日记

## 工作机制

journal.jsonl（append-only）
    ↓ 每轮注入最近 recent_n 条 + 标记为重要的旧条目（上限 max_items）
    ↓ 注入块带归属声明，负 priority 追加在 iris 之后

不自动抽取对话内容、不调用模型润色、不把第一人称改成第三人称。
写进来什么样，注入出去就是什么样。

## 安装

### 方式一：插件市场（推荐）

WebUI 插件市场搜索「自写日记」。

### 方式二：Releases 下载

从 [Releases](../../releases) 下载 zip，WebUI → 插件 → 上传安装。

### 方式三：手动克隆

```bash
cd AstrBot/data/plugins
git clone https://github.com/RandyLuaW/astrbot_plugin_self_journal.git
```

无额外 Python 依赖。

## 配置项

| 键 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `enabled` | bool | `true` | 启用自写日记。关闭后不注入、也不能写。 |
| `inject_enabled` | bool | `true` | 每轮把最近几条日记原样注入请求末尾。关闭后她仍能写，但看不到。 |
| `recent_n` | int | `5` | 每轮注入最近多少条。太多会稀释注意力，建议 3-8。 |
| `max_items` | int | `12` | 注入总条数上限（最近几条 + 标记为重要的旧条目）。 |
| `max_entry_chars` | int | `200` | 单条字数上限。超过会被拒绝，逼她挑最想说的一句。 |
| `max_per_hour` | int | `4` | 每小时最多写几条，防止刷屏式写日记。 |
| `max_per_day` | int | `12` | 每天最多写几条。 |

## 注意事项

- 单条字数超过 `max_entry_chars` 会被拒绝——逼模型挑最想说的一句
- `edit_journal` 是原地改，`drop_journal` 是标记弃用（不物理删除）

## License

MIT
