#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""媒体处理工具"""

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


class MediaSplitter:
    """媒体分段 - 按段数或每段时长切分音频/视频文件"""

    @staticmethod
    def parse_duration(s: str) -> Optional[float]:
        """解析时长字符串，支持 'SS'、'MM:SS'、'HH:MM:SS'"""
        try:
            if ':' in s:
                parts = s.split(':')
                if len(parts) == 2:
                    return float(parts[0]) * 60 + float(parts[1])
                if len(parts) == 3:
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
            return float(s)
        except ValueError:
            return None

    @staticmethod
    def split(file_path: Path, spec: str,
              output_dir: Optional[Path] = None) -> int:
        """按段数（纯整数 1-100）或每段时长切分，返回成功切分的段数"""
        info = MediaInfo.get_info(file_path)
        duration = info.get('duration', 0)
        if duration <= 0:
            print("错误: 无法获取文件时长")
            return 0

        if output_dir is None:
            output_dir = file_path.parent / f"{file_path.stem}_parts"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 判断：纯整数且范围合理 → 按段数；否则按时长
        is_segment_count = (
            ':' not in spec
            and spec.isdigit()
            and 1 <= int(spec) <= 100
        )

        count = 0
        if is_segment_count:
            num = int(spec)
            if num > 100:
                print(f"错误: 段数过多 ({num})，最多 100 段")
                return 0
            seg_dur = duration / num
            print(f"按段数切分: {num} 段，每段约 {MediaInfo.format_duration(seg_dur)}")
            for i in range(num):
                start = i * seg_dur
                out = output_dir / f"{file_path.stem}_part{i + 1:02d}{file_path.suffix}"
                cmd = ['ffmpeg', '-y', '-loglevel', 'warning',
                       '-ss', f'{start:.3f}', '-t', f'{seg_dur:.3f}',
                       '-i', str(file_path),
                       '-c', 'copy', str(out)]
                if subprocess.run(cmd, capture_output=True, timeout=30).returncode == 0 and out.exists():
                    count += 1
                    print(f"  ✓ {out.name}")
        else:
            t = MediaSplitter.parse_duration(spec)
            if t is None or t <= 0:
                print(f"错误: 无效的分段规格 '{spec}'（应为段数或时长如 60 / 01:30）")
                return 0
            print(f"按时长切分: 每段 {MediaInfo.format_duration(t)}")
            i = 0
            start = 0.0
            while start < duration:
                i += 1
                out = output_dir / f"{file_path.stem}_part{i:02d}{file_path.suffix}"
                cmd = ['ffmpeg', '-y', '-loglevel', 'warning',
                       '-ss', f'{start:.3f}', '-t', f'{t:.3f}',
                       '-i', str(file_path),
                       '-c', 'copy', str(out)]
                if subprocess.run(cmd, capture_output=True, timeout=30).returncode == 0 and out.exists():
                    count += 1
                    print(f"  ✓ {out.name}")
                start += t
        print(f"\n共切分 {count} 段 → {output_dir}")
        return count




