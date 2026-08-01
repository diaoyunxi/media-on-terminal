#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音频效果器"""

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

class AudioConverter:
    """音频转换器 - 在不同格式间转换音频文件"""

    SUPPORTED_FORMATS = {
        '.mp3': ['-codec:a', 'libmp3lame', '-b:a', '192k'],
        '.wav': ['-codec:a', 'pcm_s16le'],
        '.ogg': ['-codec:a', 'libvorbis', '-b:a', '192k'],
        '.m4a': ['-codec:a', 'aac', '-b:a', '192k'],
        '.flac': ['-codec:a', 'flac'],
        '.aac': ['-codec:a', 'aac', '-b:a', '192k'],
        '.opus': ['-codec:a', 'libopus', '-b:a', '128k'],
    }

    @staticmethod
    def convert(input_path: Path, output_format: str, output_dir: Optional[Path] = None) -> bool:
        """转换音频格式"""
        if not input_path.exists():
            print(f"错误: 文件不存在 {input_path}")
            return False

        output_format = output_format.lower()
        if not output_format.startswith('.'):
            output_format = '.' + output_format

        if output_format not in AudioConverter.SUPPORTED_FORMATS:
            print(f"不支持的格式: {output_format}")
            print(f"支持的格式: {', '.join(AudioConverter.SUPPORTED_FORMATS.keys())}")
            return False

        # 确定输出路径
        if output_dir:
            output_path = output_dir / (input_path.stem + output_format)
        else:
            output_path = input_path.with_suffix(output_format)

        print(f"转换中: {input_path.name} → {output_path.name}")

        # 构建 ffmpeg 命令
        cmd = [
            'ffmpeg',
            '-i', str(input_path),
            '-y',  # 覆盖输出文件
            '-loglevel', 'quiet',
        ]

        # 添加格式特定参数
        cmd.extend(AudioConverter.SUPPORTED_FORMATS[output_format])
        cmd.append(str(output_path))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print(f"✓ 转换成功: {output_path.name}")
                return True
            else:
                print(f"✗ 转换失败: {result.stderr}")
                return False
        except Exception as e:
            print(f"✗ 转换错误: {e}")
            return False

    @staticmethod
    def batch_convert(input_files: List[Path], output_format: str, output_dir: Optional[Path] = None) -> int:
        """批量转换音频格式"""
        success_count = 0
        total = len(input_files)

        print(f"\n批量转换: {total} 个文件 → {output_format}")
        print(f"{'='*60}")

        for i, input_path in enumerate(input_files, 1):
            print(f"[{i}/{total}] ", end='')
            if AudioConverter.convert(input_path, output_format, output_dir):
                success_count += 1

        print(f"\n{'='*60}")
        print(f"转换完成: {success_count}/{total} 成功")

        return success_count




