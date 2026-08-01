#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""媒体文件信息"""

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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
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