class SilenceCutter:
    """静音检测与裁剪 - 检测音频/视频中的静音段，可自动裁剪音频"""

    @staticmethod
    def detect(file_path: Path, threshold_db: float = -30.0,
               min_duration: float = 0.5) -> List[Tuple[float, Optional[float]]]:
        """检测静音段，返回 [(start, end), ...]，end 为 None 表示到结尾"""
        cmd = [
            'ffmpeg', '-i', str(file_path),
            '-af', f'silencedetect=noise={threshold_db}dB:d={min_duration}',
            '-f', 'null', '-'
        ]
        # silencedetect 信息输出在 stderr，需要 info 级别
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        starts = []
        ends = []
        for line in result.stderr.splitlines():
            line = line.strip()
            if 'silence_start:' in line:
                try:
                    val = float(line.split('silence_start:')[1].split()[0])
                    starts.append(val)
                except (ValueError, IndexError):
                    pass
            elif 'silence_end:' in line:
                try:
                    val = float(line.split('silence_end:')[1].split()[0])
                    ends.append(val)
                except (ValueError, IndexError):
                    pass
        segments = []
        n = min(len(starts), len(ends))
        for i in range(n):
            segments.append((starts[i], ends[i]))
        # 处理未闭合的静音段（持续到结尾）
        if len(starts) > len(ends):
            for s in starts[len(ends):]:
                segments.append((s, None))
        return segments

    @staticmethod
    def detect_and_display(file_path: Path, threshold_db: float = -30.0,
                           min_duration: float = 0.5) -> int:
        """检测并展示静音段"""
        segments = SilenceCutter.detect(file_path, threshold_db, min_duration)
        info = MediaInfo.get_info(file_path)
        duration = info.get('duration', 0)
        if not segments:
            print(f"未检测到静音段（阈值 {threshold_db}dB，最短 {min_duration}秒）")
            return 0
        print(f"检测到 {len(segments)} 个静音段:")
        print(f"{'序号':<6}{'起始':<12}{'结束':<12}{'时长':<12}")
        print('-' * 42)
        total_silence = 0.0
        for i, (s, e) in enumerate(segments, 1):
            end_str = MediaInfo.format_duration(e) if e is not None else '结尾'
            dur = (e - s) if e is not None else (duration - s if duration > 0 else 0)
            total_silence += dur
            print(f"{i:<6}{MediaInfo.format_duration(s):<12}{end_str:<12}"
                  f"{MediaInfo.format_duration(dur):<12}")
        print('-' * 42)
        if duration > 0:
            pct = total_silence / duration * 100
            print(f"总静音时长: {MediaInfo.format_duration(total_silence)} "
                  f"({pct:.1f}% / 总时长 {MediaInfo.format_duration(duration)})")
        return len(segments)

    @staticmethod
    def cut(file_path: Path, threshold_db: float = -30.0,
            min_duration: float = 0.5,
            output_path: Optional[Path] = None) -> bool:
        """使用 silenceremove 滤镜自动裁剪音频中的静音段"""
        info = MediaInfo.get_info(file_path)
        has_video = info.get('width', 0) > 0
        if has_video:
            print("提示: 视频文件的静音裁剪仅处理音频流，视频流保持不变")
            print("      如需同步裁剪视频画面，请使用 'mp --trim' 手动指定时间段")
        if output_path is None:
            output_path = file_path.with_name(
                f"{file_path.stem}_silencecut{file_path.suffix}")

        af = (f"silenceremove=stop_periods=-1:"
              f"stop_duration={min_duration}:"
              f"stop_threshold={threshold_db}dB")

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

        print(f"静音裁剪: {file_path.name} (阈值 {threshold_db}dB，最短 {min_duration}秒)")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and output_path.exists():
                old_dur = info.get('duration', 0)
                new_info = MediaInfo.get_info(output_path)
                new_dur = new_info.get('duration', 0)
                saved = max(0, old_dur - new_dur)
                print(f"✓ 裁剪完成: {output_path.name}")
                print(f"  原时长: {MediaInfo.format_duration(old_dur)}")
                print(f"  新时长: {MediaInfo.format_duration(new_dur)}")
                print(f"  节省: {MediaInfo.format_duration(saved)}")
                print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
                return True
            print(f"✗ 失败: {result.stderr.strip()}")
            return False
        except Exception as e:
            print(f"✗ 错误: {e}")
            return False