class Equalizer:
    """均衡器 - 多频段音频均衡控制"""

    # 预设均衡器配置
    PRESETS = {
        'flat': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        'rock': [5, 4, 3, 1, -1, -1, 0, 2, 3, 4],
        'pop': [-1, 0, 2, 4, 4, 3, 1, 0, -1, -2],
        'jazz': [3, 2, 1, 2, -1, -1, 0, 1, 2, 3],
        'classical': [4, 3, 2, 1, -1, -1, 0, 2, 3, 4],
        'bass': [6, 5, 4, 2, 0, -1, -2, -2, -1, 0],
        'treble': [-2, -1, 0, 1, 2, 3, 4, 5, 6, 6],
        'vocal': [-2, -1, 0, 2, 4, 4, 3, 1, 0, -1],
        'electronic': [4, 3, 1, 0, -2, -2, 0, 2, 3, 4],
    }

    # 频段频率
    FREQUENCIES = ['60Hz', '170Hz', '310Hz', '600Hz', '1kHz', '3kHz', '6kHz', '12kHz', '14kHz', '16kHz']

    def __init__(self):
        self.bands = [0] * 10  # 10频段均衡器
        self.enabled = False
        self.current_preset = 'flat'

    def set_preset(self, preset_name: str) -> bool:
        """设置预设"""
        if preset_name in self.PRESETS:
            self.bands = self.PRESETS[preset_name].copy()
            self.current_preset = preset_name
            return True
        return False

    def set_band(self, band_index: int, value: int):
        """设置单个频段"""
        if 0 <= band_index < len(self.bands):
            self.bands[band_index] = max(-12, min(12, value))

    def get_filter_string(self) -> str:
        """获取 ffmpeg 均衡器滤镜字符串"""
        if not self.enabled:
            return ''

        filters = []
        for i, gain in enumerate(self.bands):
            if gain != 0:
                freq = self._get_frequency(i)
                filters.append(f"equalizer=f={freq}:width_type=o:width=1.5:g={gain}")

        return ','.join(filters) if filters else ''

    def _get_frequency(self, band_index: int) -> int:
        """获取频段中心频率"""
        freq_map = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]
        if 0 <= band_index < len(freq_map):
            return freq_map[band_index]
        return 1000

    def display(self):
        """显示均衡器状态"""
        print(f"\n{'='*60}")
        print(f"  均衡器 - {self.current_preset.upper()}")
        print(f"{'='*60}")

        # 显示频段
        for i, (freq, gain) in enumerate(zip(self.FREQUENCIES, self.bands)):
            bar_length = 20
            center = bar_length // 2
            bar = [' '] * bar_length

            if gain > 0:
                for j in range(center, center + gain):
                    if j < bar_length:
                        bar[j] = '█'
            elif gain < 0:
                for j in range(center + gain, center):
                    if j >= 0:
                        bar[j] = '█'

            bar[center] = '┼'
            bar_str = ''.join(bar)
            print(f"  {freq:6s} |{bar_str}| {gain:+2d}dB")

        print(f"{'='*60}\n")

    def toggle(self):
        """切换均衡器开关"""
        self.enabled = not self.enabled
        return self.enabled

    def list_presets(self):
        """列出所有预设"""
        print(f"\n{'='*60}")
        print(f"  均衡器预设")
        print(f"{'='*60}")
        for name in self.PRESETS.keys():
            marker = "▶ " if name == self.current_preset else "  "
            print(f"{marker}{name}")
        print(f"{'='*60}\n")




class CrossfadeManager:
    """交叉淡入淡出管理器 - 在播放列表曲目间平滑过渡"""

    def __init__(self):
        self.enabled = False
        self.duration = 3.0  # 交叉淡入淡出时长（秒）

    def toggle(self) -> bool:
        """切换启用状态"""
        self.enabled = not self.enabled
        return self.enabled

    def set_duration(self, seconds: float):
        """设置淡入淡出时长"""
        self.duration = max(0.5, min(15.0, seconds))

    def get_status(self) -> str:
        """获取状态字符串"""
        if self.enabled:
            return f"🔀 交叉淡入 {self.duration:.1f}s"
        return ""




class PitchControl:
    """音调控制 - 独立于播放速度调整音调"""

    def __init__(self):
        self.semitones = 0.0  # 半音偏移 (-12 to +12)
        self.enabled = False

    def set_semitones(self, value: float):
        """设置半音偏移"""
        self.semitones = max(-12.0, min(12.0, value))
        self.enabled = self.semitones != 0.0

    def adjust(self, delta: float):
        """调整半音"""
        self.set_semitones(self.semitones + delta)

    def get_filter_string(self) -> str:
        """获取 ffmpeg 音调滤镜字符串"""
        if not self.enabled or self.semitones == 0.0:
            return ''
        # 使用 asetrate + aresample 来改变音调
        # 半音到频率比: ratio = 2^(semitones/12)
        ratio = 2 ** (self.semitones / 12.0)
        sample_rate = int(44100 * ratio)
        return f'asetrate=44100*{ratio:.6f},aresample=44100'

    def reset(self):
        """重置音调"""
        self.semitones = 0.0
        self.enabled = False

    def get_status(self) -> str:
        """获取状态字符串"""
        if self.enabled:
            sign = '+' if self.semitones > 0 else ''
            return f"🎵 音调: {sign}{self.semitones:.1f}半音"
        return ""




