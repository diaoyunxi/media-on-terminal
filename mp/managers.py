#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""播放管理器集合"""

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
from mp.constants import CONFIG_DIR, FAVORITES_FILE, HISTORY_FILE, RADIO_FILE

class BookmarkManager:
    """书签管理 - 保存和恢复播放位置"""
    
    BOOKMARK_FILE = CONFIG_DIR / 'bookmarks.json'
    
    def __init__(self):
        self.bookmarks: Dict[str, float] = {}
        self.load()
    
    def load(self):
        """加载书签"""
        try:
            if self.BOOKMARK_FILE.exists():
                with open(self.BOOKMARK_FILE, 'r', encoding='utf-8') as f:
                    self.bookmarks = json.load(f)
        except Exception:
            self.bookmarks = {}
    
    def save(self):
        """保存书签"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.BOOKMARK_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.bookmarks, f, indent=2)
        except Exception:
            pass
    
    def get_position(self, file_path: Path) -> float:
        """获取文件的书签位置（秒）"""
        key = str(file_path.resolve())
        return self.bookmarks.get(key, 0.0)
    
    def set_position(self, file_path: Path, position: float):
        """设置文件的书签位置（秒）"""
        key = str(file_path.resolve())
        if position > 5:  # 只保存超过5秒的位置
            self.bookmarks[key] = position
            self.save()
    
    def clear_position(self, file_path: Path):
        """清除文件的书签"""
        key = str(file_path.resolve())
        if key in self.bookmarks:
            del self.bookmarks[key]
            self.save()
    
    def has_position(self, file_path: Path) -> bool:
        """检查文件是否有书签"""
        key = str(file_path.resolve())
        return key in self.bookmarks and self.bookmarks[key] > 5




class FavoritesManager:
    """收藏管理 - 管理喜欢的歌曲"""
    
    def __init__(self):
        self.favorites: List[str] = []
        self.load()
    
    def load(self):
        """加载收藏列表"""
        try:
            if FAVORITES_FILE.exists():
                with open(FAVORITES_FILE, 'r', encoding='utf-8') as f:
                    self.favorites = json.load(f)
        except Exception:
            self.favorites = []
    
    def save(self):
        """保存收藏列表"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(FAVORITES_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.favorites, f, indent=2)
        except Exception:
            pass
    
    def add(self, file_path: Path):
        """添加歌曲到收藏"""
        key = str(file_path.resolve())
        if key not in self.favorites:
            self.favorites.append(key)
            self.save()
            return True
        return False
    
    def remove(self, file_path: Path):
        """从收藏中移除歌曲"""
        key = str(file_path.resolve())
        if key in self.favorites:
            self.favorites.remove(key)
            self.save()
            return True
        return False
    
    def is_favorite(self, file_path: Path) -> bool:
        """检查歌曲是否在收藏中"""
        key = str(file_path.resolve())
        return key in self.favorites
    
    def toggle(self, file_path: Path) -> bool:
        """切换收藏状态，返回新的收藏状态"""
        if self.is_favorite(file_path):
            self.remove(file_path)
            return False
        else:
            self.add(file_path)
            return True
    
    def get_all(self) -> List[Path]:
        """获取所有收藏的歌曲路径"""
        result = []
        for path_str in self.favorites:
            path = Path(path_str)
            if path.exists():
                result.append(path)
        return result
    
    def display(self):
        """显示收藏列表"""
        if not self.favorites:
            print("\n收藏列表为空")
            return
        
        print(f"\n{'='*60}")
        print(f"  我的收藏 ({len(self.favorites)} 首)")
        print(f"{'='*60}")
        
        for i, path_str in enumerate(self.favorites):
            path = Path(path_str)
            if path.exists():
                print(f"  {i+1:3d}. {path.name}")
            else:
                print(f"  {i+1:3d}. {path.name} (文件不存在)")
        
        print(f"{'='*60}\n")




