#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文件浏览器"""

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


class FileBrowser:
    """交互式文件浏览器 - 在终端中浏览和选择媒体文件"""

    MEDIA_EXTENSIONS = {
        '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.opus', '.m4b',
        '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'
    }

    def __init__(self, start_dir: Optional[Path] = None):
        self.current_dir = start_dir or Path.home()
        self.cursor = 0
        self.scroll_offset = 0
        self.selected: List[Path] = []
        self.entries: List[Path] = []
        self.refresh_entries()

    def refresh_entries(self):
        """刷新当前目录内容"""
        dirs = []
        files = []
        try:
            for entry in sorted(self.current_dir.iterdir(), key=lambda x: x.name.lower()):
                if entry.name.startswith('.'):
                    continue
                if entry.is_dir():
                    dirs.append(entry)
                elif entry.is_file() and entry.suffix.lower() in self.MEDIA_EXTENSIONS:
                    files.append(entry)
        except PermissionError:
            pass
        self.entries = dirs + files
        self.cursor = min(self.cursor, max(0, len(self.entries) - 1))

    def _get_display_height(self) -> int:
        try:
            return os.get_terminal_size().lines - 6
        except Exception:
            return 20

    def _has_parent_entry(self) -> bool:
        """是否有上级目录条目"""
        return self.current_dir.parent != self.current_dir

    def _total_items(self) -> int:
        """总条目数（包括..）"""
        return len(self.entries) + (1 if self._has_parent_entry() else 0)

    def _render(self):
        """渲染文件浏览器界面"""
        try:
            term_width = os.get_terminal_size().columns
        except Exception:
            term_width = 80

        display_height = self._get_display_height()
        has_parent = self._has_parent_entry()
        total_items = self._total_items()

        # 调整滚动
        if self.cursor < self.scroll_offset:
            self.scroll_offset = self.cursor
        elif self.cursor >= self.scroll_offset + display_height:
            self.scroll_offset = self.cursor - display_height + 1

        # 清屏
        sys.stdout.write('\033[2J\033[H')

        # 标题栏
        print(f"\033[1;34m{'═' * term_width}\033[0m")
        title = "  mp 文件浏览器"
        print(f"\033[1;34m{title:<{term_width - 1}}\033[0m")
        print(f"\033[1;34m{'═' * term_width}\033[0m")

        # 当前路径
        path_display = str(self.current_dir)
        if len(path_display) > term_width - 10:
            path_display = '...' + path_display[-(term_width - 13):]
        print(f"\033[33m  📁 {path_display}\033[0m")
        print(f"\033[90m  已选: {len(self.selected)} 个文件\033[0m")
        print(f"\033[1;34m{'─' * term_width}\033[0m")

        # 计算可见范围
        visible_start = self.scroll_offset
        visible_end = min(visible_start + display_height, total_items)

        for display_idx in range(visible_start, visible_end):
            is_cursor = (display_idx == self.cursor)
            marker = "▶ " if is_cursor else "  "

            if has_parent and display_idx == 0:
                # 上级目录
                line = f"{marker}\033[36m⬆ ..\033[0m"
            else:
                entry_idx = display_idx - (1 if has_parent else 0)
                if entry_idx < len(self.entries):
                    entry = self.entries[entry_idx]

                    if entry.is_dir():
                        icon = "📁"
                        color = "\033[36m"
                        name = entry.name + "/"
                    else:
                        icon = "🎵"
                        color = "\033[0m"
                        name = entry.name

                    sel_marker = ""
                    if entry in self.selected:
                        sel_marker = " \033[32m✓\033[0m"

                    line = f"{marker}{icon} {color}{name}\033[0m{sel_marker}"
                else:
                    continue

            if is_cursor:
                line = f"\033[7m{line:<{term_width - 1}}\033[0m"

            print(line)

        # 底部帮助
        print(f"\033[1;34m{'─' * term_width}\033[0m")
        help_text = " ↑↓导航  Enter选择/进入  Space选中  a全选  c清除  p播放  q返回 "
        padding = max(0, (term_width - len(help_text)) // 2)
        print(f"\033[90m{' ' * padding}{help_text}\033[0m")
        sys.stdout.flush()

    def run(self) -> List[Path]:
        """运行文件浏览器，返回选中的文件列表"""
        if platform.system() == "Windows":
            return self._run_windows()
        else:
            return self._run_unix()

    def _run_unix(self) -> List[Path]:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)

        try:
            tty.setcbreak(fd)

            while True:
                self._render()

                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)

                    if ch == '\x1b':
                        ch2 = sys.stdin.read(1)
                        if ch2 == '[':
                            ch3 = sys.stdin.read(1)
                            if ch3 == 'A':  # Up
                                self.cursor = max(0, self.cursor - 1)
                            elif ch3 == 'B':  # Down
                                self.cursor = min(self._total_items() - 1, self.cursor + 1)
                    elif ch == '\n' or ch == '\r':  # Enter
                        if self.cursor == 0 and self.current_dir.parent != self.current_dir:
                            self.current_dir = self.current_dir.parent
                            self.cursor = 0
                            self.scroll_offset = 0
                            self.refresh_entries()
                        elif self.cursor < len(self.entries):
                            entry = self.entries[self.cursor]
                            if entry.is_dir():
                                self.current_dir = entry
                                self.cursor = 0
                                self.scroll_offset = 0
                                self.refresh_entries()
                            else:
                                self.toggle_select(entry)
                    elif ch == ' ':  # Space - toggle select
                        if self.cursor < len(self.entries):
                            entry = self.entries[self.cursor]
                            if entry.is_file():
                                self.toggle_select(entry)
                    elif ch == 'a':  # Select all
                        self.select_all()
                    elif ch == 'c':  # Clear selection
                        self.selected.clear()
                    elif ch == 'p':  # Play selected
                        if self.selected:
                            break
                        elif self.cursor < len(self.entries) and self.entries[self.cursor].is_file():
                            self.selected.append(self.entries[self.cursor])
                            break
                    elif ch in ('q', 'Q', '\x03'):
                        self.selected.clear()
                        break

        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            sys.stdout.write('\033[2J\033[H')
            sys.stdout.flush()

        return self.selected.copy()

    def _run_windows(self) -> List[Path]:
        import msvcrt

        while True:
            self._render()

            if msvcrt.kbhit():
                key = msvcrt.getch()

                if key == b'\xe0':
                    key2 = msvcrt.getch()
                    if key2 == b'H':  # Up
                        self.cursor = max(0, self.cursor - 1)
                    elif key2 == b'P':  # Down
                        self.cursor = min(self._total_items() - 1, self.cursor + 1)
                elif key in (b'\r', b'\n'):  # Enter
                    if self.cursor == 0 and self.current_dir.parent != self.current_dir:
                        self.current_dir = self.current_dir.parent
                        self.cursor = 0
                        self.scroll_offset = 0
                        self.refresh_entries()
                    elif self.cursor < len(self.entries):
                        entry = self.entries[self.cursor]
                        if entry.is_dir():
                            self.current_dir = entry
                            self.cursor = 0
                            self.scroll_offset = 0
                            self.refresh_entries()
                        else:
                            self.toggle_select(entry)
                elif key == b' ':
                    if self.cursor < len(self.entries):
                        entry = self.entries[self.cursor]
                        if entry.is_file():
                            self.toggle_select(entry)
                elif key == b'a':
                    self.select_all()
                elif key == b'c':
                    self.selected.clear()
                elif key == b'p':
                    if self.selected:
                        break
                    elif self.cursor < len(self.entries) and self.entries[self.cursor].is_file():
                        self.selected.append(self.entries[self.cursor])
                        break
                elif key in (b'q', b'Q'):
                    self.selected.clear()
                    break

            time.sleep(0.05)

        return self.selected.copy()

    def toggle_select(self, entry: Path):
        """切换文件选中状态"""
        if entry in self.selected:
            self.selected.remove(entry)
        else:
            self.selected.append(entry)

    def select_all(self):
        """选中所有文件"""
        for entry in self.entries:
            if entry.is_file() and entry not in self.selected:
                self.selected.append(entry)