class FadeEffect:
    """淡入淡出 - 为音频添加淡入和淡出效果"""

    @staticmethod
    def apply_fade(file_path: Path, fade_in: float = 0.0, fade_out: float = 0.0,
                   output_path: Optional[Path] = None) -> bool:
        """添加淡入/淡出效果
        fade_in: 淡入时长（秒）
        fade_out: 淡出时长（秒）
        """
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if fade_in <= 0 and fade_out <= 0:
            print("✗ 请指定淡入或淡出时长（>0）")
            return False

        info = MediaInfo.get_info(file_path)
        duration = info.get('duration', 0) if isinstance(info, dict) else 0
        if duration <= 0:
            print("✗ 无法读取音频时长")
            return False

        if fade_in + fade_out >= duration:
            print(f"✗ 淡入淡出总时长 ({fade_in + fade_out}s) 超过音频时长 ({duration:.2f}s)")
            return False

        if output_path is None:
            output_path = file_path.with_name(f"{file_path.stem}_fade{file_path.suffix}")

        filters = []
        if fade_in > 0:
            filters.append(f"afade=t=in:st=0:d={fade_in:.3f}")
        if fade_out > 0:
            fade_out_start = duration - fade_out
            filters.append(f"afade=t=out:st={fade_out_start:.3f}:d={fade_out:.3f}")

        af = ','.join(filters)
        print(f"淡入淡出: {file_path.name} (in={fade_in}s, out={fade_out}s)")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-af', af,
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 淡入淡出完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class ReverbEffect:
    """混响效果 - 为音频添加混响/回声"""

    PRESETS = {
        'room':       ('房间',       'aecho=0.8:0.9:1000:0.3'),
        'hall':       ('音乐厅',     'aecho=0.8:0.9:2000:0.4'),
        'cathedral':  ('大教堂',     'aecho=0.8:0.9:3000:0.5'),
        'plate':      ('板式混响',   'aecho=0.6:0.7:500:0.4'),
        'spring':     ('弹簧混响',   'aecho=0.5:0.6:200:0.5'),
        'cave':       ('洞穴',       'aecho=0.9:0.95:5000:0.6'),
        'stadium':    ('体育场',     'aecho=0.85:0.92:4000:0.55'),
    }

    @staticmethod
    def list_presets():
        print(f"\n可用混响预设:")
        print(f"{'='*40}")
        for name, (desc, _) in ReverbEffect.PRESETS.items():
            print(f"  {name:12s} - {desc}")
        print(f"{'='*40}\n")

    @staticmethod
    def apply_reverb(file_path: Path, preset: str = 'room',
                     output_path: Optional[Path] = None) -> bool:
        """应用混响预设"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        preset = preset.lower()
        if preset not in ReverbEffect.PRESETS:
            print(f"✗ 未知预设: {preset}")
            print("使用 --reverb-list 查看可用预设")
            return False

        if output_path is None:
            output_path = file_path.with_name(f"{file_path.stem}_{preset}{file_path.suffix}")

        desc, filt = ReverbEffect.PRESETS[preset]
        print(f"混响: {file_path.name} [{preset}] ({desc})")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-af', filt,
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 混响完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class AudioNormalizer:
    """音频归一化 - 统一音频文件的音量水平"""

    METHODS = {
        'loudnorm': 'EBU R128 响度归一化（推荐，-16 LUFS）',
        'dynaudnorm': '动态音频归一化（平滑）',
        'loudnorm_db': '峰值归一化到 0dB',
    }

    @staticmethod
    def normalize(file_path: Path, method: str = 'loudnorm',
                  output_path: Optional[Path] = None) -> bool:
        """归一化音频音量"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        method = method.lower()
        if method not in AudioNormalizer.METHODS:
            print(f"不支持的归一化方法: {method}")
            print("可用方法:")
            for m, desc in AudioNormalizer.METHODS.items():
                print(f"  {m:14s} - {desc}")
            return False

        if output_path is None:
            # 默认输出到同目录，加 _norm 后缀，避免覆盖原文件
            output_path = file_path.with_name(file_path.stem + '_norm' + file_path.suffix)

        if output_path == file_path:
            # 输出到临时文件再替换
            tmp = file_path.with_suffix(file_path.suffix + '.tmp_norm')
        else:
            tmp = output_path

        # 选择滤镜
        if method == 'loudnorm':
            filt = 'loudnorm=I=-16:TP=-1.5:LRA=11'
        elif method == 'dynaudnorm':
            filt = 'dynaudnorm=f=150:g=15:p=0.9'
        else:  # loudnorm_db
            filt = 'loudnorm=I=-23:TP=-2:LRA=7'

        print(f"归一化: {file_path.name} [{method}]")
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-af', filt,
            '-c:v', 'copy',
            str(tmp)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0 or not tmp.exists():
                print(f"✗ 归一化失败: {result.stderr.strip()}")
                if tmp.exists():
                    tmp.unlink()
                return False

            if output_path == file_path:
                tmp.replace(file_path)
                print(f"✓ 已归一化并覆盖原文件: {file_path.name}")
            else:
                print(f"✓ 归一化完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(tmp.stat().st_size)}")
            return True
        except Exception as e:
            if tmp.exists() and output_path != file_path:
                tmp.unlink()
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_normalize(file_paths: List[Path], method: str = 'loudnorm') -> int:
        """批量归一化"""
        success = 0
        total = len(file_paths)
        print(f"\n批量归一化: {total} 个文件 [{method}]")
        print(f"{'='*60}")
        for i, fp in enumerate(file_paths, 1):
            print(f"[{i}/{total}] ", end='')
            if AudioNormalizer.normalize(fp, method):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success




