#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""歌词显示与在线搜索"""

import sys
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import re
import signal
import platform
import subprocess
import shutil
import argparse
import time
import threading
import random
import json
import hashlib
import struct
import zipfile
import tempfile
import base64
import urllib.request
import urllib.error
import urllib.parse
import unicodedata
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

from mp.config import Config

class LyricsDisplay:
    """歌词显示类 - 支持本地 .lrc 文件和在线搜索

    在线搜索策略：
    1. 启动时若本地无 .lrc 文件，自动在线搜索（QQ优先，网易云回退）
    2. 搜索成功后缓存为同名 .lrc 文件，下次播放直接读取本地
    3. 自动搜索不覆盖已存在的 .lrc；手动搜索会覆盖
    4. 仅采用带时间轴的 LRC 歌词，纯文本歌词丢弃
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.lyrics: List[tuple] = []  # (时间戳, 歌词内容)
        self.current_index = -1
        self.offset = 0.0  # 歌词时间偏移（秒）
        self.enabled = True
        # 在线搜索相关
        self.fetcher: Optional[OnlineLyricsFetcher] = None
        self.online_source: Optional[str] = None  # 当前歌词来源 "qq" / "netease" / None(本地)
        self.auto_searched: bool = False  # 是否已尝试过自动搜索
        self.load_lyrics()

    def _lrc_path(self) -> Path:
        """获取同名 .lrc 文件路径"""
        return self.file_path.with_suffix('.lrc')

    def _find_local_lrc(self) -> Optional[Path]:
        """查找本地 .lrc 文件（含同名 .txt 回退）"""
        lrc_path = self._lrc_path()
        if lrc_path.exists():
            return lrc_path
        # 同级目录查找 stem.lrc / stem.txt
        for ext in ['.lrc', '.txt']:
            potential = self.file_path.parent / (self.file_path.stem + ext)
            if potential.exists():
                return potential
        return None

    def load_lyrics(self):
        """加载本地歌词文件"""
        lrc_path = self._find_local_lrc()
        if not lrc_path:
            self.lyrics = []
            return
        try:
            with open(lrc_path, 'r', encoding='utf-8') as f:
                self._parse_lrc(f.read())
        except Exception:
            self.lyrics = []

    def _parse_lrc(self, content: str):
        """解析LRC格式歌词

        兼容多种时间标签格式：
        - [mm:ss.xx]  标准（2位毫秒）
        - [mm:ss.xxx] 3位毫秒
        - [mm:ss]     无毫秒
        - [m:ss.xx]   1位分钟
        - [mm:ss:xx]  冒号分隔毫秒
        - 一行多时间标签 [00:01.00][00:05.00]歌词
        - 元数据标签 [ti:xxx] [ar:xxx] [al:xxx] [by:xxx]（跳过）
        - 偏移标签 [offset:ms]
        保留空行时间锚点（用于间奏显示）。
        """
        self.lyrics = []
        self.offset = 0.0

        for line in content.split('\n'):
            line = line.rstrip()
            if not line:
                continue

            # 先解析偏移标签
            offset_match = re.search(r'\[offset:([+-]?\d+)\]', line)
            if offset_match:
                self.offset = int(offset_match.group(1)) / 1000.0

            # 提取所有时间标签 [mm:ss.xx] / [m:ss] / [mm:ss:xx] 等
            # 分钟 1-3 位，秒 1-2 位，毫秒部分可选（.xx / .xxx / :xx）
            time_tags = re.findall(r'\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,3}))?\]', line)
            if not time_tags:
                continue

            # 去掉所有时间标签后的文本内容
            text = re.sub(r'\[\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?\]', '', line).strip()

            # 计算每个时间标签的时间戳
            for tag in time_tags:
                minutes = int(tag[0])
                seconds = int(tag[1])
                # 秒数进位归一化（LRC 标准秒数为 0-59，
                # 但有些文件可能写错如 [01:99.00]，按 60 进位到分钟）
                if seconds >= 60:
                    minutes += seconds // 60
                    seconds = seconds % 60
                ms_str = tag[2] if tag[2] else ''
                if ms_str:
                    # 毫秒归一化到秒：1位按十分位，2位按百分位，3位按千分位
                    if len(ms_str) == 1:
                        ms = int(ms_str) / 10.0
                    elif len(ms_str) == 2:
                        ms = int(ms_str) / 100.0
                    elif len(ms_str) == 3:
                        ms = int(ms_str) / 1000.0
                    else:
                        # 兜底：未知位数按百分位处理（罕见格式）
                        ms = int(ms_str) / 100.0
                else:
                    ms = 0.0
                timestamp = minutes * 60 + seconds + ms
                self.lyrics.append((timestamp, text))

        # 按时间排序，相同时间保留先后顺序
        self.lyrics.sort(key=lambda x: x[0])

    def get_lyrics_at_time(self, current_time: float) -> tuple:
        """获取当前时间对应的歌词和下一句"""
        adjusted_time = current_time + self.offset

        # 找到当前歌词索引
        new_index = -1
        for i, (timestamp, _) in enumerate(self.lyrics):
            if timestamp <= adjusted_time:
                new_index = i

        self.current_index = new_index

        if new_index >= 0 and new_index < len(self.lyrics):
            current = self.lyrics[new_index][1]
            next_line = self.lyrics[new_index + 1][1] if new_index + 1 < len(self.lyrics) else ''
            return current, next_line

        return '', ''

    def display_current(self, current_time: float, terminal_width: int = 80):
        """显示当前歌词"""
        if not self.enabled or not self.lyrics:
            return

        current, next_line = self.get_lyrics_at_time(current_time)

        if current:
            # 居中显示当前歌词
            padding = max(0, (terminal_width - len(current)) // 2)
            print(f"\r{' ' * padding}{current}", end='', flush=True)

        if next_line:
            next_padding = max(0, (terminal_width - len(next_line)) // 2)
            print(f"\r{' ' * next_padding}{next_line}", end='', flush=True)

    # ===== 在线搜索相关方法 =====

    @staticmethod
    def build_search_keyword(file_path: Path) -> str:
        """构造搜索关键词：元数据优先，文件名回退

        优先级：
        1. ffprobe 提取的 title + artist
        2. 清洗后的文件名（去扩展名、序号、音质标识等）
        """
        # 1. 尝试从元数据获取
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                tags = data.get('format', {}).get('tags', {}) or {}
                # 兼容大小写键
                title = tags.get('title') or tags.get('TITLE')
                artist = tags.get('artist') or tags.get('ARTIST')
                if title:
                    title = str(title).strip()
                    if artist:
                        return f"{artist} {title}"
                    return title
        except Exception:
            pass
        # 2. 回退到清洗后的文件名
        return OnlineLyricsFetcher._normalize_filename(file_path.stem)

    def _ensure_fetcher(self):
        """惰性初始化在线搜索器"""
        if self.fetcher is None:
            self.fetcher = OnlineLyricsFetcher()

    def _save_lrc(self, lrc_text: str) -> bool:
        """将歌词保存为同名 .lrc 文件

        返回: 是否保存成功
        """
        try:
            lrc_path = self._lrc_path()
            with open(lrc_path, 'w', encoding='utf-8') as f:
                f.write(lrc_text)
            return True
        except Exception:
            return False

    def _apply_lrc(self, lrc_text: str, source: str, cache: bool = True) -> bool:
        """应用歌词文本并（可选）缓存

        参数:
            lrc_text: LRC 格式歌词
            source: 来源 "qq" / "netease"
            cache: 是否缓存为 .lrc 文件

        返回: 是否成功应用
        """
        self._parse_lrc(lrc_text)
        if not self.lyrics:
            return False
        self.online_source = source
        self.enabled = True
        if cache:
            self._save_lrc(lrc_text)
        return True

    def auto_search_online(self) -> Tuple[str, Optional[str]]:
        """自动在线搜索（不覆盖本地已存在的 .lrc）

        返回:
            (status, message)
            status: "ok" | "no_result" | "no_timeline" | "network_error" | "skipped_local_exists" | "already_searched"
        """
        # 已有本地歌词则跳过
        if self.lyrics:
            return "skipped_local_exists", "本地已有歌词，跳过在线搜索"
        # 防止重复自动搜索
        if self.auto_searched:
            return "already_searched", "已尝试过自动搜索"
        self.auto_searched = True

        self._ensure_fetcher()
        keyword = self.build_search_keyword(self.file_path)
        if not keyword:
            return "no_result", "无法构造搜索关键词"

        status, lrc, source = self.fetcher.search_first(keyword)
        if status == "ok" and lrc and source:
            if self._apply_lrc(lrc, source, cache=True):
                src_name = "QQ音乐" if source == "qq" else "网易云"
                return "ok", f"在线搜索成功（{src_name}），已缓存为 .lrc"
            return "no_timeline", "歌词解析失败"
        elif status == "no_result":
            return "no_result", f"未找到 '{keyword}' 的歌词"
        elif status == "no_timeline":
            return "no_timeline", f"找到歌词但无时间轴，已丢弃"
        else:
            return "network_error", "网络搜索失败"

    def manual_search_candidates(self, keyword: Optional[str] = None) -> Tuple[str, List[Tuple[str, str, str, str]], str]:
        """手动搜索：返回候选列表

        参数:
            keyword: 自定义关键词；为空则自动构造

        返回:
            (status, candidates, used_keyword)
            status: "ok" | "no_result" | "network_error"
        """
        self._ensure_fetcher()
        used = keyword or self.build_search_keyword(self.file_path)
        try:
            candidates = self.fetcher.search_candidates(used, top_n=5)
        except Exception:
            return "network_error", [], used
        if not candidates:
            return "no_result", [], used
        return "ok", candidates, used

    def apply_candidate_by_index(self, index: int, overwrite: bool = True) -> Tuple[str, Optional[str]]:
        """应用候选索引对应的歌词（手动选择，默认覆盖本地）

        返回:
            (status, message)
        """
        self._ensure_fetcher()
        # 本地已存在且不覆盖
        if not overwrite and self._find_local_lrc() is not None:
            return "skipped_local_exists", "本地已存在 .lrc，未覆盖"

        status, lrc, source = self.fetcher.fetch_lyric_by_index(index)
        if status == "ok" and lrc and source:
            if self._apply_lrc(lrc, source, cache=True):
                src_name = "QQ音乐" if source == "qq" else "网易云"
                return "ok", f"已应用并缓存歌词（{src_name}）"
            return "no_timeline", "歌词解析失败"
        elif status == "no_result":
            return "no_result", "未找到该候选的歌词"
        elif status == "no_timeline":
            return "no_timeline", "该候选歌词无时间轴，已丢弃"
        return "network_error", "获取歌词失败"




class OnlineLyricsFetcher:
    """在线歌词搜索器 - 聚合 QQ音乐 + 网易云音乐

    策略：
    1. 优先查询 QQ音乐（原唱匹配好，时间轴完整）
    2. QQ音乐无结果或无时间轴时回退网易云
    3. 仅采用带时间轴的 LRC 歌词，纯文本歌词丢弃
    """

    UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    TIMEOUT = 8  # 单次请求超时秒数

    def __init__(self):
        # 候选结果缓存：(song_name, artist, source, song_id_or_mid)
        self._cached_candidates: List[Tuple[str, str, str, str]] = []

    @staticmethod
    def _http_get(url: str, extra_headers: Optional[Dict[str, str]] = None) -> str:
        """发起 GET 请求并返回文本

        参数:
            url: 请求地址
            extra_headers: 额外请求头

        返回:
            响应文本；失败抛出异常
        """
        headers = {"User-Agent": OnlineLyricsFetcher.UA}
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=OnlineLyricsFetcher.TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")

    @staticmethod
    def _has_timeline(lrc: str) -> bool:
        """判断 LRC 文本是否包含有效时间轴标签

        过滤以下无效歌词：
        - 空文本
        - 无时间轴的纯文本
        - 纯音乐/无歌词占位（"此歌曲为没有填词的纯音乐"等）
        - 歌词行数过少（< 3 行有效歌词，通常是占位）
        """
        if not lrc:
            return False
        # 纯音乐/无歌词占位文本检测
        instrumental_markers = (
            "此歌曲为没有填词的纯音乐",
            "纯音乐，请欣赏",
            "暂无歌词",
            "无歌词",
            "instrumental",
            "no lyrics",
        )
        lrc_lower = lrc.lower()
        for marker in instrumental_markers:
            if marker.lower() in lrc_lower:
                return False
        # 必须含时间轴
        if not re.search(r"\[\d{1,3}:\d{1,2}", lrc):
            return False
        # 统计有效歌词行数（有时间轴且非空文本）
        lines = re.findall(r"\[\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?\](.+)", lrc)
        valid_lines = [l for l in (s.strip() for s in lines) if l]
        return len(valid_lines) >= 3

    @staticmethod
    def _normalize_filename(stem: str) -> str:
        """清洗文件名作为搜索关键词

        去除常见干扰字符：扩展名残留、音质标识、序号、括注等
        """
        # 去除常见音质/版本标识
        s = re.sub(r"\((?:FLAC|flac|320|320k|320kbps|HQ|SQ|HD|无损|高品质)\)", "", stem)
        s = re.sub(r"\[(?:FLAC|flac|320|320k|320kbps|HQ|SQ|HD|无损|高品质)\]", "", s)
        # 去除前导序号 "01. " "01 - " "01_-_ " 等
        s = re.sub(r"^\d{1,3}[\s.\-_]+", "", s)
        # 去除网址
        s = re.sub(r"https?://\S+", "", s)
        # 把常见分隔符替换为空格（先替换分隔符，再合并空白）
        s = re.sub(r"[_\-]+", " ", s)
        # 多空白合一
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _qq_search(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """QQ音乐搜索"""
        url = (f"https://c.y.qq.com/soso/fcgi-bin/client_search_cp"
               f"?w={urllib.parse.quote(keyword)}&format=json&n={limit}&p=1")
        text = self._http_get(url, extra_headers={"Referer": "https://y.qq.com/"})
        data = json.loads(text)
        return data.get("data", {}).get("song", {}).get("list", []) or []

    def _qq_lyric(self, songmid: str) -> str:
        """QQ音乐获取歌词"""
        url = (f"https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_new.fcg"
               f"?songmid={songmid}&format=json&nobase64=1")
        text = self._http_get(url, extra_headers={"Referer": "https://y.qq.com/"})
        # QQ音乐可能返回 jsonp 包裹（函数名不固定，如 callback/MusicJsonCallback 等）
        # 用正则提取最外层括号内的 JSON，兼容各种函数名
        m = re.match(r"^\s*[\w$]+\s*\((.*)\)\s*$", text, re.DOTALL)
        if m:
            text = m.group(1)
        data = json.loads(text)
        return data.get("lyric", "") or ""

    def _netease_search(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """网易云搜索"""
        url = (f"https://music.163.com/api/search/get"
               f"?s={urllib.parse.quote(keyword)}&type=1&limit={limit}")
        text = self._http_get(url)
        data = json.loads(text)
        return data.get("result", {}).get("songs", []) or []

    def _netease_lyric(self, song_id: int) -> str:
        """网易云获取歌词"""
        url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1"
        text = self._http_get(url)
        data = json.loads(text)
        return data.get("lrc", {}).get("lyric", "") or ""

    def _kugou_search(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """酷狗音乐搜索（先搜歌，再取 hash）

        酷狗搜索接口返回歌曲 hash，用于后续获取歌词。
        """
        url = (f"http://mobilecdn.kugou.com/api/v3/search/song"
               f"?keyword={urllib.parse.quote(keyword)}&pagesize={limit}&page=1")
        text = self._http_get(url)
        data = json.loads(text)
        return data.get("data", {}).get("info", []) or []

    def _kugou_lyric(self, hash_id: str) -> str:
        """酷狗获取歌词

        步骤：先通过 hash 查歌词信息，再下载歌词内容。
        """
        # 步骤1：查歌词信息
        url = (f"http://krcs.kugou.com/search"
               f"?ver=1&man=yes&client=mobi&hash={hash_id}&duration=0&album_audio_id=0")
        text = self._http_get(url)
        data = json.loads(text)
        candidates = data.get("candidates", []) or []
        if not candidates:
            return ""
        info = candidates[0]
        lyric_id = info.get("id", "")
        accesskey = info.get("accesskey", "")
        if not lyric_id or not accesskey:
            return ""
        # 步骤2：下载歌词
        url = (f"http://lyrics.kugou.com/download"
               f"?ver=1&client=pc&id={lyric_id}&accesskey={accesskey}"
               f"&fmt=lrc&charset=utf8")
        text = self._http_get(url)
        data = json.loads(text)
        # content 字段是 base64 编码的歌词（base64 已在模块顶部导入）
        content = data.get("content", "") or ""
        if not content:
            return ""
        return base64.b64decode(content).decode("utf-8", errors="replace")

    def _collect_candidates(self, keyword: str) -> List[Tuple[str, str, str, str]]:
        """聚合三源搜索结果作为候选

        返回: [(song_name, artist, source, id_or_mid), ...]
        源：QQ音乐 → 网易云 → 酷狗
        """
        candidates: List[Tuple[str, str, str, str]] = []
        # QQ音乐候选
        try:
            for s in self._qq_search(keyword):
                name = s.get("songname", "") or ""
                artists = "/".join(a.get("name", "") for a in s.get("singer", []))
                mid = s.get("songmid", "") or ""
                if name and mid:
                    candidates.append((name, artists, "qq", mid))
        except Exception:
            pass
        # 网易云候选（去重，避免与QQ同名重复展示）
        try:
            for s in self._netease_search(keyword):
                name = s.get("name", "") or ""
                artists = "/".join(a.get("name", "") for a in s.get("artists", []))
                sid = s.get("id", 0) or 0
                if name and sid and not any(c[0] == name and c[1] == artists for c in candidates):
                    candidates.append((name, artists, "netease", str(sid)))
        except Exception:
            pass
        # 酷狗候选（去重）
        try:
            for s in self._kugou_search(keyword):
                name = s.get("songname", "") or ""
                artists = s.get("singername", "") or ""
                hash_id = s.get("hash", "") or ""
                if name and hash_id and not any(c[0] == name and c[1] == artists for c in candidates):
                    candidates.append((name, artists, "kugou", hash_id))
        except Exception:
            pass
        return candidates

    def _fetch_lyric_by_candidate(self, candidate: Tuple[str, str, str, str]) -> str:
        """根据候选获取歌词文本"""
        name, artist, source, ident = candidate
        try:
            if source == "qq":
                return self._qq_lyric(ident)
            elif source == "netease":
                return self._netease_lyric(int(ident))
            elif source == "kugou":
                return self._kugou_lyric(ident)
        except Exception:
            return ""
        # 未知 source 兜底，避免隐式返回 None 导致下游 _has_timeline(None) 行为不一致
        return ""

    @staticmethod
    def _score_candidate(keyword: str, candidate: Tuple[str, str, str, str]) -> int:
        """计算候选与关键词的匹配度评分，分数越高越匹配

        评分规则：
        - 歌名完全等于关键词（忽略大小写）：+100
        - 歌名包含关键词或反之：+50
        - 歌手在关键词中出现：+30
        - 关键词每个分词在歌名中出现：+10
        - 歌名为空或明显是伴奏/翻唱标识：-20

        注意：当关键词不含歌手名（纯歌名回退场景）时，
        歌名完全匹配会因 +100 导致多个候选并列最高分，
        此时由 search_first 的稳定排序保留搜索原顺序（热门优先）。
        """
        name, artist, _, _ = candidate
        kw = keyword.strip().lower()
        name_l = (name or '').strip().lower()
        artist_l = (artist or '').strip().lower()

        # 伴奏/纯音乐/翻唱标识降权
        # 中文标识用子串匹配（中文无单词边界概念）
        zh_markers = ('伴奏', '纯音乐', '翻唱', 'dj版', '现场', '卡拉ok',
                      '高燃', '降调', '节目', '氛围', '慢摇')
        if any(m in name_l or m in artist_l for m in zh_markers):
            return -20
        # 英文标识用 token 完全匹配，避免子串误伤
        # （如 'live' 误伤 'alive'/'oliver'，'3d' 误伤 '3dream'）
        # 将非字母数字字符替换为空格后分词，'inst.' 会变成 token 'inst'
        name_tokens = set(re.split(r'[^a-z0-9]+', name_l))
        artist_tokens = set(re.split(r'[^a-z0-9]+', artist_l))
        all_tokens = name_tokens | artist_tokens
        en_markers = {'cover', 'inst', 'instrumental', 'remix', 'live', 'karaoke', '3d'}
        if all_tokens & en_markers:
            return -20

        score = 0
        if name_l and name_l == kw:
            score += 100
        elif name_l and (name_l in kw or kw in name_l):
            score += 50

        if artist_l and artist_l in kw:
            score += 30

        # 分词匹配
        tokens = [t for t in re.split(r'\s+', kw) if len(t) > 1]
        for t in tokens:
            if t in name_l:
                score += 10
            if t in artist_l:
                score += 5
        return score

    def search_first(self, keyword: str) -> Tuple[str, Optional[str], Optional[str]]:
        """自动搜索：返回首个带时间轴的歌词

        参数:
            keyword: 搜索关键词

        返回:
            (status, lrc_text, source)
            status: "ok" | "no_result" | "no_timeline" | "network_error"

        匹配策略：对候选按匹配度评分排序后，优先尝试最匹配的候选，
        减少"歌词与歌曲不对应"问题（避免取到翻唱/伴奏版）。
        在已找到行数充足（>= 15 行）的歌词时提前停止，减少网络请求；
        否则遍历所有候选，选行数最多的有效歌词。
        """
        self._cached_candidates = []
        try:
            candidates = self._collect_candidates(keyword)
        except Exception as e:
            return "network_error", None, None
        self._cached_candidates = candidates

        if not candidates:
            return "no_result", None, None

        # 按匹配度评分（仅计算一次，避免重复计算）
        scored = [(c, self._score_candidate(keyword, c)) for c in candidates]
        # 过滤掉明显是伴奏/翻唱的（负分），除非全部都是负分
        positive = [(c, s) for c, s in scored if s >= 0]
        filtered = positive if positive else scored
        # 稳定排序：按分数降序，同分保留搜索原顺序（热门优先）作 tiebreak
        filtered.sort(key=lambda x: x[1], reverse=True)
        ordered = [c for c, _ in filtered]

        # 逐个候选尝试，收集所有有效歌词，选行数最多的
        # 避免选到只有几行的占位歌词（如纯音乐标识、间奏等）
        best_lrc = None
        best_source = None
        best_lines = 0
        for cand in ordered:
            lrc = self._fetch_lyric_by_candidate(cand)
            if not self._has_timeline(lrc):
                continue
            # 统计有效歌词行数
            lines = re.findall(r"\[\d{1,3}:\d{1,2}(?:[.:]\d{1,3})?\](.+)", lrc)
            valid = [l for l in (s.strip() for s in lines) if l]
            n = len(valid)
            # 首个有效候选先记录
            if best_lrc is None:
                best_lrc, best_source, best_lines = lrc, cand[2], n
            elif n > best_lines:
                best_lrc, best_source, best_lines = lrc, cand[2], n
            # 如果已找到行数充足的（>= 15 行），不再继续尝试，减少网络请求
            if best_lines >= 15:
                break

        if best_lrc:
            return "ok", best_lrc, best_source

        return "no_timeline", None, None

    def search_candidates(self, keyword: str, top_n: int = 5) -> List[Tuple[str, str, str, str]]:
        """手动搜索：返回候选列表（前 top_n 项）

        返回: [(song_name, artist, source, id_or_mid), ...]
        """
        try:
            candidates = self._collect_candidates(keyword)
        except Exception:
            candidates = []
        self._cached_candidates = candidates
        return candidates[:top_n]

    def fetch_lyric_by_index(self, index: int) -> Tuple[str, Optional[str], Optional[str]]:
        """根据缓存候选索引获取歌词

        返回:
            (status, lrc_text, source)
        """
        if not self._cached_candidates or index < 0 or index >= len(self._cached_candidates):
            return "no_result", None, None
        cand = self._cached_candidates[index]
        lrc = self._fetch_lyric_by_candidate(cand)
        if not lrc:
            return "no_result", None, None
        if not self._has_timeline(lrc):
            return "no_timeline", None, None
        return "ok", lrc, cand[2]

    @property
    def cached_candidates(self) -> List[Tuple[str, str, str, str]]:
        """已缓存的候选列表（只读视图）"""
        return list(self._cached_candidates)

    # ===== 歌曲播放/下载 URL 获取 =====

    def _qq_song_url(self, songmid: str) -> Optional[str]:
        """QQ音乐获取歌曲播放 URL（优先高音质）

        返回: 播放 URL 字符串，失败返回 None
        """
        try:
            # 使用 QQ音乐 vkey 接口获取播放地址
            params = json.dumps({
                "req_0": {
                    "module": "vkey.GetVkeyServer",
                    "method": "CgiGetVkey",
                    "param": {
                        "guid": "0",
                        "songmid": [songmid],
                        "songtype": [0],
                        "uin": "0",
                        "loginflag": 0,
                        "platform": "20",
                    }
                }
            })
            url = f"https://u.y.qq.com/cgi-bin/musicu.fcg?data={urllib.parse.quote(params)}"
            text = self._http_get(url, extra_headers={"Referer": "https://y.qq.com/"})
            data = json.loads(text)
            midurlinfo = data.get("req_0", {}).get("data", {}).get("midurlinfo", [])
            if midurlinfo:
                purl = midurlinfo[0].get("purl") or ""
                if purl:
                    # 拼接完整 URL（某些 CDN 需加协议头）
                    if purl.startswith("http"):
                        return purl
                    return f"http://dl.stream.qqmusic.qq.com/{purl}"
            return None
        except Exception:
            return None

    def _netease_song_url(self, song_id: int) -> Optional[str]:
        """网易云获取歌曲播放 URL（优先 320kbps）

        返回: 播放 URL 字符串，失败返回 None
        """
        try:
            url = f"https://music.163.com/api/song/enhance/player/url?id={song_id}&ids=[{song_id}]&br=320000"
            text = self._http_get(url)
            data = json.loads(text)
            songs = data.get("data", []) or []
            if songs:
                dl_url = songs[0].get("url") or ""
                if dl_url:
                    return dl_url
            return None
        except Exception:
            return None

    def _kugou_song_url(self, hash_id: str) -> Optional[str]:
        """酷狗获取歌曲播放 URL

        返回: 播放 URL 字符串，失败返回 None
        """
        try:
            url = f"http://m.kugou.com/app/i/getSongInfo.php?cmd=playInfo&hash={hash_id}"
            text = self._http_get(url)
            data = json.loads(text)
            dl_url = data.get("url") or data.get("playUrl") or ""
            if dl_url:
                return dl_url
            return None
        except Exception:
            return None

    def fetch_song_url_by_candidate(self, candidate: Tuple[str, str, str, str]) -> Optional[str]:
        """根据候选获取歌曲播放 URL

        参数:
            candidate: (song_name, artist, source, id_or_mid)

        返回:
            URL 字符串，失败返回 None
        """
        name, artist, source, ident = candidate
        try:
            if source == "qq":
                return self._qq_song_url(ident)
            elif source == "netease":
                return self._netease_song_url(int(ident))
            elif source == "kugou":
                return self._kugou_song_url(ident)
        except Exception:
            return None
        return None

    def fetch_song_url_by_index(self, index: int) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """根据缓存候选索引获取歌曲播放 URL

        返回:
            (url, source, song_name) 三元组，失败返回 (None, None, None)
        """
        if not self._cached_candidates or index < 0 or index >= len(self._cached_candidates):
            return None, None, None
        cand = self._cached_candidates[index]
        url = self.fetch_song_url_by_candidate(cand)
        if url:
            return url, cand[2], f"{cand[0]} - {cand[1] or '未知'}"
        return None, None, None