class HistoryManager:
    """历史记录管理 - 记录播放历史"""
    
    MAX_HISTORY = 100  # 最多保存100条记录
    
    def __init__(self):
        self.history: List[Dict[str, Any]] = []
        self.load()
    
    def load(self):
        """加载历史记录"""
        try:
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
        except Exception:
            self.history = []
    
    def save(self):
        """保存历史记录"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2)
        except Exception:
            pass
    
    def add(self, file_path: Path, duration_played: float = 0):
        """添加播放记录"""
        record = {
            'path': str(file_path.resolve()),
            'name': file_path.name,
            'timestamp': time.time(),
            'duration_played': duration_played
        }
        
        # 添加到开头
        self.history.insert(0, record)
        
        # 限制历史记录数量
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[:self.MAX_HISTORY]
        
        self.save()
    
    def get_recent(self, count: int = 20) -> List[Dict[str, Any]]:
        """获取最近的播放记录"""
        return self.history[:count]
    
    def display(self, count: int = 20):
        """显示历史记录"""
        recent = self.get_recent(count)
        
        if not recent:
            print("\n播放历史为空")
            return
        
        print(f"\n{'='*60}")
        print(f"  最近播放 (最近 {len(recent)} 首)")
        print(f"{'='*60}")
        
        for i, record in enumerate(recent):
            path = Path(record['path'])
            name = record['name']
            timestamp = time.localtime(record['timestamp'])
            time_str = time.strftime('%Y-%m-%d %H:%M', timestamp)
            
            exists = "✓" if path.exists() else "✗"
            print(f"  {exists} {i+1:3d}. {name}")
            print(f"       播放时间: {time_str}")
        
        print(f"{'='*60}\n")
    
    def clear(self):
        """清空历史记录"""
        self.history = []
        self.save()
        print("播放历史已清空")




class SleepTimer:
    """定时停止 - 睡眠定时器"""
    
    def __init__(self):
        self.remaining_time = 0  # 剩余时间（秒）
        self.is_active = False
        self.start_time = 0
        self.callback = None
    
    def set(self, minutes: int, callback=None):
        """设置定时器（分钟）"""
        self.remaining_time = minutes * 60
        self.start_time = time.time()
        self.is_active = True
        self.callback = callback
        return self.remaining_time
    
    def cancel(self):
        """取消定时器"""
        self.is_active = False
        self.remaining_time = 0
        self.callback = None
    
    def get_remaining(self) -> int:
        """获取剩余时间（秒）"""
        if not self.is_active:
            return 0
        
        elapsed = time.time() - self.start_time
        remaining = max(0, self.remaining_time - elapsed)
        
        # 如果时间到了，触发回调
        if remaining == 0 and self.callback:
            self.is_active = False
            self.callback()
        
        return int(remaining)
    
    def format_remaining(self) -> str:
        """格式化剩余时间显示"""
        remaining = self.get_remaining()
        if remaining == 0:
            return ""
        
        minutes = remaining // 60
        seconds = remaining % 60
        return f"⏰ {minutes:02d}:{seconds:02d}"




class ABLoop:
    """AB循环 - 区间循环播放"""
    
    def __init__(self):
        self.point_a = 0.0  # A点位置（秒）
        self.point_b = 0.0  # B点位置（秒）
        self.is_active = False
        self.is_setting_a = True  # 正在设置A点还是B点
    
    def set_point_a(self, position: float):
        """设置A点位置"""
        self.point_a = position
        self.is_setting_a = False
    
    def set_point_b(self, position: float):
        """设置B点位置"""
        self.point_b = position
        self.is_active = True
        self.is_setting_a = True
    
    def toggle(self):
        """切换AB循环状态"""
        if self.is_active:
            self.deactivate()
        elif self.point_a > 0 and self.point_b > self.point_a:
            self.is_active = True
    
    def deactivate(self):
        """停用AB循环"""
        self.is_active = False
        self.point_a = 0.0
        self.point_b = 0.0
        self.is_setting_a = True
    
    def check_position(self, current_position: float) -> Optional[float]:
        """检查当前位置，如果超出B点则返回A点位置"""
        if not self.is_active:
            return None
        
        if current_position >= self.point_b:
            return self.point_a
        
        return None
    
    def get_status(self) -> str:
        """获取状态字符串"""
        if not self.is_active:
            return ""
        
        return f"🔁 AB: {self._format_time(self.point_a)}-{self._format_time(self.point_b)}"
    
    def _format_time(self, seconds: float) -> str:
        """格式化时间"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"