class VolumeGain:
    """音量增益 - 以分贝(dB)为单位调整音量"""

    @staticmethod
    def apply(file_path: Path, gain_db: float,
              output_path: Optional[Path] = None) -> bool:
        """对音频应用音量增益"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if gain_db < -60 or gain_db > 30:
            print(f"✗ 增益超出范围 (-60 ~ +30 dB): {gain_db}")
            return False

        if output_path is None:
            sign = 'p' if gain_db >= 0 else 'n'
            output_path = file_path.with_name(
                f"{file_path.stem}_gain{sign}{abs(gain_db):.1f}dB{file_path.suffix}")

        print(f"音量增益: {file_path.name} ({gain_db:+.1f} dB)")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-af', f'volume={gain_db:+.2f}dB',
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_apply(files: List[Path], gain_db: float) -> int:
        """批量应用音量增益"""
        success = 0
        total = len(files)
        print(f"\n批量音量增益: {total} 个文件 ({gain_db:+.1f} dB)")
        print(f"{'='*60}")
        for i, f in enumerate(files, 1):
            print(f"[{i}/{total}] ", end='')
            if VolumeGain.apply(f, gain_db):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success




class VolumeRamp:
    """音量渐变 - 从起始 dB 线性渐变到结束 dB（渐强/渐弱）"""

    @staticmethod
    def apply(file_path: Path, start_db: float, end_db: float,
              output_path: Optional[Path] = None) -> bool:
        info = MediaInfo.get_info(file_path)
        duration = info.get('duration', 0)
        if duration <= 0:
            print("错误: 无法获取文件时长")
            return False
        if output_path is None:
            tag = (f"ramp{start_db:+.1f}to{end_db:+.1f}"
                   .replace('+', 'p').replace('-', 'n').replace('.', 'd'))
            output_path = file_path.with_name(f"{file_path.stem}_{tag}{file_path.suffix}")

        start_gain = 10 ** (start_db / 20.0)
        end_gain = 10 ** (end_db / 20.0)
        # volume 滤镜按帧求值，线性插值
        af = (f"volume='if(lt(t,{duration}),"
              f"{start_gain}+({end_gain}-{start_gain})*t/{duration},"
              f"{end_gain})':eval=frame")

        has_video = info.get('width', 0) > 0
        cmd = ['ffmpeg', '-y', '-loglevel', 'warning',
               '-i', str(file_path),
               '-af', af]
        if has_video:
            cmd += ['-c:v', 'copy']
        # 根据输出后缀选择合适的音频编码器（复用 AudioConverter 映射）
        audio_args = AudioConverter.SUPPORTED_FORMATS.get(
            output_path.suffix.lower(),
            ['-c:a', 'aac', '-b:a', '192k']
        )
        cmd += audio_args
        cmd.append(str(output_path))

        direction = "渐强" if end_db > start_db else ("渐弱" if end_db < start_db else "恒定")
        print(f"音量{direction}: {start_db:+.1f}dB → {end_db:+.1f}dB ({file_path.name})")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


