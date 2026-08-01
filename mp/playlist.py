#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""播放列表"""

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
from mp.constants import PLAYLIST_DIR
from mp.media_info import MediaInfo


class Playlist:
    """播放列表类"""
    
    def __init__(self):
        self.files: List[Path] = []
        self.current_index = 0
        self.shuffled_order: List[int] = []
        self.is_shuffled = False
    
    def add_file(self, file_path: Path):
        """添加文件"""
        if file_path.exists() and file_path not in self.files:
            self.files.append(file_path)
    
    def add_directory(self, dir_path: Path, recursive: bool = False):
        """添加目录中的所有媒体文件"""
        if not dir_path.is_dir():
            return
        
        media_extensions = {
            '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.opus', '.m4b',
            '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'
        }
        
        if recursive:
            pattern = '**/*'
        else:
            pattern = '*'
        
        for file in dir_path.glob(pattern):
            if file.is_file() and file.suffix.lower() in media_extensions:
                self.add_file(file)
        
        # 按文件名排序
        self.files.sort(key=lambda x: x.name.lower())
    
    def clear(self):
        """清空播放列表"""
        self.files.clear()
        self.current_index = 0
        self.shuffled_order.clear()
    
    def get_current(self) -> Optional[Path]:
        """获取当前文件"""
        if not self.files:
            return None
        
        if self.is_shuffled and self.shuffled_order:
            idx = self.shuffled_order[self.current_index]
        else:
            idx = self.current_index
        
        if 0 <= idx < len(self.files):
            return self.files[idx]
        return None
    
    def next(self) -> Optional[Path]:
        """下一首"""
        if not self.files:
            return None
        
        self.current_index += 1
        if self.current_index >= len(self.files):
            self.current_index = 0
            return None  # 表示列表结束
        
        return self.get_current()
    
    def previous(self) -> Optional[Path]:
        """上一首"""
        if not self.files:
            return None
        
        self.current_index -= 1
        if self.current_index < 0:
            self.current_index = len(self.files) - 1
        
        return self.get_current()
    
    def shuffle(self):
        """随机排序"""
        self.shuffled_order = list(range(len(self.files)))
        random.shuffle(self.shuffled_order)
        self.is_shuffled = True
        self.current_index = 0
    
    def unshuffle(self):
        """取消随机"""
        self.shuffled_order.clear()
        self.is_shuffled = False
    
    def toggle_shuffle(self):
        """切换随机状态"""
        if self.is_shuffled:
            self.unshuffle()
        else:
            self.shuffle()
    
    def display(self):
        """显示播放列表"""
        if not self.files:
            print("播放列表为空")
            return
        
        print(f"\n{'='*60}")
        print(f"  播放列表 ({len(self.files)} 个文件)")
        print(f"{'='*60}")
        
        for i, file in enumerate(self.files):
            marker = "▶ " if i == self.current_index else "  "
            print(f"{marker}{i+1:3d}. {file.name}")
        
        print(f"{'='*60}\n")
    
    def save_to_file(self, name: str):
        """保存播放列表到文件"""
        try:
            PLAYLIST_DIR.mkdir(parents=True, exist_ok=True)
            playlist_file = PLAYLIST_DIR / f"{name}.m3u"
            
            with open(playlist_file, 'w', encoding='utf-8') as f:
                f.write("#EXTM3U\n")
                for file in self.files:
                    f.write(f"{file}\n")
            
            print(f"播放列表已保存: {playlist_file}")
        except Exception as e:
            print(f"保存失败: {e}")
    
    def load_from_file(self, name: str):
        """从文件加载播放列表"""
        try:
            playlist_file = PLAYLIST_DIR / f"{name}.m3u"
            
            if not playlist_file.exists():
                # 尝试直接作为路径
                playlist_file = Path(name)
            
            if not playlist_file.exists():
                print(f"播放列表不存在: {name}")
                return
            
            self.clear()
            
            with open(playlist_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        file_path = Path(line)
                        if file_path.exists():
                            self.add_file(file_path)
            
            print(f"已加载 {len(self.files)} 个文件")
        except Exception as e:
            print(f"加载失败: {e}")




class PlaylistIO:
    """播放列表导入/导出 - 支持 M3U/M3U8 格式"""

    @staticmethod
    def export_m3u(files: List[Path], output_path: Path, playlist_name: str = 'Playlist') -> bool:
        """导出为 M3U 播放列表文件"""
        if not files:
            print("错误: 播放列表为空")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('#EXTM3U\n')
                f.write(f'#PLAYLIST:{playlist_name}\n')
                for fp in files:
                    if not fp.exists():
                        continue
                    info = MediaInfo.get_info(fp)
                    title = info.get('title') or fp.stem
                    artist = info.get('artist', '')
                    display = f"{artist} - {title}" if artist else title
                    duration = int(info.get('duration', -1))
                    f.write(f'#EXTINF:{duration},{display}\n')
                    # 写入绝对路径
                    f.write(str(fp.resolve()) + '\n')

            print(f"✓ 已导出播放列表: {output_path}")
            print(f"  包含 {len(files)} 个文件")
            return True
        except Exception as e:
            print(f"✗ 导出失败: {e}")
            return False

    @staticmethod
    def import_m3u(file_path: Path) -> List[Path]:
        """从 M3U/M3U8 文件导入播放列表"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return []

        files: List[Path] = []
        base_dir = file_path.parent

        try:
            # 尝试多种编码
            content = None
            for enc in ('utf-8', 'utf-8-sig', 'gbk', 'latin-1'):
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        content = f.read()
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

            if content is None:
                print("✗ 无法解码文件（请确认文件编码）")
                return []

            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                p = Path(line)
                if not p.is_absolute():
                    p = base_dir / p
                if p.exists():
                    files.append(p.resolve())
                else:
                    print(f"  跳过（不存在）: {line}")

            print(f"✓ 导入播放列表: {file_path.name}")
            print(f"  共 {len(files)} 个有效文件")
            return files
        except Exception as e:
            print(f"✗ 导入失败: {e}")
            return []


