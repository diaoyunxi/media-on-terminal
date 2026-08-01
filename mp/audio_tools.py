#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""音频工具集"""

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
from mp.effects import AudioConverter


class AudioRecorder:
    """音频录制器 - 从麦克风录制音频"""

    SUPPORTED_FORMATS = {
        '.wav': ['-c:a', 'pcm_s16le'],
        '.mp3': ['-c:a', 'libmp3lame', '-b:a', '192k'],
        '.ogg': ['-c:a', 'libvorbis', '-b:a', '192k'],
        '.m4a': ['-c:a', 'aac', '-b:a', '192k'],
        '.flac': ['-c:a', 'flac'],
    }

    @staticmethod
    def _find_input_device() -> List[str]:
        """根据平台选择合适的 ffmpeg 音频输入设备"""
        system = platform.system()
        if system == "Linux":
            # 优先使用 pulse，回退到 alsa default
            return ['-f', 'pulse', '-i', 'default']
        elif system == "Darwin":
            # macOS 使用 avfoundation，:0 表示默认音频设备
            return ['-f', 'avfoundation', '-i', ':0']
        else:
            # Windows 使用 dshow（需要用户配置设备名，这里给默认值）
            return ['-f', 'dshow', '-i', 'audio=Microphone']

    @staticmethod
    def record(output_path: Path, duration: Optional[float] = None) -> bool:
        """录制音频到指定文件"""
        ext = output_path.suffix.lower()
        if ext not in AudioRecorder.SUPPORTED_FORMATS:
            print(f"不支持的格式: {ext}")
            print(f"支持的格式: {', '.join(AudioRecorder.SUPPORTED_FORMATS.keys())}")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning']
        cmd.extend(AudioRecorder._find_input_device())
        if duration and duration > 0:
            cmd.extend(['-t', str(duration)])
        cmd.extend(AudioRecorder.SUPPORTED_FORMATS[ext])
        cmd.append(str(output_path))

        print(f"\n{'='*60}")
        print(f"  音频录制")
        print(f"{'='*60}")
        print(f"  输出文件: {output_path}")
        if duration:
            print(f"  录制时长: {MediaInfo.format_duration(duration)}")
        else:
            print(f"  录制时长: 直至按 Ctrl+C 停止")
        print(f"  按 Ctrl+C 停止录制")
        print(f"{'='*60}\n")

        try:
            # 录制为长进程（用户按 Ctrl+C 停止），不设 timeout 避免被中途终止
            subprocess.run(cmd)
            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"\n✓ 录制完成: {output_path}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            else:
                print("\n✗ 录制失败：输出文件为空（请检查麦克风设备）")
                return False
        except KeyboardInterrupt:
            print(f"\n停止录制")
            if output_path.exists():
                print(f"✓ 已保存: {output_path}")
                return True
            return False
        except FileNotFoundError:
            print("✗ 未找到 ffmpeg，请先安装")
            return False
        except Exception as e:
            print(f"✗ 录制错误: {e}")
            return False

    @staticmethod
    def run_interactive(output_path: Optional[Path] = None):
        """交互式录制"""
        if output_path is None:
            print(f"\n音频录制器")
            print(f"{'='*60}")
            name = input("输出文件名 (默认 recording.wav): ").strip()
            if not name:
                name = 'recording.wav'
            if not name.startswith('.'):
                output_path = Path(name)
            else:
                output_path = Path('recording' + name)

        dur_input = input("录制时长（秒，留空则手动停止）: ").strip()
        duration = None
        if dur_input:
            try:
                duration = float(dur_input)
                if duration <= 0:
                    duration = None
            except ValueError:
                print("无效的时长，将手动停止")

        AudioRecorder.record(output_path, duration)