class SegmentRepeater:
    """片段重复 - 将指定时间段重复 N 次后接原文件结尾"""

    @staticmethod
    def repeat(file_path: Path, start: float, end: float, times: int,
               output_path: Optional[Path] = None) -> bool:
        """重复 [start,end] 片段 times 次，再接原文件 [end,末尾]
        使用 trim+concat 滤镜实现"""
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_path}")
            return False
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return False
        if start < 0:
            print(f"错误: 起始时间不能为负: {start}")
            return False
        if end <= start:
            print(f"错误: 结束时间需大于起始时间 (start={start}, end={end})")
            return False
        if times < 1 or times > 100:
            print(f"错误: 重复次数超出范围 (1 ~ 100): {times}")
            return False

        info = MediaInfo.get_info(file_path)
        duration = info.get('duration', 0) if isinstance(info, dict) else 0
        if duration <= 0:
            print("✗ 无法读取文件时长")
            return False
        if end > duration:
            print(f"✗ 结束时间 {end}s 超出文件时长 {duration:.2f}s")
            return False

        if output_path is None:
            output_path = file_path.with_name(
                f"{file_path.stem}_repeat_{int(start)}s-{int(end)}s x{times}{file_path.suffix}")

        suffix = output_path.suffix.lower()
        codec_args = AudioConverter.SUPPORTED_FORMATS.get(suffix)
        # 视频文件：使用流复制；音频文件：用对应编码器
        video_exts = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}
        is_video = suffix in video_exts

        # 构造 filter_complex：片段A=[start,end]重复times次，片段B=[end,末尾]
        # 用 asplit 将片段复制 N 份，再用 concat 拼接
        filters = []
        # 提取重复片段并复制 times 份
        split_labels = ''.join(f"[s{i}]" for i in range(times))
        filters.append(
            f"[0:a]atrim={start}:{end},asetpts=PTS-STARTPTS,"
            f"asplit={times}{split_labels}"
        )
        # 尾段 [end, 末尾]
        filters.append(f"[0:a]atrim=start={end},asetpts=PTS-STARTPTS[atail]")
        # concat n = times + 1（times 个重复片段 + 1 个尾段）
        concat_n = times + 1
        concat_inputs = ''.join(f"[s{i}]" for i in range(times)) + "[atail]"
        filters.append(f"{concat_inputs}concat=n={concat_n}:v=0:a=1[aout]")

        filter_complex = ";".join(filters)
        cmd = ['ffmpeg', '-y', '-loglevel', 'warning',
               '-i', str(file_path),
               '-filter_complex', filter_complex,
               '-map', '[aout]']
        if is_video:
            # 视频用默认 aac
            cmd += ['-c:a', 'aac', '-b:a', '192k']
        elif codec_args:
            cmd += codec_args
        else:
            cmd += ['-c:a', 'aac', '-b:a', '192k']
        cmd += [str(output_path)]

        seg_duration = end - start
        total_audio_duration = seg_duration * times + (duration - end)
        print(f"片段重复: {file_path.name} [{start:.2f}s→{end:.2f}s] x {times} + 尾段")
        print(f"  输出预计时长: {total_audio_duration:.2f}s (原 {duration:.2f}s)")
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




class MediaHealthChecker:
    """媒体健康检查 - 检测媒体文件是否损坏、能否正常解码"""

    @staticmethod
    def check(file_path: Path) -> Dict[str, Any]:
        """检查单个文件的健康状况"""
        result = {
            'file': str(file_path),
            'name': file_path.name,
            'exists': file_path.exists(),
            'size': 0,
            'decodable': False,
            'errors': [],
            'warnings': [],
        }
        if not file_path.exists():
            result['errors'].append('文件不存在')
            return result
        result['size'] = file_path.stat().st_size
        if result['size'] == 0:
            result['errors'].append('文件大小为 0 字节')
            return result

        # 第一步：ffprobe 探测容器与流
        probe_cmd = [
            'ffprobe', '-v', 'error',
            '-print_format', 'json',
            '-show_format', '-show_streams',
            str(file_path)
        ]
        probe = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        if probe.returncode != 0:
            result['errors'].append(f'容器解析失败: {probe.stderr.strip()}')
            return result
        try:
            data = json.loads(probe.stdout)
        except json.JSONDecodeError:
            result['errors'].append('无法解析 ffprobe 输出')
            return result
        streams = data.get('streams', [])
        if not streams:
            result['errors'].append('未找到任何媒体流')
            return result

        # 第二步：ffmpeg 完整解码检测错误
        decode_cmd = [
            'ffmpeg', '-v', 'error',
            '-err_detect', 'explode',
            '-i', str(file_path),
            '-f', 'null', '-'
        ]
        decode = subprocess.run(decode_cmd, capture_output=True, text=True, timeout=30)
        if decode.returncode == 0 and not decode.stderr.strip():
            result['decodable'] = True
        else:
            for line in decode.stderr.splitlines():
                line = line.strip()
                if not line:
                    continue
                low = line.lower()
                if low.startswith('error') or 'error' in low or 'invalid' in low or 'corrupt' in low:
                    result['errors'].append(line)
                else:
                    result['warnings'].append(line)
            # 有警告但能完成解码也视为可解码
            if decode.returncode == 0:
                result['decodable'] = True
        return result

    @staticmethod
    def check_and_display(file_paths: List[Path]) -> int:
        """批量检查并展示结果，返回异常文件数"""
        total = len(file_paths)
        ok = 0
        abnormal = 0
        for i, fp in enumerate(file_paths, 1):
            print(f"\n[{i}/{total}] 检查: {fp}")
            r = MediaHealthChecker.check(fp)
            size = MediaInfo.format_size(r['size']) if r['size'] else '0 B'
            if r['decodable'] and not r['errors']:
                print(f"  ✓ 健康（大小: {size}）")
                ok += 1
            else:
                print(f"  ✗ 异常（大小: {size}）")
                abnormal += 1
                for e in r['errors']:
                    print(f"    错误: {e}")
                for w in r['warnings'][:5]:
                    print(f"    警告: {w}")
        print(f"\n{'=' * 50}")
        print(f"总计: {total}，健康: {ok}，异常: {abnormal}")
        return abnormal




