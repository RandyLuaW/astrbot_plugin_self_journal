# Self Journal: a first-person, append-only notebook

> AstrBot plugin · The model writes its own entries; injected as-is

## The problem

Auto-extracted memory is a third-person archive ("Alex is a programmer"), written asynchronously by another model — it answers "who are the others".

This plugin gives the model its own notebook: first-person narrative, written by itself, injected verbatim — it answers "who am I".

## Features

- `write_journal` / `read_journal` / `edit_journal` / `drop_journal`
- `/journal` command for manual inspection
- Injection block explicitly declares ownership
- Negative hook priority keeps it after other memory blocks
- Hourly and daily write limits

## Install

### Option 1: Plugin marketplace (recommended)

Search "自写日记" in the AstrBot WebUI plugin marketplace.

### Option 2: Download from Releases

Grab the zip from [Releases](../../releases), then WebUI → Plugins → Upload.

### Option 3: Clone manually

```bash
cd AstrBot/data/plugins
git clone https://github.com/RandyLuaW/astrbot_plugin_self_journal.git
```

No extra Python dependencies.

## Configuration

| Key | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `true` | See Chinese README |
| `inject_enabled` | bool | `true` | See Chinese README |
| `recent_n` | int | `5` | See Chinese README |
| `max_items` | int | `12` | See Chinese README |
| `max_entry_chars` | int | `200` | See Chinese README |
| `max_per_hour` | int | `4` | See Chinese README |
| `max_per_day` | int | `12` | See Chinese README |

## Notes

- Entries longer than `max_entry_chars` are rejected
- `drop_journal` marks an entry as unused rather than deleting it

## License

MIT
