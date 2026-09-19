#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""元数据编辑"""

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


class MetadataEditor:
    """元数据编辑器 - 编辑媒体文件的标签信息"""

    SUPPORTED_TAGS = {
        '.mp3': {'title': 'title', 'artist': 'artist', 'album': 'album', 'track': 'track', 'genre': 'genre', 'date': 'date'},
        '.m4a': {'title': 'title', 'artist': 'artist', 'album': 'album', 'track': 'track', 'genre': 'genre', 'date': 'date'},
        '.flac': {'title': 'TITLE', 'artist': 'ARTIST', 'album': 'ALBUM', 'track': 'TRACKNUMBER', 'genre': 'GENRE', 'date': 'DATE'},
        '.ogg': {'title': 'TITLE', 'artist': 'ARTIST', 'album': 'ALBUM', 'track': 'TRACKNUMBER', 'genre': 'GENRE', 'date': 'DATE'},
        '.opus': {'title': 'TITLE', 'artist': 'ARTIST', 'album': 'ALBUM', 'track': 'TRACKNUMBER', 'genre': 'GENRE', 'date': 'DATE'},
        '.wav': {'title': 'INAM', 'artist': 'IART', 'album': 'IPRD', 'track': 'ITRK', 'genre': 'IGNR', 'date': 'ICRD'},
    }

    @staticmethod
    def get_tags(file_path: Path) -> Dict[str, str]:
        """获取文件的标签信息"""
        tags = {}
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                fmt_tags = data.get('format', {}).get('tags', {})
                for key, value in fmt_tags.items():
                    tags[key.upper()] = value
        except Exception:
            pass
        return tags

    @staticmethod
    def set_tag(file_path: Path, tag: str, value: str) -> bool:
        """设置单个标签"""
        ext = file_path.suffix.lower()
        if ext not in MetadataEditor.SUPPORTED_TAGS:
            print(f"不支持的格式: {ext}")
            return False

        # 创建临时输出文件
        temp_path = file_path.with_suffix(file_path.suffix + '.tmp')

        cmd = [
            'ffmpeg', '-y', '-i', str(file_path),
            '-codec', 'copy',
            '-metadata', f'{tag}={value}',
            str(temp_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                # 替换原文件
                temp_path.replace(file_path)
                return True
            else:
                if temp_path.exists():
                    temp_path.unlink()
                print(f"设置标签失败: {result.stderr}")
                return False
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            print(f"错误: {e}")
            return False

    @staticmethod
    def display_tags(file_path: Path):
        """显示文件的标签信息"""
        tags = MetadataEditor.get_tags(file_path)

        print(f"\n{'='*60}")
        print(f"  元数据: {file_path.name}")
        print(f"{'='*60}")

        if not tags:
            print("  (无标签信息)")
        else:
            for key, value in sorted(tags.items()):
                # 跳过一些技术性标签
                if key in ('ENCODER', 'MAJOR_BRAND', 'MINOR_VERSION', 'COMPATIBLE_BRANDS'):
                    continue
                print(f"  {key:20s}: {value}")

        print(f"{'='*60}\n")

    @staticmethod
    def run_interactive(file_path: Path):
        """交互式编辑标签"""
        ext = file_path.suffix.lower()
        if ext not in MetadataEditor.SUPPORTED_TAGS:
            print(f"不支持编辑的格式: {ext}")
            print(f"支持的格式: {', '.join(MetadataEditor.SUPPORTED_TAGS.keys())}")
            return

        tag_map = MetadataEditor.SUPPORTED_TAGS[ext]
        current_tags = MetadataEditor.get_tags(file_path)

        print(f"\n编辑元数据: {file_path.name}")
        print(f"{'='*60}")

        tag_names = {
            'title': '标题', 'artist': '艺术家', 'album': '专辑',
            'track': '曲目号', 'genre': '流派', 'date': '日期/年份'
        }

        for i, (tag_key, _) in enumerate(tag_map.items(), 1):
            display_name = tag_names.get(tag_key, tag_key)
            current_value = ''
            # 尝试从现有标签中查找
            for k, v in current_tags.items():
                if k.lower() == tag_key.lower():
                    current_value = v
                    break
            print(f"  {i}. {display_name:8s}: {current_value or '(空)'}")

        print(f"\n输入编号修改 (1-6), 0 取消, q 退出:")

        try:
            choice = input("> ").strip()
            if choice in ('0', 'q', 'Q'):
                return

            idx = int(choice) - 1
            tag_keys = list(tag_map.keys())
            if 0 <= idx < len(tag_keys):
                tag_key = tag_keys[idx]
                display_name = tag_names.get(tag_key, tag_key)
                new_value = input(f"输入新的{display_name}: ").strip()
                if new_value:
                    ffmpeg_tag = tag_map[tag_key]
                    if MetadataEditor.set_tag(file_path, ffmpeg_tag, new_value):
                        print(f"✓ {display_name} 已更新为: {new_value}")
                    else:
                        print("✗ 更新失败")
        except (ValueError, EOFError):
            pass




class BatchRenamer:
    """批量重命名 - 基于媒体元数据重命名文件"""

    SUPPORTED_PLACEHOLDERS = ['{title}', '{artist}', '{album}', '{year}', '{track}']

    @staticmethod
    def _sanitize(name: str) -> str:
        """去除文件名中的非法字符"""
        if not name:
            return ''
        for ch in '/\\:*?"<>|':
            name = name.replace(ch, '_')
        return name.strip()

    @staticmethod
    def rename_in_directory(directory: Path, pattern: str = '{artist} - {title}',
                             recursive: bool = False,
                             dry_run: bool = False) -> int:
        """按模式重命名目录中的媒体文件
        pattern 支持占位符: {title} {artist} {album} {year} {track}
        """
        if not directory.exists() or not directory.is_dir():
            print(f"错误: 目录不存在 {directory}")
            return 0

        if not any(ph in pattern for ph in BatchRenamer.SUPPORTED_PLACEHOLDERS):
            print(f"✗ 模式不包含任何占位符")
            print(f"  可用占位符: {', '.join(BatchRenamer.SUPPORTED_PLACEHOLDERS)}")
            return 0

        glob_pattern = '**/*' if recursive else '*'
        count = 0
        skipped = 0
        for entry in directory.glob(glob_pattern):
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in AudioExtractor.VIDEO_EXTENSIONS and \
               entry.suffix.lower() not in AudioConverter.SUPPORTED_FORMATS:
                continue

            info = MediaInfo.get_info(entry)
            title = info.get('title', '') or entry.stem
            artist = info.get('artist', '') or 'Unknown'
            album = info.get('album', '') or ''

            # 从 ffprobe tags 中提取 year 和 track
            year = ''
            track = ''
            try:
                cmd = [
                    'ffprobe', '-v', 'quiet',
                    '-print_format', 'json', '-show_format',
                    str(entry)
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    tags = data.get('format', {}).get('tags', {})
                    for k in ('date', 'DATE', 'year', 'YEAR'):
                        if k in tags:
                            year = str(tags[k])[:4]
                            break
                    for k in ('track', 'TRACK', 'TRCK'):
                        if k in tags:
                            track = str(tags[k]).split('/')[0]
                            break
            except Exception:
                pass

            new_name = pattern.format(
                title=BatchRenamer._sanitize(title),
                artist=BatchRenamer._sanitize(artist),
                album=BatchRenamer._sanitize(album),
                year=BatchRenamer._sanitize(year),
                track=BatchRenamer._sanitize(track),
            ).strip() or entry.stem

            # 限制文件名长度
            if len(new_name) > 200:
                new_name = new_name[:200]

            new_path = entry.with_name(new_name + entry.suffix)
            if new_path == entry:
                skipped += 1
                continue
            if new_path.exists():
                print(f"  ✗ 跳过（目标已存在）: {entry.name} → {new_path.name}")
                skipped += 1
                continue

            if dry_run:
                print(f"  [DRY] {entry.name} → {new_path.name}")
            else:
                try:
                    entry.rename(new_path)
                    print(f"  ✓ {entry.name} → {new_path.name}")
                except Exception as e:
                    print(f"  ✗ 失败: {entry.name} - {e}")
                    skipped += 1
                    continue
            count += 1

        action = "将重命名" if dry_run else "已重命名"
        print(f"\n{action} {count} 个文件，跳过 {skipped} 个")
        return count




class MetadataStripper:
    """元数据剥离 - 移除媒体文件中的所有元数据（保留音视频流）"""

    @staticmethod
    def strip(file_path: Path,
              output_path: Optional[Path] = None) -> bool:
        """移除所有元数据，流复制保留原编码"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return False

        if output_path is None:
            output_path = file_path.with_name(
                f"{file_path.stem}_clean{file_path.suffix}")

        cmd = ['ffmpeg', '-y', '-loglevel', 'warning',
               '-i', str(file_path),
               '-map_metadata', '-1',
               '-map_chapters', '-1',
               '-c', 'copy',
               str(output_path)]

        print(f"剥离元数据: {file_path.name}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                src_size = file_path.stat().st_size
                dst_size = output_path.stat().st_size
                saved = src_size - dst_size
                print(f"✓ 完成: {output_path.name}")
                print(f"  原始大小: {MediaInfo.format_size(src_size)}")
                print(f"  输出大小: {MediaInfo.format_size(dst_size)}"
                      + (f" (减少 {MediaInfo.format_size(saved)})" if saved > 0 else ""))
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False

    @staticmethod
    def batch_strip(files: List[Path]) -> int:
        """批量剥离元数据，返回成功数"""
        total = len(files)
        success = 0
        print(f"===== 批量剥离元数据: {total} 个文件 =====")
        for i, f in enumerate(files, 1):
            print(f"\n[{i}/{total}] {f.name}")
            if MetadataStripper.strip(f):
                success += 1
        print(f"\n===== 完成: {success}/{total} 成功 =====")
        return success




class BPMDetector:
    """BPM 检测 - 通过自相关检测音频节拍速度"""

    MIN_BPM = 60
    MAX_BPM = 200

    @staticmethod
    def detect(file_path: Path) -> Optional[float]:
        """检测音频 BPM（每分钟节拍数）"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return None

        # 提取为单声道 8kHz 16-bit PCM
        cmd = [
            'ffmpeg', '-y', '-loglevel', 'quiet',
            '-i', str(file_path),
            '-ac', '1', '-ar', '8000',
            '-f', 's16le', '-'
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode != 0 or not result.stdout:
                print("✗ 无法读取音频数据")
                return None

            data = result.stdout
            n_samples = len(data) // 2
            if n_samples < 8000:
                print("✗ 音频太短，无法检测")
                return None

            samples = struct.unpack(f'<{n_samples}h', data)

            # 计算能量包络（每 128 样本一个能量值，约 16ms）
            window = 128
            energy = []
            for i in range(0, len(samples) - window, window):
                e = sum(s * s for s in samples[i:i + window]) / window
                energy.append(e)

            if not energy:
                return None

            # 去除直流分量
            avg = sum(energy) / len(energy)
            energy = [e - avg for e in energy]

            # 能量采样率
            energy_rate = 8000.0 / window  # ~62.5 Hz
            min_lag = max(1, int(60 * energy_rate / BPMDetector.MAX_BPM))
            max_lag = int(60 * energy_rate / BPMDetector.MIN_BPM)
            max_lag = min(max_lag, len(energy) - 1)

            best_lag = 0
            best_corr = -1.0
            for lag in range(min_lag, max_lag + 1):
                if lag >= len(energy):
                    break
                corr = 0.0
                for i in range(len(energy) - lag):
                    corr += energy[i] * energy[i + lag]
                if corr > best_corr:
                    best_corr = corr
                    best_lag = lag

            if best_lag == 0:
                return None

            bpm = 60.0 * energy_rate / best_lag
            return round(bpm, 1)
        except Exception as e:
            print(f"✗ 检测失败: {e}")
            return None

    @staticmethod
    def detect_and_display(file_path: Path):
        print(f"\n分析: {file_path.name}")
        print(f"{'='*50}")
        bpm = BPMDetector.detect(file_path)
        if bpm is not None:
            print(f"  BPM: {bpm}")
            if bpm < 70:
                desc = "慢板（缓慢抒情）"
            elif bpm < 90:
                desc = "中慢板"
            elif bpm < 110:
                desc = "中板"
            elif bpm < 130:
                desc = "中快板"
            elif bpm < 160:
                desc = "快板（流行/摇滚节奏）"
            else:
                desc = "极快板（电子/舞曲）"
            print(f"  速度: {desc}")
        print(f"{'='*50}")




class SubtitleExtractor:
    """字幕提取 - 从视频文件提取字幕轨道"""

    @staticmethod
    def list_streams(video_path: Path) -> List[Dict[str, Any]]:
        """列出视频中所有字幕流"""
        cmd = [
            'ffprobe', '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams', '-select_streams', 's',
            str(video_path)
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return data.get('streams', [])
        except Exception:
            pass
        return []

    @staticmethod
    def extract(video_path: Path, stream_index: Optional[int] = None,
                output_format: str = 'srt',
                output_path: Optional[Path] = None) -> bool:
        """从视频提取字幕
        stream_index: 字幕流索引（0-based），None 表示第一个字幕流
        output_format: srt 或 ass
        """
        if not video_path.exists():
            print(f"错误: 文件不存在 {video_path}")
            return False

        streams = SubtitleExtractor.list_streams(video_path)
        if not streams:
            print(f"✗ 未找到字幕轨道: {video_path.name}")
            return False

        if stream_index is None:
            stream_index = 0
        if stream_index >= len(streams):
            print(f"✗ 字幕流索引超出范围 (0-{len(streams)-1})")
            return False

        stream = streams[stream_index]
        # ffprobe 返回的 index 是绝对索引（包含视频/音频流）
        abs_index = stream.get('index', 0)
        codec = stream.get('codec_name', 'unknown')
        lang = stream.get('tags', {}).get('language', '未知')

        if output_path is None:
            suffix = '.srt' if output_format == 'srt' else '.ass'
            lang_suffix = f".{lang}" if lang and lang != '未知' else ""
            output_path = video_path.with_suffix(f"{lang_suffix}{suffix}")

        print(f"提取字幕: {video_path.name}")
        print(f"  字幕流 #{stream_index}: 编码={codec}, 语言={lang}")

        # 选择输出编码
        if output_format == 'ass':
            codec_args = ['-c:s', 'ass']
        else:
            codec_args = ['-c:s', 'srt']

        cmd = [
            'ffmpeg', '-y', '-loglevel', 'warning',
            '-i', str(video_path),
            '-map', f'0:{abs_index}',
        ] + codec_args + [str(output_path)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                size = output_path.stat().st_size
                if size == 0:
                    print(f"✗ 字幕为空")
                    output_path.unlink()
                    return False
                print(f"✓ 提取完成: {output_path.name}")
                print(f"  文件大小: {MediaInfo.format_size(size)}")
                return True
            print(f"✗ 提取失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False


