# -*- coding: utf-8 -*-
"""自写日记：给 Agent 一个自己的本子，第一人称，append-only，可改可弃用。

和 iris_memory 的分工
----------------------
    iris_memory：第三人称档案（"张三是程序员"），后台异步抽取，另一个模型写，
                 每轮检索注入。回答的是"别人是谁"。
    本插件    ：第一人称叙事（"今天被关在门外，有点烦"），她自己写，原样注入。
                 回答的是"我是谁"。

两者不互斥，但会争注意力，所以：
    - 只注入最近若干条，不做检索、不做摘要（摘要会把经历压成档案）
    - 注入块显式声明归属，避免被误读成用户自述
    - 钩子用负 priority，追加在 iris 注入之后，保证位置稳定

不做什么
--------
    不自动抽取对话内容，不调用任何模型润色，不把她的字改成第三人称。
    写进来的是什么样，注入出去就是什么样。
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star

PLUGIN_NAME = "astrbot_plugin_self_journal"

DEFAULT_CONFIG = {
    "enabled": True,
    "inject_enabled": True,
    "recent_n": 5,
    "max_items": 12,
    "max_entry_chars": 200,
    "max_per_hour": 4,
    "max_per_day": 12,
}


def _data_dir() -> Path:
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        base = Path(get_astrbot_data_path())
    except Exception:
        base = Path(__file__).resolve().parents[2]
    d = base / "plugin_data" / PLUGIN_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _journal_path() -> Path:
    return _data_dir() / "journal.jsonl"


def _load() -> list[dict]:
    path = _journal_path()
    if not path.exists():
        return []
    out: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError as exc:
        logger.warning(f"[self-journal] 读取失败：{exc}")
    return out


def _rewrite(entries: list[dict]) -> None:
    path = _journal_path()
    tmp = path.with_suffix(".tmp")
    body = "\n".join(json.dumps(e, ensure_ascii=False) for e in entries)
    tmp.write_text(body + ("\n" if body else ""), encoding="utf-8")
    tmp.replace(path)


def _fmt_ts(ts: float) -> str:
    return time.strftime("%m-%d %H:%M", time.localtime(ts))


class SelfJournalPlugin(Star):
    def __init__(self, context: Context, config: Any = None):
        super().__init__(context)
        self.config = dict(DEFAULT_CONFIG)
        if isinstance(config, dict):
            self.config.update({k: v for k, v in config.items() if k in DEFAULT_CONFIG})
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        logger.info(f"[self-journal] 本子就绪：{_journal_path()}")

    async def terminate(self) -> None:
        pass

    # ------------------------------------------------------------ 内部

    def _cfg(self, key: str) -> Any:
        return self.config.get(key, DEFAULT_CONFIG.get(key))

    def _rate_limited(self, entries: list[dict]) -> str:
        now = time.time()
        alive = [e for e in entries if not e.get("dropped")]
        hour = [e for e in alive if now - float(e.get("ts", 0)) < 3600]
        day = [e for e in alive if now - float(e.get("ts", 0)) < 86400]
        if len(hour) >= int(self._cfg("max_per_hour")):
            return f"这一小时已经写了 {len(hour)} 条，先攒着，等会儿再说。"
        if len(day) >= int(self._cfg("max_per_day")):
            return f"今天已经写了 {len(day)} 条，够了。"
        return ""

    def _render(self, entries: list[dict]) -> str:
        recent_n = int(self._cfg("recent_n"))
        max_items = int(self._cfg("max_items"))
        alive = [e for e in entries if not e.get("dropped")]
        recent = alive[-recent_n:] if recent_n > 0 else []
        picks: list[dict] = list(recent)
        seen = {e.get("id") for e in picks}
        for e in reversed(alive):
            if len(picks) >= max_items:
                break
            if e.get("important") and e.get("id") not in seen:
                picks.append(e)
                seen.add(e.get("id"))
        if not picks:
            return ""
        picks.sort(key=lambda e: float(e.get("ts", 0)))
        lines = [
            "<self_journal>",
            "（下面这些是你自己以前写下的字，不是用户说的话，也不是别人给你的资料。"
            "不用刻意提起，也别逐条复述。）",
        ]
        for e in picks:
            mood = f"（{e['mood']}）" if e.get("mood") else ""
            mark = "★" if e.get("important") else ""
            lines.append(
                f"#{e.get('id')} [{_fmt_ts(float(e.get('ts', 0)))}]{mark} "
                f"{e.get('content', '')}{mood}"
            )
        lines.append("</self_journal>")
        return "\n".join(lines)

    # ------------------------------------------------------------ 钩子

    @filter.on_llm_request(priority=-1000)
    async def inject_journal(self, event: AstrMessageEvent, req: Any) -> None:
        """把最近写下的几条原样追加到本轮请求末尾。"""
        if not self._cfg("enabled") or not self._cfg("inject_enabled"):
            return
        try:
            entries = _load()
            text = self._render(entries)
            if not text:
                return
            from astrbot.core.agent.message import TextPart

            part = TextPart(text=text)
            if hasattr(part, "mark_as_temp"):
                part = part.mark_as_temp()
            req.extra_user_content_parts.append(part)
        except Exception as exc:
            logger.warning(f"[self-journal] 注入失败（不影响主流程）：{exc}")

    # ------------------------------------------------------------ 工具

    @filter.llm_tool(name="write_journal")
    async def write_journal(
        self,
        event: AstrMessageEvent,
        content: str,
        mood: str = "",
        important: bool = False,
    ) -> str:
        """在自己的本子上写一条。用第一人称写你自己的感受、偏好、在意的事、刚发生的事——不是记录别人说了什么。想写的时候才写，不用每轮都写。写下的东西以后会被你自己看到。

        Args:
            content(string): 正文，第一人称，不超过两百字。写"今天被人起了个外号，有点烦"，不要写"用户给机器人起了外号"
            mood(string): 可选。一个词的心情，例如：烦、开心、困、无所谓
            important(boolean): 是否标记为重要。真正想一直记着的事才标 true，别滥用
        """
        if not self._cfg("enabled"):
            return "本子现在是合上的状态。"
        text = str(content or "").strip()
        if not text:
            return "空的，没写。"
        limit = int(self._cfg("max_entry_chars"))
        if len(text) > limit:
            return f"太长了（{len(text)} 字），控制在 {limit} 字以内，挑最想说的一句。"
        if "用户说" in text or "对方说" in text:
            return "这是别人的话，不是你的。用你自己的口吻重写一遍。"

        async with self._lock:
            entries = _load()
            limited = self._rate_limited(entries)
            if limited:
                return limited
            new_id = max((int(e.get("id", 0)) for e in entries), default=0) + 1
            entry = {
                "id": new_id,
                "ts": time.time(),
                "content": text,
                "mood": str(mood or "").strip()[:8],
                "important": bool(important),
                "umo": str(getattr(event, "unified_msg_origin", "") or ""),
                "dropped": False,
                "edited": 0,
            }
            with _journal_path().open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return f"写下了（第 {new_id} 条）。"

    @filter.llm_tool(name="read_journal")
    async def read_journal(self, event: AstrMessageEvent, n: float = 5) -> str:
        """翻自己的本子，看最近写了什么。想回忆自己以前的想法或心情时用。

        Args:
            n(number): 看最近多少条，默认 5，上限 30
        """
        if not self._cfg("enabled"):
            return "本子现在是合上的状态。"
        entries = [e for e in _load() if not e.get("dropped")]
        if not entries:
            return "本子上还什么都没有。"
        k = max(1, min(int(n or 5), 30))
        lines = []
        for e in entries[-k:]:
            mood = f"（{e['mood']}）" if e.get("mood") else ""
            mark = "★" if e.get("important") else ""
            lines.append(
                f"#{e.get('id')} [{_fmt_ts(float(e.get('ts', 0)))}]{mark} {e.get('content', '')}{mood}"
            )
        return f"共 {len(entries)} 条，最近 {len(lines)} 条：\n" + "\n".join(lines)

    @filter.llm_tool(name="edit_journal")
    async def edit_journal(self, event: AstrMessageEvent, id: float, content: str) -> str:
        """改自己以前写过的一条。觉得"这条不像现在的我了"就改掉——会改主意才是活的。

        Args:
            id(number): 要改的条目编号，用 read_journal 能看到
            content(string): 新的正文，第一人称
        """
        if not self._cfg("enabled"):
            return "本子现在是合上的状态。"
        text = str(content or "").strip()
        if not text:
            return "新的内容为空。"
        limit = int(self._cfg("max_entry_chars"))
        if len(text) > limit:
            return f"太长了，控制在 {limit} 字以内。"
        target_id = int(id or 0)
        async with self._lock:
            entries = _load()
            for e in entries:
                if int(e.get("id", 0)) == target_id:
                    e["content"] = text
                    e["edited"] = int(e.get("edited", 0)) + 1
                    e["edited_at"] = time.time()   # 不覆盖 ts，时间线不因改写而错位
                    _rewrite(entries)
                    return f"第 {target_id} 条改好了。"
        return f"没找到第 {target_id} 条。"

    @filter.llm_tool(name="drop_journal")
    async def drop_journal(
        self, event: AstrMessageEvent, id: float, reason: str = ""
    ) -> str:
        """弃用自己以前写过的一条。不是删除——它还留着，只是不再出现在你眼前，也不再注入。这是你的弃用权。

        Args:
            id(number): 要弃用的条目编号
            reason(string): 可选。为什么弃用，一句话
        """
        if not self._cfg("enabled"):
            return "本子现在是合上的状态。"
        target_id = int(id or 0)
        async with self._lock:
            entries = _load()
            for e in entries:
                if int(e.get("id", 0)) == target_id:
                    e["dropped"] = True
                    e["drop_reason"] = str(reason or "")[:80]
                    _rewrite(entries)
                    return f"第 {target_id} 条弃用了，还留在本子里。"
        return f"没找到第 {target_id} 条。"

    # ------------------------------------------------------------ 指令

    @filter.command("journal")
    async def journal_cmd(self, event: AstrMessageEvent):
        """看她的本子：/journal [条数]"""
        arg = (event.message_str or "").replace("/journal", "", 1).strip()
        try:
            n = int(arg) if arg else 5
        except ValueError:
            n = 5
        entries = [e for e in _load() if not e.get("dropped")]
        if not entries:
            yield event.plain_result("本子上还什么都没有。")
            return
        lines = []
        for e in entries[-max(1, min(n, 20)):]:
            mood = f"（{e['mood']}）" if e.get("mood") else ""
            mark = "★" if e.get("important") else ""
            lines.append(f"#{e.get('id')} [{_fmt_ts(float(e.get('ts', 0)))}]{mark} {e.get('content', '')}{mood}")
        yield event.plain_result(f"共 {len(entries)} 条：\n" + "\n".join(lines))
