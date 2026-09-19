#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""噪声生成器"""

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

        # 注意：subprocess.Popen 不支持 timeout 构造参数，应在 wait()/communicate() 中使用 timeout
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


