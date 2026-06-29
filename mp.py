#!/usr/bin/env python3
"""
Terminal Media Player - mp
轻量级终端媒体播放器
支持音频和视频播放，包含播放列表、音量控制、循环播放等功能
"""

import sys
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
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
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

__version__ = "2.8.0"

# 配置文件路径
CONFIG_DIR = Path.home() / '.config' / 'mp'
CONFIG_FILE = CONFIG_DIR / 'config.json'
PLAYLIST_DIR = CONFIG_DIR / 'playlists'
FAVORITES_FILE = CONFIG_DIR / 'favorites.json'
HISTORY_FILE = CONFIG_DIR / 'history.json'
RADIO_FILE = CONFIG_DIR / 'radio.json'


def get_pip_install_args():
    """根据系统返回合适的pip安装参数"""
    system = platform.system()
    if system == "Linux":
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        if not in_venv:
            return ['--break-system-packages']
    return []


def install_system_dependencies():
    """安装系统级依赖（Linux需要）"""
    system = platform.system()
    if system == "Linux":
        try:
            if subprocess.run(['which', 'apt'], capture_output=True).returncode == 0:
                subprocess.run(['sudo', 'apt', 'install', '-y', 'libsdl2-2.0-0', 'libsdl2-mixer-2.0-0'], check=True)
        except Exception as e:
            print(f"系统依赖安装警告: {e}")


def check_and_install_dependencies():
    """检查并安装Python依赖"""
    if sys.version_info < (3, 7):
        print("错误: 需要Python 3.7或更高版本")
        sys.exit(1)
    
    required_packages = ['pygame']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"正在安装缺失的依赖: {', '.join(missing)}")
        install_system_dependencies()
        
        pip_args = get_pip_install_args()
        cmd = [sys.executable, '-m', 'pip', 'install'] + pip_args + missing
        
        try:
            subprocess.check_call(cmd)
            print("依赖安装完成！")
        except subprocess.CalledProcessError:
            print("依赖安装失败，请手动安装：")
            print(f"  pip install {' '.join(pip_args)} {' '.join(missing)}")
            sys.exit(1)
    
    check_ffmpeg()


def check_ffmpeg():
    """检查并安装ffmpeg"""
    import shutil
    if not shutil.which('ffmpeg'):
        system = platform.system()
        print("未检测到ffmpeg，正在尝试自动安装...")
        
        try:
            if system == "Darwin":
                if shutil.which('brew'):
                    subprocess.run(['brew', 'install', 'ffmpeg'], check=True)
                else:
                    raise Exception("Homebrew未安装")
            elif system == "Linux":
                if shutil.which('apt'):
                    subprocess.run(['sudo', 'apt', 'update'], check=True)
                    subprocess.run(['sudo', 'apt', 'install', '-y', 'ffmpeg'], check=True)
                elif shutil.which('pacman'):
                    subprocess.run(['sudo', 'pacman', '-S', '--noconfirm', 'ffmpeg'], check=True)
                elif shutil.which('dnf'):
                    subprocess.run(['sudo', 'dnf', 'install', '-y', 'ffmpeg'], check=True)
                else:
                    raise Exception("未找到支持的包管理器")
            print("ffmpeg安装完成！")
        except Exception as e:
            print(f"ffmpeg安装失败: {e}")
            print("\n请手动安装ffmpeg")
            if system == "Linux":
                print("  sudo apt install ffmpeg  # Debian/Ubuntu")
                print("  sudo pacman -S ffmpeg    # Arch")
            sys.exit(1)


class Config:
    """配置管理类"""
    
    DEFAULT_CONFIG = {
        'volume': 100,  # 音量 0-100
        'playback_speed': 1.0,  # 播放速度
        'loop_mode': 'none',  # none, single, all
        'shuffle': False,  # 随机播放
        'last_directory': str(Path.home()),  # 上次打开的目录
    }
    
    def __init__(self):
        self.config = self.DEFAULT_CONFIG.copy()
        self.load()
    
    def load(self):
        """加载配置"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    self.config.update(saved)
        except Exception:
            pass
    
    def save(self):
        """保存配置"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        self.save()


class MediaInfo:
    """媒体信息类"""
    
    @staticmethod
    def get_info(file_path: Path) -> Dict[str, Any]:
        """获取媒体文件的详细信息"""
        info = {
            'path': str(file_path),
            'name': file_path.name,
            'size': 0,
            'duration': 0,
            'format': file_path.suffix.lower(),
            'bit_rate': 0,
            'sample_rate': 0,
            'channels': 0,
            'width': 0,
            'height': 0,
            'fps': 0,
            'codec': '',
            'title': '',
            'artist': '',
            'album': '',
        }
        
        try:
            # 获取文件大小
            info['size'] = file_path.stat().st_size
            
            # 使用 ffprobe 获取详细信息
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format', '-show_streams',
                str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # 格式信息
                if 'format' in data:
                    fmt = data['format']
                    info['duration'] = float(fmt.get('duration', 0))
                    info['bit_rate'] = int(fmt.get('bit_rate', 0))
                    
                    # 标签信息
                    tags = fmt.get('tags', {})
                    info['title'] = tags.get('title', '')
                    info['artist'] = tags.get('artist', tags.get('ARTIST', ''))
                    info['album'] = tags.get('album', tags.get('ALBUM', ''))
                
                # 流信息
                for stream in data.get('streams', []):
                    codec_type = stream.get('codec_type', '')
                    
                    if codec_type == 'audio' and info['channels'] == 0:
                        info['codec'] = stream.get('codec_name', '')
                        info['sample_rate'] = int(stream.get('sample_rate', 0))
                        info['channels'] = stream.get('channels', 0)
                    
                    elif codec_type == 'video' and info['width'] == 0:
                        info['width'] = stream.get('width', 0)
                        info['height'] = stream.get('height', 0)
                        
                        # 获取帧率
                        fps_str = stream.get('r_frame_rate', '0/1')
                        if '/' in fps_str:
                            num, den = fps_str.split('/')
                            if int(den) > 0:
                                info['fps'] = float(num) / float(den)
        
        except Exception:
            pass
        
        return info
    
    @staticmethod
    def format_size(size_bytes: int) -> str:
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    @staticmethod
    def format_duration(seconds: float) -> str:
        """格式化时长"""
        if seconds <= 0:
            return "00:00"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    
    @staticmethod
    def display_info(info: Dict[str, Any]):
        """显示媒体信息"""
        print(f"\n{'='*60}")
        print(f"  媒体信息")
        print(f"{'='*60}")
        print(f"  文件名: {info['name']}")
        print(f"  格式: {info['format'].upper()}")
        print(f"  大小: {MediaInfo.format_size(info['size'])}")
        print(f"  时长: {MediaInfo.format_duration(info['duration'])}")
        
        if info['bit_rate'] > 0:
            print(f"  比特率: {info['bit_rate'] // 1000} kbps")
        
        if info['artist']:
            print(f"  艺术家: {info['artist']}")
        if info['album']:
            print(f"  专辑: {info['album']}")
        if info['title']:
            print(f"  标题: {info['title']}")
        
        # 音频信息
        if info['channels'] > 0:
            print(f"\n  --- 音频 ---")
            print(f"  编码: {info['codec'].upper()}")
            print(f"  采样率: {info['sample_rate']} Hz")
            print(f"  声道: {info['channels']}")
        
        # 视频信息
        if info['width'] > 0:
            print(f"\n  --- 视频 ---")
            print(f"  分辨率: {info['width']}x{info['height']}")
            if info['fps'] > 0:
                print(f"  帧率: {info['fps']:.2f} fps")
        
        print(f"{'='*60}\n")


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


class AudioConverter:
    """音频转换器 - 在不同格式间转换音频文件"""

    SUPPORTED_FORMATS = {
        '.mp3': ['-codec:a', 'libmp3lame', '-b:a', '192k'],
        '.wav': ['-codec:a', 'pcm_s16le'],
        '.ogg': ['-codec:a', 'libvorbis', '-b:a', '192k'],
        '.m4a': ['-codec:a', 'aac', '-b:a', '192k'],
        '.flac': ['-codec:a', 'flac'],
        '.aac': ['-codec:a', 'aac', '-b:a', '192k'],
        '.opus': ['-codec:a', 'libopus', '-b:a', '128k'],
    }

    @staticmethod
    def convert(input_path: Path, output_format: str, output_dir: Optional[Path] = None) -> bool:
        """转换音频格式"""
        if not input_path.exists():
            print(f"错误: 文件不存在 {input_path}")
            return False

        output_format = output_format.lower()
        if not output_format.startswith('.'):
            output_format = '.' + output_format

        if output_format not in AudioConverter.SUPPORTED_FORMATS:
            print(f"不支持的格式: {output_format}")
            print(f"支持的格式: {', '.join(AudioConverter.SUPPORTED_FORMATS.keys())}")
            return False

        # 确定输出路径
        if output_dir:
            output_path = output_dir / (input_path.stem + output_format)
        else:
            output_path = input_path.with_suffix(output_format)

        print(f"转换中: {input_path.name} → {output_path.name}")

        # 构建 ffmpeg 命令
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-y',  # 覆盖输出文件
            '-loglevel', 'quiet',
        ]

        # 添加格式特定参数
        cmd.extend(AudioConverter.SUPPORTED_FORMATS[output_format])
        cmd.append(str(output_path))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✓ 转换成功: {output_path.name}")
                return True
            else:
                print(f"✗ 转换失败: {result.stderr}")
                return False
        except Exception as e:
            print(f"✗ 转换错误: {e}")
            return False

    @staticmethod
    def batch_convert(input_files: List[Path], output_format: str, output_dir: Optional[Path] = None) -> int:
        """批量转换音频格式"""
        success_count = 0
        total = len(input_files)

        print(f"\n批量转换: {total} 个文件 → {output_format}")
        print(f"{'='*60}")

        for i, input_path in enumerate(input_files, 1):
            print(f"[{i}/{total}] ", end='')
            if AudioConverter.convert(input_path, output_format, output_dir):
                success_count += 1

        print(f"\n{'='*60}")
        print(f"转换完成: {success_count}/{total} 成功")

        return success_count


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


class Equalizer:
    """均衡器 - 多频段音频均衡控制"""

    # 预设均衡器配置
    PRESETS = {
        'flat': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        'rock': [5, 4, 3, 1, -1, -1, 0, 2, 3, 4],
        'pop': [-1, 0, 2, 4, 4, 3, 1, 0, -1, -2],
        'jazz': [3, 2, 1, 2, -1, -1, 0, 1, 2, 3],
        'classical': [4, 3, 2, 1, -1, -1, 0, 2, 3, 4],
        'bass': [6, 5, 4, 2, 0, -1, -2, -2, -1, 0],
        'treble': [-2, -1, 0, 1, 2, 3, 4, 5, 6, 6],
        'vocal': [-2, -1, 0, 2, 4, 4, 3, 1, 0, -1],
        'electronic': [4, 3, 1, 0, -2, -2, 0, 2, 3, 4],
    }

    # 频段频率
    FREQUENCIES = ['60Hz', '170Hz', '310Hz', '600Hz', '1kHz', '3kHz', '6kHz', '12kHz', '14kHz', '16kHz']

    def __init__(self):
        self.bands = [0] * 10  # 10频段均衡器
        self.enabled = False
        self.current_preset = 'flat'

    def set_preset(self, preset_name: str) -> bool:
        """设置预设"""
        if preset_name in self.PRESETS:
            self.bands = self.PRESETS[preset_name].copy()
            self.current_preset = preset_name
            return True
        return False

    def set_band(self, band_index: int, value: int):
        """设置单个频段"""
        if 0 <= band_index < len(self.bands):
            self.bands[band_index] = max(-12, min(12, value))

    def get_filter_string(self) -> str:
        """获取 ffmpeg 均衡器滤镜字符串"""
        if not self.enabled:
            return ''

        filters = []
        for i, gain in enumerate(self.bands):
            if gain != 0:
                freq = self._get_frequency(i)
                filters.append(f"equalizer=f={freq}:width_type=o:width=1.5:g={gain}")

        return ','.join(filters) if filters else ''

    def _get_frequency(self, band_index: int) -> int:
        """获取频段中心频率"""
        freq_map = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]
        if 0 <= band_index < len(freq_map):
            return freq_map[band_index]
        return 1000

    def display(self):
        """显示均衡器状态"""
        print(f"\n{'='*60}")
        print(f"  均衡器 - {self.current_preset.upper()}")
        print(f"{'='*60}")

        # 显示频段
        for i, (freq, gain) in enumerate(zip(self.FREQUENCIES, self.bands)):
            bar_length = 20
            center = bar_length // 2
            bar = [' '] * bar_length

            if gain > 0:
                for j in range(center, center + gain):
                    if j < bar_length:
                        bar[j] = '█'
            elif gain < 0:
                for j in range(center + gain, center):
                    if j >= 0:
                        bar[j] = '█'

            bar[center] = '┼'
            bar_str = ''.join(bar)
            print(f"  {freq:6s} |{bar_str}| {gain:+2d}dB")

        print(f"{'='*60}\n")

    def toggle(self):
        """切换均衡器开关"""
        self.enabled = not self.enabled
        return self.enabled

    def list_presets(self):
        """列出所有预设"""
        print(f"\n{'='*60}")
        print(f"  均衡器预设")
        print(f"{'='*60}")
        for name in self.PRESETS.keys():
            marker = "▶ " if name == self.current_preset else "  "
            print(f"{marker}{name}")
        print(f"{'='*60}\n")


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


class NoiseGenerator:
    """噪声生成器 - 生成白噪声/粉红噪声/棕噪声用于助眠/专注"""

    NOISE_TYPES = {
        'white': '白噪声',
        'pink': '粉红噪声',
        'brown': '棕噪声',
        'rain': '雨声',
        'ocean': '海浪',
    }

    def __init__(self):
        self.noise_type = 'white'
        self.volume = 30
        self.process = None
        self.is_playing = False

    def _generate_noise_cmd(self) -> List[str]:
        """生成 ffmpeg 噪声命令"""
        if self.noise_type == 'white':
            return [
                'ffmpeg', '-f', 'lavfi', '-i',
                f'anoisesrc=color=white:amplitude=0.3',
                '-f', 'wav', '-'
            ]
        elif self.noise_type == 'pink':
            return [
                'ffmpeg', '-f', 'lavfi', '-i',
                f'anoisesrc=color=pink:amplitude=0.3',
                '-f', 'wav', '-'
            ]
        elif self.noise_type == 'brown':
            return [
                'ffmpeg', '-f', 'lavfi', '-i',
                f'anoisesrc=color=brown:amplitude=0.3',
                '-f', 'wav', '-'
            ]
        elif self.noise_type == 'rain':
            # 模拟雨声：白噪声 + 低通滤波
            return [
                'ffmpeg', '-f', 'lavfi', '-i',
                f'anoisesrc=color=white:amplitude=0.5',
                '-af', 'lowpass=f=2000,highpass=f=200,tremolo=f=8:d=0.7',
                '-f', 'wav', '-'
            ]
        elif self.noise_type == 'ocean':
            # 模拟海浪：棕噪声 + 低频调制
            return [
                'ffmpeg', '-f', 'lavfi', '-i',
                f'anoisesrc=color=brown:amplitude=0.4',
                '-af', 'lowpass=f=500,tremolo=f=0.15:d=0.8',
                '-f', 'wav', '-'
            ]
        return ['ffmpeg', '-f', 'lavfi', '-i', 'anoisesrc=color=white', '-f', 'wav', '-']

    def play(self):
        """开始播放噪声"""
        if self.is_playing:
            self.stop()

        cmd = self._generate_noise_cmd()
        cmd.extend([
            '-ar', '44100', '-ac', '2',
            '-f', 's16le', '-'
        ])

        # 使用 ffplay 播放
        play_cmd = [
            'ffplay',
            '-nodisp', '-autoexit',
            '-loglevel', 'quiet', '-hide_banner',
            '-volume', str(self.volume),
            '-f', 's16le', '-ar', '44100', '-ac', '2',
            'pipe:0'
        ]

        noise_proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        self.process = subprocess.Popen(
            play_cmd,
            stdin=noise_proc.stdout,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        noise_proc.stdout.close()
        self._noise_proc = noise_proc
        self.is_playing = True

    def stop(self):
        """停止播放"""
        self.is_playing = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except Exception:
                self.process.kill()
        if hasattr(self, '_noise_proc') and self._noise_proc and self._noise_proc.poll() is None:
            self._noise_proc.terminate()
            try:
                self._noise_proc.wait(timeout=1)
            except Exception:
                self._noise_proc.kill()

    def set_type(self, noise_type: str):
        """设置噪声类型"""
        if noise_type in self.NOISE_TYPES:
            self.noise_type = noise_type
            if self.is_playing:
                self.play()  # Restart with new type

    def set_volume(self, vol: int):
        """设置音量"""
        self.volume = max(0, min(100, vol))

    def run_interactive(self):
        """交互式噪声播放器"""
        self.play()

        print(f"\n🔊 噪声生成器 - {self.NOISE_TYPES[self.noise_type]}")
        print(f"音量: {self.volume}%")
        print("\n控制:")
        print("  1-5  切换噪声类型")
        print("  ↑/↓  调整音量")
        print("  q    退出\n")

        if platform.system() != "Windows":
            import select
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)

            try:
                tty.setcbreak(fd)

                while self.is_playing:
                    # 显示状态
                    types_str = " ".join(
                        f"\033[7m{k}: {v}\033[0m" if k == self.noise_type else f"{k}: {v}"
                        for k, v in self.NOISE_TYPES.items()
                    )
                    print(f"\r  类型: {types_str} | 音量: {self.volume}%    ", end='', flush=True)

                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        ch = sys.stdin.read(1)

                        if ch in ('q', 'Q', '\x03'):
                            break
                        elif ch == '1':
                            self.set_type('white')
                        elif ch == '2':
                            self.set_type('pink')
                        elif ch == '3':
                            self.set_type('brown')
                        elif ch == '4':
                            self.set_type('rain')
                        elif ch == '5':
                            self.set_type('ocean')
                        elif ch == '\x1b':
                            ch2 = sys.stdin.read(1)
                            if ch2 == '[':
                                ch3 = sys.stdin.read(1)
                                if ch3 == 'A':
                                    self.set_volume(self.volume + 5)
                                elif ch3 == 'B':
                                    self.set_volume(self.volume - 5)
                    time.sleep(0.1)

            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        self.stop()
        print("\n噪声生成器已停止")