class RadioManager:
    """网络电台管理 - 支持在线流媒体播放"""
    
    # 预设电台列表
    DEFAULT_STATIONS = {
        "经典音乐": "http://stream.rthk.hk/radio/pth",
        "新闻频道": "http://stream.rthk.hk/radio/news",
        "流行音乐": "http://stream.rthk.hk/radio/pop",
        "古典音乐": "http://stream.rthk.hk/radio/classical",
    }
    
    def __init__(self):
        self.stations: Dict[str, str] = {}
        self.load()
    
    def load(self):
        """加载电台列表"""
        try:
            if RADIO_FILE.exists():
                with open(RADIO_FILE, 'r', encoding='utf-8') as f:
                    self.stations = json.load(f)
            else:
                # 首次使用，加载默认电台
                self.stations = self.DEFAULT_STATIONS.copy()
                self.save()
        except Exception:
            self.stations = self.DEFAULT_STATIONS.copy()
    
    def save(self):
        """保存电台列表"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(RADIO_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.stations, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def add_station(self, name: str, url: str):
        """添加电台"""
        self.stations[name] = url
        self.save()
        print(f"电台已添加: {name}")
    
    def remove_station(self, name: str):
        """删除电台"""
        if name in self.stations:
            del self.stations[name]
            self.save()
            print(f"电台已删除: {name}")
            return True
        print(f"电台不存在: {name}")
        return False
    
    def get_station_url(self, name: str) -> Optional[str]:
        """获取电台URL"""
        return self.stations.get(name)
    
    def list_stations(self):
        """显示电台列表"""
        if not self.stations:
            print("\n电台列表为空")
            print("使用 'mp --radio-add <名称> <URL>' 添加电台")
            return
        
        print(f"\n{'='*60}")
        print(f"  网络电台 ({len(self.stations)} 个)")
        print(f"{'='*60}")
        
        for i, (name, url) in enumerate(self.stations.items()):
            print(f"  {i+1:3d}. {name}")
            print(f"       {url}")
        
        print(f"{'='*60}\n")
        print("使用 'mp --radio <名称>' 播放电台")




class QueueManager:
    """队列管理 - 管理播放队列，支持添加、删除、重新排序"""

    def __init__(self):
        self.queue: List[Path] = []
        self.history: List[int] = []  # 已播放的索引
        self.current_position = -1

    def add(self, file_path: Path):
        """添加文件到队列"""
        if file_path.exists() and file_path not in self.queue:
            self.queue.append(file_path)
            return True
        return False

    def add_multiple(self, files: List[Path]):
        """批量添加文件"""
        count = 0
        for f in files:
            if self.add(f):
                count += 1
        return count

    def remove(self, index: int) -> bool:
        """移除指定位置的文件"""
        if 0 <= index < len(self.queue):
            self.queue.pop(index)
            # 调整当前位置
            if index < self.current_position:
                self.current_position -= 1
            return True
        return False

    def move(self, from_idx: int, to_idx: int) -> bool:
        """移动文件位置"""
        if 0 <= from_idx < len(self.queue) and 0 <= to_idx < len(self.queue):
            item = self.queue.pop(from_idx)
            self.queue.insert(to_idx, item)
            return True
        return False

    def clear(self):
        """清空队列"""
        self.queue.clear()
        self.history.clear()
        self.current_position = -1

    def get_next(self) -> Optional[Path]:
        """获取下一首"""
        self.current_position += 1
        if self.current_position < len(self.queue):
            return self.queue[self.current_position]
        return None

    def get_previous(self) -> Optional[Path]:
        """获取上一首"""
        if self.current_position > 0:
            self.current_position -= 1
            return self.queue[self.current_position]
        return None

    def get_current(self) -> Optional[Path]:
        """获取当前文件"""
        if 0 <= self.current_position < len(self.queue):
            return self.queue[self.current_position]
        return None

    def display(self):
        """显示队列"""
        if not self.queue:
            print("\n队列为空")
            return

        print(f"\n{'='*60}")
        print(f"  播放队列 ({len(self.queue)} 首)")
        print(f"{'='*60}")

        for i, file in enumerate(self.queue):
            marker = "▶ " if i == self.current_position else "  "
            print(f"{marker}{i+1:3d}. {file.name}")

        print(f"{'='*60}\n")




class StatisticsManager:
    """统计管理器 - 详细的播放统计和分析"""

    STATS_FILE = CONFIG_DIR / 'statistics.json'

    def __init__(self):
        self.stats = {
            'total_play_time': 0,  # 总播放时长（秒）
            'total_songs': 0,  # 总播放歌曲数
            'songs_by_format': {},  # 按格式统计
            'most_played': {},  # 最常播放的歌曲
            'daily_stats': {},  # 每日统计
            'weekly_stats': {},  # 每周统计
        }
        self.load()

    def load(self):
        """加载统计数据"""
        try:
            if self.STATS_FILE.exists():
                with open(self.STATS_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.stats.update(saved)
        except Exception:
            pass

    def save(self):
        """保存统计数据"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(self.STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def record_play(self, file_path: Path, duration: float):
        """记录播放"""
        if duration < 5:  # 忽略少于5秒的播放
            return

        # 更新总播放时长
        self.stats['total_play_time'] += duration
        self.stats['total_songs'] += 1

        # 按格式统计
        fmt = file_path.suffix.lower()
        self.stats['songs_by_format'][fmt] = self.stats['songs_by_format'].get(fmt, 0) + 1

        # 最常播放的歌曲
        key = str(file_path.resolve())
        self.stats['most_played'][key] = self.stats['most_played'].get(key, 0) + 1

        # 每日统计
        today = time.strftime('%Y-%m-%d')
        if today not in self.stats['daily_stats']:
            self.stats['daily_stats'][today] = {'songs': 0, 'time': 0}
        self.stats['daily_stats'][today]['songs'] += 1
        self.stats['daily_stats'][today]['time'] += duration

        # 每周统计
        week = time.strftime('%Y-W%W')
        if week not in self.stats['weekly_stats']:
            self.stats['weekly_stats'][week] = {'songs': 0, 'time': 0}
        self.stats['weekly_stats'][week]['songs'] += 1
        self.stats['weekly_stats'][week]['time'] += duration

        self.save()

    def display(self):
        """显示统计信息"""
        print(f"\n{'='*60}")
        print(f"  播放统计")
        print(f"{'='*60}")

        # 总体统计
        total_time = self.stats['total_play_time']
        hours = int(total_time // 3600)
        minutes = int((total_time % 3600) // 60)
        print(f"\n  总播放时长: {hours}小时 {minutes}分钟")
        print(f"  总播放歌曲: {self.stats['total_songs']} 首")

        # 格式统计
        if self.stats['songs_by_format']:
            print(f"\n  格式分布:")
            sorted_formats = sorted(self.stats['songs_by_format'].items(), key=lambda x: x[1], reverse=True)
            for fmt, count in sorted_formats[:5]:
                print(f"    {fmt.upper():6s}: {count:3d} 首")

        # 最常播放
        if self.stats['most_played']:
            print(f"\n  最常播放 (Top 5):")
            sorted_songs = sorted(self.stats['most_played'].items(), key=lambda x: x[1], reverse=True)
            for i, (path, count) in enumerate(sorted_songs[:5], 1):
                name = Path(path).name
                print(f"    {i}. {name} ({count}次)")

        # 最近7天
        print(f"\n  最近7天:")
        for i in range(6, -1, -1):
            date = (time.time() - i * 86400)
            date_str = time.strftime('%Y-%m-%d', time.localtime(date))
            if date_str in self.stats['daily_stats']:
                day_stats = self.stats['daily_stats'][date_str]
                songs = day_stats['songs']
                play_time = day_stats['time']
                minutes = int(play_time // 60)
                print(f"    {date_str}: {songs:2d}首, {minutes:2d}分钟")
            else:
                print(f"    {date_str}:  0首,  0分钟")

        print(f"{'='*60}\n")

    def clear(self):
        """清空统计"""
        self.stats = {
            'total_play_time': 0,
            'total_songs': 0,
            'songs_by_format': {},
            'most_played': {},
            'daily_stats': {},
            'weekly_stats': {},
        }
        self.save()
        print("统计数据已清空")


