#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置管理"""

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
from mp.constants import CONFIG_DIR, CONFIG_FILE
from mp.media_info import MediaInfo


class Config:
    """配置管理类

    优化建议：后续版本可改用 @dataclass 装饰器实现，获得类型安全、
    自动 __repr__、字段默认值管理、frozen（不可变）等优势，
    替代当前基于字典的手动管理方式。
    """
    
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


