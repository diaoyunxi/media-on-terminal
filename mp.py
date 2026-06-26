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
from pathlib import Path
from typing import List, Optional, Dict, Any


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
    • 歌词文件需与音频文件同名（.lrc格式）
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
    main()
