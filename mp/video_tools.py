#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视频工具集"""

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


class GifConverter:
    """GIF转换器 - 将视频片段转换为GIF动画"""

    @staticmethod
    def convert(video_path: Path, output_path: Optional[Path] = None,
                start: float = 0.0, duration: Optional[float] = None,
                width: int = 480, fps: int = 15) -> bool:
        """将视频片段转为GIF"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False

        if output_path is None:
            output_path = video_path.with_suffix('.gif')

        if duration is None or duration <= 0:
            # 默认截取 5 秒
            duration = 5.0

        # 获取视频信息以确定起始时间合法性
        info = MediaInfo.get_info(video_path)
        total_duration = info.get('duration', 0)
        if total_duration > 0 and start >= total_duration:
            print(f"错误: 起始时间 {start}s 超出视频时长 {MediaInfo.format_duration(total_duration)}")
            return False
        if total_duration > 0 and start + duration > total_duration:
            duration = max(0.1, total_duration - start)
            print(f"提示: 已将时长调整为 {duration:.1f}s 以匹配视频长度")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\n转换 GIF: {video_path.name}")
        print(f"  起始: {start:.1f}s | 时长: {duration:.1f}s | 宽度: {width}px | FPS: {fps}")
        print(f"  输出: {output_path.name}")

        # 使用 ffmpeg 的 palettegen + paletteuse 两步法生成高质量 GIF
        palette_path = output_path.with_suffix('.palette.png')
        try:
            # 步骤1: 生成调色板
            cmd1 = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-ss', str(start), '-t', str(duration),
                '-i', str(video_path),
                '-vf', f'fps={fps},scale={width}:-1:flags=lanczos,palettegen',
                str(palette_path)
            ]
            r1 = subprocess.run(cmd1, capture_output=True, text=True, timeout=30)
            if r1.returncode != 0:
                print(f"✗ 生成调色板失败: {r1.stderr.strip()}")
                return False

            # 步骤2: 应用调色板生成GIF
            cmd2 = [
                'ffmpeg', '-y', '-loglevel', 'warning',
                '-ss', str(start), '-t', str(duration),
                '-i', str(video_path), '-i', str(palette_path),
                '-lavfi', f'fps={fps},scale={width}:-1:flags=lanczos [x]; [x][1:v] paletteuse',
                str(output_path)
            ]
            r2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)

            # 清理调色板
            if palette_path.exists():
                palette_path.unlink()

            if r2.returncode == 0 and output_path.exists():
                print(f"✓ 转换成功: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            else:
                print(f"✗ 转换失败: {r2.stderr.strip()}")
                return False
        except Exception as e:
            if palette_path.exists():
                palette_path.unlink()
            print(f"✗ 错误: {e}")
            return False




class ScreenshotCapture:
    """视频截图 - 从视频捕获指定时间点的画面帧"""

    @staticmethod
    def capture(video_path: Path, timestamp: float = 0.0,
                output_path: Optional[Path] = None) -> bool:
        """捕获指定时间点的视频帧"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False

        if timestamp < 0:
            timestamp = 0.0

        if output_path is None:
            ts_str = f"{int(timestamp // 60):02d}-{int(timestamp % 60):02d}"
            output_path = video_path.with_name(f"{video_path.stem}_shot_{ts_str}.png")

        info = MediaInfo.get_info(video_path)
        total_duration = info.get('duration', 0)
        if total_duration > 0 and timestamp >= total_duration:
            print(f"错误: 时间点 {timestamp}s 超出视频时长 {MediaInfo.format_duration(total_duration)}")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"捕获截图: {video_path.name} @ {MediaInfo.format_duration(timestamp)}")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-ss', str(timestamp),
            '-i', str(video_path),
            '-frames:v', '1',
            '-q:v', '2',  # 高质量
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 截图成功: {output_path.name}")
                if info.get('width'):
                    print(f"  分辨率: {info['width']}x{info['height']}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            else:
                print(f"✗ 截图失败: {result.stderr.strip()}")
                return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def capture_multi(video_path: Path, count: int = 5,
                      output_dir: Optional[Path] = None) -> int:
        """从视频中均匀捕获多张截图"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return 0

        info = MediaInfo.get_info(video_path)
        total = info.get('duration', 0)
        if total <= 0:
            print("✗ 无法获取视频时长")
            return 0

        if count < 1:
            count = 1
        if count == 1:
            ts = total / 2
            return 1 if ScreenshotCapture.capture(video_path, ts, None) else 0

        if output_dir is None:
            output_dir = video_path.parent / f"{video_path.stem}_screenshots"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 在 10% ~ 90% 区间均匀采样
        success = 0
        print(f"\n批量截图: {count} 张")
        print(f"{'='*60}")
        for i in range(count):
            ratio = 0.1 + 0.8 * i / (count - 1)
            ts = total * ratio
            out = output_dir / f"{video_path.stem}_{i+1:02d}.png"
            print(f"[{i+1}/{count}] ", end='')
            if ScreenshotCapture.capture(video_path, ts, out):
                success += 1
        print(f"\n{'='*60}")
        print(f"完成: {success}/{count} 张截图保存到 {output_dir}")
        return success




class VideoConcat:
    """视频拼接 - 将多个视频文件顺序拼接为一个（concat demuxer，要求编码参数一致）"""

    @staticmethod
    def concat(input_files: List[Path], output_path: Path) -> bool:
        """使用 concat demuxer 拼接，要求各文件编码/分辨率/采样率一致"""
        if len(input_files) < 2:
            print("错误: 拼接至少需要 2 个文件")
            return False
        for f in input_files:
            if not f.exists():
                print(f"错误: 文件不存在 {f}")
                return False
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return False

        # 写入 concat 列表文件（使用绝对路径，转义单引号）
        list_fd, list_path = tempfile.mkstemp(suffix='.txt', prefix='mp_concat_')
        try:
            with os.fdopen(list_fd, 'w', encoding='utf-8') as f:
                for fp in input_files:
                    abs_path = str(fp.resolve())
                    # 单引号转义：' -> '\''
                    escaped = abs_path.replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            cmd = ['ffmpeg', '-y', '-loglevel', 'warning',
                   '-f', 'concat', '-safe', '0',
                   '-i', list_path,
                   '-c', 'copy',
                   str(output_path)]

            print(f"拼接: {len(input_files)} 个文件 → {output_path.name}")
            print(f"  （要求各文件编码/分辨率/时基一致，否则需先统一格式）")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 拼接完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            # 流复制失败时提示
            print(f"✗ 流复制拼接失败: {result.stderr.strip()}")
            print(f"  提示: 各文件编码不一致时，请先用 --convert 或 ffmpeg 统一格式后再拼接")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False
        finally:
            try:
                os.unlink(list_path)
            except OSError:
                pass




class VideoScaler:
    """视频缩放 - 改变视频分辨率"""

    @staticmethod
    def scale(video_path: Path, width: int, height: int,
              output_path: Optional[Path] = None,
              keep_aspect: bool = True) -> bool:
        """缩放视频到指定分辨率，默认保持宽高比并填充黑边"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return False
        if width < 16 or width > 7680 or height < 16 or height > 4320:
            print(f"错误: 分辨率超出范围 (16x16 ~ 7680x4320): {width}x{height}")
            return False

        if output_path is None:
            output_path = video_path.with_name(
                f"{video_path.stem}_scaled_{width}x{height}{video_path.suffix}")

        if keep_aspect:
            # 保持宽高比，不足处填充黑边
            vf = (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                  f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2")
        else:
            vf = f"scale={width}:{height}"

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning',
               '-i', str(video_path),
               '-vf', vf,
               '-c:a', 'copy',
               str(output_path)]

        print(f"缩放: {video_path.name} → {width}x{height}"
              f"{' (保持宽高比)' if keep_aspect else ' (强制拉伸)'}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 缩放完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 缩放失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class VideoRotator:
    """视频旋转 - 90/180/270 度旋转"""

    VALID_DEGREES = {90, 180, 270}

    @staticmethod
    def rotate(video_path: Path, degrees: int,
               output_path: Optional[Path] = None) -> bool:
        """旋转视频，90/270 会交换宽高"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return False
        if degrees not in VideoRotator.VALID_DEGREES:
            print(f"错误: 旋转角度必须是 {sorted(VideoRotator.VALID_DEGREES)} 之一")
            return False

        if output_path is None:
            output_path = video_path.with_name(
                f"{video_path.stem}_rot{degrees}{video_path.suffix}")

        # transpose: 1=顺时针90, 2=逆时针90(=顺时针270), 180需两次翻转
        if degrees == 90:
            vf = "transpose=1"
        elif degrees == 270:
            vf = "transpose=2"
        else:  # 180
            vf = "transpose=2,transpose=2"

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning',
               '-i', str(video_path),
               '-vf', vf,
               '-c:a', 'copy',
               str(output_path)]

        print(f"旋转: {video_path.name} → 顺时针 {degrees}°")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 旋转完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 旋转失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class VideoCropper:
    """视频画面裁剪 - 裁取指定矩形区域"""

    @staticmethod
    def crop(video_path: Path, width: int, height: int,
             x: int, y: int,
             output_path: Optional[Path] = None) -> bool:
        """裁剪视频画面，从 (x,y) 起取 width x height 区域"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return False
        if width < 2 or height < 2:
            print(f"错误: 裁剪尺寸过小 (需 ≥2): {width}x{height}")
            return False
        if x < 0 or y < 0:
            print(f"错误: 起点坐标不能为负: ({x},{y})")
            return False

        info = MediaInfo.get_info(video_path)
        src_w = info.get('width', 0) if isinstance(info, dict) else 0
        src_h = info.get('height', 0) if isinstance(info, dict) else 0
        if src_w and src_h:
            if x + width > src_w or y + height > src_h:
                print(f"错误: 裁剪区域超出画面 ({src_w}x{src_h})")
                print(f"  裁剪区: ({x},{y}) + {width}x{height} → 右下角 ({x+width},{y+height})")
                return False

        if output_path is None:
            output_path = video_path.with_name(
                f"{video_path.stem}_crop_{width}x{height}{video_path.suffix}")

        vf = f"crop={width}:{height}:{x}:{y}"
        cmd = ['ffmpeg', '-y', '-loglevel', 'warning',
               '-i', str(video_path),
               '-vf', vf,
               '-c:a', 'copy',
               str(output_path)]

        print(f"裁剪: {video_path.name} 画面 ({x},{y}) + {width}x{height}")
        try:
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




class FpsConverter:
    """视频帧率转换 - 改变视频每秒帧数"""

    @staticmethod
    def convert(video_path: Path, fps: float,
                output_path: Optional[Path] = None) -> bool:
        """通过 fps 滤镜改变视频帧率（插值/丢帧）"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return False
        if fps < 1 or fps > 240:
            print(f"错误: 帧率超出范围 (1 ~ 240): {fps}")
            return False

        if output_path is None:
            # 帧率取整用于文件名
            fps_tag = int(fps) if fps == int(fps) else f"{fps:.2f}".rstrip('0').rstrip('.')
            output_path = video_path.with_name(
                f"{video_path.stem}_{fps_tag}fps{video_path.suffix}")

        vf = f"fps={fps}"
        cmd = ['ffmpeg', '-y', '-loglevel', 'warning',
               '-i', str(video_path),
               '-vf', vf,
               '-c:a', 'copy',
               str(output_path)]

        print(f"帧率转换: {video_path.name} → {fps} fps")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 转换完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 转换失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class ContactSheet:
    """接触印片 - 生成视频缩略图组合"""

    @staticmethod
    def generate(video_path: Path, rows: int = 4, cols: int = 4,
                 output_path: Optional[Path] = None,
                 width: int = 320) -> bool:
        """生成视频缩略图组合"""
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False

        if rows < 1 or cols < 1:
            print("✗ 行列数必须 ≥1")
            return False

        info = MediaInfo.get_info(video_path)
        duration = info.get('duration', 0) if isinstance(info, dict) else 0
        if duration <= 0:
            print("✗ 无法读取视频时长")
            return False

        if output_path is None:
            output_path = video_path.with_suffix('.contact_sheet.png')

        total = rows * cols
        # 在视频 10%-90% 区间均匀采样，避免黑屏开头/结尾
        sample_duration = duration * 0.8
        if sample_duration <= 0:
            print("✗ 视频时长太短")
            return False

        fps = total / sample_duration
        start_time = duration * 0.1

        print(f"生成缩略图组合: {rows}×{cols} = {total} 张 (各 {width}px 宽)")

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-ss', f'{start_time:.3f}',
            '-i', str(video_path),
            '-t', f'{sample_duration:.3f}',
            '-vf', f'fps={fps:.6f},scale={width}:-1,tile={cols}x{rows}',
            '-frames:v', '1',
            '-q:v', '3',
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                print(f"✓ 缩略图组合已生成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 生成失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


