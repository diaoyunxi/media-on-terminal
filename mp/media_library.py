#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""媒体库管理"""

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
from mp.constants import CONFIG_DIR
from mp.media_info import MediaInfo


class MediaLibrary:
    """媒体库 - 扫描本地媒体文件并建立可搜索索引"""

    LIBRARY_FILE = CONFIG_DIR / 'library.json'
    MEDIA_EXTENSIONS = {
        '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.opus',
        '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v',
    }
    MAX_RESULTS = 50

    def __init__(self):
        self.library = {'files': [], 'last_scan': 0, 'scan_dirs': []}
        self.load()

    def load(self):
        try:
            if self.LIBRARY_FILE.exists():
                with open(self.LIBRARY_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.library.update(saved)
        except Exception:
            pass

    def save(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.LIBRARY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.library, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def scan(self, directory: Path, recursive: bool = True) -> int:
        """扫描目录，建立媒体库索引"""
        if not directory.exists() or not directory.is_dir():
            print(f"错误: 目录不存在 {directory}")
            return 0

        # 已扫描记录去重：以路径为键
        existing = {item['path']: item for item in self.library['files']}
        scan_dirs = set(self.library.get('scan_dirs', []))
        scan_dirs.add(str(directory.resolve()))

        print(f"扫描目录: {directory}")
        print(f"{'='*60}")

        count = 0
        iterator = directory.rglob('*') if recursive else directory.iterdir()
        for fp in iterator:
            try:
                if not fp.is_file():
                    continue
                if fp.suffix.lower() not in self.MEDIA_EXTENSIONS:
                    continue
                abs_path = str(fp.resolve())
                if abs_path in existing:
                    continue
                info = MediaInfo.get_info(fp)
                entry = {
                    'path': abs_path,
                    'name': fp.name,
                    'ext': fp.suffix.lower(),
                    'size': fp.stat().st_size,
                    'duration': info.get('duration', 0),
                    'artist': info.get('artist', ''),
                    'album': info.get('album', ''),
                    'title': info.get('title', ''),
                }
                existing[abs_path] = entry
                count += 1
                if count % 50 == 0:
                    print(f"  已扫描 {count} 个文件...")
            except (PermissionError, OSError):
                continue

        self.library['files'] = list(existing.values())
        self.library['scan_dirs'] = list(scan_dirs)
        self.library['last_scan'] = time.time()
        self.save()

        print(f"\n✓ 本次新增 {count} 个媒体文件")
        print(f"  媒体库总计: {len(self.library['files'])} 个文件")
        return count

    def search(self, query: str, field: str = 'all') -> List[Dict[str, Any]]:
        """在媒体库中搜索"""
        query_lower = query.lower()
        results = []
        for entry in self.library['files']:
            if field == 'all':
                haystack = ' '.join([
                    entry.get('name', ''), entry.get('artist', ''),
                    entry.get('album', ''), entry.get('title', '')
                ]).lower()
                if query_lower in haystack:
                    results.append(entry)
            else:
                val = str(entry.get(field, '')).lower()
                if query_lower in val:
                    results.append(entry)
            if len(results) >= self.MAX_RESULTS:
                break
        return results

    def display_results(self, results: List[Dict[str, Any]]):
        """显示搜索结果"""
        print(f"\n{'='*60}")
        print(f"  搜索结果 ({len(results)} 条)")
        print(f"{'='*60}")
        if not results:
            print("  (无匹配结果)")
            return

        for i, entry in enumerate(results, 1):
            path = Path(entry['path'])
            duration = MediaInfo.format_duration(entry.get('duration', 0))
            size = MediaInfo.format_size(entry.get('size', 0))
            artist = entry.get('artist', '')
            name = entry.get('title') or path.stem
            label = f"{artist} - {name}" if artist else name
            print(f"  {i:3d}. {label}")
            print(f"       {path}")
            print(f"       [{entry['ext'].upper()}] {duration} | {size}")

    def display_stats(self):
        """显示媒体库统计"""
        files = self.library['files']
        print(f"\n{'='*60}")
        print(f"  媒体库统计")
        print(f"{'='*60}")
        print(f"  文件总数: {len(files)}")

        if not files:
            return

        # 格式分布
        by_ext: Dict[str, int] = {}
        total_size = 0
        total_dur = 0
        for entry in files:
            ext = entry.get('ext', '?')
            by_ext[ext] = by_ext.get(ext, 0) + 1
            total_size += entry.get('size', 0)
            total_dur += entry.get('duration', 0)

        print(f"  总大小: {MediaInfo.format_size(total_size)}")
        print(f"  总时长: {MediaInfo.format_duration(total_dur)}")
        print(f"\n  格式分布:")
        for ext, cnt in sorted(by_ext.items(), key=lambda x: x[1], reverse=True):
            print(f"    {ext.upper():6s}: {cnt}")

        if self.library.get('last_scan'):
            ts = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.library['last_scan']))
            print(f"\n  上次扫描: {ts}")

    def clear(self):
        """清空媒体库"""
        self.library = {'files': [], 'last_scan': 0, 'scan_dirs': []}
        self.save()
        print("✓ 媒体库已清空")


# ===== v2.7.0 新增工具类 =====


