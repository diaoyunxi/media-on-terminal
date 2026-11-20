#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工具函数与依赖检查"""

import sys
import os
# 路径常量从 constants.py 导入（向后兼容）
from mp.constants import (
    CONFIG_DIR, CONFIG_FILE, PLAYLIST_DIR,
    FAVORITES_FILE, HISTORY_FILE, RADIO_FILE,
    UPDATE_CACHE_FILE,
)
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


def _char_display_width(ch: str) -> int:
    """返回单个字符常用的终端显示宽度。

    方块和制表符在主流终端中占 1 列，不能因 East Asian Width 为
    ``A``（宽度模糊）就按 2 列计算，否则进度条宽度及填充都会出错。
    """
    code = ord(ch)
    if code < 0x80:
        return 1
    if 0xFE00 <= code <= 0xFE0F or unicodedata.combining(ch):
        return 0
    if 0x2500 <= code <= 0x259F:
        # Box Drawing (U+2500-U+257F) 和 Block Elements (U+2580-U+259F)
        return 1
    if unicodedata.east_asian_width(ch) in ('W', 'F'):
        return 2
    if code < 0x3000:
        if (0x25A0 <= code <= 0x25FF or 0x2300 <= code <= 0x23FF or
                0x2600 <= code <= 0x26FF or 0x2700 <= code <= 0x27BF):
            # 常用图形符号和 emoji
            return 2
        return 1
    # CJK 区段、emoji 等按 2 列处理
    return 2


def _display_width(s: str) -> int:
    """计算字符串在终端中的常用显示宽度，忽略 ANSI 转义序列。"""
    # 状态行的 ANSI 颜色码不占终端列宽。
    s = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', s)
    return sum(_char_display_width(ch) for ch in s)


def _truncate_to_width(s: str, max_width: int) -> str:
    """按显示宽度截断纯文本，保证截断后显示宽度不超过 max_width。"""
    width = 0
    result = []
    for ch in s:
        ch_w = _char_display_width(ch)
        if width + ch_w > max_width:
            break
        result.append(ch)
        width += ch_w
    return ''.join(result)





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
        cmd = [sys.executable, '-m', 'pip', 'install', *pip_args, *missing]
        
        try:
            subprocess.check_call(cmd, timeout=300)
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


