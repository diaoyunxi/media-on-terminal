#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可视化与频谱"""

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
from mp.media_info import MediaInfo


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




class SpectrogramGenerator:
    """频谱图生成 - 生成音频频谱图图片"""

    @staticmethod
    def generate(file_path: Path, output_path: Optional[Path] = None,
                 start: float = 0.0, duration: Optional[float] = None,
                 size: str = '1024x512') -> bool:
        """生成音频频谱图 PNG"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if output_path is None:
            output_path = file_path.with_suffix('.spectrogram.png')

        print(f"生成频谱图: {file_path.name}")

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning']
        if start > 0:
            cmd.extend(['-ss', str(start)])
        cmd.extend(['-i', str(file_path)])
        if duration is not None:
            cmd.extend(['-t', str(duration)])

        cmd.extend([
            '-lavfi', f'showspectrumpic=s={size}:legend=1:color=intensity',
            '-frames:v', '1',
            str(output_path)
        ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 频谱图已生成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 生成失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class WaveformGenerator:
    """波形图生成 - 生成音频波形图图片"""

    @staticmethod
    def generate(file_path: Path, output_path: Optional[Path] = None,
                 start: float = 0.0, duration: Optional[float] = None,
                 size: str = '1280x240') -> bool:
        """生成音频波形图 PNG"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if output_path is None:
            output_path = file_path.with_suffix('.waveform.png')

        print(f"生成波形图: {file_path.name}")

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning']
        if start > 0:
            cmd.extend(['-ss', str(start)])
        cmd.extend(['-i', str(file_path)])
        if duration is not None:
            cmd.extend(['-t', str(duration)])

        cmd.extend([
            '-filter_complex',
            f'showwavespic=s={size}:colors=white|0x4a90d2:split_channels=1',
            '-frames:v', '1',
            str(output_path)
        ])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 波形图已生成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 生成失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class CoverExtractor:
    """封面提取 - 从音频/视频文件提取嵌入的封面或海报图片"""

    @staticmethod
    def _find_cover_stream(file_path: Path) -> Optional[int]:
        """查找封面/海报流（abs index），未找到返回 None"""
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams', str(file_path)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return None
            data = json.loads(result.stdout)
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    # 嵌入封面通常是 mjpeg/png 且只有一帧
                    codec = stream.get('codec_name', '')
                    nb_frames = stream.get('nb_frames', '')
                    disposition = stream.get('disposition', {})
                    if disposition.get('attached_pic') == 1 or codec in ('mjpeg', 'png'):
                        return stream.get('index')
                    if nb_frames == '1':
                        return stream.get('index')
        except Exception:
            pass
        return None

    @staticmethod
    def extract(file_path: Path, output_path: Optional[Path] = None) -> bool:
        """提取封面/海报图片"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        stream_index = CoverExtractor._find_cover_stream(file_path)
        if stream_index is None:
            print(f"✗ 未找到嵌入的封面/海报: {file_path.name}")
            return False

        if output_path is None:
            output_path = file_path.with_suffix('.cover.png')

        print(f"提取封面: {file_path.name}")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-map', f'0:{stream_index}',
            '-frames:v', '1',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                print(f"✓ 封面已提取: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 提取失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class AsciiArtExporter:
    """视频 ASCII 艺术导出 - 将视频画面转为 ASCII 文本动画"""

    CHARS = " .:-=+*#%@"  # 由暗到亮 10 级

    @staticmethod
    def export(video_path: Path, output_path: Optional[Path] = None,
               width: int = 80, fps: int = 10,
               max_duration: Optional[float] = None) -> bool:
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return False
        info = MediaInfo.get_info(video_path)
        if info.get('width', 0) == 0:
            print("错误: 不是视频文件")
            return False

        # 字符宽高比约为 1:2，按此保持画面比例
        aspect = info['height'] / info['width']
        height = max(1, int(width * aspect / 2))

        if output_path is None:
            output_path = video_path.with_suffix('.txt')

        vf = (f"fps={fps},scale={width}:{height}:"
              f"force_original_aspect_ratio=decrease,"
              f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=gray")
        cmd = ['ffmpeg', '-y', '-loglevel', 'error',
               '-i', str(video_path)]
        if max_duration:
            cmd += ['-t', str(max_duration)]
        cmd += ['-vf', vf, '-f', 'rawvideo', '-pix_fmt', 'gray', '-']

        print(f"导出 ASCII 艺术: {video_path.name} ({width}x{height} @ {fps}fps)")
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=30)
            if proc.returncode != 0:
                err = proc.stderr.decode(errors='ignore').strip()
                print(f"✗ 失败: {err[:200]}")
                return False
            data = proc.stdout
            frame_size = width * height
            total_frames = len(data) // frame_size
            if total_frames == 0:
                print("✗ 无有效帧数据")
                return False

            chars = AsciiArtExporter.CHARS
            n_chars = len(chars)
            frames_text = []
            for i in range(total_frames):
                frame = data[i * frame_size:(i + 1) * frame_size]
                lines = []
                for y in range(height):
                    row = frame[y * width:(y + 1) * width]
                    line = ''.join(
                        chars[min(n_chars - 1, int(b / 256 * n_chars))]
                        for b in row
                    )
                    lines.append(line)
                frames_text.append('\n'.join(lines))

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# ASCII 艺术动画 - {video_path.name}\n")
                f.write(f"# 分辨率: {width}x{height} @ {fps}fps，共 {total_frames} 帧\n")
                f.write(f"# 播放: 用 less/cat 查看静态帧；动画播放请用原视频\n\n")
                for i, frame in enumerate(frames_text):
                    f.write(f"--- 帧 {i + 1}/{total_frames} ---\n")
                    f.write(frame)
                    f.write('\n\n')

            print(f"✓ 已导出 {total_frames} 帧到 {output_path.name}")
            print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
            return True
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


