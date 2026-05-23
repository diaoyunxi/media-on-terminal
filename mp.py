#!/usr/bin/env python3
"""
Terminal Audio Player - mp
轻量级终端音频播放器
"""

import sys
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import signal
import platform
import subprocess
import argparse
import time
import threading
from pathlib import Path


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


class AudioPlayer:
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            print(f"错误: 文件 '{file_path}' 不存在")
            sys.exit(1)
        
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
        ]
        
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
            elapsed = int((time.time() - start_time) * 1000)
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
        
        status = "▶ 播放中" if not self.is_paused else "⏸ 暂停"
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
        print("\n控制: [空格] 暂停/继续  [←/→] 后退/前进10秒  [q/Ctrl+C] 退出\n")
        
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
                        elif key == b'\xe0':
                            key2 = msvcrt.getch()
                            if key2 == b'K':
                                self.seek(-10000)
                            elif key2 == b'M':
                                self.seek(10000)
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
                            elif ch in ('q', 'Q', '\x03'):
                                break
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception as e:
            print(f"\n控制监听错误: {e}")
        
        self.stop()
        print("\n播放结束")


def show_help():
    """显示帮助信息"""
    help_text = """
╔═══════════════════════════════════════════════════════════════╗
║                    mp - Terminal Audio Player                 ║
╚═══════════════════════════════════════════════════════════════╝

一个轻量级的终端音频播放器，支持多种音频格式。

用法:
    mp [选项] <音频文件>

选项:
    -h, --help          显示此帮助信息

参数:
    <音频文件>          要播放的音频文件路径

支持格式:
    MP3, WAV, OGG, M4A, FLAC, AAC, OPUS 等

示例:
    mp song.mp3                         # 播放音乐
    mp "music/歌曲.flac"                # 支持带空格的路径

播放控制:
    空格键              暂停/继续
    ← 左箭头            后退10秒
    → 右箭头            前进10秒
    q 或 Ctrl+C         退出播放

提示:
    • 播放器会自动安装ffmpeg和pygame依赖
    • 支持带空格的路径，请使用引号括起来
"""
    print(help_text)


def main():
    # 处理帮助命令
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        show_help()
        sys.exit(0)
    
    # 检查依赖
    check_and_install_dependencies()
    
    # 导入 pygame（必须在依赖检查之后）
    import pygame
    
    # 解析参数
    parser = argparse.ArgumentParser(
        prog='mp',
        description='Terminal Audio Player - 轻量级终端音频播放器',
        add_help=False
    )
    parser.add_argument('-h', '--help', action='store_true', help='显示帮助信息')
    parser.add_argument('file', nargs='?', help='音频文件路径')
    
    args = parser.parse_args()
    
    if args.help:
        show_help()
        sys.exit(0)
    
    if not args.file:
        print("错误: 请指定要播放的音频文件")
        print("使用 'mp --help' 查看使用方法")
        sys.exit(1)
    
    # 创建播放器实例
    player = AudioPlayer(args.file)
    
    # 设置信号处理
    def signal_handler(sig, frame):
        print("\n退出播放")
        player.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # 运行播放器
    try:
        player.run()
    except KeyboardInterrupt:
        print("\n退出播放")
        player.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
