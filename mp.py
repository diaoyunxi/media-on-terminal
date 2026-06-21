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
        
        # 播放速度
        if self.playback_speed != 1.0:
            cmd.extend(['-af', f'atempo={self.playback_speed}'])
        
        if position_sec > 0:
            cmd.extend(['-ss', str(position_sec)])
        
        cmd.append(str(self.file_path))
        
        devnull = open(os.devnull, 'w')
        self.process = subprocess.Popen(
            cmd,
            stdout=devnull,
            stderr=devnull,
            stdin=subprocess.DEVNULL
        )
        
        self.current_position = position_sec * 1000
        self.is_playing = True
        self.is_paused = False
        
        self.progress_thread = threading.Thread(target=self.update_progress, daemon=True)
        self.progress_thread.start()
    
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
        
        status = " | ".join(status_parts)
        print(f"\r{status} |{bar}| {current_time}/{total_time}", end='', flush=True)
    
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
        self.is_playing = False
        if self.process and self.process.poll() is None:
            self.process.terminate()
            time.sleep(0.1)
            if self.process.poll() is None:
                self.process.kill()
    
    def run(self):
        """主播放循环"""
        print(f"\n播放: {self.file_path.name}")
        print(f"时长: {self.format_time(self.total_duration)}")
        print("\n控制:")
        print("  [空格] 暂停/继续  [←/→] 后退/前进10秒  [↑/↓] 音量")
        print("  [</>] 播放速度  [l] 循环模式  [i] 媒体信息  [q/Ctrl+C] 退出\n")
        
        self.play_from_position(0)
        
        # 控制监听
        try:
            if platform.system() == "Windows":
                import msvcrt
                while self.is_playing or self.is_paused:
                    if msvcrt.kbhit():
                        key = msvcrt.getch()
                        if key == b' ':
                            self.pause()
                        elif key == b'q' or key == b'Q':
                            break
                        elif key == b'i' or key == b'I':
                            info = MediaInfo.get_info(self.file_path)
                            MediaInfo.display_info(info)
                        elif key == b'l' or key == b'L':
                            self.toggle_loop()
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
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception as e:
            print(f"\n控制监听错误: {e}")
        
        self.stop()
        print("\n播放结束")


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

选项:
    -h, --help          显示此帮助信息
    -i, --info          显示媒体文件详细信息
    -p, --playlist      播放列表模式
    -s, --shuffle       随机播放
    -l, --loop          循环模式 (single/all)
    -v, --volume N      设置音量 (0-100)
    --speed N           设置播放速度 (0.5-2.0)

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

提示:
    • 播放器会自动安装ffmpeg和pygame依赖
    • 视频播放使用ASCII字符渲染，需要支持256色的终端
    • 支持带空格的路径，请使用引号括起来
    • 配置保存在 ~/.config/mp/config.json
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
    parser.add_argument('files', nargs='*', help='媒体文件路径')
    
    args = parser.parse_args()
    
    if args.help:
        show_help()
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
