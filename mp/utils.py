#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具函数与依赖检查"""

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


def _display_width(s: str) -> int:
    """计算字符串在终端中的实际显示宽度

    emoji 和宽字符（中日韩全角）算 2 列，ASCII 算 1 列。
    用于解决含 emoji 的状态行被 [:term_width] 按字符数截断后，
    实际显示宽度仍超过终端宽度导致自动换行的问题。

    修正：对 Block Elements (U+2580-U+259F)、Geometric Shapes (U+25A0-U+25FF)、
    Miscellaneous Technical (U+2300-U+23FF)、Miscellaneous Symbols (U+2600-U+26FF)、
    Dingbats (U+2700-U+27BF) 等终端常显示为双宽的符号统一按 2 列计算；
    变体选择器 (U+FE00-U+FE0F) 按 0 列计算，避免 emoji+变体组合宽度多算。
    """
    width = 0
    for ch in s:
        code = ord(ch)
        if code < 0x80:
            width += 1
        elif 0xFE00 <= code <= 0xFE0F:
            # 变体选择器，零宽
            width += 0
        elif code < 0x3000:
            w = unicodedata.east_asian_width(ch)
            # 全角(W)、全宽(F)、模糊(A)
            if w in ('W', 'F', 'A'):
                width += 2
            elif 0x2580 <= code <= 0x259F or 0x25A0 <= code <= 0x25FF:
                # Block Elements 和 Geometric Shapes
                width += 2
            elif (0x2300 <= code <= 0x23FF or
                  0x2600 <= code <= 0x26FF or
                  0x2700 <= code <= 0x27BF):
                # Miscellaneous Technical / Symbols / Dingbats
                # 包含 ⏸ ⏹ ⏺ ⏏ ⚡ ★ ✨ ❤ 等常用 emoji
                width += 2
            else:
                width += 1
        else:
            # CJK 区段、emoji 等按 2 列处理
            width += 2
    return width




def _truncate_to_width(s: str, max_width: int) -> str:
    """按显示宽度截断字符串，保证截断后实际显示宽度 <= max_width"""
    width = 0
    result = []
    for ch in s:
        code = ord(ch)
        if code < 0x80:
            ch_w = 1
        elif 0xFE00 <= code <= 0xFE0F:
            ch_w = 0
        elif code < 0x3000:
            w = unicodedata.east_asian_width(ch)
            if w in ('W', 'F', 'A'):
                ch_w = 2
            elif 0x2580 <= code <= 0x259F or 0x25A0 <= code <= 0x25FF:
                ch_w = 2
            elif (0x2300 <= code <= 0x23FF or
                  0x2600 <= code <= 0x26FF or
                  0x2700 <= code <= 0x27BF):
                ch_w = 2
            else:
                ch_w = 1
        else:
            ch_w = 2
        if width + ch_w > max_width:
            break
        result.append(ch)
        width += ch_w
    return ''.join(result)

# 路径常量从 constants.py 导入（向后兼容）
from mp.constants import (
    CONFIG_DIR, CONFIG_FILE, PLAYLIST_DIR,
    FAVORITES_FILE, HISTORY_FILE, RADIO_FILE,
    UPDATE_CACHE_FILE,
)




def get_pip_install_args():
    """根据系统返回合适的pip安装参数"""
    system = platform.system()
    if system == "Linux":
        in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
        if not in_venv:
            return ['--break-system-packages']
    return []




def install_system_dependencies():
    """安装系统级依赖（Linux需要）

    安全提示：自动使用 sudo 安装系统依赖存在安全风险，
    此处添加用户确认环节，避免未经授权的特权操作。
    """
    system = platform.system()
    if system == "Linux":
        try:
            if subprocess.run(['which', 'apt'], capture_output=True, timeout=30).returncode == 0:
                # 添加用户确认，避免未经授权自动使用 sudo
                try:
                    confirm = input("即将使用 sudo 安装系统依赖 (libsdl2-2.0-0, libsdl2-mixer-2.0-0)，是否继续？(y/N): ")
                except (EOFError, KeyboardInterrupt):
                    print("已取消安装")
                    return
                if confirm.lower() != 'y':
                    print("已取消安装，部分功能可能不可用")
                    return
                subprocess.run(['sudo', 'apt', 'install', '-y', 'libsdl2-2.0-0', 'libsdl2-mixer-2.0-0'],
                               check=True, timeout=120)
        except subprocess.TimeoutExpired:
            print("系统依赖安装超时")
        except Exception as e:
            print(f"系统依赖安装警告: {e}")




def check_and_install_dependencies():
    """检查并安装Python依赖"""
    if sys.version_info < (3, 8):
        print("错误: 需要Python 3.8或更高版本")
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
            # 不立即退出，让不需要 pygame 的命令仍能使用
            # 真正使用 pygame 时（AudioPlayer 等）会因 ImportError 给出清晰错误
            print("警告: 依赖安装失败，播放/录音/噪声等功能将不可用")
            print(f"  如需使用，请手动安装: pip install {' '.join(pip_args)} {' '.join(missing)}")

    check_ffmpeg()




def check_ffmpeg():
    """检查并安装ffmpeg

    注意：安装失败时不再直接 sys.exit(1)，改为打印警告并返回。
    延迟到实际调用 ffmpeg/ffprobe 时才报错，让 --help、--lyrics 等不依赖
    ffmpeg 的命令仍能正常运行。
    """
    import shutil
    if not shutil.which('ffmpeg'):
        system = platform.system()
        print("未检测到ffmpeg，正在尝试自动安装...")
        
        try:
            if system == "Darwin":
                if shutil.which('brew'):
                    subprocess.run(['brew', 'install', 'ffmpeg'], check=True, timeout=300)
                else:
                    raise Exception("Homebrew未安装")
            elif system == "Linux":
                if shutil.which('apt'):
                    subprocess.run(['sudo', 'apt', 'update'], check=True, timeout=120)
                    subprocess.run(['sudo', 'apt', 'install', '-y', 'ffmpeg'], check=True, timeout=300)
                elif shutil.which('pacman'):
                    subprocess.run(['sudo', 'pacman', '-S', '--noconfirm', 'ffmpeg'], check=True, timeout=300)
                elif shutil.which('dnf'):
                    subprocess.run(['sudo', 'dnf', 'install', '-y', 'ffmpeg'], check=True, timeout=300)
                else:
                    raise Exception("未找到支持的包管理器")
            print("ffmpeg安装完成！")
        except subprocess.TimeoutExpired:
            print("ffmpeg安装超时")
            print("\n请手动安装ffmpeg")
            if system == "Linux":
                print("  sudo apt install ffmpeg  # Debian/Ubuntu")
                print("  sudo pacman -S ffmpeg    # Arch")
            # 延迟检查：不退出，让不依赖 ffmpeg 的命令继续运行
            return
        except Exception as e:
            print(f"ffmpeg安装失败: {e}")
            print("\n请手动安装ffmpeg")
            if system == "Linux":
                print("  sudo apt install ffmpeg  # Debian/Ubuntu")
                print("  sudo pacman -S ffmpeg    # Arch")
            # 延迟检查：不退出，让不依赖 ffmpeg 的命令继续运行
            return