class AudioExtractor:
    """音频提取器 - 从视频文件提取音轨"""

    SUPPORTED_FORMATS = {
        '.mp3': ['-c:a', 'libmp3lame', '-b:a', '192k'],
        '.wav': ['-c:a', 'pcm_s16le'],
        '.ogg': ['-c:a', 'libvorbis', '-b:a', '192k'],
        '.m4a': ['-c:a', 'aac', '-b:a', '192k'],
        '.flac': ['-c:a', 'flac'],
        '.aac': ['-c:a', 'aac', '-b:a', '192k'],
        '.opus': ['-c:a', 'libopus', '-b:a', '128k'],
    }

    VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}

    @staticmethod
    def extract(video_path: Path, output_format: str = 'mp3',
                output_dir: Optional[Path] = None) -> bool:
        """从视频文件提取音频"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False

        ext = video_path.suffix.lower()
        if ext not in AudioExtractor.VIDEO_EXTENSIONS:
            print(f"错误: 不是视频文件: {ext}")
            return False

        output_format = output_format.lower()
        if not output_format.startswith('.'):
            output_format = '.' + output_format
        if output_format not in AudioExtractor.SUPPORTED_FORMATS:
            print(f"不支持的音频格式: {output_format}")
            print(f"支持: {', '.join(AudioExtractor.SUPPORTED_FORMATS.keys())}")
            return False

        if output_dir:
            output_path = output_dir / (video_path.stem + output_format)
        else:
            output_path = video_path.with_suffix(output_format)

        # 如果输出路径与输入相同（视频恰好是 .mp3 等极罕见情况），加后缀
        if output_path == video_path:
            output_path = video_path.with_name(video_path.stem + '_audio' + output_format)

        print(f"提取音频: {video_path.name} → {output_path.name}")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(video_path),
            '-vn',  # 不要视频
        ]
        cmd.extend(AudioExtractor.SUPPORTED_FORMATS[output_format])
        cmd.append(str(output_path))

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 提取成功: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            else:
                print(f"✗ 提取失败: {result.stderr.strip() or '未知错误'}")
                return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_extract(video_files: List[Path], output_format: str = 'mp3') -> int:
        """批量提取音频"""
        success = 0
        total = len(video_files)
        print(f"\n批量提取音频: {total} 个文件 → {output_format}")
        print(f"{'='*60}")
        for i, vf in enumerate(video_files, 1):
            print(f"[{i}/{total}] ", end='')
            if AudioExtractor.extract(vf, output_format):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success




class AudioTrimmer:
    """媒体裁剪 - 提取指定时间范围的音频/视频片段"""

    @staticmethod
    def trim(file_path: Path, start: float, end: Optional[float] = None,
             output_path: Optional[Path] = None) -> bool:
        """裁剪媒体文件，提取 [start, end] 时间段"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        info = MediaInfo.get_info(file_path)
        duration = info.get('duration', 0) if isinstance(info, dict) else 0
        if duration <= 0:
            print(f"✗ 无法读取文件时长")
            return False

        if start < 0 or start >= duration:
            print(f"✗ 起始时间无效: {start}s（文件时长 {duration:.1f}s）")
            return False

        if end is None:
            end = duration
        if end <= start:
            print(f"✗ 结束时间需大于起始时间（start={start}, end={end}）")
            return False
        if end > duration:
            end = duration

        if output_path is None:
            output_path = file_path.with_name(
                f"{file_path.stem}_trim_{int(start)}s-{int(end)}s{file_path.suffix}")

        seg_duration = end - start
        print(f"裁剪: {file_path.name} [{start:.2f}s → {end:.2f}s] (时长 {seg_duration:.2f}s)")

        # 流复制保留原编码，速度快、无损
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-ss', f'{start:.3f}',
            '-to', f'{end:.3f}',
            '-i', str(file_path),
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 裁剪完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            # 流复制失败时回退到重编码
            print(f"  流复制失败，尝试重编码...")
            cmd = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-ss', f'{start:.3f}',
                '-to', f'{end:.3f}',
                '-i', str(file_path),
                str(output_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 裁剪完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 裁剪失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class AudioMerger:
    """音频合并 - 将多个音频文件合并为一个"""

    @staticmethod
    def merge(input_files: List[Path], output_path: Path,
              output_format: Optional[str] = None) -> bool:
        """合并多个音频文件到一个输出文件"""
        if len(input_files) < 2:
            print("错误: 合并至少需要 2 个文件")
            return False

        for f in input_files:
            if not f.exists():
                print(f"错误: 文件不存在 {f}")
                return False

        if output_format is None:
            output_format = output_path.suffix.lstrip('.').lower()
        if not output_format:
            output_format = 'mp3'
            output_path = output_path.with_suffix('.mp3')

        print(f"合并 {len(input_files)} 个文件 → {output_path.name}")
        for i, f in enumerate(input_files, 1):
            print(f"  [{i}/{len(input_files)}] {f.name}")

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning']
        for f in input_files:
            cmd.extend(['-i', str(f)])

        # concat filter：拼接所有音频输入
        filter_inputs = ''.join(f'[{i}:a]' for i in range(len(input_files)))
        filter_complex = f"{filter_inputs}concat=n={len(input_files)}:v=0:a=1[a]"

        # 输出编码参数
        fmt_args = AudioConverter.SUPPORTED_FORMATS.get(f'.{output_format}',
                                                       ['-c:a', 'libmp3lame', '-b:a', '192k'])

        cmd.extend([
            '-filter_complex', filter_complex,
            '-map', '[a]',
        ] + fmt_args + [str(output_path)])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 合并完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 合并失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class AudioReverser:
    """音频反向 - 反转音频播放方向"""

    @staticmethod
    def reverse(file_path: Path, output_path: Optional[Path] = None) -> bool:
        """反转音频播放方向"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if output_path is None:
            output_path = file_path.with_name(f"{file_path.stem}_reversed{file_path.suffix}")

        print(f"反向: {file_path.name}")
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-map', '0:a',
            '-af', 'areverse',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 反向完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 反向失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_reverse(file_paths: List[Path]) -> int:
        success = 0
        total = len(file_paths)
        print(f"\n批量反向: {total} 个文件")
        print(f"{'='*60}")
        for i, fp in enumerate(file_paths, 1):
            print(f"[{i}/{total}] ", end='')
            if AudioReverser.reverse(fp):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success




class ChannelConverter:
    """声道转换 - 转换音频声道数"""

    @staticmethod
    def convert(file_path: Path, channels: int,
                output_path: Optional[Path] = None) -> bool:
        """转换音频声道数 (1=单声道, 2=立体声)"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if channels not in (1, 2):
            print(f"✗ 仅支持 1(单声道) 或 2(立体声)，当前: {channels}")
            return False

        if output_path is None:
            label = 'mono' if channels == 1 else 'stereo'
            output_path = file_path.with_name(
                f"{file_path.stem}_{label}{file_path.suffix}")

        label = '单声道' if channels == 1 else '立体声'
        print(f"声道转换: {file_path.name} → {label}")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-ac', str(channels),
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
    def batch_convert(files: List[Path], channels: int) -> int:
        """批量转换声道数"""
        success = 0
        total = len(files)
        label = '单声道' if channels == 1 else '立体声'
        print(f"\n批量声道转换: {total} 个文件 → {label}")
        print(f"{'='*60}")
        for i, f in enumerate(files, 1):
            print(f"[{i}/{total}] ", end='')
            if ChannelConverter.convert(f, channels):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success




class SampleRateConverter:
    """采样率转换 - 转换音频采样率"""

    COMMON_RATES = [8000, 16000, 22050, 32000, 44100, 48000, 96000, 192000]

    @staticmethod
    def convert(file_path: Path, sample_rate: int,
                output_path: Optional[Path] = None) -> bool:
        """转换音频采样率"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        if sample_rate < 1000 or sample_rate > 384000:
            print(f"✗ 采样率超出范围: {sample_rate} Hz")
            return False

        if output_path is None:
            output_path = file_path.with_name(
                f"{file_path.stem}_{sample_rate}Hz{file_path.suffix}")

        print(f"采样率转换: {file_path.name} → {sample_rate} Hz")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(file_path),
            '-ar', str(sample_rate),
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
    def batch_convert(files: List[Path], sample_rate: int) -> int:
        """批量转换采样率"""
        success = 0
        total = len(files)
        print(f"\n批量采样率转换: {total} 个文件 → {sample_rate} Hz")
        print(f"{'='*60}")
        for i, f in enumerate(files, 1):
            print(f"[{i}/{total}] ", end='')
            if SampleRateConverter.convert(f, sample_rate):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{total} 成功")
        return success




class AVMuxer:
    """音视频合成 - 将音频合并到视频（替换或作为新音轨）"""

    @staticmethod
    def mux(video_path: Path, audio_path: Path,
            output_path: Optional[Path] = None,
            replace: bool = True) -> bool:
        """将音频合并到视频
        replace=True 替换原音轨；False 则同时保留原音轨
        """
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {video_path}")
            return False
        if not audio_path.exists():
            print(f"错误: 音频文件不存在 {audio_path}")
            return False

        if output_path is None:
            output_path = video_path.with_name(
                f"{video_path.stem}_muxed{video_path.suffix}")

        print(f"音视频合成: {video_path.name} + {audio_path.name}")

        if replace:
            # 用新音频替换原音轨，视频流复制
            cmd = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-i', str(video_path),
                '-i', str(audio_path),
                '-map', '0:v:0',
                '-map', '1:a:0',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-shortest',
                str(output_path)
            ]
        else:
            # 保留原音轨并加入新音轨
            cmd = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-i', str(video_path),
                '-i', str(audio_path),
                '-map', '0:v:0',
                '-map', '0:a:0?',
                '-map', '1:a:0',
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-b:a', '192k',
                '-shortest',
                str(output_path)
            ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 合成完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


# ===== v2.9.0 新增功能类 =====



class AudioMixMixer:
    """音频混音 - 将多个音轨混合为一个（音量自动平衡）"""

    @staticmethod
    def mix(input_files: List[Path], output_path: Path,
            output_format: Optional[str] = None) -> bool:
        """混合多个音频文件，使用 amix 滤镜自动归一化音量"""
        if len(input_files) < 2:
            print("错误: 混音至少需要 2 个文件")
            return False
        for f in input_files:
            if not f.exists():
                print(f"错误: 文件不存在 {f}")
                return False
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return False

        # 输出后缀决定编码器
        if output_format:
            suffix = '.' + output_format.lstrip('.').lower()
        else:
            suffix = output_path.suffix.lower()
        codec_args = AudioConverter.SUPPORTED_FORMATS.get(suffix)
        if codec_args is None:
            print(f"错误: 不支持的输出格式 {suffix}")
            print(f"  支持: {', '.join(AudioConverter.SUPPORTED_FORMATS.keys())}")
            return False

        n = len(input_files)
        # amix: inputs=N, duration=longest, dropout_transition=0
        amix_filter = f"[0:a][1:a]amix=inputs={n}:duration=longest:dropout_transition=0[aout]"
        cmd = ['ffmpeg', '-y', '-loglevel', 'warning']
        for f in input_files:
            cmd += ['-i', str(f)]
        cmd += ['-filter_complex', amix_filter,
                '-map', '[aout]']
        cmd += codec_args
        cmd += [str(output_path)]

        print(f"混音: {n} 个文件 → {output_path.name}")
        for i, f in enumerate(input_files, 1):
            print(f"  [{i}/{n}] {f.name}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 混音完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 混音失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class RingtoneMaker:
    """铃声生成 - 截取片段并添加淡入淡出，生成铃声"""

    DEFAULT_DURATION = 30.0
    DEFAULT_FADE = 2.0

    @staticmethod
    def make(file_path: Path, start: float = 0.0,
             duration: Optional[float] = None,
             fade: float = 2.0,
             output_path: Optional[Path] = None) -> bool:
        """从媒体文件生成铃声"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False

        info = MediaInfo.get_info(file_path)
        total = info.get('duration', 0) if isinstance(info, dict) else 0
        if total <= 0:
            print(f"✗ 无法读取文件时长")
            return False

        if duration is None:
            duration = RingtoneMaker.DEFAULT_DURATION
        if start < 0:
            start = 0.0
        if start >= total:
            print(f"✗ 起始时间超出文件时长 ({total:.1f}s)")
            return False
        if start + duration > total:
            duration = total - start

        if output_path is None:
            output_path = file_path.with_name(
                f"{file_path.stem}_ringtone{file_path.suffix}")

        fade_in = min(fade, duration / 2)
        fade_out = min(fade, duration / 2)

        print(f"生成铃声: {file_path.name} [{start:.1f}s +{duration:.1f}s]")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-ss', f'{start:.3f}',
            '-t', f'{duration:.3f}',
            '-i', str(file_path),
            '-af',
            f'afade=t=in:st=0:d={fade_in:.2f},'
            f'afade=t=out:st={duration - fade_out:.2f}:d={fade_out:.2f}',
            '-c:v', 'copy',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 铃声已生成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            # 视频流复制可能因 af 失败，回退重编码
            cmd_fallback = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-ss', f'{start:.3f}',
                '-t', f'{duration:.3f}',
                '-i', str(file_path),
                '-af',
                f'afade=t=in:st=0:d={fade_in:.2f},'
                f'afade=t=out:st={duration - fade_out:.2f}:d={fade_out:.2f}',
                str(output_path)
            ]
            result = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 铃声已生成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


