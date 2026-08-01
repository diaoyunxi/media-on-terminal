#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音频/视频播放器"""

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
from mp.media_info import MediaInfo
from mp.managers import BookmarkManager, FavoritesManager, HistoryManager, SleepTimer, ABLoop, RadioManager, QueueManager, StatisticsManager
from mp.effects import Equalizer, CrossfadeManager, PitchControl, AudioConverter
from mp.lyrics import LyricsDisplay
from mp.visual import AudioVisualizer
from mp.metadata import MetadataEditor
from mp.playlist import Playlist

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
        try:
            import pygame
        except ImportError:
            print("错误: pygame 未安装，音频播放功能不可用")
            print("请运行: pip install pygame")
            sys.exit(1)

        # 抑制pygame的欢迎信息（用 try-finally 确保异常时也能恢复 stdout 并关闭 devnull 文件句柄）
        original_stdout = sys.stdout
        devnull_fp = open(os.devnull, 'w')
        sys.stdout = devnull_fp
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        finally:
            sys.stdout = original_stdout
            devnull_fp.close()
        
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

        # 终端显示状态：跟踪上次输出的行数，用于精确清除避免残留
        self._last_display_lines = 0
        self._last_term_width = 0  # 上次终端宽度，用于检测窗口大小变化
        
        self.load_audio()
    
    def get_audio_duration(self):
        """使用ffprobe获取音频时长（秒）"""
        try:
            cmd = [
                'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1', str(self.file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass  # ffprobe 获取时长失败，返回 0（调用方会处理未知时长）
        return 0
    
    def load_audio(self):
        """加载音频文件"""
        print(f"正在加载: {self.file_path.name}")

        duration_sec = self.get_audio_duration()
        if duration_sec == 0:
            print("警告: 无法获取音频时长，将显示为未知时长")
            self.total_duration = 0  # 设为 0 表示未知时长，UI 中标注"未知"
        else:
            self.total_duration = duration_sec * 1000

        print(f"时长: {self.format_time(self.total_duration)}")

        # 本地无歌词时，后台自动在线搜索（不阻塞播放）
        if not self.lyrics.lyrics:
            t = threading.Thread(target=self._auto_search_lyrics_thread, daemon=True)
            t.start()

    def _auto_search_lyrics_thread(self):
        """后台线程：自动在线搜索歌词"""
        try:
            status, msg = self.lyrics.auto_search_online()
            if status == "ok":
                print(f"\n📝 {msg}")
            elif status in ("no_result", "no_timeline", "network_error"):
                # 静默失败，不打扰用户；可按 N 手动重试
                pass
        except Exception as e:
            # 记录异常信息，避免后台线程异常被完全吞掉（便于排查问题）
            # 注意：此处不使用 logging 模块以保持轻量，后续版本可引入 logging 统一管理
            import traceback
            traceback.print_exc()
            print(f"\n⚠️ 歌词后台搜索异常: {e}")

    def _manual_search_lyrics_interactive(self):
        """交互式手动搜索歌词（快捷键 N 触发）

        流程：
        1. 提示输入关键词（默认使用元数据/文件名自动构造）
        2. 显示前5首候选
        3. 用户选择序号应用，并缓存为 .lrc

        注意：调用方（Linux 下）需在调用前恢复终端到正常模式，调用后重新设 raw，
        否则 input() 在 raw 模式下回车不提交会卡死。
        """
        was_paused = self.is_paused
        if not was_paused:
            self.pause()

        try:
            default_kw = LyricsDisplay.build_search_keyword(self.file_path)
            print("\n" + "=" * 60)
            print("  在线搜索歌词")
            print("=" * 60)
            try:
                kw_input = input(f"  搜索关键词 [{default_kw}] (回车使用默认): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  已取消")
                return
            keyword = kw_input or default_kw
            if not keyword:
                print("  关键词为空，已取消")
                return

            print(f"  正在搜索 '{keyword}' ...")
            status, candidates, used = self.lyrics.manual_search_candidates(keyword)
            if status != "ok" or not candidates:
                print(f"  未找到结果（{status}）")
                print("  提示：可尝试简化关键词，如只输入歌名")
                return

            print(f"\n  找到 {len(candidates)} 首候选:")
            for i, (name, artist, source, _) in enumerate(candidates):
                src_label = {"qq": "QQ音乐", "netease": "网易云", "kugou": "酷狗"}.get(source, source)
                print(f"  [{i + 1}] {name} - {artist or '未知'}  ({src_label})")
            print("  [0] 取消")

            try:
                choice = input("\n  选择序号: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  已取消")
                return
            if not choice or choice == "0":
                print("  已取消")
                return
            try:
                idx = int(choice) - 1
            except ValueError:
                print("  无效的序号")
                return

            status, msg = self.lyrics.apply_candidate_by_index(idx, overwrite=True)
            print(f"  {msg}")
            if status == "ok":
                print(f"  共加载 {len(self.lyrics.lyrics)} 行歌词，按 [o] 切换显示")
            print("=" * 60)
        finally:
            # 恢复播放状态：仅当搜索前未暂停，且当前仍处于暂停状态时才恢复
            # 避免搜索期间状态被其他线程改变导致状态反转
            if not was_paused and self.is_paused:
                self.pause()  # 再次切换回播放
    
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
        
        # 使用 subprocess.DEVNULL 替代手动打开的 devnull 文件，避免文件句柄泄漏（Python 3.3+ 内置）
        # 注意：Popen 不支持 timeout 构造参数，进程在 stop() 中通过 wait(timeout=1) 控制超时
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
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
            
            # 注意：Popen 不支持 timeout 构造参数，此进程为持续频谱捕获，由主循环控制生命周期
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
                # 清除最后的进度显示并换行，避免残留
                self._clear_progress_display()
                print()
                break

    def _clear_progress_display(self):
        """清除当前进度显示区域，使光标回到第一行位置。
        适配 display_progress 的多行输出格式（最后一行也换行，光标在下一行行首）。
        """
        n = self._last_display_lines
        if n <= 0:
            return
        # 单行输出时 display_progress 不换行，光标停在当前行末尾，不能上移
        if n == 1:
            sys.stdout.write("\r\033[2K")
            sys.stdout.write("\033[J")
            sys.stdout.flush()
            self._last_display_lines = 0
            return
        # 多行输出时最后一行也换行了，光标在最后一行的下一行行首，上移 n 行到第一行行首
        sys.stdout.write(f"\033[{n}A")
        for i in range(n):
            sys.stdout.write("\r\033[2K")
            if i < n - 1:
                sys.stdout.write("\033[1B")
        # 清除完毕后光标在第 n 行行首，上移回第 1 行
        sys.stdout.write(f"\033[{n - 1}A")
        sys.stdout.write("\033[J")
        sys.stdout.flush()
        self._last_display_lines = 0

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
            status_parts.append(f"⚡ {self.playback_speed:.1f}x")
        
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
            if self.lyrics.online_source == "qq":
                status_parts.append("📝 歌词(QQ)")
            elif self.lyrics.online_source == "netease":
                status_parts.append("📝 歌词(网易云)")
            elif self.lyrics.online_source == "kugou":
                status_parts.append("📝 歌词(酷狗)")
            else:
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
        except Exception:
            term_width = 80  # 非 TTY 环境回退到 80 列

        # 检测终端宽度变化：如果窗口大小变了，之前记录的行数不可靠，
        # 需要清除所有旧行并重置计数
        if self._last_term_width != 0 and self._last_term_width != term_width:
            n = self._last_display_lines
            if n > 0:
                if n > 1:
                    sys.stdout.write(f"\033[{n - 1}A")
                for i in range(n):
                    sys.stdout.write("\r\033[2K")
                    if i < n - 1:
                        sys.stdout.write("\033[1B")
                sys.stdout.write("\r")
                sys.stdout.flush()
            self._last_display_lines = 0
        self._last_term_width = term_width

        # 动态调整 bar 长度，保证整行显示宽度不超过 term_width
        # 注意：█ / ─ 等方块字符显示宽度为 2 列，所以 bar_length 是字符数，
        # 实际显示宽度 = bar_length * 2，必须用 available_for_bar // 2 来计算字符数
        prefix = f"{status} |"
        suffix = f"| {current_time}/{total_time}"
        prefix_w = _display_width(prefix)
        suffix_w = _display_width(suffix)
        # bar 可用显示宽度（列），至少留 10 列给进度条
        available_for_bar = term_width - prefix_w - suffix_w
        # bar 字符数 = 可用列数 // 2（每个方块字符占 2 列），最少 5 格，最多 60 格
        bar_length = max(5, min(60, available_for_bar // 2))
        percent = self.current_position / self.total_duration if self.total_duration > 0 else 0
        filled = int(bar_length * percent)
        bar = '█' * filled + '─' * (bar_length - filled)
        line1 = f"{prefix}{bar}{suffix}"
        # 二次校验：如果实际显示宽度仍超限，再逐格缩短 bar
        while bar_length > 3 and _display_width(line1) > term_width - 2:
            bar_length -= 1
            filled = int(bar_length * percent)
            bar = '█' * filled + '─' * (bar_length - filled)
            line1 = f"{prefix}{bar}{suffix}"

        # 收集本次要输出的所有行（按显示宽度截断，避免自动换行导致行数错乱）
        # 关键：每行截断到 term_width - 3，留 3 列余量，防止内容恰好填满一行时
        # 某些终端自动换行（光标到行尾再写下一字符会换行）
        # 同时给 _display_width 的估算误差留出裕量
        safe_width = max(10, term_width - 3)
        lines = [_truncate_to_width(line1, safe_width)]

        # 可视化器频谱
        if self.visualizer_enabled:
            viz_lines = self.visualizer.render().split('\n')
            for line in viz_lines[-4:]:  # 只显示最后4行
                lines.append(_truncate_to_width("  " + line, safe_width))

        # 歌词当前行：加粗 + 青色，居中显示
        if self.lyrics.enabled and self.lyrics.lyrics:
            current_time_sec = self.current_position / 1000
            current_lyric, _ = self.lyrics.get_lyrics_at_time(current_time_sec)
            if current_lyric:
                # 先截断歌词纯文本到安全宽度，再加 ANSI 码
                # ANSI 码（\033[1;36m / \033[0m）不占显示宽度，无需计入
                truncated = _truncate_to_width(current_lyric, safe_width)
                lyric_w = _display_width(truncated)
                padding = max(0, (safe_width - lyric_w) // 2)
                lines.append(' ' * padding + f"\033[1;36m{truncated}\033[0m")

        # 清除上次输出的所有行（避免终端残留）
        # 关键：必须确保每行实际显示宽度 <= term_width，否则自动换行会让行数对不上
        self._clear_progress_display()

        # 单行情况：使用 \r 强制回到行首 + 空格填充覆盖旧内容，最可靠
        if len(lines) == 1:
            output = f"\r{lines[0]}"
            sys.stdout.write(output)
            # 用空格填充到 term_width，确保旧内容被完全覆盖
            line_w = _display_width(lines[0])
            if line_w < term_width:
                sys.stdout.write(' ' * (term_width - line_w))
            sys.stdout.write("\033[K")  # 清除行尾
            sys.stdout.flush()
            self._last_display_lines = 1
            return

        # 多行情况：每行输出后换行，最后一行也换行（光标停在最后一行的下一行行首）
        # 这样下次刷新时，光标位置 = 上次输出最后一行的下一行，上移 n-1 行即回到第一行
        for i, line in enumerate(lines):
            sys.stdout.write(line)
            sys.stdout.write("\033[K\n")  # 清除行尾 + 换行（最后一行也换行）
        sys.stdout.flush()

        # 记录本次行数，供下次清除
        self._last_display_lines = len(lines)
    
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
            except Exception:
                pass  # 终端属性恢复失败可忽略，不影响后续输入

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
        print("  [v] 可视化器  [b] 保存书签  [r] 恢复书签  [o] 歌词开关  [N] 在线搜索歌词")
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
                        elif key == b'N':
                            # 清除进度显示，避免和交互界面叠加残留
                            self._clear_progress_display()
                            self._manual_search_lyrics_interactive()
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
                            elif ch == 'N':
                                # 先清除进度显示，避免和交互界面叠加残留
                                self._clear_progress_display()
                                # 临时恢复终端到正常模式，否则 input() 在 raw 模式下回车不提交会卡死
                                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                                try:
                                    self._manual_search_lyrics_interactive()
                                finally:
                                    tty.setraw(fd)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception as e:
            print(f"\n控制监听错误: {e}")

        # 退出前清除进度显示，避免残留
        self._clear_progress_display()
        print()

        # 单曲循环：自然播放结束时（非用户主动退出）重新播放
        if self.loop_mode == 'single':
            self.stop()
            print("\n🔁 单曲循环，重新播放...")
            self.run()
            return

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
        except Exception:
            pass  # 书签恢复交互异常时忽略，正常开始播放
        
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
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
                            except Exception:
                                pass  # 帧率解析失败，后续使用默认值
                        
                        # 解析宽度、高度
                        try:
                            self.width = int(parts[1])
                            self.height = int(parts[2])
                        except Exception:
                            pass  # 宽高解析失败，后续使用默认值
                        
                        # 解析时长
                        try:
                            self.duration = float(parts[3])
                        except Exception:
                            try:
                                self.duration = float(parts[4])
                            except Exception:
                                pass  # 时长解析失败，后续使用默认值
                
                if self.fps > 0 and self.duration > 0:
                    self.total_frames = int(self.fps * self.duration)
        except Exception as e:
            print(f"警告: 无法获取视频信息: {e}")
        
        # 默认值：获取失败时使用回退值并提示用户
        info_failed = (self.fps == 0 or self.width == 0 or self.height == 0 or self.duration == 0)
        if info_failed:
            print("提示: 部分视频信息获取失败，将使用默认值（可能影响播放体验）")
        if self.fps == 0:
            self.fps = 25  # 默认 25 fps
        if self.width == 0:
            self.width = 640  # 默认宽度
        if self.height == 0:
            self.height = 480  # 默认高度
        if self.duration == 0:
            self.duration = 0  # 未知时长，保持 0
    
    def _get_terminal_size(self):
        """获取终端尺寸"""
        try:
            size = os.get_terminal_size()
            return size.columns, size.lines
        except Exception:
            return 80, 24  # 非 TTY 环境回退到 80x24
    
    def _pixel_to_char(self, pixel_value):
        """将像素值转换为ASCII字符"""
        index = int(pixel_value * (len(self.ASCII_CHARS) - 1) / 255)
        return self.ASCII_CHARS[index]
    
    def _render_frame(self, frame_data, width, height):
        """渲染一帧到终端

        性能说明：
        此处使用逐像素嵌套循环（O(width*height)）将 RGB 帧数据转换为 ASCII 灰度字符。
        对于较大分辨率（如 200x80 = 16000 像素），每帧需遍历全部像素，
        是视频播放的主要性能瓶颈。

        优化建议（后续版本）：
        1. 使用 numpy 向量化计算：frame_data.reshape(-1,3) 后用矩阵运算批量求灰度，
           可提升 5~10 倍性能。
        2. 添加降采样选项：在 ffmpeg 输出时通过 -vf scale 降低帧分辨率，
           或在渲染前对 frame_data 做步长采样（如每隔 2 像素取一个）。
        3. 预计算灰度→字符的查找表（LUT），避免每次调用 _pixel_to_char 计算索引。
        """
        # 移动到光标起始位置
        sys.stdout.write('\033[H')
        
        # 将帧数据转换为灰度图并渲染
        # 性能瓶颈：逐像素遍历，大分辨率时帧率下降明显
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
        
        # 使用 subprocess.DEVNULL 替代手动打开的 devnull 文件，避免文件句柄泄漏（Python 3.3+ 内置）
        # 注意：Popen 不支持 timeout 构造参数，进程在 stop() 中通过 wait(timeout=1) 控制超时
        self.audio_process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
        
        # 注意：Popen 不支持 timeout 构造参数，此进程为视频帧捕获，由主播放循环控制生命周期
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
                    # 判断是否自然结束（非用户主动退出）
                    if self.loop_mode == 'single':
                        self.stop()
                        print("\n🔁 单曲循环，重新播放...")
                        self.run()
                        return
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
                        elif key in (b'l', b'L'):
                            modes = ['none', 'single', 'all']
                            current_idx = modes.index(self.loop_mode)
                            self.loop_mode = modes[(current_idx + 1) % len(modes)]
                            self.config.set('loop_mode', self.loop_mode)
                            mode_names = {'none': '关闭', 'single': '🔁 单曲', 'all': '🔄 列表'}
                            print(f"\n循环模式: {mode_names.get(self.loop_mode, self.loop_mode)}")
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
                        elif ch in ('l', 'L'):
                            modes = ['none', 'single', 'all']
                            current_idx = modes.index(self.loop_mode)
                            self.loop_mode = modes[(current_idx + 1) % len(modes)]
                            self.config.set('loop_mode', self.loop_mode)
                            mode_names = {'none': '关闭', 'single': '🔁 单曲', 'all': '🔄 列表'}
                            print(f"\n循环模式: {mode_names.get(self.loop_mode, self.loop_mode)}")
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
            except Exception:
                self.ffmpeg_process.kill()  # 等待超时则强制终止
        
        if self.audio_process and self.audio_process.poll() is None:
            self.audio_process.terminate()
            try:
                self.audio_process.wait(timeout=1)
            except Exception:
                self.audio_process.kill()  # 等待超时则强制终止
    
    def format_time(self, ms):
        """格式化时间显示"""
        total_seconds = int(ms // 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"


