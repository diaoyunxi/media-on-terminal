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
import shutil
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


class VideoPlayer:
    """终端视频播放器 - 使用字符渲染视频帧"""
    
    # ASCII 字符梯度（从暗到亮）
    ASCII_CHARS = '@%#*+=-:. '
    
    def __init__(self, file_path):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            print(f"错误: 文件 '{file_path}' 不存在")
            sys.exit(1)
        
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
            str(self.file_path)
        ]
        
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
        print("\n控制: [空格] 暂停/继续  [q/Ctrl+C] 退出\n")
        
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
                else:
                    if select.select([sys.stdin], [], [], 0)[0]:
                        ch = sys.stdin.read(1)
                        if ch == ' ':
                            self._toggle_pause()
                        elif ch in ('q', 'Q', '\x03'):
                            break
                
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
    mp [选项] <媒体文件>

选项:
    -h, --help          显示此帮助信息

参数:
    <媒体文件>          要播放的音频或视频文件路径

支持格式:
    音频: MP3, WAV, OGG, M4A, FLAC, AAC, OPUS 等
    视频: MP4, MKV, AVI, MOV, WEBM 等

示例:
    mp song.mp3                         # 播放音乐
    mp video.mp4                        # 播放视频（字符渲染）
    mp "music/歌曲.flac"                # 支持带空格的路径

播放控制:
    空格键              暂停/继续
    ← 左箭头            后退10秒（仅音频）
    → 右箭头            前进10秒（仅音频）
    q 或 Ctrl+C         退出播放

提示:
    • 播放器会自动安装ffmpeg和pygame依赖
    • 视频播放使用ASCII字符渲染，需要支持256色的终端
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
    
    # 解析参数
    parser = argparse.ArgumentParser(
        prog='mp',
        description='Terminal Media Player - 轻量级终端媒体播放器',
        add_help=False
    )
    parser.add_argument('-h', '--help', action='store_true', help='显示帮助信息')
    parser.add_argument('file', nargs='?', help='媒体文件路径')
    
    args = parser.parse_args()
    
    if args.help:
        show_help()
        sys.exit(0)
    
    if not args.file:
        print("错误: 请指定要播放的媒体文件")
        print("使用 'mp --help' 查看使用方法")
        sys.exit(1)
    
    # 检测文件类型
    file_ext = Path(args.file).suffix.lower()
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}
    
    # 创建播放器实例
    if file_ext in video_extensions:
        # 视频文件
        player = VideoPlayer(args.file)
        
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
        # 音频文件 - 导入 pygame
        import pygame
        
        player = AudioPlayer(args.file)
        
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