class MetadataEditor:
    """元数据编辑器 - 编辑媒体文件的标签信息"""

    SUPPORTED_TAGS = {
        '.mp3': {'title': 'title', 'artist': 'artist', 'album': 'album', 'track': 'track', 'genre': 'genre', 'date': 'date'},
        '.m4a': {'title': 'title', 'artist': 'artist', 'album': 'album', 'track': 'track', 'genre': 'genre', 'date': 'date'},
        '.flac': {'title': 'TITLE', 'artist': 'ARTIST', 'album': 'ALBUM', 'track': 'TRACKNUMBER', 'genre': 'GENRE', 'date': 'DATE'},
        '.ogg': {'title': 'TITLE', 'artist': 'ARTIST', 'album': 'ALBUM', 'track': 'TRACKNUMBER', 'genre': 'GENRE', 'date': 'DATE'},
        '.opus': {'title': 'TITLE', 'artist': 'ARTIST', 'album': 'ALBUM', 'track': 'TRACKNUMBER', 'genre': 'GENRE', 'date': 'DATE'},
        '.wav': {'title': 'INAM', 'artist': 'IART', 'album': 'IPRD', 'track': 'ITRK', 'genre': 'IGNR', 'date': 'ICRD'},
    }

    @staticmethod
    def get_tags(file_path: Path) -> Dict[str, str]:
        """获取文件的标签信息"""
        tags = {}
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                fmt_tags = data.get('format', {}).get('tags', {})
                for key, value in fmt_tags.items():
                    tags[key.upper()] = value
        except Exception:
            pass
        return tags

    @staticmethod
    def set_tag(file_path: Path, tag: str, value: str) -> bool:
        """设置单个标签"""
        ext = file_path.suffix.lower()
        if ext not in MetadataEditor.SUPPORTED_TAGS:
            print(f"不支持的格式: {ext}")
            return False

        # 创建临时输出文件
        temp_path = file_path.with_suffix(file_path.suffix + '.tmp')

        cmd = [
            'ffmpeg', '-y', '-i', str(file_path),
            '-codec', 'copy',
            '-metadata', f'{tag}={value}',
            str(temp_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                # 替换原文件
                temp_path.replace(file_path)
                return True
            else:
                if temp_path.exists():
                    temp_path.unlink()
                print(f"设置标签失败: {result.stderr}")
                return False
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            print(f"错误: {e}")
            return False

    @staticmethod
    def display_tags(file_path: Path):
        """显示文件的标签信息"""
        tags = MetadataEditor.get_tags(file_path)

        print(f"\n{'='*60}")
        print(f"  元数据: {file_path.name}")
        print(f"{'='*60}")

        if not tags:
            print("  (无标签信息)")
        else:
            for key, value in sorted(tags.items()):
                # 跳过一些技术性标签
                if key in ('ENCODER', 'MAJOR_BRAND', 'MINOR_VERSION', 'COMPATIBLE_BRANDS'):
                    continue
                print(f"  {key:20s}: {value}")

        print(f"{'='*60}\n")

    @staticmethod
    def run_interactive(file_path: Path):
        """交互式编辑标签"""
        ext = file_path.suffix.lower()
        if ext not in MetadataEditor.SUPPORTED_TAGS:
            print(f"不支持编辑的格式: {ext}")
            print(f"支持的格式: {', '.join(MetadataEditor.SUPPORTED_TAGS.keys())}")
            return

        tag_map = MetadataEditor.SUPPORTED_TAGS[ext]
        current_tags = MetadataEditor.get_tags(file_path)

        print(f"\n编辑元数据: {file_path.name}")
        print(f"{'='*60}")

        tag_names = {
            'title': '标题', 'artist': '艺术家', 'album': '专辑',
            'track': '曲目号', 'genre': '流派', 'date': '日期/年份'
        }

        for i, (tag_key, _) in enumerate(tag_map.items(), 1):
            display_name = tag_names.get(tag_key, tag_key)
            current_value = ''
            # 尝试从现有标签中查找
            for k, v in current_tags.items():
                if k.lower() == tag_key.lower():
                    current_value = v
                    break
            print(f"  {i}. {display_name:8s}: {current_value or '(空)'}")

        print(f"\n输入编号修改 (1-6), 0 取消, q 退出:")

        try:
            choice = input("> ").strip()
            if choice in ('0', 'q', 'Q'):
                return

            idx = int(choice) - 1
            tag_keys = list(tag_map.keys())
            if 0 <= idx < len(tag_keys):
                tag_key = tag_keys[idx]
                display_name = tag_names.get(tag_key, tag_key)
                new_value = input(f"输入新的{display_name}: ").strip()
                if new_value:
                    ffmpeg_tag = tag_map[tag_key]
                    if MetadataEditor.set_tag(file_path, ffmpeg_tag, new_value):
                        print(f"✓ {display_name} 已更新为: {new_value}")
                    else:
                        print("✗ 更新失败")
        except (ValueError, EOFError):
            pass


class CrossfadeManager:
    """交叉淡入淡出管理器 - 在播放列表曲目间平滑过渡"""

    def __init__(self):
        self.enabled = False
        self.duration = 3.0  # 交叉淡入淡出时长（秒）

    def toggle(self) -> bool:
        """切换启用状态"""
        self.enabled = not self.enabled
        return self.enabled

    def set_duration(self, seconds: float):
        """设置淡入淡出时长"""
        self.duration = max(0.5, min(15.0, seconds))

    def get_status(self) -> str:
        """获取状态字符串"""
        if self.enabled:
            return f"🔀 交叉淡入 {self.duration:.1f}s"
        return ""


class PitchControl:
    """音调控制 - 独立于播放速度调整音调"""

    def __init__(self):
        self.semitones = 0.0  # 半音偏移 (-12 to +12)
        self.enabled = False

    def set_semitones(self, value: float):
        """设置半音偏移"""
        self.semitones = max(-12.0, min(12.0, value))
        self.enabled = self.semitones != 0.0

    def adjust(self, delta: float):
        """调整半音"""
        self.set_semitones(self.semitones + delta)

    def get_filter_string(self) -> str:
        """获取 ffmpeg 音调滤镜字符串"""
        if not self.enabled or self.semitones == 0.0:
            return ''
        # 使用 asetrate + aresample 来改变音调
        # 半音到频率比: ratio = 2^(semitones/12)
        ratio = 2 ** (self.semitones / 12.0)
        sample_rate = int(44100 * ratio)
        return f'asetrate=44100*{ratio:.6f},aresample=44100'

    def reset(self):
        """重置音调"""
        self.semitones = 0.0
        self.enabled = False

    def get_status(self) -> str:
        """获取状态字符串"""
        if self.enabled:
            sign = '+' if self.semitones > 0 else ''
            return f"🎵 音调: {sign}{self.semitones:.1f}半音"
        return ""


class LyricsDisplay:
    """歌词显示类"""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.lyrics: List[tuple] = []  # (时间戳, 歌词内容)
        self.current_index = -1
        self.offset = 0.0  # 歌词时间偏移（秒）
        self.enabled = True
        self.load_lyrics()
    
    def load_lyrics(self):
        """加载歌词文件"""
        # 尝试查找同名 .lrc 文件
        lrc_path = self.file_path.with_suffix('.lrc')
        
        # 也尝试在同级目录查找
        if not lrc_path.exists():
            for ext in ['.lrc', '.txt']:
                potential = self.file_path.parent / (self.file_path.stem + ext)
                if potential.exists():
                    lrc_path = potential
                    break
        
        if not lrc_path.exists():
            self.lyrics = []
            return
        
        try:
            with open(lrc_path, 'r', encoding='utf-8') as f:
                self._parse_lrc(f.read())
        except Exception:
            self.lyrics = []
    
    def _parse_lrc(self, content: str):
        """解析LRC格式歌词"""
        self.lyrics = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # 解析时间标签 [mm:ss.xx] 或 [mm:ss:xx]
            import re
            time_tags = re.findall(r'\[(\d{2}):(\d{2})([.:])(\d{2})\](.*)', line)
            
            if time_tags:
                for tag in time_tags:
                    minutes = int(tag[0])
                    seconds = int(tag[1])
                    ms = int(tag[3]) / 100.0 if tag[2] == '.' else int(tag[3])
                    text = tag[4].strip()
                    
                    if text:
                        timestamp = minutes * 60 + seconds + ms
                        self.lyrics.append((timestamp, text))
            
            # 解析偏移标签 [offset:ms]
            offset_match = re.search(r'\[offset:([+-]?\d+)\]', line)
            if offset_match:
                self.offset = int(offset_match.group(1)) / 1000.0
        
        # 按时间排序
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


class AudioVisualizer:
    """音频可视化器 - 在终端显示音频频谱"""
    
    # ASCII 字符从密集到稀疏
    BLOCK_CHARS = ' ▏▎▍▌▋▊▉█'
    
    def __init__(self, width: int = 60, height: int = 10):
        self.width = width
        self.height = height
        self.fft_data: List[float] = [0.0] * width
        self.smoothing: List[float] = [0.0] * width
        self.smooth_factor = 0.3
    
    def update(self, samples: bytes):
        """更新频谱数据（从PCM样本计算）"""
        try:
            import struct
            
            if len(samples) < 256:
                return
            
            # 简化频谱计算 - 将字节转换为频谱幅度
            n = len(samples)
            spectrum = [0.0] * self.width
            
            # 将样本分成多个频段
            step = n // (self.width * 4)
            if step < 1:
                step = 1
            
            for i in range(self.width):
                start = i * step * 4
                end = min(start + step * 4, n)
                if start < n:
                    # 计算该频段的均方根值
                    total = 0
                    count = 0
                    for j in range(start, end, 2):
                        if j + 1 < n:
                            # 16位样本
                            sample = struct.unpack('<h', samples[j:j+2])[0] if j + 2 <= len(samples) else 0
                            total += sample * sample
                            count += 1
                    
                    if count > 0:
                        rms = (total / count) ** 0.5
                        # 归一化到0-1
                        normalized = min(1.0, rms / 8000)
                        spectrum[i] = normalized
            
            # 平滑过渡
            for i in range(self.width):
                self.smoothing[i] = self.smoothing[i] * (1 - self.smooth_factor) + spectrum[i] * self.smooth_factor
            
            self.fft_data = self.smoothing.copy()
            
        except Exception:
            pass
    
    def render(self) -> str:
        """渲染可视化条形图"""
        lines = []
        
        for y in range(self.height - 1, -1, -1):
            line = ''
            threshold = y / self.height
            
            for i in range(self.width):
                value = self.fft_data[i] if i < len(self.fft_data) else 0
                
                if value >= threshold:
                    # 根据强度选择字符
                    intensity = int((value - threshold) / (1 - threshold + 0.01) * (len(self.BLOCK_CHARS) - 1))
                    intensity = max(0, min(len(self.BLOCK_CHARS) - 1, intensity))
                    line += self.BLOCK_CHARS[intensity]
                else:
                    line += ' '
            
            lines.append(line)
        
        return '\n'.join(lines)


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


class AudioPlayer:
    """音频播放器类"""
    
    def __init__(self, file_path: Path, config: Config):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            print(f"错误: 文件 '{file_path}' 不存在")
            sys.exit(1)
        
        self.config = config
        self.bookmark_manager = BookmarkManager()
        self.favorites_manager = FavoritesManager()
        self.history_manager = HistoryManager()
        self.sleep_timer = SleepTimer()
        self.ab_loop = ABLoop()
        self.queue_manager = QueueManager()
        self.statistics_manager = StatisticsManager()
        self.equalizer = Equalizer()
        self.pitch_control = PitchControl()
        self.crossfade = CrossfadeManager()
        
        # 导入 pygame（在依赖检查之后已经导入）
        import pygame
        
        # 抑制pygame的欢迎信息
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        sys.stdout = original_stdout
        
        self.is_playing = False
        self.is_paused = False
        self.current_position = 0
        self.total_duration = 0.0
        self.process = None
        
        # 新增功能
        self.volume = config.get('volume', 100)
        self.playback_speed = config.get('playback_speed', 1.0)
        self.loop_mode = config.get('loop_mode', 'none')  # none, single, all
        
        # 歌词和可视化器
        self.lyrics = LyricsDisplay(self.file_path)
        self.visualizer_enabled = False
        self.visualizer_width = 60
        self.visualizer = AudioVisualizer(width=self.visualizer_width, height=8)
        
        self.load_audio()
    
    def get_audio_duration(self):
        """使用ffprobe获取音频时长（秒）"""
        try:
            cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', str(self.file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except:
            pass
        return 0
    
    def load_audio(self):
        """加载音频文件"""
        print(f"正在加载: {self.file_path.name}")
        
        duration_sec = self.get_audio_duration()
        if duration_sec == 0:
            print("警告: 无法获取音频时长")
            self.total_duration = 180000
        else:
            self.total_duration = duration_sec * 1000
        
        print(f"时长: {self.format_time(self.total_duration)}")
    
    def play_from_position(self, position_sec):
        """从指定位置开始播放"""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            time.sleep(0.1)
        
        cmd = [
            'ffplay',
            '-nodisp',
            '-autoexit',
            '-loglevel', 'quiet',
            '-hide_banner',
            '-volume', str(self.volume),
        ]

        # 构建音频滤镜链
        audio_filters = []

        # 播放速度
        if self.playback_speed != 1.0:
            audio_filters.append(f'atempo={self.playback_speed}')

        # 音调控制
        pitch_filter = self.pitch_control.get_filter_string()
        if pitch_filter:
            audio_filters.append(pitch_filter)

        # 均衡器
        eq_filter = self.equalizer.get_filter_string()
        if eq_filter:
            audio_filters.append(eq_filter)

        # 应用滤镜
        if audio_filters:
            cmd.extend(['-af', ','.join(audio_filters)])
        
        if position_sec > 0:
            cmd.extend(['-ss', str(position_sec)])
        
        cmd.append(str(self.file_path))
        
        devnull = open(os.devnull, 'w')
        self.process = subprocess.Popen(
            cmd,
            stdout=devnull,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL
        )
        
        self.current_position = position_sec * 1000
        self.is_playing = True
        self.is_paused = False
        
        self.progress_thread = threading.Thread(target=self.update_progress, daemon=True)
        self.progress_thread.start()
        
        # 如果启用了可视化器，启动频谱捕获线程
        if self.visualizer_enabled:
            self.spectrum_thread = threading.Thread(target=self.capture_spectrum, daemon=True)
            self.spectrum_thread.start()
    
    def capture_spectrum(self):
        """捕获音频频谱数据"""
        try:
            # 使用 ffmpeg 提取原始音频数据用于可视化
            cmd = [
                'ffmpeg', '-i', str(self.file_path),
                '-f', 's16le', '-acodec', 'pcm_s16le',
                '-ar', '22050', '-ac', '1',
                '-ss', str(self.current_position / 1000),
                '-t', '60',  # 每次捕获60秒
                '-'
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            while self.is_playing and not self.is_paused:
                data = process.stdout.read(1024 * 10)
                if not data:
                    break
                self.visualizer.update(data)
                time.sleep(0.03)
            
            process.terminate()
        except Exception:
            pass
    
    def update_progress(self):
        """更新播放进度"""
        start_time = time.time()
        start_position = self.current_position
        
        while self.is_playing and not self.is_paused:
            elapsed = int((time.time() - start_time) * 1000 * self.playback_speed)
            self.current_position = min(start_position + elapsed, self.total_duration)
            self.display_progress()
            time.sleep(0.1)
            
            if self.process and self.process.poll() is not None:
                self.is_playing = False
                print()
                break
    
    def display_progress(self):
        """显示播放进度条"""
        bar_length = 50
        percent = self.current_position / self.total_duration if self.total_duration > 0 else 0
        filled = int(bar_length * percent)
        bar = '█' * filled + '─' * (bar_length - filled)
        
        current_time = self.format_time(self.current_position)
        total_time = self.format_time(self.total_duration)
        
        # 显示状态信息
        status_parts = []
        if self.is_paused:
            status_parts.append("⏸ 暂停")
        else:
            status_parts.append("▶ 播放中")
        
        # 音量
        status_parts.append(f"🔊 {self.volume}%")
        
        # 播放速度
        if self.playback_speed != 1.0:
            status_parts.append(f"⚡ {self.playback_speed}x")
        
        # 循环模式
        if self.loop_mode == 'single':
            status_parts.append("🔁 单曲")
        elif self.loop_mode == 'all':
            status_parts.append("🔄 列表")
        
        # AB循环
        ab_status = self.ab_loop.get_status()
        if ab_status:
            status_parts.append(ab_status)
        
        # 收藏状态
        if self.favorites_manager.is_favorite(self.file_path):
            status_parts.append("❤️")
        
        # 定时停止
        timer_str = self.sleep_timer.format_remaining()
        if timer_str:
            status_parts.append(timer_str)
        
        # 可视化器
        if self.visualizer_enabled:
            status_parts.append("📊 可视化")
        
        # 歌词
        if self.lyrics.enabled and self.lyrics.lyrics:
            status_parts.append("📝 歌词")

        # 均衡器
        if self.equalizer.enabled:
            status_parts.append(f"🎛️ {self.equalizer.current_preset.upper()}")

        # 音调控制
        pitch_status = self.pitch_control.get_status()
        if pitch_status:
            status_parts.append(pitch_status)

        # 交叉淡入淡出
        crossfade_status = self.crossfade.get_status()
        if crossfade_status:
            status_parts.append(crossfade_status)

        status = " | ".join(status_parts)
        
        # 获取终端宽度
        try:
            term_width = os.get_terminal_size().columns
        except:
            term_width = 80
        
        print(f"\r{status} |{bar}| {current_time}/{total_time}", end='', flush=True)
        
        # 如果启用可视化器，显示频谱
        if self.visualizer_enabled:
            print()
            viz_lines = self.visualizer.render().split('\n')
            for line in viz_lines[-4:]:  # 只显示最后4行
                print(f"  {line}", end='', flush=True)
                print()  # 换行
        
        # 如果有歌词，显示当前行
        if self.lyrics.enabled and self.lyrics.lyrics:
            current_time_sec = self.current_position / 1000
            current_lyric, _ = self.lyrics.get_lyrics_at_time(current_time_sec)
            if current_lyric:
                padding = max(0, (term_width - len(current_lyric)) // 2)
                print(f"\r{' ' * padding}{current_lyric}", end='', flush=True)
    
    def format_time(self, ms):
        """格式化时间显示"""
        total_seconds = int(ms // 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"
    
    def pause(self):
        """暂停/继续"""
        if self.is_playing:
            if self.is_paused:
                self.play_from_position(self.current_position / 1000)
            else:
                if self.process:
                    self.process.send_signal(signal.SIGSTOP)
                self.is_paused = True
    
    def seek(self, delta_ms):
        """前进/后退"""
        new_pos = max(0, min(self.current_position + delta_ms, self.total_duration))
        new_pos_sec = new_pos / 1000
        
        if not self.is_paused:
            self.play_from_position(new_pos_sec)
        else:
            self.current_position = new_pos
            self.display_progress()
    
    def set_volume(self, delta: int):
        """调整音量"""
        self.volume = max(0, min(100, self.volume + delta))
        self.config.set('volume', self.volume)
        
        # 重启播放以应用新音量
        if self.is_playing and not self.is_paused:
            self.play_from_position(self.current_position / 1000)
        else:
            self.display_progress()
    
    def set_speed(self, speed: float):
        """设置播放速度"""
        self.playback_speed = max(0.5, min(2.0, speed))
        self.config.set('playback_speed', self.playback_speed)
        
        # 重启播放以应用新速度
        if self.is_playing and not self.is_paused:
            self.play_from_position(self.current_position / 1000)
        else:
            self.display_progress()
    
    def toggle_loop(self):
        """切换循环模式"""
        modes = ['none', 'single', 'all']
        current_idx = modes.index(self.loop_mode)
        self.loop_mode = modes[(current_idx + 1) % len(modes)]
        self.config.set('loop_mode', self.loop_mode)
        self.display_progress()
    
    def stop(self):
        """停止播放"""
        # 记录播放统计
        play_duration = self.current_position / 1000  # 转换为秒
        self.statistics_manager.record_play(self.file_path, play_duration)

        self.is_playing = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
            time.sleep(0.1)
            if self.process.poll() is None:
                self.process.kill()
    
    def _set_sleep_timer(self):
        """交互式设置定时停止"""
        print("\n定时停止: 输入分钟数 (1-180), 0 取消")
        try:
            # 临时恢复终端
            import termios
            import tty
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except:
                pass

            user_input = input("分钟数: ").strip()
            try:
                minutes = int(user_input)
                if minutes == 0:
                    self.sleep_timer.cancel()
                    print("定时停止已取消")
                elif 1 <= minutes <= 180:
                    def on_timer_end():
                        self.stop()
                    self.sleep_timer.set(minutes, callback=on_timer_end)
                    print(f"定时停止已设置: {minutes} 分钟后停止")
                else:
                    print("无效输入")
            except ValueError:
                print("无效输入")
        except Exception:
            pass

    def _handle_ab_loop(self):
        """处理AB循环设置"""
        current_sec = self.current_position / 1000
        if self.ab_loop.is_setting_a:
            self.ab_loop.set_point_a(current_sec)
            print(f"\nAB循环 A点: {self.ab_loop._format_time(current_sec)}")
            print("移动到B点后按 [a] 设置B点")
        else:
            if current_sec > self.ab_loop.point_a:
                self.ab_loop.set_point_b(current_sec)
                print(f"\nAB循环 B点: {self.ab_loop._format_time(current_sec)}")
                print(f"AB循环已激活: {self.ab_loop.get_status()}")
            else:
                print("\nB点必须大于A点")

    def _convert_audio(self):
        """交互式音频转换"""
        print("\n音频格式转换")
        print("支持的格式: mp3, wav, ogg, m4a, flac, aac, opus")
        try:
            output_format = input("目标格式 (例如: mp3): ").strip().lower()
            if not output_format:
                print("已取消")
                return

            # 转换当前文件
            success = AudioConverter.convert(self.file_path, output_format)
            if success:
                print("转换完成")
            else:
                print("转换失败")
        except Exception as e:
            print(f"错误: {e}")

    def run(self):
        """主播放循环"""
        print(f"\n播放: {self.file_path.name}")
        print(f"时长: {self.format_time(self.total_duration)}")

        # 记录到播放历史
        self.history_manager.add(self.file_path)

        # 检查书签
        saved_pos = self.bookmark_manager.get_position(self.file_path)
        if saved_pos > 5:
            print(f"📑 发现书签: 从 {self.format_time(saved_pos * 1000)} 恢复? 按 [r] 恢复或按其他键开始")

        # 检查收藏状态
        fav_status = "❤️ 已收藏" if self.favorites_manager.is_favorite(self.file_path) else ""
        if fav_status:
            print(fav_status)

        print("\n控制:")
        print("  [空格] 暂停/继续  [←/→] 后退/前进10秒  [↑/↓] 音量")
        print("  [</>] 播放速度  [l] 循环模式  [i] 媒体信息")
        print("  [v] 可视化器  [b] 保存书签  [r] 恢复书签  [o] 歌词")
        print("  [f] 收藏/取消  [a] AB循环  [t] 定时停止  [h] 播放历史")
        print("  [e] 切换均衡器  [E] 均衡器预设  [Q] 播放队列  [S] 统计")
        print("  [c] 转换格式  [m] 编辑元数据  [p/P] 音调控制  [x] 交叉淡入")
        print("  [F] 文件浏览器  [q/Ctrl+C] 退出\n")

        # 等待用户决定是否恢复书签
        if saved_pos > 5:
            self._wait_for_resume_key(saved_pos)
        else:
            self.play_from_position(0)

        # 控制监听
        try:
            if platform.system() == "Windows":
                import msvcrt
                while self.is_playing or self.is_paused:
                    # 检查定时停止
                    if self.sleep_timer.is_active:
                        remaining = self.sleep_timer.get_remaining()
                        if remaining == 0:
                            break

                    # 检查AB循环
                    if self.ab_loop.is_active:
                        current_sec = self.current_position / 1000
                        loop_to = self.ab_loop.check_position(current_sec)
                        if loop_to is not None:
                            self.play_from_position(loop_to)

                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b' ':
                            self.pause()
                        elif key == b'q' or key == b'Q':
                            self.bookmark_manager.set_position(self.file_path, self.current_position / 1000)
                            break
                        elif key == b'i' or key == b'I':
                            info = MediaInfo.get_info(self.file_path)
                            MediaInfo.display_info(info)
                        elif key == b'l' or key == b'L':
                            self.toggle_loop()
                        elif key == b'v' or key == b'V':
                            self.visualizer_enabled = not self.visualizer_enabled
                            if self.visualizer_enabled and not self.is_paused:
                                self.spectrum_thread = threading.Thread(target=self.capture_spectrum, daemon=True)
                                self.spectrum_thread.start()
                        elif key == b'b' or key == b'B':
                            self.bookmark_manager.set_position(self.file_path, self.current_position / 1000)
                            print(f"\n书签已保存: {self.format_time(self.current_position)}")
                        elif key == b'r' or key == b'R':
                            saved = self.bookmark_manager.get_position(self.file_path)
                            if saved > 0:
                                self.play_from_position(saved)
                                print(f"\n已从书签恢复: {self.format_time(saved * 1000)}")
                        elif key == b'o' or key == b'O':
                            self.lyrics.enabled = not self.lyrics.enabled
                            print(f"\n歌词: {'开启' if self.lyrics.enabled else '关闭'}")
                        elif key == b'f' or key == b'F':
                            is_fav = self.favorites_manager.toggle(self.file_path)
                            print(f"\n{'❤️ 已收藏' if is_fav else '已取消收藏'}")
                        elif key == b'a' or key == b'A':
                            self._handle_ab_loop()
                        elif key == b't' or key == b'T':
                            self._set_sleep_timer()
                        elif key == b'h' or key == b'H':
                            self.history_manager.display()
                        elif key == b'e' or key == b'E':
                            if key == b'e':
                                enabled = self.equalizer.toggle()
                                print(f"\n均衡器: {'开启' if enabled else '关闭'}")
                                if enabled:
                                    self.play_from_position(self.current_position / 1000)
                            else:
                                self.equalizer.list_presets()
                        elif key == b'Q':
                            self.queue_manager.display()
                        elif key == b'S':
                            self.statistics_manager.display()
                        elif key == b'c' or key == b'C':
                            self._convert_audio()
                        elif key == b'm':
                            MetadataEditor.run_interactive(self.file_path)
                        elif key == b'p':
                            self.pitch_control.adjust(-0.5)
                            print(f"\n{self.pitch_control.get_status()}")
                            self.play_from_position(self.current_position / 1000)
                        elif key == b'P':
                            self.pitch_control.adjust(0.5)
                            print(f"\n{self.pitch_control.get_status()}")
                            self.play_from_position(self.current_position / 1000)
                        elif key == b'x':
                            enabled = self.crossfade.toggle()
                            print(f"\n交叉淡入淡出: {'开启' if enabled else '关闭'}")
                        elif key == b'X':
                            self.pitch_control.reset()
                            print(f"\n音调已重置")
                            self.play_from_position(self.current_position / 1000)
                        elif key == b'\xe0':
                            key2 = msvcrt.getch()
                            if key2 == b'K':
                                self.seek(-10000)
                            elif key2 == b'M':
                                self.seek(10000)
                            elif key2 == b'H':
                                self.set_volume(5)
                            elif key2 == b'P':
                                self.set_volume(-5)
                    time.sleep(0.05)
                    if not self.is_playing and not self.is_paused:
                        break
            else:
                import select
                import termios
                import tty

                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)

                try:
                    tty.setraw(fd)
                    while self.is_playing or self.is_paused:
                        # 检查定时停止
                        if self.sleep_timer.is_active:
                            remaining = self.sleep_timer.get_remaining()
                            if remaining == 0:
                                break

                        # 检查AB循环
                        if self.ab_loop.is_active:
                            current_sec = self.current_position / 1000
                            loop_to = self.ab_loop.check_position(current_sec)
                            if loop_to is not None:
                                self.play_from_position(loop_to)

                        if select.select([sys.stdin], [], [], 0.05)[0]:
                            ch = sys.stdin.read(1)
                            if ch == ' ':
                                self.pause()
                            elif ch == '\x1b':
                                ch2 = sys.stdin.read(1)
                                if ch2 == '[':
                                    ch3 = sys.stdin.read(1)
                                    if ch3 == 'D':
                                        self.seek(-10000)
                                    elif ch3 == 'C':
                                        self.seek(10000)
                                    elif ch3 == 'A':
                                        self.set_volume(5)
                                    elif ch3 == 'B':
                                        self.set_volume(-5)
                            elif ch in ('q', 'Q', '\x03'):
                                self.bookmark_manager.set_position(self.file_path, self.current_position / 1000)
                                break
                            elif ch in ('i', 'I'):
                                info = MediaInfo.get_info(self.file_path)
                                MediaInfo.display_info(info)
                            elif ch in ('l', 'L'):
                                self.toggle_loop()
                            elif ch in (',', '<'):
                                self.set_speed(self.playback_speed - 0.1)
                            elif ch in ('.', '>'):
                                self.set_speed(self.playback_speed + 0.1)
                            elif ch in ('v', 'V'):
                                self.visualizer_enabled = not self.visualizer_enabled
                                if self.visualizer_enabled and not self.is_paused:
                                    self.spectrum_thread = threading.Thread(target=self.capture_spectrum, daemon=True)
                                    self.spectrum_thread.start()
                            elif ch in ('b', 'B'):
                                self.bookmark_manager.set_position(self.file_path, self.current_position / 1000)
                                print(f"\n书签已保存: {self.format_time(self.current_position)}")
                            elif ch in ('r', 'R'):
                                saved = self.bookmark_manager.get_position(self.file_path)
                                if saved > 0:
                                    self.play_from_position(saved)
                                    print(f"\n已从书签恢复: {self.format_time(saved * 1000)}")
                            elif ch in ('o', 'O'):
                                self.lyrics.enabled = not self.lyrics.enabled
                                print(f"\n歌词: {'开启' if self.lyrics.enabled else '关闭'}")
                            elif ch in ('f', 'F'):
                                is_fav = self.favorites_manager.toggle(self.file_path)
                                print(f"\n{'❤️ 已收藏' if is_fav else '已取消收藏'}")
                            elif ch in ('a', 'A'):
                                self._handle_ab_loop()
                            elif ch in ('t', 'T'):
                                self._set_sleep_timer()
                            elif ch in ('h', 'H'):
                                self.history_manager.display()
                            elif ch == 'e':
                                enabled = self.equalizer.toggle()
                                print(f"\n均衡器: {'开启' if enabled else '关闭'}")
                                if enabled:
                                    self.play_from_position(self.current_position / 1000)
                            elif ch == 'E':
                                self.equalizer.list_presets()
                            elif ch == 'Q':
                                self.queue_manager.display()
                            elif ch == 'S':
                                self.statistics_manager.display()
                            elif ch in ('c', 'C'):
                                self._convert_audio()
                            elif ch == 'm':
                                MetadataEditor.run_interactive(self.file_path)
                            elif ch == 'p':
                                self.pitch_control.adjust(-0.5)
                                print(f"\n{self.pitch_control.get_status()}")
                                self.play_from_position(self.current_position / 1000)
                            elif ch == 'P':
                                self.pitch_control.adjust(0.5)
                                print(f"\n{self.pitch_control.get_status()}")
                                self.play_from_position(self.current_position / 1000)
                            elif ch == 'x':
                                enabled = self.crossfade.toggle()
                                print(f"\n交叉淡入淡出: {'开启' if enabled else '关闭'}")
                            elif ch == 'X':
                                self.pitch_control.reset()
                                print(f"\n音调已重置")
                                self.play_from_position(self.current_position / 1000)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception as e:
            print(f"\n控制监听错误: {e}")

        self.stop()
        print("\n播放结束")
    
    def _wait_for_resume_key(self, saved_pos):
        """等待用户按键决定是否恢复书签"""
        try:
            if platform.system() == "Windows":
                import msvcrt
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    if key == b'r' or key == b'R':
                        self.play_from_position(saved_pos)
                        print(f"\n已从书签恢复: {self.format_time(saved_pos * 1000)}")
                        return
            else:
                import select
                import termios
                import tty
                
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                tty.setcbreak(fd)
                
                if select.select([sys.stdin], [], [], 2)[0]:  # 2秒超时
                    ch = sys.stdin.read(1)
                    if ch in ('r', 'R'):
                        self.play_from_position(saved_pos)
                        print(f"\n已从书签恢复: {self.format_time(saved_pos * 1000)}")
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                        return
                
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except:
            pass
        
        # 超时或按其他键，正常开始播放
        self.play_from_position(0)


class VideoPlayer:
    """终端视频播放器 - 使用字符渲染视频帧"""
    
    # ASCII 字符梯度（从暗到亮）
    ASCII_CHARS = '@%#*+=-:. '
    
    def __init__(self, file_path: Path, config: Config):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            print(f"错误: 文件 '{file_path}' 不存在")
            sys.exit(1)
        
        self.config = config
        self.is_playing = False
        self.is_paused = False
        self.process = None
        self.audio_process = None
        self.ffmpeg_process = None
        self.current_frame = 0
        self.fps = 0
        self.total_frames = 0
        self.duration = 0
        self.width = 0
        self.height = 0
        
        # 新增功能
        self.volume = config.get('volume', 100)
        self.playback_speed = config.get('playback_speed', 1.0)
        self.loop_mode = config.get('loop_mode', 'none')
        
        # 获取视频信息
        self._get_video_info()
    
    def _get_video_info(self):
        """获取视频信息"""
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=r_frame_rate,nb_frames,width,height,duration',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                str(self.file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    parts = line.split(',')
                    if len(parts) >= 4:
                        # 尝试解析帧率
                        if '/' in parts[0]:
                            num, den = parts[0].split('/')
                            if den != '0':
                                self.fps = float(num) / float(den)
                        else:
                            try:
                                self.fps = float(parts[0])
                            except:
                                pass
                        
                        # 解析宽度、高度
                        try:
                            self.width = int(parts[1])
                            self.height = int(parts[2])
                        except:
                            pass
                        
                        # 解析时长
                        try:
                            self.duration = float(parts[3])
                        except:
                            try:
                                self.duration = float(parts[4])
                            except:
                                pass
                
                if self.fps > 0 and self.duration > 0:
                    self.total_frames = int(self.fps * self.duration)
        except Exception as e:
            print(f"警告: 无法获取视频信息: {e}")
        
        # 默认值
        if self.fps == 0:
            self.fps = 25
        if self.width == 0:
            self.width = 640
        if self.height == 0:
            self.height = 480
        if self.duration == 0:
            self.duration = 0
    
    def _get_terminal_size(self):
        """获取终端尺寸"""
        try:
            size = os.get_terminal_size()
            return size.columns, size.lines
        except:
            return 80, 24
    
    def _pixel_to_char(self, pixel_value):
        """将像素值转换为ASCII字符"""
        index = int(pixel_value * (len(self.ASCII_CHARS) - 1) / 255)
        return self.ASCII_CHARS[index]
    
    def _render_frame(self, frame_data, width, height):
        """渲染一帧到终端"""
        # 移动到光标起始位置
        sys.stdout.write('\033[H')
        
        # 将帧数据转换为灰度图并渲染
        chars_per_row = width * 3  # RGB
        lines = []
        
        for y in range(height):
            line = []
            for x in range(width):
                idx = (y * width + x) * 3
                if idx + 2 < len(frame_data):
                    r, g, b = frame_data[idx], frame_data[idx+1], frame_data[idx+2]
                    # 转换为灰度
                    gray = int(0.299 * r + 0.587 * g + 0.114 * b)
                    char = self._pixel_to_char(gray)
                    line.append(char)
            lines.append(''.join(line))
        
        sys.stdout.write('\n'.join(lines))
        sys.stdout.flush()
    
    def _play_audio(self):
        """播放音频轨道"""
        cmd = [
            'ffplay',
            '-nodisp',
            '-autoexit',
            '-loglevel', 'quiet',
            '-hide_banner',
            '-volume', str(self.volume),
            str(self.file_path)
        ]
        
        # 播放速度
        if self.playback_speed != 1.0:
            cmd.extend(['-af', f'atempo={self.playback_speed}'])
        
        devnull = open(os.devnull, 'w')
        self.audio_process = subprocess.Popen(
            cmd,
            stdout=devnull,
            stderr=devnull,
            stdin=subprocess.DEVNULL
        )
    
    def play(self):
        """主播放循环"""
        print(f"\n播放视频: {self.file_path.name}")
        print(f"分辨率: {self.width}x{self.height}")
        print(f"时长: {self.format_time(self.duration * 1000)}")
        print(f"帧率: {self.fps:.2f} fps")
        print("\n控制: [空格] 暂停/继续  [↑/↓] 音量  [i] 媒体信息  [q/Ctrl+C] 退出\n")
        
        # 获取终端尺寸
        term_width, term_height = self._get_terminal_size()
        
        # 计算合适的视频尺寸（保持宽高比）
        # 字符宽高比约为 1:2，需要调整
        max_width = term_width
        max_height = (term_height - 2) * 2  # 预留空间给控制信息
        
        aspect_ratio = self.width / self.height if self.height > 0 else 1.33
        
        if max_width / aspect_ratio <= max_height:
            render_width = max_width
            render_height = int(max_width / aspect_ratio / 2)
        else:
            render_height = max_height // 2
            render_width = int(max_height * aspect_ratio / 2)
        
        # 确保尺寸合理
        render_width = max(20, min(render_width, 200))
        render_height = max(10, min(render_height, 80))
        
        # 清空屏幕并隐藏光标
        sys.stdout.write('\033[2J\033[?25l')
        sys.stdout.flush()
        
        # 启动音频播放
        self._play_audio()
        
        # 启动 ffmpeg 进程读取视频帧
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', str(self.file_path),
            '-f', 'rawvideo',
            '-pix_fmt', 'rgb24',
            '-s', f'{render_width}x{render_height}',
            '-v', 'quiet',
            '-'
        ]
        
        self.ffmpeg_process = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=render_width * render_height * 3 * 10
        )
        
        self.is_playing = True
        frame_size = render_width * render_height * 3
        frame_delay = 1.0 / self.fps if self.fps > 0 else 0.04
        
        try:
            # 设置非阻塞输入
            if platform.system() != "Windows":
                import select
                import termios
                import tty
                
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                tty.setcbreak(fd)
            
            while self.is_playing:
                start_time = time.time()
                
                # 读取一帧
                frame_data = self.ffmpeg_process.stdout.read(frame_size)
                if len(frame_data) < frame_size:
                    break
                
                # 检查用户输入
                if platform.system() == "Windows":
                    import msvcrt
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b' ':
                            self._toggle_pause()
                        elif key in (b'q', b'Q'):
                            break
                        elif key in (b'i', b'I'):
                            info = MediaInfo.get_info(self.file_path)
                            MediaInfo.display_info(info)
                else:
                    if select.select([sys.stdin], [], [], 0)[0]:
                        ch = sys.stdin.read(1)
                        if ch == ' ':
                            self._toggle_pause()
                        elif ch in ('q', 'Q', '\x03'):
                            break
                        elif ch in ('i', 'I'):
                            info = MediaInfo.get_info(self.file_path)
                            MediaInfo.display_info(info)
                        elif ch == '\x1b':
                            ch2 = sys.stdin.read(1)
                            if ch2 == '[':
                                ch3 = sys.stdin.read(1)
                                if ch3 == 'A':
                                    self._change_volume(5)
                                elif ch3 == 'B':
                                    self._change_volume(-5)
                
                if not self.is_paused:
                    # 渲染帧
                    self._render_frame(frame_data, render_width, render_height)
                    self.current_frame += 1
                
                # 控制帧率
                elapsed = time.time() - start_time
                sleep_time = frame_delay - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
        except Exception as e:
            print(f"\n播放错误: {e}")
        finally:
            # 恢复终端设置
            if platform.system() != "Windows":
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            
            # 恢复光标显示
            sys.stdout.write('\033[?25h\033[2J\033[H')
            sys.stdout.flush()
            
            self.stop()
            print("\n播放结束")
    
    def _toggle_pause(self):
        """切换暂停状态"""
        if self.is_paused:
            self.is_paused = False
            if self.audio_process and self.audio_process.poll() is not None:
                # 重新启动音频
                self._play_audio()
            else:
                # 继续音频播放
                if self.audio_process:
                    self.audio_process.send_signal(signal.SIGCONT)
        else:
            self.is_paused = True
            # 暂停音频
            if self.audio_process and self.audio_process.poll() is None:
                self.audio_process.send_signal(signal.SIGSTOP)
    
    def _change_volume(self, delta: int):
        """调整音量"""
        self.volume = max(0, min(100, self.volume + delta))
        self.config.set('volume', self.volume)
        # 显示音量提示（在终端底部）
        print(f"\n音量: {self.volume}%")
    
    def stop(self):
        """停止播放"""
        self.is_playing = False
        
        if self.ffmpeg_process and self.ffmpeg_process.poll() is None:
            self.ffmpeg_process.terminate()
            try:
                self.ffmpeg_process.wait(timeout=1)
            except:
                self.ffmpeg_process.kill()
        
        if self.audio_process and self.audio_process.poll() is None:
            self.audio_process.terminate()
            try:
                self.audio_process.wait(timeout=1)
            except:
                self.audio_process.kill()
    
    def format_time(self, ms):
        """格式化时间显示"""
        total_seconds = int(ms // 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"


class AudioRecorder:
    """音频录制器 - 从麦克风录制音频"""

    SUPPORTED_FORMATS = {
        '.wav': ['-c:a', 'pcm_s16le'],
        '.mp3': ['-c:a', 'libmp3lame', '-b:a', '192k'],
        '.ogg': ['-c:a', 'libvorbis', '-b:a', '192k'],
        '.m4a': ['-c:a', 'aac', '-b:a', '192k'],
        '.flac': ['-c:a', 'flac'],
    }

    @staticmethod
    def _find_input_device() -> List[str]:
        """根据平台选择合适的 ffmpeg 音频输入设备"""
        system = platform.system()
        if system == "Linux":
            # 优先使用 pulse，回退到 alsa default
            return ['-f', 'pulse', '-i', 'default']
        elif system == "Darwin":
            # macOS 使用 avfoundation，:0 表示默认音频设备
            return ['-f', 'avfoundation', '-i', ':0']
        else:
            # Windows 使用 dshow（需要用户配置设备名，这里给默认值）
            return ['-f', 'dshow', '-i', 'audio=Microphone']

    @staticmethod
    def record(output_path: Path, duration: Optional[float] = None) -> bool:
        """录制音频到指定文件"""
        ext = output_path.suffix.lower()
        if ext not in AudioRecorder.SUPPORTED_FORMATS:
            print(f"不支持的格式: {ext}")
            print(f"支持的格式: {', '.join(AudioRecorder.SUPPORTED_FORMATS.keys())}")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning']
        cmd.extend(AudioRecorder._find_input_device())
        if duration and duration > 0:
            cmd.extend(['-t', str(duration)])
        cmd.extend(AudioRecorder.SUPPORTED_FORMATS[ext])
        cmd.append(str(output_path))

        print(f"\n{'='*60}")
        print(f"  音频录制")
        print(f"{'='*60}")
        print(f"  输出文件: {output_path}")
        if duration:
            print(f"  录制时长: {MediaInfo.format_duration(duration)}")
        else:
            print(f"  录制时长: 直至按 Ctrl+C 停止")
        print(f"  按 Ctrl+C 停止录制")
        print(f"{'='*60}\n")

        try:
            subprocess.run(cmd)
            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"\n✓ 录制完成: {output_path}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            else:
                print("\n✗ 录制失败：输出文件为空（请检查麦克风设备）")
                return False
        except KeyboardInterrupt:
            print(f"\n停止录制")
            if output_path.exists():
                print(f"✓ 已保存: {output_path}")
                return True
            return False
        except FileNotFoundError:
            print("✗ 未找到 ffmpeg，请先安装")
            return False
        except Exception as e:
            print(f"✗ 录制错误: {e}")
            return False

    @staticmethod
    def run_interactive(output_path: Optional[Path] = None):
        """交互式录制"""
        if output_path is None:
            print(f"\n音频录制器")
            print(f"{'='*60}")
            name = input("输出文件名 (默认 recording.wav): ").strip()
            if not name:
                name = 'recording.wav'
            if not name.startswith('.'):
                output_path = Path(name)
            else:
                output_path = Path('recording' + name)

        dur_input = input("录制时长（秒，留空则手动停止）: ").strip()
        duration = None
        if dur_input:
            try:
                duration = float(dur_input)
                if duration <= 0:
                    duration = None
            except ValueError:
                print("无效的时长，将手动停止")

        AudioRecorder.record(output_path, duration)


class AudioExtractor:
    """音频提取器 - 从视频文件提取音轨"""

    SUPPORTED_FORMATS = {
        '.mp3': ['-c:a', 'libmp3lame', '-b:a', '192k'],
        '.wav': ['-c:a', 'pcm_s16le'],
        '.ogg': ['-c:a', 'libvorbis', '-b:a', '192k'],
        '.m4a': ['-c:a', 'aac', '-b:a', '192k'],
        '.flac': ['-c:a', 'flac'],
        '.aac': ['-c:a', 'aac', '-b:a', '192k'],
        '.opus': ['-c:a', 'libopus', '-b:a', '128k'],
    }

    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}

    @staticmethod
    def extract(video_path: Path, output_format: str = 'mp3',
                output_dir: Optional[Path] = None) -> bool:
        """从视频文件提取音频"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False

        ext = video_path.suffix.lower()
        if ext not in AudioExtractor.VIDEO_EXTENSIONS:
            print(f"错误: 不是视频文件: {ext}")
            return False

        output_format = output_format.lower()
        if not output_format.startswith('.'):
            output_format = '.' + output_format
        if output_format not in AudioExtractor.SUPPORTED_FORMATS:
            print(f"不支持的音频格式: {output_format}")
            print(f"支持: {', '.join(AudioExtractor.SUPPORTED_FORMATS.keys())}")
            return False

        if output_dir:
            output_path = output_dir / (video_path.stem + output_format)
        else:
            output_path = video_path.with_suffix(output_format)

        # 如果输出路径与输入相同（视频恰好是 .mp3 等极罕见情况），加后缀
        if output_path == video_path:
            output_path = video_path.with_name(video_path.stem + '_audio' + output_format)

        print(f"提取音频: {video_path.name} → {output_path.name}")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(video_path),
            '-vn',  # 不要视频
        ]
        cmd.extend(AudioExtractor.SUPPORTED_FORMATS[output_format])
        cmd.append(str(output_path))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 提取成功: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            else:
                print(f"✗ 提取失败: {result.stderr.strip() or '未知错误'}")
                return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_extract(video_files: List[Path], output_format: str = 'mp3') -> int:
        """批量提取音频"""
        success = 0
        total = len(video_files)
        print(f"\n批量提取音频: {total} 个文件 → {output_format}")
        print(f"{'='*60}")
        for i, vf in enumerate(video_files, 1):
            print(f"[{i}/{total}] ", end='')
            if AudioExtractor.extract(vf, output_format):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success


class GifConverter:
    """GIF转换器 - 将视频片段转换为GIF动画"""

    @staticmethod
    def convert(video_path: Path, output_path: Optional[Path] = None,
                start: float = 0.0, duration: Optional[float] = None,
                width: int = 480, fps: int = 15) -> bool:
        """将视频片段转为GIF"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False

        if output_path is None:
            output_path = video_path.with_suffix('.gif')

        if duration is None or duration <= 0:
            # 默认截取 5 秒
            duration = 5.0

        # 获取视频信息以确定起始时间合法性
        info = MediaInfo.get_info(video_path)
        total_duration = info.get('duration', 0)
        if total_duration > 0 and start >= total_duration:
            print(f"错误: 起始时间 {start}s 超出视频时长 {MediaInfo.format_duration(total_duration)}")
            return False
        if total_duration > 0 and start + duration > total_duration:
            duration = max(0.1, total_duration - start)
            print(f"提示: 已将时长调整为 {duration:.1f}s 以匹配视频长度")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\n转换 GIF: {video_path.name}")
        print(f"  起始: {start:.1f}s | 时长: {duration:.1f}s | 宽度: {width}px | FPS: {fps}")
        print(f"  输出: {output_path.name}")

        # 使用 ffmpeg 的 palettegen + paletteuse 两步法生成高质量 GIF
        palette_path = output_path.with_suffix('.palette.png')
        try:
            # 步骤1: 生成调色板
            cmd1 = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-ss', str(start), '-t', str(duration),
                '-i', str(video_path),
                '-vf', f'fps={fps},scale={width}:-1:flags=lanczos,palettegen',
                str(palette_path)
            ]
            r1 = subprocess.run(cmd1, capture_output=True, text=True)
            if r1.returncode != 0:
                print(f"✗ 生成调色板失败: {r1.stderr.strip()}")
                return False

            # 步骤2: 应用调色板生成GIF
            cmd2 = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-ss', str(start), '-t', str(duration),
                '-i', str(video_path), '-i', str(palette_path),
                '-lavfi', f'fps={fps},scale={width}:-1:flags=lanczos [x]; [x][1:v] paletteuse',
                str(output_path)
            ]
            r2 = subprocess.run(cmd2, capture_output=True, text=True)

            # 清理调色板
            if palette_path.exists():
                palette_path.unlink()

            if r2.returncode == 0 and output_path.exists():
                print(f"✓ 转换成功: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            else:
                print(f"✗ 转换失败: {r2.stderr.strip()}")
                return False
        except Exception as e:
            if palette_path.exists():
                palette_path.unlink()
            print(f"✗ 错误: {e}")
            return False


class ScreenshotCapture:
    """视频截图 - 从视频捕获指定时间点的画面帧"""

    @staticmethod
    def capture(video_path: Path, timestamp: float = 0.0,
                output_path: Optional[Path] = None) -> bool:
        """捕获指定时间点的视频帧"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False

        if timestamp < 0:
            timestamp = 0.0

        if output_path is None:
            ts_str = f"{int(timestamp // 60):02d}-{int(timestamp % 60):02d}"
            output_path = video_path.with_name(f"{video_path.stem}_shot_{ts_str}.png")

        info = MediaInfo.get_info(video_path)
        total_duration = info.get('duration', 0)
        if total_duration > 0 and timestamp >= total_duration:
            print(f"错误: 时间点 {timestamp}s 超出视频时长 {MediaInfo.format_duration(total_duration)}")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"捕获截图: {video_path.name} @ {MediaInfo.format_duration(timestamp)}")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-ss', str(timestamp),
            '-i', str(video_path),
            '-frames:v', '1',
            '-q:v', '2',  # 高质量
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 截图成功: {output_path.name}")
                if info.get('width'):
                    print(f"  分辨率: {info['width']}x{info['height']}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            else:
                print(f"✗ 截图失败: {result.stderr.strip()}")
                return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def capture_multi(video_path: Path, count: int = 5,
                      output_dir: Optional[Path] = None) -> int:
        """从视频中均匀捕获多张截图"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return 0

        info = MediaInfo.get_info(video_path)
        total = info.get('duration', 0)
        if total <= 0:
            print("✗ 无法获取视频时长")
            return 0

        if count < 1:
            count = 1
        if count == 1:
            ts = total / 2
            return 1 if ScreenshotCapture.capture(video_path, ts, None) else 0

        if output_dir is None:
            output_dir = video_path.parent / f"{video_path.stem}_screenshots"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 在 10% ~ 90% 区间均匀采样
        success = 0
        print(f"\n批量截图: {count} 张")
        print(f"{'='*60}")
        for i in range(count):
            ratio = 0.1 + 0.8 * i / (count - 1)
            ts = total * ratio
            out = output_dir / f"{video_path.stem}_{i+1:02d}.png"
            print(f"[{i+1}/{count}] ", end='')
            if ScreenshotCapture.capture(video_path, ts, out):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{count} 张截图保存到 {output_dir}")
        return success


class AudioNormalizer:
    """音频归一化 - 统一音频文件的音量水平"""

    METHODS = {
        'loudnorm': 'EBU R128 响度归一化（推荐，-16 LUFS）',
        'dynaudnorm': '动态音频归一化（平滑）',
        'loudnorm_db': '峰值归一化到 0dB',
    }

    @staticmethod
    def normalize(file_path: Path, method: str = 'loudnorm',
                  output_path: Optional[Path] = None) -> bool:
        """归一化音频音量"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        method = method.lower()
        if method not in AudioNormalizer.METHODS:
            print(f"不支持的归一化方法: {method}")
            print("可用方法:")
            for m, desc in AudioNormalizer.METHODS.items():
                print(f"  {m:14s} - {desc}")
            return False

        if output_path is None:
            # 默认输出到同目录，加 _norm 后缀，避免覆盖原文件
            output_path = file_path.with_name(file_path.stem + '_norm' + file_path.suffix)

        if output_path == file_path:
            # 输出到临时文件再替换
            tmp = file_path.with_suffix(file_path.suffix + '.tmp_norm')
        else:
            tmp = output_path

        # 选择滤镜
        if method == 'loudnorm':
            filt = 'loudnorm=I=-16:TP=-1.5:LRA=11'
        elif method == 'dynaudnorm':
            filt = 'dynaudnorm=f=150:g=15:p=0.9'
        else:  # loudnorm_db
            filt = 'loudnorm=I=-23:TP=-2:LRA=7'

        print(f"归一化: {file_path.name} [{method}]")
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-af', filt,
            '-c:v', 'copy',
            str(tmp)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0 or not tmp.exists():
                print(f"✗ 归一化失败: {result.stderr.strip()}")
                if tmp.exists():
                    tmp.unlink()
                return False

            if output_path == file_path:
                tmp.replace(file_path)
                print(f"✓ 已归一化并覆盖原文件: {file_path.name}")
            else:
                print(f"✓ 归一化完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(tmp.stat().st_size)}")
            return True
        except Exception as e:
            if tmp.exists() and output_path != file_path:
                tmp.unlink()
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_normalize(file_paths: List[Path], method: str = 'loudnorm') -> int:
        """批量归一化"""
        success = 0
        total = len(file_paths)
        print(f"\n批量归一化: {total} 个文件 [{method}]")
        print(f"{'='*60}")
        for i, fp in enumerate(file_paths, 1):
            print(f"[{i}/{total}] ", end='')
            if AudioNormalizer.normalize(fp, method):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success


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


class AudioTrimmer:
    """媒体裁剪 - 提取指定时间范围的音频/视频片段"""

    @staticmethod
    def trim(file_path: Path, start: float, end: Optional[float] = None,
             output_path: Optional[Path] = None) -> bool:
        """裁剪媒体文件，提取 [start, end] 时间段"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        info = MediaInfo.get_info(file_path)
        duration = info.get('duration', 0) if isinstance(info, dict) else 0
        if duration <= 0:
            print(f"✗ 无法读取文件时长")
            return False

        if start < 0 or start >= duration:
            print(f"✗ 起始时间无效: {start}s（文件时长 {duration:.1f}s）")
            return False

        if end is None:
            end = duration
        if end <= start:
            print(f"✗ 结束时间需大于起始时间（start={start}, end={end}）")
            return False
        if end > duration:
            end = duration

        if output_path is None:
            output_path = file_path.with_name(
                f"{file_path.stem}_trim_{int(start)}s-{int(end)}s{file_path.suffix}")

        seg_duration = end - start
        print(f"裁剪: {file_path.name} [{start:.2f}s → {end:.2f}s] (时长 {seg_duration:.2f}s)")

        # 流复制保留原编码，速度快、无损
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-ss', f'{start:.3f}',
            '-to', f'{end:.3f}',
            '-i', str(file_path),
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 裁剪完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            # 流复制失败时回退到重编码
            print(f"  流复制失败，尝试重编码...")
            cmd = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-ss', f'{start:.3f}',
                '-to', f'{end:.3f}',
                '-i', str(file_path),
                str(output_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 裁剪完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 裁剪失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


class AudioMerger:
    """音频合并 - 将多个音频文件合并为一个"""

    @staticmethod
    def merge(input_files: List[Path], output_path: Path,
              output_format: Optional[str] = None) -> bool:
        """合并多个音频文件到一个输出文件"""
        if len(input_files) < 2:
            print("错误: 合并至少需要 2 个文件")
            return False

        for f in input_files:
            if not f.exists():
                print(f"错误: 文件不存在 {f}")
                return False

        if output_format is None:
            output_format = output_path.suffix.lstrip('.').lower()
        if not output_format:
            output_format = 'mp3'
            output_path = output_path.with_suffix('.mp3')

        print(f"合并 {len(input_files)} 个文件 → {output_path.name}")
        for i, f in enumerate(input_files, 1):
            print(f"  [{i}/{len(input_files)}] {f.name}")

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning']
        for f in input_files:
            cmd.extend(['-i', str(f)])

        # concat filter：拼接所有音频输入
        filter_inputs = ''.join(f'[{i}:a]' for i in range(len(input_files)))
        filter_complex = f"{filter_inputs}concat=n={len(input_files)}:v=0:a=1[a]"

        # 输出编码参数
        fmt_args = AudioConverter.SUPPORTED_FORMATS.get(f'.{output_format}',
                                                       ['-c:a', 'libmp3lame', '-b:a', '192k'])

        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[a]',
        ] + fmt_args + [str(output_path)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 合并完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 合并失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


class AudioReverser:
    """音频反向 - 反转音频播放方向"""

    @staticmethod
    def reverse(file_path: Path, output_path: Optional[Path] = None) -> bool:
        """反转音频播放方向"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if output_path is None:
            output_path = file_path.with_name(f"{file_path.stem}_reversed{file_path.suffix}")

        print(f"反向: {file_path.name}")
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-map', '0:a',
            '-af', 'areverse',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 反向完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 反向失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_reverse(file_paths: List[Path]) -> int:
        success = 0
        total = len(file_paths)
        print(f"\n批量反向: {total} 个文件")
        print(f"{'='*60}")
        for i, fp in enumerate(file_paths, 1):
            print(f"[{i}/{total}] ", end='')
            if AudioReverser.reverse(fp):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success


class FadeEffect:
    """淡入淡出 - 为音频添加淡入和淡出效果"""

    @staticmethod
    def apply_fade(file_path: Path, fade_in: float = 0.0, fade_out: float = 0.0,
                   output_path: Optional[Path] = None) -> bool:
        """添加淡入/淡出效果
        fade_in: 淡入时长（秒）
        fade_out: 淡出时长（秒）
        """
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if fade_in <= 0 and fade_out <= 0:
            print("✗ 请指定淡入或淡出时长（>0）")
            return False

        info = MediaInfo.get_info(file_path)
        duration = info.get('duration', 0) if isinstance(info, dict) else 0
        if duration <= 0:
            print("✗ 无法读取音频时长")
            return False

        if fade_in + fade_out >= duration:
            print(f"✗ 淡入淡出总时长 ({fade_in + fade_out}s) 超过音频时长 ({duration:.2f}s)")
            return False

        if output_path is None:
            output_path = file_path.with_name(f"{file_path.stem}_fade{file_path.suffix}")

        filters = []
        if fade_in > 0:
            filters.append(f"afade=t=in:st=0:d={fade_in:.3f}")
        if fade_out > 0:
            fade_out_start = duration - fade_out
            filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}")

        af = ','.join(filters)
        print(f"淡入淡出: {file_path.name} (in={fade_in}s, out={fade_out}s)")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-af', af,
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 淡入淡出完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


class ReverbEffect:
    """混响效果 - 为音频添加混响/回声"""

    PRESETS = {
        'room':       ('房间',       'aecho=0.8:0.9:1000:0.3'),
        'hall':       ('音乐厅',     'aecho=0.8:0.9:2000:0.4'),
        'cathedral':  ('大教堂',     'aecho=0.8:0.9:3000:0.5'),
        'plate':      ('板式混响',   'aecho=0.6:0.7:500:0.4'),
        'spring':     ('弹簧混响',   'aecho=0.5:0.6:200:0.5'),
        'cave':       ('洞穴',       'aecho=0.9:0.95:5000:0.6'),
        'stadium':    ('体育场',     'aecho=0.85:0.92:4000:0.55'),
    }

    @staticmethod
    def list_presets():
        print(f"\n可用混响预设:")
        print(f"{'='*40}")
        for name, (desc, _) in ReverbEffect.PRESETS.items():
            print(f"  {name:12s} - {desc}")
        print(f"{'='*40}\n")

    @staticmethod
    def apply_reverb(file_path: Path, preset: str = 'room',
                     output_path: Optional[Path] = None) -> bool:
        """应用混响预设"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        preset = preset.lower()
        if preset not in ReverbEffect.PRESETS:
            print(f"✗ 未知预设: {preset}")
            print("使用 --reverb-list 查看可用预设")
            return False

        if output_path is None:
            output_path = file_path.with_name(f"{file_path.stem}_{preset}{file_path.suffix}")

        desc, filt = ReverbEffect.PRESETS[preset]
        print(f"混响: {file_path.name} [{preset}] ({desc})")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-af', filt,
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 混响完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


class SubtitleExtractor:
    """字幕提取 - 从视频文件提取字幕轨道"""

    @staticmethod
    def list_streams(video_path: Path) -> List[Dict[str, Any]]:
        """列出视频中所有字幕流"""
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams', '-select_streams', 's',
            str(video_path)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get('streams', [])
        except Exception:
            pass
        return []

    @staticmethod
    def extract(video_path: Path, stream_index: Optional[int] = None,
                output_format: str = 'srt',
                output_path: Optional[Path] = None) -> bool:
        """从视频提取字幕
        stream_index: 字幕流索引（0-based），None 表示第一个字幕流
        output_format: srt 或 ass
        """
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False

        streams = SubtitleExtractor.list_streams(video_path)
        if not streams:
            print(f"✗ 未找到字幕轨道: {video_path.name}")
            return False

        if stream_index is None:
            stream_index = 0
        if stream_index >= len(streams):
            print(f"✗ 字幕流索引超出范围 (0-{len(streams)-1})")
            return False

        stream = streams[stream_index]
        # ffprobe 返回的 index 是绝对索引（包含视频/音频流）
        abs_index = stream.get('index', 0)
        codec = stream.get('codec_name', 'unknown')
        lang = stream.get('tags', {}).get('language', '未知')

        if output_path is None:
            suffix = '.srt' if output_format == 'srt' else '.ass'
            lang_suffix = f".{lang}" if lang and lang != '未知' else ""
            output_path = video_path.with_suffix(f"{lang_suffix}{suffix}")

        print(f"提取字幕: {video_path.name}")
        print(f"  字幕流 #{stream_index}: 编码={codec}, 语言={lang}")

        # 选择输出编码
        if output_format == 'ass':
            codec_args = ['-c:s', 'ass']
        else:
            codec_args = ['-c:s', 'srt']

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(video_path),
            '-map', f'0:{abs_index}',
        ] + codec_args + [str(output_path)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                size = output_path.stat().st_size
                if size == 0:
                    print(f"✗ 字幕为空")
                    output_path.unlink()
                    return False
                print(f"✓ 提取完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(size)}")
                return True
            print(f"✗ 提取失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


class BPMDetector:
    """BPM 检测 - 通过自相关检测音频节拍速度"""

    MIN_BPM = 60
    MAX_BPM = 200

    @staticmethod
    def detect(file_path: Path) -> Optional[float]:
        """检测音频 BPM（每分钟节拍数）"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return None

        # 提取为单声道 8kHz 16-bit PCM
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'quiet',
            '-i', str(file_path),
            '-ac', '1', '-ar', '8000',
            '-f', 's16le', '-'
        ]

        try:
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode != 0 or not result.stdout:
                print("✗ 无法读取音频数据")
                return None

            data = result.stdout
            n_samples = len(data) // 2
            if n_samples < 8000:
                print("✗ 音频太短，无法检测")
                return None

            samples = struct.unpack(f'<{n_samples}h', data)

            # 计算能量包络（每 128 样本一个能量值，约 16ms）
            window = 128
            energy = []
            for i in range(0, len(samples) - window, window):
                e = sum(s * s for s in samples[i:i + window]) / window
                energy.append(e)

            if not energy:
                return None

            # 去除直流分量
            avg = sum(energy) / len(energy)
            energy = [e - avg for e in energy]

            # 能量采样率
            energy_rate = 8000.0 / window  # ~62.5 Hz
            min_lag = max(1, int(60 * energy_rate / BPMDetector.MAX_BPM))
            max_lag = int(60 * energy_rate / BPMDetector.MIN_BPM)
            max_lag = min(max_lag, len(energy) - 1)

            best_lag = 0
            best_corr = -1.0
            for lag in range(min_lag, max_lag + 1):
                if lag >= len(energy):
                    break
                corr = 0.0
                for i in range(len(energy) - lag):
                    corr += energy[i] * energy[i + lag]
                if corr > best_corr:
                    best_corr = corr
                    best_lag = lag

            if best_lag == 0:
                return None

            bpm = 60.0 * energy_rate / best_lag
            return round(bpm, 1)
        except Exception as e:
            print(f"✗ 检测失败: {e}")
            return None

    @staticmethod
    def detect_and_display(file_path: Path):
        print(f"\n分析: {file_path.name}")
        print(f"{'='*50}")
        bpm = BPMDetector.detect(file_path)
        if bpm is not None:
            print(f"  BPM: {bpm}")
            if bpm < 70:
                desc = "慢板（缓慢抒情）"
            elif bpm < 90:
                desc = "中慢板"
            elif bpm < 110:
                desc = "中板"
            elif bpm < 130:
                desc = "中快板"
            elif bpm < 160:
                desc = "快板（流行/摇滚节奏）"
            else:
                desc = "极快板（电子/舞曲）"
            print(f"  速度: {desc}")
        print(f"{'='*50}")


class ContactSheet:
    """接触印片 - 生成视频缩略图组合"""

    @staticmethod
    def generate(video_path: Path, rows: int = 4, cols: int = 4,
                 output_path: Optional[Path] = None,
                 width: int = 320) -> bool:
        """生成视频缩略图组合"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False

        if rows < 1 or cols < 1:
            print("✗ 行列数必须 ≥1")
            return False

        info = MediaInfo.get_info(video_path)
        duration = info.get('duration', 0) if isinstance(info, dict) else 0
        if duration <= 0:
            print("✗ 无法读取视频时长")
            return False

        if output_path is None:
            output_path = video_path.with_suffix('.contact_sheet.png')

        total = rows * cols
        # 在视频 10%-90% 区间均匀采样，避免黑屏开头/结尾
        sample_duration = duration * 0.8
        if sample_duration <= 0:
            print("✗ 视频时长太短")
            return False

        fps = total / sample_duration
        start_time = duration * 0.1

        print(f"生成缩略图组合: {rows}×{cols} = {total} 张 (各 {width}px 宽)")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-ss', f'{start_time:.3f}',
            '-i', str(video_path),
            '-t', f'{sample_duration:.3f}',
            '-vf', f'fps={fps:.6f},scale={width}:-1,tile={cols}x{rows}',
            '-frames:v', '1',
            '-q:v', '3',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 缩略图组合已生成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 生成失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


class DuplicateFinder:
    """重复文件查找 - 基于内容哈希查找重复媒体文件"""

    MEDIA_EXTENSIONS = {
        '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.opus',
        '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v',
    }

    @staticmethod
    def _file_hash(file_path: Path, chunk_size: int = 65536) -> str:
        """计算文件 SHA-256 哈希（先按大小过滤）"""
        h = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def find(directory: Path, recursive: bool = True) -> Dict[str, List[Path]]:
        """查找重复文件，返回 {hash: [paths]} 字典（仅包含重复项）"""
        if not directory.exists() or not directory.is_dir():
            print(f"错误: 目录不存在 {directory}")
            return {}

        # 先按大小分组，相同大小再算哈希（避免无谓的哈希计算）
        size_map: Dict[int, List[Path]] = {}
        glob_pattern = '**/*' if recursive else '*'
        for entry in directory.glob(glob_pattern):
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in DuplicateFinder.MEDIA_EXTENSIONS:
                continue
            try:
                size = entry.stat().st_size
            except OSError:
                continue
            size_map.setdefault(size, []).append(entry)

        # 只对相同大小的文件计算哈希
        hash_map: Dict[str, List[Path]] = {}
        for size, paths in size_map.items():
            if len(paths) < 2:
                continue
            for p in paths:
                try:
                    h = DuplicateFinder._file_hash(p)
                except Exception:
                    continue
                hash_map.setdefault(h, []).append(p)

        # 仅返回有重复的
        return {h: ps for h, ps in hash_map.items() if len(ps) > 1}

    @staticmethod
    def find_and_display(directory: Path, recursive: bool = True) -> int:
        duplicates = DuplicateFinder.find(directory, recursive)
        if not duplicates:
            print(f"\n✓ 未发现重复文件: {directory}")
            return 0

        total_dupes = sum(len(ps) - 1 for ps in duplicates.values())
        print(f"\n发现 {len(duplicates)} 组重复文件，共 {total_dupes} 个冗余文件")
        print(f"{'='*70}")
        waste = 0
        for i, (h, paths) in enumerate(duplicates.items(), 1):
            size = paths[0].stat().st_size
            waste += size * (len(paths) - 1)
            print(f"\n[组 {i}] 哈希: {h[:16]}... ({MediaInfo.format_size(size)} × {len(paths)})")
            for p in paths:
                print(f"  {p}")
        print(f"\n{'='*70}")
        print(f"可释放空间: {MediaInfo.format_size(waste)}")
        return total_dupes


class ConfigBackup:
    """配置备份 - 备份和恢复 mp 配置（zip）"""

    @staticmethod
    def backup(output_path: Optional[Path] = None) -> bool:
        """备份整个 ~/.config/mp 配置目录到 zip"""
        if not CONFIG_DIR.exists():
            print(f"✗ 配置目录不存在: {CONFIG_DIR}")
            return False

        if output_path is None:
            ts = time.strftime('%Y%m%d_%H%M%S')
            output_path = Path.home() / f"mp_config_backup_{ts}.zip"
        elif output_path.is_dir():
            ts = time.strftime('%Y%m%d_%H%M%S')
            output_path = output_path / f"mp_config_backup_{ts}.zip"

        if not output_path.suffix:
            output_path = output_path.with_suffix('.zip')
        elif output_path.suffix.lower() != '.zip':
            output_path = output_path.with_suffix('.zip')

        print(f"备份配置: {CONFIG_DIR} → {output_path}")

        file_count = 0
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in CONFIG_DIR.rglob('*'):
                    if f.is_file():
                        arcname = f.relative_to(CONFIG_DIR)
                        zf.write(f, arcname)
                        file_count += 1
            if file_count == 0:
                print("✗ 配置目录为空，未创建备份")
                if output_path.exists():
                    output_path.unlink()
                return False
            print(f"✓ 备份完成: {output_path.name}")
            print(f"  包含 {file_count} 个文件")
            print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
            return True
        except Exception as e:
            print(f"✗ 备份失败: {e}")
            return False

    @staticmethod
    def restore(input_path: Path) -> bool:
        """从 zip 文件恢复配置"""
        if not input_path.exists():
            print(f"错误: 文件不存在 {input_path}")
            return False

        if input_path.suffix.lower() != '.zip':
            print(f"✗ 仅支持 .zip 备份文件")
            return False

        print(f"恢复配置: {input_path} → {CONFIG_DIR}")

        try:
            with zipfile.ZipFile(input_path, 'r') as zf:
                # 安全检查：阻止 zip slip 攻击
                members = zf.namelist()
                for m in members:
                    target = (CONFIG_DIR / m).resolve()
                    if not str(target).startswith(str(CONFIG_DIR.resolve())):
                        print(f"✗ 检测到非法路径: {m}")
                        return False
                # 确保目录存在
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                zf.extractall(CONFIG_DIR)
            file_count = len(members)
            print(f"✓ 恢复完成: {file_count} 个文件")
            return True
        except Exception as e:
            print(f"✗ 恢复失败: {e}")
            return False


class BatchRenamer:
    """批量重命名 - 基于媒体元数据重命名文件"""

    SUPPORTED_PLACEHOLDERS = ['{title}', '{artist}', '{album}', '{year}', '{track}']

    @staticmethod
    def _sanitize(name: str) -> str:
        """去除文件名中的非法字符"""
        if not name:
            return ''
        for ch in '/\\:*?"<>|':
            name = name.replace(ch, '_')
        return name.strip()

    @staticmethod
    def rename_in_directory(directory: Path, pattern: str = '{artist} - {title}',
                             recursive: bool = False,
                             dry_run: bool = False) -> int:
        """按模式重命名目录中的媒体文件
        pattern 支持占位符: {title} {artist} {album} {year} {track}
        """
        if not directory.exists() or not directory.is_dir():
            print(f"错误: 目录不存在 {directory}")
            return 0

        if not any(ph in pattern for ph in BatchRenamer.SUPPORTED_PLACEHOLDERS):
            print(f"✗ 模式不包含任何占位符")
            print(f"  可用占位符: {', '.join(BatchRenamer.SUPPORTED_PLACEHOLDERS)}")
            return 0

        glob_pattern = '**/*' if recursive else '*'
        count = 0
        skipped = 0
        for entry in directory.glob(glob_pattern):
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in AudioExtractor.VIDEO_EXTENSIONS and \
               entry.suffix.lower() not in AudioConverter.SUPPORTED_FORMATS:
                continue

            info = MediaInfo.get_info(entry)
            title = info.get('title', '') or entry.stem
            artist = info.get('artist', '') or 'Unknown'
            album = info.get('album', '') or ''

            # 从 ffprobe tags 中提取 year 和 track
            year = ''
            track = ''
            try:
                cmd = [
                    'ffprobe', '-v', 'quiet',
                    '-print_format', 'json', '-show_format',
                    str(entry)
                ]
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    tags = data.get('format', {}).get('tags', {})
                    for k in ('date', 'DATE', 'year', 'YEAR'):
                        if k in tags:
                            year = str(tags[k])[:4]
                            break
                    for k in ('track', 'TRACK', 'TRCK'):
                        if k in tags:
                            track = str(tags[k]).split('/')[0]
                            break
            except Exception:
                pass

            new_name = pattern.format(
                title=BatchRenamer._sanitize(title),
                artist=BatchRenamer._sanitize(artist),
                album=BatchRenamer._sanitize(album),
                year=BatchRenamer._sanitize(year),
                track=BatchRenamer._sanitize(track),
            ).strip() or entry.stem

            # 限制文件名长度
            if len(new_name) > 200:
                new_name = new_name[:200]

            new_path = entry.with_name(new_name + entry.suffix)
            if new_path == entry:
                skipped += 1
                continue
            if new_path.exists():
                print(f"  ✗ 跳过（目标已存在）: {entry.name} → {new_path.name}")
                skipped += 1
                continue

            if dry_run:
                print(f"  [DRY] {entry.name} → {new_path.name}")
            else:
                try:
                    entry.rename(new_path)
                    print(f"  ✓ {entry.name} → {new_path.name}")
                except Exception as e:
                    print(f"  ✗ 失败: {entry.name} - {e}")
                    skipped += 1
                    continue
            count += 1

        action = "将重命名" if dry_run else "已重命名"
        print(f"\n{action} {count} 个文件，跳过 {skipped} 个")
        return count


class SpectrogramGenerator:
    """频谱图生成 - 生成音频频谱图图片"""

    @staticmethod
    def generate(file_path: Path, output_path: Optional[Path] = None,
                 start: float = 0.0, duration: Optional[float] = None,
                 size: str = '1024x512') -> bool:
        """生成音频频谱图 PNG"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if output_path is None:
            output_path = file_path.with_suffix('.spectrogram.png')

        print(f"生成频谱图: {file_path.name}")

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning']
        if start > 0:
            cmd.extend(['-ss', str(start)])
        cmd.extend(['-i', str(file_path)])
        if duration is not None:
            cmd.extend(['-t', str(duration)])

        cmd.extend([
            '-lavfi', f'showspectrumpic=s={size}:legend=1:color=intensity',
            '-frames:v', '1',
            str(output_path)
        ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 频谱图已生成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 生成失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


class WaveformGenerator:
    """波形图生成 - 生成音频波形图图片"""

    @staticmethod
    def generate(file_path: Path, output_path: Optional[Path] = None,
                 start: float = 0.0, duration: Optional[float] = None,
                 size: str = '1280x240') -> bool:
        """生成音频波形图 PNG"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if output_path is None:
            output_path = file_path.with_suffix('.waveform.png')

        print(f"生成波形图: {file_path.name}")

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning']
        if start > 0:
            cmd.extend(['-ss', str(start)])
        cmd.extend(['-i', str(file_path)])
        if duration is not None:
            cmd.extend(['-t', str(duration)])

        cmd.extend([
            '-filter_complex',
            f'showwavespic=s={size}:colors=white|0x4a90d2:split_channels=1',
            '-frames:v', '1',
            str(output_path)
        ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 波形图已生成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 生成失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


class CoverExtractor:
    """封面提取 - 从音频/视频文件提取嵌入的封面或海报图片"""

    @staticmethod
    def _find_cover_stream(file_path: Path) -> Optional[int]:
        """查找封面/海报流（abs index），未找到返回 None"""
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams', str(file_path)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return None
            data = json.loads(result.stdout)
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    # 嵌入封面通常是 mjpeg/png 且只有一帧
                    codec = stream.get('codec_name', '')
                    nb_frames = stream.get('nb_frames', '')
                    disposition = stream.get('disposition', {})
                    if disposition.get('attached_pic') == 1 or codec in ('mjpeg', 'png'):
                        return stream.get('index')
                    if nb_frames == '1':
                        return stream.get('index')
        except Exception:
            pass
        return None

    @staticmethod
    def extract(file_path: Path, output_path: Optional[Path] = None) -> bool:
        """提取封面/海报图片"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        stream_index = CoverExtractor._find_cover_stream(file_path)
        if stream_index is None:
            print(f"✗ 未找到嵌入的封面/海报: {file_path.name}")
            return False

        if output_path is None:
            output_path = file_path.with_suffix('.cover.png')

        print(f"提取封面: {file_path.name}")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-map', f'0:{stream_index}',
            '-frames:v', '1',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                print(f"✓ 封面已提取: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 提取失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


class VolumeGain:
    """音量增益 - 以分贝(dB)为单位调整音量"""

    @staticmethod
    def apply(file_path: Path, gain_db: float,
              output_path: Optional[Path] = None) -> bool:
        """对音频应用音量增益"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if gain_db < -60 or gain_db > 30:
            print(f"✗ 增益超出范围 (-60 ~ +30 dB): {gain_db}")
            return False

        if output_path is None:
            sign = 'p' if gain_db >= 0 else 'n'
            output_path = file_path.with_name(
                f"{file_path.stem}_gain{sign}{abs(gain_db):.1f}dB{file_path.suffix}")

        print(f"音量增益: {file_path.name} ({gain_db:+.1f} dB)")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-af', f'volume={gain_db:+.2f}dB',
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_apply(files: List[Path], gain_db: float) -> int:
        """批量应用音量增益"""
        success = 0
        total = len(files)
        print(f"\n批量音量增益: {total} 个文件 ({gain_db:+.1f} dB)")
        print(f"{'='*60}")
        for i, f in enumerate(files, 1):
            print(f"[{i}/{total}] ", end='')
            if VolumeGain.apply(f, gain_db):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success


class RingtoneMaker:
    """铃声生成 - 截取片段并添加淡入淡出，生成铃声"""

    DEFAULT_DURATION = 30.0
    DEFAULT_FADE = 2.0

    @staticmethod
    def make(file_path: Path, start: float = 0.0,
             duration: Optional[float] = None,
             fade: float = 2.0,
             output_path: Optional[Path] = None) -> bool:
        """从媒体文件生成铃声"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        info = MediaInfo.get_info(file_path)
        total = info.get('duration', 0) if isinstance(info, dict) else 0
        if total <= 0:
            print(f"✗ 无法读取文件时长")
            return False

        if duration is None:
            duration = RingtoneMaker.DEFAULT_DURATION
        if start < 0:
            start = 0.0
        if start >= total:
            print(f"✗ 起始时间超出文件时长 ({total:.1f}s)")
            return False
        if start + duration > total:
            duration = total - start

        if output_path is None:
            output_path = file_path.with_name(
                f"{file_path.stem}_ringtone{file_path.suffix}")

        fade_in = min(fade, duration / 2)
        fade_out = min(fade, duration / 2)

        print(f"生成铃声: {file_path.name} [{start:.1f}s +{duration:.1f}s]")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-ss', f'{start:.3f}',
            '-t', f'{duration:.3f}',
            '-i', str(file_path),
            '-af',
            f'afade=t=in:st=0:d={fade_in:.2f},'
            f'afade=t=out:st={duration - fade_out:.2f}:d={fade_out:.2f}',
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 铃声已生成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            # 视频流复制可能因 af 失败，回退重编码
            cmd_fallback = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-ss', f'{start:.3f}',
                '-t', f'{duration:.3f}',
                '-i', str(file_path),
                '-af',
                f'afade=t=in:st=0:d={fade_in:.2f},'
                f'afade=t=out:st={duration - fade_out:.2f}:d={fade_out:.2f}',
                str(output_path)
            ]
            result = subprocess.run(cmd_fallback, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 铃声已生成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


class ChannelConverter:
    """声道转换 - 转换音频声道数"""

    @staticmethod
    def convert(file_path: Path, channels: int,
                output_path: Optional[Path] = None) -> bool:
        """转换音频声道数 (1=单声道, 2=立体声)"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if channels not in (1, 2):
            print(f"✗ 仅支持 1(单声道) 或 2(立体声)，当前: {channels}")
            return False

        if output_path is None:
            label = 'mono' if channels == 1 else 'stereo'
            output_path = file_path.with_name(
                f"{file_path.stem}_{label}{file_path.suffix}")

        label = '单声道' if channels == 1 else '立体声'
        print(f"声道转换: {file_path.name} → {label}")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-ac', str(channels),
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_convert(files: List[Path], channels: int) -> int:
        """批量转换声道数"""
        success = 0
        total = len(files)
        label = '单声道' if channels == 1 else '立体声'
        print(f"\n批量声道转换: {total} 个文件 → {label}")
        print(f"{'='*60}")
        for i, f in enumerate(files, 1):
            print(f"[{i}/{total}] ", end='')
            if ChannelConverter.convert(f, channels):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success


class SampleRateConverter:
    """采样率转换 - 转换音频采样率"""

    COMMON_RATES = [8000, 16000, 22050, 32000, 44100, 48000, 96000, 192000]

    @staticmethod
    def convert(file_path: Path, sample_rate: int,
                output_path: Optional[Path] = None) -> bool:
        """转换音频采样率"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if sample_rate < 1000 or sample_rate > 384000:
            print(f"✗ 采样率超出范围: {sample_rate} Hz")
            return False

        if output_path is None:
            output_path = file_path.with_name(
                f"{file_path.stem}_{sample_rate}Hz{file_path.suffix}")

        print(f"采样率转换: {file_path.name} → {sample_rate} Hz")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-ar', str(sample_rate),
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_convert(files: List[Path], sample_rate: int) -> int:
        """批量转换采样率"""
        success = 0
        total = len(files)
        print(f"\n批量采样率转换: {total} 个文件 → {sample_rate} Hz")
        print(f"{'='*60}")
        for i, f in enumerate(files, 1):
            print(f"[{i}/{total}] ", end='')
            if SampleRateConverter.convert(f, sample_rate):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success


class AVMuxer:
    """音视频合成 - 将音频合并到视频（替换或作为新音轨）"""

    @staticmethod
    def mux(video_path: Path, audio_path: Path,
            output_path: Optional[Path] = None,
            replace: bool = True) -> bool:
        """将音频合并到视频
        replace=True 替换原音轨；False 则同时保留原音轨
        """
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {video_path}")
            return False
        if not audio_path.exists():
            print(f"错误: 音频文件不存在 {audio_path}")
            return False

        if output_path is None:
            output_path = video_path.with_name(
                f"{video_path.stem}_muxed{video_path.suffix}")

        print(f"音视频合成: {video_path.name} + {audio_path.name}")

        if replace:
            # 用新音频替换原音轨，视频流复制
            cmd = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-i', str(video_path),
                '-i', str(audio_path),
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-shortest',
                str(output_path)
            ]
        else:
            # 保留原音轨并加入新音轨
            cmd = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-i', str(video_path),
                '-i', str(audio_path),
                '-map', '0:v:0',
                '-map', '0:a:0?',
                '-map', '1:a:0',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-shortest',
                str(output_path)
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 合成完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


def show_help():
    """显示帮助信息"""
    help_text = """
╔═══════════════════════════════════════════════════════════════╗
║                    mp - Terminal Media Player                 ║
╚═══════════════════════════════════════════════════════════════╝

一个轻量级的终端媒体播放器，支持音频和视频格式。

用法:
    mp [选项] <媒体文件/目录/播放列表>
    mp --info <媒体文件>              显示媒体信息
    mp --playlist <文件列表...>       播放多个文件
    mp --favorites                    播放收藏列表
    mp --history                      显示播放历史

选项:
    -h, --help          显示此帮助信息
    -i, --info          显示媒体文件详细信息
    -p, --playlist      播放列表模式
    -s, --shuffle       随机播放
    -l, --loop          循环模式 (single/all)
    -v, --volume N      设置音量 (0-100)
    --speed N           设置播放速度 (0.5-2.0)
    --favorites         播放收藏列表
    --history           显示播放历史
    --clear-history     清空播放历史
    --stats             显示播放统计
    --clear-stats       清空播放统计
    --convert FMT       转换音频格式 (mp3/wav/ogg/m4a/flac/aac/opus)
    --eq PRESET         使用均衡器预设播放
    --radio NAME        播放网络电台
    --radio-list        显示电台列表
    --radio-add N URL   添加电台
    --radio-del NAME    删除电台
    --browse            打开文件浏览器选择文件
    --noise [TYPE]      播放噪声 (white/pink/brown/rain/ocean)
    --edit-tags FILE    编辑媒体文件元数据
    --record [FILE]     录制麦克风音频 (wav/mp3/ogg/m4a/flac)
    --extract-audio 视频  从视频提取音轨 (默认mp3)
    --to-gif 视频       将视频片段转为GIF动画
    --screenshot 视频   从视频捕获画面帧
    --normalize FILE    音频音量归一化 (loudnorm/dynaudnorm)
    --export-m3u 输出 文件...  导出M3U播放列表
    --import-m3u FILE   导入M3U播放列表并播放
    --library-scan 目录 扫描目录建立媒体库索引
    --library-search 关键词  搜索媒体库
    --library-stats     显示媒体库统计
    --library-clear     清空媒体库
    --trim FILE START [END] 裁剪媒体文件指定时间段
    --merge OUTPUT FILE... 合并多个音频文件
    --reverse FILE...   反向音频（支持批量）
    --fade FILE IN [OUT] 添加淡入淡出效果（秒）
    --reverb [PRESET]   应用混响预设（需要先指定文件）
    --reverb-list       显示混响预设列表
    --extract-subtitles 视频  从视频提取字幕（srt/ass）
    --bpm FILE...       检测音频节拍速度 BPM（支持批量）
    --contact-sheet 视频  生成视频缩略图组合
    --find-duplicates 目录  查找重复媒体文件
    --backup-config [输出] 备份配置到zip
    --restore-config 输入  从zip恢复配置
    --rename PATTERN 目录  按元数据批量重命名文件
    --spectrogram FILE  生成音频频谱图PNG
    --waveform FILE     生成音频波形图PNG
    --cover FILE        提取嵌入的封面/海报图片
    --gain DB FILE...   音量增益(dB)，支持批量
    --ringtone FILE [START [DURATION]]  生成铃声（默认30秒，带淡入淡出）
    --channels N FILE... 转换声道数 1(单声道)/2(立体声)
    --resample RATE FILE... 转换采样率(Hz)
    --mux VIDEO AUDIO   将音频合并到视频（替换原音轨）
    --fade-sec N        铃声淡入淡出时长（秒，默认2.0）

支持格式:
    音频: MP3, WAV, OGG, M4A, FLAC, AAC, OPUS 等
    视频: MP4, MKV, AVI, MOV, WEBM 等

示例:
    mp song.mp3                         # 播放音乐
    mp video.mp4                        # 播放视频（字符渲染）
    mp "music/歌曲.flac"                # 支持带空格的路径
    mp --info song.mp3                  # 显示媒体信息
    mp -p *.mp3                         # 播放所有MP3文件
    mp -p --shuffle *.mp3               # 随机播放所有MP3
    mp -l single song.mp3               # 单曲循环
    mp -v 50 song.mp3                   # 设置50%音量
    mp --speed 1.5 song.mp3             # 1.5倍速播放
    mp ~/Music                          # 播放目录中所有媒体
    mp --favorites                      # 播放收藏列表
    mp --history                        # 查看播放历史
    mp --clear-history                  # 清空播放历史
    mp --stats                          # 查看播放统计
    mp --clear-stats                    # 清空播放统计
    mp --eq rock song.mp3               # 使用摇滚均衡器预设播放
    mp --eq-list                        # 显示均衡器预设列表
    mp --convert mp3 song.flac          # 将FLAC转换为MP3
    mp --convert ogg *.wav              # 批量将WAV转换为OGG
    mp --browse                         # 打开文件浏览器选择文件
    mp --noise rain                     # 播放雨声噪声
    mp --noise                          # 交互式噪声生成器
    mp --edit-tags song.mp3             # 编辑歌曲元数据
    mp --record                         # 交互式录制麦克风音频
    mp --record voice.mp3               # 录制并保存为MP3
    mp --extract-audio video.mp4        # 从视频提取MP3音轨
    mp --extract-audio video.mkv --fmt wav  # 提取为WAV
    mp --to-gif video.mp4               # 视频转GIF（默认前5秒）
    mp --to-gif video.mp4 --gif-start 30 --gif-duration 3
    mp --screenshot video.mp4           # 截取视频开头画面
    mp --screenshot video.mp4 --at 60   # 在60秒处截图
    mp --screenshot video.mp4 --at 90 --count 4  # 批量截图
    mp --normalize song.mp3             # 响度归一化
    mp --normalize *.mp3 --fmt dynaudnorm  # 批量动态归一化
    mp --export-m3u my.m3u *.mp3        # 导出M3U播放列表
    mp --import-m3u playlist.m3u       # 导入并播放M3U
    mp --library-scan ~/Music           # 扫描建立媒体库
    mp --library-search "周杰伦"        # 搜索媒体库
    mp --library-stats                  # 媒体库统计
    mp --trim song.mp3 30 60            # 截取 30-60 秒片段
    mp --trim video.mp4 0 10            # 截取视频前10秒
    mp --merge out.mp3 a.mp3 b.mp3 c.mp3  # 合并三个文件
    mp --reverse song.mp3               # 反向音频
    mp --fade song.mp3 2 3              # 2秒淡入 + 3秒淡出
    mp --reverb hall song.mp3           # 应用音乐厅混响
    mp --reverb-list                    # 显示混响预设
    mp --extract-subtitles movie.mkv    # 提取字幕
    mp --extract-subtitles movie.mkv --fmt ass  # 提取为ASS
    mp --bpm song.mp3                   # 检测BPM
    mp --contact-sheet movie.mp4        # 生成4x4缩略图
    mp --contact-sheet movie.mp4 --rows 3 --cols 5
    mp --find-duplicates ~/Music        # 查找重复音频
    mp --backup-config                  # 备份配置到 ~/mp_config_backup_*.zip
    mp --restore-config backup.zip      # 恢复配置
    mp --rename "{artist} - {title}" ~/Music  # 按元数据重命名
    mp --rename "{track}. {title}" . --dry-run  # 演练模式
    mp --spectrogram song.mp3           # 生成频谱图
    mp --waveform song.mp3              # 生成波形图
    mp --cover song.mp3                 # 提取嵌入封面
    mp --gain 3 song.mp3                # 音量增益 +3dB
    mp --gain -2 *.mp3                  # 批量降低音量
    mp --ringtone song.mp3              # 生成30秒铃声（从头开始）
    mp --ringtone song.mp3 30 20        # 从30秒起截取20秒铃声
    mp --channels 1 song.mp3            # 转为单声道
    mp --channels 2 *.mp3               # 批量转立体声
    mp --resample 44100 song.mp3        # 转换采样率为44100Hz
    mp --mux video.mp4 bgm.mp3          # 用bgm替换视频音轨

播放控制:
    空格键              暂停/继续
    ← 左箭头            后退10秒（仅音频）
    → 右箭头            前进10秒（仅音频）
    ↑ 上箭头            增加音量
    ↓ 下箭头            降低音量
    < 或 ,              降低播放速度（仅音频）
    > 或 .              增加播放速度（仅音频）
    l                   切换循环模式（仅音频）
    i                   显示媒体信息
    n                   下一首（播放列表模式）
    p                   上一首（播放列表模式）
    s                   切换随机播放（播放列表模式）
    q 或 Ctrl+C         退出播放

音频增强功能:
    v                   切换音频可视化器
    b                   保存当前播放位置为书签
    r                   从书签恢复播放
    o                   切换歌词显示（需要同名.lrc文件）
    f                   收藏/取消收藏当前歌曲
    a                   设置AB循环（按两次设置A点和B点）
    t                   设置定时停止（睡眠定时器）
    h                   显示播放历史
    e                   切换均衡器开关
    E                   显示均衡器预设列表
    Q                   显示播放队列
    S                   显示播放统计
    c                   转换当前音频格式
    m                   编辑当前文件元数据
    p/P                 降低/升高音调（半音）
    X                   重置音调
    x                   切换交叉淡入淡出
    F                   打开文件浏览器

提示:
    • 播放器会自动安装ffmpeg和pygame依赖
    • 视频播放使用ASCII字符渲染，需要支持256色的终端
    • 支持带空格的路径，请使用引号括起来
    • 配置保存在 ~/.config/mp/config.json
    • 书签保存在 ~/.config/mp/bookmarks.json
    • 收藏保存在 ~/.config/mp/favorites.json
    • 历史保存在 ~/.config/mp/history.json
    • 媒体库索引保存在 ~/.config/mp/library.json
    • 歌词文件需与音频文件同名（.lrc格式）
    • 录制/转换/截图/归一化/GIF等工具命令无需播放即可独立使用
"""
    print(help_text)


def play_playlist(playlist: Playlist, config: Config, loop: str = 'none'):
    """播放播放列表"""
    if not playlist.files:
        print("播放列表为空")
        return
    
    playlist.display()
    
    current_file = playlist.get_current()
    while current_file:
        file_ext = current_file.suffix.lower()
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}
        
        if file_ext in video_extensions:
            player = VideoPlayer(current_file, config)
        else:
            player = AudioPlayer(current_file, config)
            player.loop_mode = loop
        
        # 设置信号处理
        should_stop = False
        should_next = False
        
        def signal_handler(sig, frame):
            nonlocal should_stop
            should_stop = True
            player.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            player.run()
        except KeyboardInterrupt:
            break
        
        if should_stop:
            break
        
        # 获取下一个文件
        next_file = playlist.next()
        if next_file is None:
            if loop == 'all':
                playlist.current_index = 0
                current_file = playlist.get_current()
            else:
                break
        else:
            current_file = next_file


# --- GitHub 自动更新检查 ---
GITHUB_REPO = "diaoyunxi/media-on-terminal"

def _fetch_latest_version_github():
    """从 GitHub 获取最新版本号（优先 Releases，回退 Tags）"""
    import urllib.request
    import urllib.error

    # 尝试 Releases API
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(url, headers={"User-Agent": "mp-player"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("tag_name"), data.get("html_url")
    except Exception:
        pass

    # 回退到 Tags API
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/tags"
        req = urllib.request.Request(url, headers={"User-Agent": "mp-player"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data:
                tag = data[0].get("name")
                return tag, f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}"
    except Exception:
        pass

    return None, None


def _compare_versions(v1, v2):
    """比较两个版本号"""
    parts1 = v1.lstrip('v').split('.')
    parts2 = v2.lstrip('v').split('.')
    for i in range(max(len(parts1), len(parts2))):
        try:
            a = int(parts1[i]) if i < len(parts1) else 0
            b = int(parts2[i]) if i < len(parts2) else 0
            if a > b:
                return 1
            if a < b:
                return -1
        except ValueError:
            return 0
    return 0


def check_for_update():
    """检查 GitHub 上是否有新版本，如有则询问用户是否更新"""
    try:
        latest, release_url = _fetch_latest_version_github()
        if not latest:
            return

        if _compare_versions(latest, __version__) <= 0:
            return

        print(f"\n{'='*50}")
        print(f"  发现新版本！")
        print(f"  当前版本: v{__version__}")
        print(f"  最新版本: {latest}")
        print(f"{'='*50}")
        print(f"更新内容请查看: {release_url}")

        try:
            choice = input("\n是否立即更新？(y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return

        if choice == 'y':
            print("正在更新...")
            # 尝试 git pull
            script_dir = os.path.dirname(os.path.abspath(__file__))
            if os.path.isdir(os.path.join(script_dir, '.git')):
                result = subprocess.run(
                    ['git', 'pull'],
                    cwd=script_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    print("更新成功！请重新运行程序。")
                    sys.exit(0)
                else:
                    print(f"git pull 失败: {result.stderr}")

            # 回退：下载最新的 mp.py
            try:
                raw_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/mp.py"
                req = urllib.request.Request(raw_url, headers={"User-Agent": "mp-player"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    content = resp.read()
                with open(__file__, 'wb') as f:
                    f.write(content)
                print("更新成功！请重新运行程序。")
                sys.exit(0)
            except Exception as e:
                print(f"自动更新失败: {e}")
                print(f"请手动访问 {release_url} 下载最新版本")
    except Exception as e:
        # 更新检查失败不应影响正常使用
        pass


def main():
    # 处理帮助命令
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        show_help()
        sys.exit(0)
    
    # 检查依赖
    check_and_install_dependencies()
    
    # 解析参数
    parser = argparse.ArgumentParser(
        prog='mp',
        description='Terminal Media Player - 轻量级终端媒体播放器',
        add_help=False
    )
    parser.add_argument('-h', '--help', action='store_true', help='显示帮助信息')
    parser.add_argument('-i', '--info', action='store_true', help='显示媒体信息')
    parser.add_argument('-p', '--playlist', action='store_true', help='播放列表模式')
    parser.add_argument('-s', '--shuffle', action='store_true', help='随机播放')
    parser.add_argument('-l', '--loop', choices=['single', 'all'], help='循环模式')
    parser.add_argument('-v', '--volume', type=int, help='设置音量 (0-100)')
    parser.add_argument('--speed', type=float, help='设置播放速度 (0.5-2.0)')
    parser.add_argument('--favorites', action='store_true', help='播放收藏列表')
    parser.add_argument('--history', action='store_true', help='显示播放历史')
    parser.add_argument('--clear-history', action='store_true', help='清空播放历史')
    parser.add_argument('--stats', action='store_true', help='显示播放统计')
    parser.add_argument('--clear-stats', action='store_true', help='清空播放统计')
    parser.add_argument('--convert', type=str, metavar='FMT', help='转换音频格式 (mp3/wav/ogg/m4a/flac/aac/opus)')
    parser.add_argument('--eq', type=str, metavar='PRESET', help='使用均衡器预设播放')
    parser.add_argument('--eq-list', action='store_true', help='显示均衡器预设列表')
    parser.add_argument('--radio', type=str, help='播放网络电台')
    parser.add_argument('--radio-list', action='store_true', help='显示电台列表')
    parser.add_argument('--radio-add', nargs=2, metavar=('NAME', 'URL'), help='添加电台')
    parser.add_argument('--radio-del', type=str, help='删除电台')
    parser.add_argument('--browse', action='store_true', help='打开文件浏览器选择文件')
    parser.add_argument('--noise', nargs='?', const='interactive', metavar='TYPE', help='播放噪声 (white/pink/brown/rain/ocean)')
    parser.add_argument('--edit-tags', type=str, metavar='FILE', help='编辑媒体文件元数据')
    parser.add_argument('--record', nargs='?', const='interactive', metavar='FILE', help='录制麦克风音频 (wav/mp3/ogg/m4a/flac)')
    parser.add_argument('--extract-audio', metavar='VIDEO', help='从视频提取音轨')
    parser.add_argument('--to-gif', metavar='VIDEO', help='将视频片段转为GIF')
    parser.add_argument('--screenshot', metavar='VIDEO', help='从视频捕获画面帧')
    parser.add_argument('--normalize', action='store_true', help='音频音量归一化')
    parser.add_argument('--export-m3u', metavar='OUTPUT', help='导出M3U播放列表')
    parser.add_argument('--import-m3u', metavar='FILE', help='导入M3U播放列表并播放')
    parser.add_argument('--library-scan', metavar='DIR', help='扫描目录建立媒体库索引')
    parser.add_argument('--library-search', metavar='QUERY', help='搜索媒体库')
    parser.add_argument('--library-stats', action='store_true', help='显示媒体库统计')
    parser.add_argument('--library-clear', action='store_true', help='清空媒体库')
    # 新功能附加参数
    parser.add_argument('--fmt', type=str, default=None, help='指定输出格式 (用于提取/归一化)')
    parser.add_argument('--at', type=float, default=0.0, help='截图时间点（秒）')
    parser.add_argument('--count', type=int, default=1, help='批量截图数量')
    parser.add_argument('--gif-start', type=float, default=0.0, dest='gif_start', help='GIF起始时间（秒）')
    parser.add_argument('--gif-duration', type=float, default=None, dest='gif_duration', help='GIF时长（秒）')
    parser.add_argument('--gif-width', type=int, default=480, dest='gif_width', help='GIF宽度（像素）')
    parser.add_argument('--gif-fps', type=int, default=15, dest='gif_fps', help='GIF帧率')
    # ===== v2.7.0 新增参数 =====
    parser.add_argument('--trim', nargs='+', metavar=('FILE', 'TIME'),
                        help='裁剪媒体文件: --trim FILE START [END]')
    parser.add_argument('--merge', nargs='+', metavar=('OUTPUT', 'FILE'),
                        help='合并音频文件: --merge OUTPUT FILE [FILE...]')
    parser.add_argument('--reverse', action='store_true', help='反向音频（操作 args.files）')
    parser.add_argument('--fade', nargs='+', metavar=('FILE', 'SEC'),
                        help='淡入淡出: --fade FILE IN_SEC [OUT_SEC]')
    parser.add_argument('--reverb', nargs='?', const='__list__', metavar='PRESET',
                        help='应用混响预设（仅指定时列出预设）')
    parser.add_argument('--reverb-list', action='store_true', help='显示混响预设列表')
    parser.add_argument('--extract-subtitles', metavar='VIDEO', dest='extract_subtitles',
                        help='从视频提取字幕')
    parser.add_argument('--bpm', action='store_true', help='检测音频 BPM（操作 args.files）')
    parser.add_argument('--contact-sheet', metavar='VIDEO', dest='contact_sheet',
                        help='生成视频缩略图组合')
    parser.add_argument('--rows', type=int, default=4, help='接触印片行数')
    parser.add_argument('--cols', type=int, default=4, help='接触印片列数')
    parser.add_argument('--find-duplicates', metavar='DIR', dest='find_duplicates',
                        help='查找重复媒体文件')
    parser.add_argument('--backup-config', nargs='?', const='__default__',
                        metavar='OUTPUT', help='备份配置到zip')
    parser.add_argument('--restore-config', metavar='INPUT', dest='restore_config',
                        help='从zip恢复配置')
    parser.add_argument('--rename', nargs=2, metavar=('PATTERN', 'DIR'),
                        help='按元数据批量重命名: --rename PATTERN DIR')
    parser.add_argument('--dry-run', action='store_true', dest='dry_run',
                        help='演练模式（不实际操作）')
    parser.add_argument('--spectrogram', metavar='FILE', help='生成音频频谱图PNG')
    parser.add_argument('--recursive', action='store_true',
                        help='递归处理子目录（用于查找重复/重命名）')
    # ===== v2.8.0 新增参数 =====
    parser.add_argument('--waveform', metavar='FILE', help='生成音频波形图PNG')
    parser.add_argument('--cover', metavar='FILE', help='提取嵌入的封面/海报图片')
    parser.add_argument('--gain', type=float, metavar='DB',
                        help='音量增益(dB)（操作 args.files，支持批量）')
    parser.add_argument('--ringtone', nargs='+', metavar=('FILE', 'START'),
                        help='生成铃声 [--ringtone FILE [START [DURATION]]]')
    parser.add_argument('--channels', type=int, metavar='N',
                        help='转换声道数 1(单声道)/2(立体声)（操作 args.files）')
    parser.add_argument('--resample', type=int, metavar='RATE',
                        help='转换采样率(Hz)（操作 args.files，支持批量）')
    parser.add_argument('--mux', nargs=2, metavar=('VIDEO', 'AUDIO'),
                        help='将音频合并到视频（替换原音轨）')
    parser.add_argument('--fade-sec', type=float, default=2.0, dest='fade_sec',
                        help='铃声淡入淡出时长（秒，默认2.0）')
    parser.add_argument('files', nargs='*', help='媒体文件路径')
    
    args = parser.parse_args()
    
    if args.help:
        show_help()
        sys.exit(0)
    
    # 加载配置
    config = Config()
    
    # 处理收藏播放
    if args.favorites:
        favorites_manager = FavoritesManager()
        fav_files = favorites_manager.get_all()
        if not fav_files:
            print("收藏列表为空")
            sys.exit(0)
        
        print(f"播放收藏列表 ({len(fav_files)} 首)")
        playlist = Playlist()
        for f in fav_files:
            playlist.add_file(f)
        
        if args.shuffle:
            playlist.shuffle()
        
        play_playlist(playlist, config, args.loop or config.get('loop_mode', 'none'))
        sys.exit(0)
    
    # 处理历史记录
    if args.history:
        history_manager = HistoryManager()
        history_manager.display()
        sys.exit(0)
    
    if args.clear_history:
        history_manager = HistoryManager()
        history_manager.clear()
        sys.exit(0)
    
    # 处理统计相关命令
    if args.stats:
        stats_manager = StatisticsManager()
        stats_manager.display()
        sys.exit(0)
    
    if args.clear_stats:
        stats_manager = StatisticsManager()
        stats_manager.clear()
        sys.exit(0)
    
    # 处理均衡器预设列表
    if args.eq_list:
        eq = Equalizer()
        eq.list_presets()
        sys.exit(0)
    
    # 处理电台相关命令
    radio_manager = RadioManager()
    
    if args.radio_list:
        radio_manager.list_stations()
        sys.exit(0)
    
    if args.radio_add:
        name, url = args.radio_add
        radio_manager.add_station(name, url)
        sys.exit(0)
    
    if args.radio_del:
        radio_manager.remove_station(args.radio_del)
        sys.exit(0)
    
    if args.radio:
        url = radio_manager.get_station_url(args.radio)
        if not url:
            print(f"电台不存在: {args.radio}")
            print("使用 'mp --radio-list' 查看可用电台")
            sys.exit(1)
        
        print(f"正在播放电台: {args.radio}")
        print(f"URL: {url}")
        print("按 Ctrl+C 停止播放\n")
        
        # 使用 ffplay 播放流媒体
        cmd = [
            'ffplay',
            '-nodisp',
            '-autoexit',
            '-loglevel', 'quiet',
            '-hide_banner',
            '-volume', str(config.get('volume', 100)),
            url
        ]
        
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n停止播放")
        sys.exit(0)

    # 处理音频转换命令
    if args.convert:
        if not args.files:
            print("错误: 请指定要转换的音频文件")
            sys.exit(1)

        input_files = [Path(f) for f in args.files]
        output_format = args.convert.lower()

        if len(input_files) == 1:
            # 单文件转换
            AudioConverter.convert(input_files[0], output_format)
        else:
            # 批量转换
            AudioConverter.batch_convert(input_files, output_format)
        sys.exit(0)

    # 处理文件浏览器
    if args.browse:
        browser = FileBrowser()
        selected_files = browser.run()
        if not selected_files:
            print("未选择任何文件")
            sys.exit(0)
        
        if len(selected_files) == 1:
            args.files = [str(selected_files[0])]
        else:
            playlist = Playlist()
            for f in selected_files:
                playlist.add_file(f)
            if args.shuffle:
                playlist.shuffle()
            play_playlist(playlist, config, args.loop or config.get('loop_mode', 'none'))
            sys.exit(0)

    # 处理噪声生成器
    if args.noise:
        noise_gen = NoiseGenerator()
        if args.noise == 'interactive':
            noise_gen.run_interactive()
        else:
            noise_gen.set_type(args.noise)
            noise_gen.run_interactive()
        sys.exit(0)

    # 处理元数据编辑
    if args.edit_tags:
        file_path = Path(args.edit_tags)
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.edit_tags}")
            sys.exit(1)
        MetadataEditor.run_interactive(file_path)
        sys.exit(0)

    # ===== v2.5.0 新增功能 =====

    # 音频录制
    if args.record:
        if args.record == 'interactive':
            AudioRecorder.run_interactive()
        else:
            AudioRecorder.record(Path(args.record))
        sys.exit(0)

    # 从视频提取音频
    if args.extract_audio:
        video_path = Path(args.extract_audio)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.extract_audio}")
            sys.exit(1)
        out_format = (args.fmt or 'mp3').lstrip('.')
        if args.files:
            # 多个视频文件批量提取
            video_files = [video_path] + [Path(f) for f in args.files]
            AudioExtractor.batch_extract(video_files, out_format)
        else:
            AudioExtractor.extract(video_path, out_format)
        sys.exit(0)

    # 视频转GIF
    if args.to_gif:
        video_path = Path(args.to_gif)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.to_gif}")
            sys.exit(1)
        GifConverter.convert(
            video_path,
            output_path=None,
            start=args.gif_start,
            duration=args.gif_duration,
            width=args.gif_width,
            fps=args.gif_fps,
        )
        sys.exit(0)

    # 视频截图
    if args.screenshot:
        video_path = Path(args.screenshot)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.screenshot}")
            sys.exit(1)
        if args.count > 1:
            ScreenshotCapture.capture_multi(video_path, args.count)
        else:
            ScreenshotCapture.capture(video_path, args.at)
        sys.exit(0)

    # 音频归一化
    if args.normalize:
        if not args.files:
            print("错误: 请指定要归一化的音频文件")
            sys.exit(1)
        method = (args.fmt or 'loudnorm').lower()
        files = [Path(f) for f in args.files]
        if len(files) == 1:
            AudioNormalizer.normalize(files[0], method)
        else:
            AudioNormalizer.batch_normalize(files, method)
        sys.exit(0)

    # 导出M3U播放列表
    if args.export_m3u:
        if not args.files:
            print("错误: 请指定要导出的媒体文件")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        PlaylistIO.export_m3u(files, Path(args.export_m3u))
        sys.exit(0)

    # 导入M3U播放列表
    if args.import_m3u:
        m3u_path = Path(args.import_m3u)
        if not m3u_path.exists():
            print(f"错误: 文件不存在 {args.import_m3u}")
            sys.exit(1)
        files = PlaylistIO.import_m3u(m3u_path)
        if not files:
            print("播放列表为空")
            sys.exit(0)
        playlist = Playlist()
        for f in files:
            playlist.add_file(f)
        if args.shuffle:
            playlist.shuffle()
        play_playlist(playlist, config, args.loop or config.get('loop_mode', 'none'))
        sys.exit(0)

    # 媒体库扫描
    if args.library_scan:
        library = MediaLibrary()
        library.scan(Path(args.library_scan))
        sys.exit(0)

    # 媒体库搜索
    if args.library_search:
        library = MediaLibrary()
        if not library.library['files']:
            print("媒体库为空，请先使用 'mp --library-scan <目录>' 扫描")
            sys.exit(0)
        results = library.search(args.library_search)
        library.display_results(results)
        sys.exit(0)

    # 媒体库统计
    if args.library_stats:
        library = MediaLibrary()
        library.display_stats()
        sys.exit(0)

    # 清空媒体库
    if args.library_clear:
        library = MediaLibrary()
        library.clear()
        sys.exit(0)

    # ===== v2.7.0 新增命令处理 =====

    # 媒体裁剪
    if args.trim:
        if len(args.trim) < 2:
            print("错误: 用法 --trim FILE START [END]")
            sys.exit(1)
        file_path = Path(args.trim[0])
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.trim[0]}")
            sys.exit(1)
        try:
            start = float(args.trim[1])
        except ValueError:
            print(f"错误: 起始时间无效: {args.trim[1]}")
            sys.exit(1)
        end = None
        if len(args.trim) >= 3:
            try:
                end = float(args.trim[2])
            except ValueError:
                print(f"错误: 结束时间无效: {args.trim[2]}")
                sys.exit(1)
        AudioTrimmer.trim(file_path, start, end)
        sys.exit(0)

    # 音频合并
    if args.merge:
        if len(args.merge) < 3:
            print("错误: 用法 --merge OUTPUT FILE [FILE...]")
            print("至少需要 1 个输出文件 + 2 个输入文件")
            sys.exit(1)
        output_path = Path(args.merge[0])
        input_files = [Path(f) for f in args.merge[1:]]
        output_fmt = args.fmt
        AudioMerger.merge(input_files, output_path, output_fmt)
        sys.exit(0)

    # 反向音频
    if args.reverse:
        if not args.files:
            print("错误: 请指定要反向的音频文件")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        if len(files) == 1:
            AudioReverser.reverse(files[0])
        else:
            AudioReverser.batch_reverse(files)
        sys.exit(0)

    # 淡入淡出
    if args.fade:
        if len(args.fade) < 2:
            print("错误: 用法 --fade FILE IN_SEC [OUT_SEC]")
            sys.exit(1)
        file_path = Path(args.fade[0])
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.fade[0]}")
            sys.exit(1)
        try:
            fade_in = float(args.fade[1])
        except ValueError:
            print(f"错误: 淡入时长无效: {args.fade[1]}")
            sys.exit(1)
        fade_out = 0.0
        if len(args.fade) >= 3:
            try:
                fade_out = float(args.fade[2])
            except ValueError:
                print(f"错误: 淡出时长无效: {args.fade[2]}")
                sys.exit(1)
        # OUT_SEC 也可能来自 --at
        if fade_out == 0.0 and args.at > 0:
            fade_out = args.at
        FadeEffect.apply_fade(file_path, fade_in, fade_out)
        sys.exit(0)

    # 混响预设列表
    if args.reverb_list or args.reverb == '__list__':
        ReverbEffect.list_presets()
        sys.exit(0)

    # 应用混响
    if args.reverb and args.reverb != '__list__':
        if not args.files:
            print("错误: 请指定要应用混响的音频文件")
            sys.exit(1)
        preset = args.reverb
        for f in args.files:
            ReverbEffect.apply_reverb(Path(f), preset)
        sys.exit(0)

    # 提取字幕
    if args.extract_subtitles:
        video_path = Path(args.extract_subtitles)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.extract_subtitles}")
            sys.exit(1)
        out_fmt = (args.fmt or 'srt').lower()
        SubtitleExtractor.extract(video_path, stream_index=None,
                                  output_format=out_fmt)
        sys.exit(0)

    # BPM 检测
    if args.bpm:
        if not args.files:
            print("错误: 请指定要检测的音频文件")
            sys.exit(1)
        for f in args.files:
            BPMDetector.detect_and_display(Path(f))
        sys.exit(0)

    # 视频缩略图组合
    if args.contact_sheet:
        video_path = Path(args.contact_sheet)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.contact_sheet}")
            sys.exit(1)
        ContactSheet.generate(video_path, rows=args.rows, cols=args.cols)
        sys.exit(0)

    # 查找重复文件
    if args.find_duplicates:
        directory = Path(args.find_duplicates)
        DuplicateFinder.find_and_display(directory, recursive=args.recursive)
        sys.exit(0)

    # 备份配置
    if args.backup_config:
        if args.backup_config == '__default__':
            output = None
        else:
            output = Path(args.backup_config)
        ConfigBackup.backup(output)
        sys.exit(0)

    # 恢复配置
    if args.restore_config:
        ConfigBackup.restore(Path(args.restore_config))
        sys.exit(0)

    # 批量重命名
    if args.rename:
        pattern, directory = args.rename
        BatchRenamer.rename_in_directory(
            Path(directory), pattern,
            recursive=args.recursive,
            dry_run=args.dry_run
        )
        sys.exit(0)

    # 频谱图
    if args.spectrogram:
        file_path = Path(args.spectrogram)
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.spectrogram}")
            sys.exit(1)
        duration = args.gif_duration if args.gif_duration is not None else None
        SpectrogramGenerator.generate(file_path,
                                      start=args.at,
                                      duration=duration)
        sys.exit(0)

    # ===== v2.8.0 新增命令处理 =====

    # 波形图
    if args.waveform:
        file_path = Path(args.waveform)
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.waveform}")
            sys.exit(1)
        duration = args.gif_duration if args.gif_duration is not None else None
        WaveformGenerator.generate(file_path,
                                   start=args.at,
                                   duration=duration)
        sys.exit(0)

    # 封面提取
    if args.cover:
        file_path = Path(args.cover)
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.cover}")
            sys.exit(1)
        CoverExtractor.extract(file_path)
        sys.exit(0)

    # 音量增益
    if args.gain is not None:
        if not args.files:
            print("错误: 请指定要调整音量的音频文件")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        if len(files) == 1:
            VolumeGain.apply(files[0], args.gain)
        else:
            VolumeGain.batch_apply(files, args.gain)
        sys.exit(0)

    # 铃声生成
    if args.ringtone:
        if not args.ringtone:
            print("错误: 用法 --ringtone FILE [START [DURATION]]")
            sys.exit(1)
        file_path = Path(args.ringtone[0])
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.ringtone[0]}")
            sys.exit(1)
        start = 0.0
        duration = None
        try:
            if len(args.ringtone) >= 2:
                start = float(args.ringtone[1])
            if len(args.ringtone) >= 3:
                duration = float(args.ringtone[2])
        except ValueError:
            print("错误: START/DURATION 必须为数字（秒）")
            sys.exit(1)
        RingtoneMaker.make(file_path, start=start, duration=duration,
                           fade=args.fade_sec)
        sys.exit(0)

    # 声道转换
    if args.channels is not None:
        if not args.files:
            print("错误: 请指定要转换声道的音频文件")
            sys.exit(1)
        if args.channels not in (1, 2):
            print(f"错误: 声道数仅支持 1(单声道) 或 2(立体声)，当前: {args.channels}")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        if len(files) == 1:
            ChannelConverter.convert(files[0], args.channels)
        else:
            ChannelConverter.batch_convert(files, args.channels)
        sys.exit(0)

    # 采样率转换
    if args.resample is not None:
        if not args.files:
            print("错误: 请指定要转换采样率的音频文件")
            sys.exit(1)
        if args.resample < 1000 or args.resample > 384000:
            print(f"错误: 采样率超出范围 (1000 ~ 384000 Hz): {args.resample}")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        if len(files) == 1:
            SampleRateConverter.convert(files[0], args.resample)
        else:
            SampleRateConverter.batch_convert(files, args.resample)
        sys.exit(0)

    # 音视频合成
    if args.mux:
        video_path = Path(args.mux[0])
        audio_path = Path(args.mux[1])
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.mux[0]}")
            sys.exit(1)
        if not audio_path.exists():
            print(f"错误: 音频文件不存在 {args.mux[1]}")
            sys.exit(1)
        AVMuxer.mux(video_path, audio_path, replace=True)
        sys.exit(0)

    if not args.files:
        print("错误: 请指定要播放的媒体文件")
        print("使用 'mp --help' 查看使用方法")
        sys.exit(1)
    
    # 加载配置
    config = Config()
    
    # 应用命令行参数
    if args.volume is not None:
        config.set('volume', max(0, min(100, args.volume)))
    if args.speed is not None:
        config.set('playback_speed', max(0.5, min(2.0, args.speed)))
    if args.loop:
        config.set('loop_mode', args.loop)
    
    # 媒体信息模式
    if args.info:
        for file_path in args.files:
            path = Path(file_path)
            if path.exists():
                info = MediaInfo.get_info(path)
                MediaInfo.display_info(info)
            else:
                print(f"文件不存在: {file_path}")
        sys.exit(0)
    
    # 检查是否是目录
    paths = [Path(f) for f in args.files]
    first_path = paths[0]
    
    if first_path.is_dir() or args.playlist or len(paths) > 1:
        # 播放列表模式
        playlist = Playlist()
        
        for path in paths:
            if path.is_dir():
                playlist.add_directory(path, recursive=True)
            elif path.exists():
                playlist.add_file(path)
        
        if args.shuffle:
            playlist.shuffle()
        
        play_playlist(playlist, config, args.loop or config.get('loop_mode', 'none'))
    else:
        # 单文件模式
        file_ext = first_path.suffix.lower()
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}
        
        # 创建播放器实例
        if file_ext in video_extensions:
            # 视频文件
            player = VideoPlayer(first_path, config)
            
            # 设置信号处理
            def signal_handler(sig, frame):
                print("\n退出播放")
                player.stop()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            
            # 运行视频播放器
            try:
                player.play()
            except KeyboardInterrupt:
                print("\n退出播放")
                player.stop()
                sys.exit(0)
        else:
            # 音频文件
            player = AudioPlayer(first_path, config)

            # 应用均衡器预设
            if args.eq:
                if player.equalizer.set_preset(args.eq.lower()):
                    player.equalizer.enabled = True
                    print(f"均衡器预设: {args.eq}")
                else:
                    print(f"未知的均衡器预设: {args.eq}")
                    print("使用 'mp --eq-list' 查看可用预设")

            # 设置信号处理
            def signal_handler(sig, frame):
                print("\n退出播放")
                player.stop()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)

            # 运行音频播放器
            try:
                player.run()
            except KeyboardInterrupt:
                print("\n退出播放")
                player.stop()
                sys.exit(0)


if __name__ == "__main__":
    check_for_update()
    main()