class DuplicateFinder:
    """重复文件查找 - 基于内容哈希查找重复媒体文件"""

    MEDIA_EXTENSIONS = {
        '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.opus',
        '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v',
    }

    @staticmethod
    def _file_hash(file_path: Path, chunk_size: int = 65536) -> str:
        """计算文件 SHA-256 哈希（先按大小过滤）"""
        h = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def find(directory: Path, recursive: bool = True) -> Dict[str, List[Path]]:
        """查找重复文件，返回 {hash: [paths]} 字典（仅包含重复项）"""
        if not directory.exists() or not directory.is_dir():
            print(f"错误: 目录不存在 {directory}")
            return {}

        # 先按大小分组，相同大小再算哈希（避免无谓的哈希计算）
        size_map: Dict[int, List[Path]] = {}
        glob_pattern = '**/*' if recursive else '*'
        for entry in directory.glob(glob_pattern):
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in DuplicateFinder.MEDIA_EXTENSIONS:
                continue
            try:
                size = entry.stat().st_size
            except OSError:
                continue
            size_map.setdefault(size, []).append(entry)

        # 只对相同大小的文件计算哈希
        hash_map: Dict[str, List[Path]] = {}
        for size, paths in size_map.items():
            if len(paths) < 2:
                continue
            for p in paths:
                try:
                    h = DuplicateFinder._file_hash(p)
                except Exception:
                    continue
                hash_map.setdefault(h, []).append(p)

        # 仅返回有重复的
        return {h: ps for h, ps in hash_map.items() if len(ps) > 1}

    @staticmethod
    def find_and_display(directory: Path, recursive: bool = True) -> int:
        duplicates = DuplicateFinder.find(directory, recursive)
        if not duplicates:
            print(f"\n✓ 未发现重复文件: {directory}")
            return 0

        total_dupes = sum(len(ps) - 1 for ps in duplicates.values())
        print(f"\n发现 {len(duplicates)} 组重复文件，共 {total_dupes} 个冗余文件")
        print(f"{'='*70}")
        waste = 0
        for i, (h, paths) in enumerate(duplicates.items(), 1):
            size = paths[0].stat().st_size
            waste += size * (len(paths) - 1)
            print(f"\n[组 {i}] 哈希: {h[:16]}... ({MediaInfo.format_size(size)} × {len(paths)})")
            for p in paths:
                print(f"  {p}")
        print(f"\n{'='*70}")
        print(f"可释放空间: {MediaInfo.format_size(waste)}")
        return total_dupes




