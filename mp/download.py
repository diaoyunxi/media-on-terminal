#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""歌曲下载"""

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

from mp.lyrics import OnlineLyricsFetcher
from mp.config import Config

def download_song_interactive(config: 'Config', keyword: str, output_dir: str = None):
    """交互式歌曲下载：搜索 → 试听 → 选择下载（含歌词）

    流程：
    1. 输入关键词搜索歌曲
    2. 显示候选列表
    3. 用户选择或输入试听
    4. 播放歌曲，用户按键控制
    5. 播完后选择：下载 / 换版本 / 重新搜索 / 退出

    :param config: Config 对象
    :param keyword: 搜索关键词，'__interactive__' 表示进入交互搜索
    :param output_dir: 下载输出目录，默认当前目录
    """
    import subprocess
    import select

    out_dir = Path(output_dir) if output_dir else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    fetcher = OnlineLyricsFetcher()
    src_name_map = {"qq": "QQ音乐", "netease": "网易云", "kugou": "酷狗"}

    def _safe_filename(s: str) -> str:
        """清理文件名中的非法字符"""
        return re.sub(r'[\\/*?:"<>|]', '_', s)

    def _download_url_to_file(url: str, save_path: Path, timeout: int = 120) -> bool:
        """下载 URL 到文件，带进度显示"""
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                written = 0
                with open(save_path, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
                        written += len(chunk)
                        if total:
                            pct = written * 100 // total
                            bar_w = 30
                            filled = int(bar_w * pct / 100)
                            bar = "█" * filled + "─" * (bar_w - filled)
                            print(f"\r  下载进度: |{bar}| {pct}% ({written}/{total})", end="")
                if total:
                    print()
            return True
        except Exception as e:
            print(f"\n  下载失败: {e}")
            return False

    def _preview_play(url: str, title: str) -> str:
        """使用 ffplay 试听歌曲，返回用户最终选择

        返回:
            'download'  - 下载
            'next'       - 找另一个版本
            'quit'       - 退出
            'search'     - 重新搜索
        """
        print(f"\n  试听: {title}")
        print("  ────────────────────────────────────")
        print("  [d] 下载此版本  [n] 换一个版本")
        print("  [s] 重新搜索    [q] 退出")
        print("  [空格] 暂停/继续  [←/→] 快进/快退")
        print("  ────────────────────────────────────")
        print("  ▶ 正在播放...")

        try:
            # 使用 ffplay 播放，-nodisp 隐藏视频窗口，-autoexit 自动退出
            proc = subprocess.Popen(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", url],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError:
            print("  错误: 未找到 ffplay，请安装 ffmpeg")
            choice = input("  \n  输入选择 [d/n/s/q]: ").strip().lower()
            return choice

        # 非阻塞读取用户输入
        import tty
        import termios

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            choice = ""
            while proc.poll() is None:
                if select.select([sys.stdin], [], [], 0.2)[0]:
                    ch = sys.stdin.read(1)
                    if ch in ('d', 'D', 'n', 'N', 's', 'S', 'q', 'Q', '\x03'):
                        choice = ch.lower()
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        break
                    elif ch == ' ':
                        try:
                            proc.stdin.write(b' ')
                            proc.stdin.flush()
                        except Exception:
                            pass
                    elif ch == '\x1b':
                        # 可能是 Escape 键或方向键开头
                        # 尝试读取剩余序列（50ms 内）
                        seq = ""
                        try:
                            while select.select([sys.stdin], [], [], 0.05)[0]:
                                seq += sys.stdin.read(1)
                        except Exception:
                            pass
                        if seq:
                            # 方向键序列，转发给 ffplay
                            try:
                                proc.stdin.write(('\x1b' + seq).encode())
                                proc.stdin.flush()
                            except Exception:
                                pass
                        else:
                            # 纯 Escape 键 = 退出
                            choice = 'q'
                            proc.terminate()
                            try:
                                proc.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                            break
                    else:
                        # 其他键，转发给 ffplay
                        try:
                            proc.stdin.write(ch.encode())
                            proc.stdin.flush()
                        except Exception:
                            pass
            if proc.poll() is not None and not choice:
                # 播放完毕，等待用户选择
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                print("\n  ▶ 播放完毕")
                choice = input("  输入选择 [d/n/s/q]: ").strip().lower()
                return choice
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()

        return choice

    def _download_lyrics_for(candidate: Tuple[str, str, str, str], save_dir: Path) -> Optional[Path]:
        """下载候选歌曲的歌词"""
        name, artist, source, ident = candidate
        safe_name = _safe_filename(f"{name} - {artist or '未知'}")
        lrc_path = save_dir / f"{safe_name}.lrc"
        try:
            lrc = fetcher._fetch_lyric_by_candidate(candidate)
            if lrc and fetcher._has_timeline(lrc):
                lrc_path.write_text(lrc, encoding='utf-8')
                print(f"  ✓ 歌词已保存: {lrc_path.name}")
                return lrc_path
            else:
                print(f"  ! 该歌曲无有效歌词（无时间轴或纯音乐）")
                return None
        except Exception as e:
            print(f"  ! 歌词下载失败: {e}")
            return None

    # ===== 主流程 =====
    current_keyword = keyword if keyword != '__interactive__' else None

    while True:
        # 步骤1: 获取搜索关键词
        if not current_keyword:
            try:
                current_keyword = input("\n输入歌曲名/歌手名搜索 (输入 q 退出): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n已退出")
                return
            if not current_keyword or current_keyword.lower() == 'q':
                print("已退出")
                return

        # 步骤2: 搜索
        print(f"\n正在搜索 \"{current_keyword}\" ...")
        candidates = fetcher.search_candidates(current_keyword, top_n=10)
        if not candidates:
            print("未找到结果，请尝试其他关键词")
            current_keyword = None
            continue

        print(f"\n找到 {len(candidates)} 首候选:")
        for i, (name, artist, source, _) in enumerate(candidates):
            src_label = src_name_map.get(source, source)
            print(f"  [{i + 1}] {name} - {artist or '未知'}  ({src_label})")
        print("  [0] 重新搜索")
        print("  [q] 退出")

        # 步骤3: 选择候选
        try:
            choice = input("\n选择序号试听: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出")
            return

        if not choice or choice.lower() == 'q':
            print("已退出")
            return
        if choice == '0':
            current_keyword = None
            continue

        try:
            idx = int(choice) - 1
        except ValueError:
            print("请输入数字序号")
            continue

        if idx < 0 or idx >= len(candidates):
            print("序号超出范围")
            continue

        # 步骤4: 获取播放 URL 并试听
        cand = candidates[idx]
        song_name = f"{cand[0]} - {cand[1] or '未知'}"
        print(f"\n获取播放链接中...")
        song_url = fetcher.fetch_song_url_by_candidate(cand)
        if not song_url:
            print(f"未能获取 {song_name} 的播放链接，尝试下一个")
            continue

        # 步骤5: 试听 + 用户选择
        action = _preview_play(song_url, song_name)

        if action == 'q':
            print("已退出")
            return
        elif action == 's':
            current_keyword = None
            continue
        elif action == 'n':
            # 返回候选列表，让用户选另一个
            continue
        elif action == 'd':
            # 下载
            safe_name = _safe_filename(f"{cand[0]} - {cand[1] or '未知'}")
            print(f"\n正在下载: {safe_name}")

            # 下载歌词
            _download_lyrics_for(cand, out_dir)

            # 下载歌曲
            # 尝试从 URL 推断扩展名
            ext = ".mp3"
            if ".m4a" in song_url or "mp4" in song_url.lower():
                ext = ".m4a"
            elif ".flac" in song_url.lower():
                ext = ".flac"
            song_path = out_dir / f"{safe_name}{ext}"
            if _download_url_to_file(song_url, song_path):
                print(f"  ✓ 歌曲已保存: {song_path}")
            else:
                print(f"  ✗ 歌曲下载失败")

            # 下载完成后，询问是否继续搜索
            print()
            try:
                again = input("继续搜索其他歌曲？[Y/n/q]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n已退出")
                return
            if again == 'q':
                print("已退出")
                return
            elif again == 'n':
                print("已退出")
                return
            else:
                current_keyword = None
                continue
        else:
            # 默认返回候选列表
            continue