class MetadataExporter:
    """元数据批量导出 CSV - 将多个媒体文件的元数据导出为 CSV 表格"""

    FIELDS = [
        ('文件名', 'name'),
        ('格式', 'fmt'),
        ('大小', 'size_h'),
        ('时长', 'dur_h'),
        ('比特率', 'br_h'),
        ('编码', 'codec'),
        ('采样率', 'sr_h'),
        ('声道', 'channels'),
        ('宽度', 'width'),
        ('高度', 'height'),
        ('帧率', 'fps_h'),
        ('标题', 'title'),
        ('艺术家', 'artist'),
        ('专辑', 'album'),
    ]

    @staticmethod
    def export(file_paths: List[Path], output_path: Path) -> bool:
        import csv
        rows = []
        for fp in file_paths:
            info = MediaInfo.get_info(fp)
            rows.append({
                '文件名': fp.name,
                '格式': info.get('format', '').lstrip('.'),
                '大小': MediaInfo.format_size(info.get('size', 0)),
                '时长': MediaInfo.format_duration(info.get('duration', 0)),
                '比特率': f"{info.get('bit_rate', 0) // 1000} kbps" if info.get('bit_rate') else '',
                '编码': info.get('codec', ''),
                '采样率': f"{info.get('sample_rate', 0)} Hz" if info.get('sample_rate') else '',
                '声道': info.get('channels', '') if info.get('channels') else '',
                '宽度': info.get('width', '') if info.get('width') else '',
                '高度': info.get('height', '') if info.get('height') else '',
                '帧率': f"{info.get('fps', 0):.2f}" if info.get('fps') else '',
                '标题': info.get('title', ''),
                '艺术家': info.get('artist', ''),
                '专辑': info.get('album', ''),
            })
        if not rows:
            print("错误: 没有可导出的文件")
            return False
        fieldnames = [k for k, _ in MetadataExporter.FIELDS]
        try:
            # utf-8-sig 便于 Excel 直接打开中文
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            print(f"✓ 已导出 {len(rows)} 条记录到 {output_path}")
            print(f"  文件大小: {MediaInfo.format_size(output_path.stat().st_size)}")
            return True
        except Exception as e:
            print(f"✗ 导出失败: {e}")
            return False




class AudioFingerprinter:
    """音频指纹识别 - 基于 chromaprint 生成指纹并比对相似度"""

    @staticmethod
    def fingerprint(file_path: Path) -> Optional[bytes]:
        """生成原始指纹二进制数据"""
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return None
        cmd = ['ffmpeg', '-i', str(file_path),
               '-map', '0:a',
               '-f', 'chromaprint',
               '-fp_format', 'raw',
               '-']
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0 and result.stdout:
                return result.stdout
        except Exception:
            pass
        return None

    @staticmethod
    def _hamming_distance(a: bytes, b: bytes) -> int:
        """计算两个指纹的汉明距离"""
        n = min(len(a), len(b))
        return sum(bin(a[i] ^ b[i]).count('1') for i in range(n))

    @staticmethod
    def compare_and_display(file_paths: List[Path]) -> None:
        """生成指纹并两两比对相似度"""
        if not shutil.which('ffmpeg'):
            print("错误: 未安装 ffmpeg")
            return
        prints = []
        for fp in file_paths:
            fp_data = AudioFingerprinter.fingerprint(fp)
            prints.append((fp, fp_data))
            if fp_data:
                print(f"✓ 指纹: {fp.name} ({len(fp_data)} 字节)")
            else:
                print(f"✗ 失败: {fp.name}（可能 ffmpeg 未启用 chromaprint）")

        if len(prints) >= 2:
            print(f"\n相似度对比:")
            print('-' * 60)
            for i in range(len(prints)):
                for j in range(i + 1, len(prints)):
                    a, fa = prints[i]
                    b, fb = prints[j]
                    if fa and fb:
                        total_bits = min(len(fa), len(fb)) * 8
                        dist = AudioFingerprinter._hamming_distance(fa, fb)
                        similarity = max(0.0, 1.0 - dist / max(1, total_bits))
                        print(f"  {a.name}  vs  {b.name}: {similarity * 100:.1f}%")
                    else:
                        print(f"  {a.name}  vs  {b.name}: 无法比较（指纹缺失）")


