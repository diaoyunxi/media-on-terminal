#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""主入口：命令行参数解析与分发"""

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

from mp import __version__
from mp.config import Config
from mp.media_info import MediaInfo
from mp.utils import check_and_install_dependencies, check_ffmpeg
from mp.constants import GITHUB_REPO, _GITHUB_MIRROR
from mp.playlist import Playlist, PlaylistIO
from mp.players import AudioPlayer, VideoPlayer
from mp.managers import (
    BookmarkManager, FavoritesManager, HistoryManager,
    StatisticsManager, RadioManager,
)
from mp.effects import Equalizer
from mp.file_browser import FileBrowser
from mp.noise import NoiseGenerator
from mp.metadata import MetadataEditor, BatchRenamer, MetadataStripper, BPMDetector, SubtitleExtractor
from mp.lyrics import LyricsDisplay, OnlineLyricsFetcher
from mp.audio_tools import (
    AudioRecorder, AudioExtractor, AudioTrimmer, AudioMerger, AudioReverser,
    ChannelConverter, SampleRateConverter, AVMuxer, AudioMixMixer, RingtoneMaker,
)
from mp.video_tools import (
    GifConverter, ScreenshotCapture, VideoConcat, VideoScaler,
    VideoRotator, VideoCropper, FpsConverter, ContactSheet,
)
from mp.media_tools import (
    MediaSplitter, SilenceCutter, SegmentRepeater,
    MediaHealthChecker, DuplicateFinder, MetadataExporter, AudioFingerprinter,
)
from mp.effects import (
    FadeEffect, ReverbEffect, AudioNormalizer, VolumeGain, VolumeRamp,
    AudioConverter, CrossfadeManager, PitchControl,
)
from mp.visual import (
    SpectrogramGenerator, WaveformGenerator, CoverExtractor, AsciiArtExporter,
)
from mp.media_library import MediaLibrary
from mp.config import ConfigBackup
from mp.updater import check_for_update
from mp.download import download_song_interactive
from mp.help_text import show_help

def play_playlist(playlist: Playlist, config: Config, loop: str = 'none', explicit_loop: bool = False):
    """播放播放列表

    :param playlist: 播放列表
    :param config: 配置对象
    :param loop: 循环模式，仅当 explicit_loop=True 时覆盖 player 从配置读取的值
    :param explicit_loop: 是否为命令行显式指定的 --loop 参数
    """
    if not playlist.files:
        print("播放列表为空")
        return
    
    playlist.display()
    
    current_file = playlist.get_current()
    while current_file:
        file_ext = current_file.suffix.lower()
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}
        
        if file_ext in video_extensions:
            player = VideoPlayer(current_file, config)
        else:
            player = AudioPlayer(current_file, config)
        # 仅命令行显式指定 --loop 时才覆盖 player 从配置文件读取的 loop_mode
        # 播放中按 [l] 切换的模式已通过 config.set 持久化，列表下一曲会自动继承
        if explicit_loop:
            player.loop_mode = loop
        
        # 设置信号处理
        should_stop = False
        should_next = False
        
        def signal_handler(sig, frame):
            nonlocal should_stop
            should_stop = True
            player.stop()
        
        signal.signal(signal.SIGINT, signal_handler)
        
        try:
            player.run()
        except KeyboardInterrupt:
            break
        
        if should_stop:
            break
        
        # 获取下一个文件
        next_file = playlist.next()
        if next_file is None:
            if player.loop_mode == 'all':
                playlist.current_index = 0
                current_file = playlist.get_current()
            else:
                break
        else:
            current_file = next_file


# --- GitHub 自动更新检查 ---
# GITHUB_REPO 和 _GITHUB_MIRROR 从 mp.constants 导入




def main():
    # 处理帮助命令
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help']:
        show_help()
        sys.exit(0)
    
    # 检查依赖
    check_and_install_dependencies()
    
    # 解析参数
    parser = argparse.ArgumentParser(
        prog='mp',
        description='Terminal Media Player - 轻量级终端媒体播放器',
        add_help=False
    )
    parser.add_argument('-h', '--help', action='store_true', help='显示帮助信息')
    parser.add_argument('-V', '--version', action='store_true', help='显示当前版本号')
    parser.add_argument('--update', action='store_true', help='检查并更新到最新版本')
    parser.add_argument('-i', '--info', action='store_true', help='显示媒体信息')
    parser.add_argument('-p', '--playlist', action='store_true', help='播放列表模式')
    parser.add_argument('-s', '--shuffle', action='store_true', help='随机播放')
    parser.add_argument('-l', '--loop', choices=['single', 'all'], help='循环模式')
    parser.add_argument('-v', '--volume', type=int, help='设置音量 (0-100)')
    parser.add_argument('--speed', type=float, help='设置播放速度 (0.5-2.0)')
    parser.add_argument('--favorites', action='store_true', help='播放收藏列表')
    parser.add_argument('--history', action='store_true', help='显示播放历史')
    parser.add_argument('--clear-history', action='store_true', help='清空播放历史')
    parser.add_argument('--stats', action='store_true', help='显示播放统计')
    parser.add_argument('--clear-stats', action='store_true', help='清空播放统计')
    parser.add_argument('--convert', type=str, metavar='FMT', help='转换音频格式 (mp3/wav/ogg/m4a/flac/aac/opus)')
    parser.add_argument('--eq', type=str, metavar='PRESET', help='使用均衡器预设播放')
    parser.add_argument('--eq-list', action='store_true', help='显示均衡器预设列表')
    parser.add_argument('--radio', type=str, help='播放网络电台')
    parser.add_argument('--radio-list', action='store_true', help='显示电台列表')
    parser.add_argument('--radio-add', nargs=2, metavar=('NAME', 'URL'), help='添加电台')
    parser.add_argument('--radio-del', type=str, help='删除电台')
    parser.add_argument('--browse', action='store_true', help='打开文件浏览器选择文件')
    parser.add_argument('--noise', nargs='?', const='interactive', metavar='TYPE', help='播放噪声 (white/pink/brown/rain/ocean)')
    parser.add_argument('--edit-tags', type=str, metavar='FILE', help='编辑媒体文件元数据')
    parser.add_argument('--record', nargs='?', const='interactive', metavar='FILE', help='录制麦克风音频 (wav/mp3/ogg/m4a/flac)')
    parser.add_argument('--extract-audio', metavar='VIDEO', help='从视频提取音轨')
    parser.add_argument('--to-gif', metavar='VIDEO', help='将视频片段转为GIF')
    parser.add_argument('--screenshot', metavar='VIDEO', help='从视频捕获画面帧')
    parser.add_argument('--normalize', action='store_true', help='音频音量归一化')
    parser.add_argument('--export-m3u', metavar='OUTPUT', help='导出M3U播放列表')
    parser.add_argument('--import-m3u', metavar='FILE', help='导入M3U播放列表并播放')
    parser.add_argument('--library-scan', metavar='DIR', help='扫描目录建立媒体库索引')
    parser.add_argument('--library-search', metavar='QUERY', help='搜索媒体库')
    parser.add_argument('--library-stats', action='store_true', help='显示媒体库统计')
    parser.add_argument('--library-clear', action='store_true', help='清空媒体库')
    # 新功能附加参数
    parser.add_argument('--fmt', type=str, default=None, help='指定输出格式 (用于提取/归一化)')
    parser.add_argument('--at', type=float, default=0.0, help='截图时间点（秒）')
    parser.add_argument('--count', type=int, default=1, help='批量截图数量')
    parser.add_argument('--gif-start', type=float, default=0.0, dest='gif_start', help='GIF起始时间（秒）')
    parser.add_argument('--gif-duration', type=float, default=None, dest='gif_duration', help='GIF时长（秒）')
    parser.add_argument('--gif-width', type=int, default=480, dest='gif_width', help='GIF宽度（像素）')
    parser.add_argument('--gif-fps', type=int, default=15, dest='gif_fps', help='GIF帧率')
    # ===== v2.7.0 新增参数 =====
    parser.add_argument('--trim', nargs='+', metavar=('FILE', 'TIME'),
                        help='裁剪媒体文件: --trim FILE START [END]')
    parser.add_argument('--merge', nargs='+', metavar=('OUTPUT', 'FILE'),
                        help='合并音频文件: --merge OUTPUT FILE [FILE...]')
    parser.add_argument('--reverse', action='store_true', help='反向音频（操作 args.files）')
    parser.add_argument('--fade', nargs='+', metavar=('FILE', 'SEC'),
                        help='淡入淡出: --fade FILE IN_SEC [OUT_SEC]')
    parser.add_argument('--reverb', nargs='?', const='__list__', metavar='PRESET',
                        help='应用混响预设（仅指定时列出预设）')
    parser.add_argument('--reverb-list', action='store_true', help='显示混响预设列表')
    parser.add_argument('--extract-subtitles', metavar='VIDEO', dest='extract_subtitles',
                        help='从视频提取字幕')
    parser.add_argument('--bpm', action='store_true', help='检测音频 BPM（操作 args.files）')
    parser.add_argument('--contact-sheet', metavar='VIDEO', dest='contact_sheet',
                        help='生成视频缩略图组合')
    parser.add_argument('--rows', type=int, default=4, help='接触印片行数')
    parser.add_argument('--cols', type=int, default=4, help='接触印片列数')
    parser.add_argument('--find-duplicates', metavar='DIR', dest='find_duplicates',
                        help='查找重复媒体文件')
    parser.add_argument('--backup-config', nargs='?', const='__default__',
                        metavar='OUTPUT', help='备份配置到zip')
    parser.add_argument('--restore-config', metavar='INPUT', dest='restore_config',
                        help='从zip恢复配置')
    parser.add_argument('--rename', nargs=2, metavar=('PATTERN', 'DIR'),
                        help='按元数据批量重命名: --rename PATTERN DIR')
    parser.add_argument('--dry-run', action='store_true', dest='dry_run',
                        help='演练模式（不实际操作）')
    parser.add_argument('--spectrogram', metavar='FILE', help='生成音频频谱图PNG')
    parser.add_argument('--recursive', action='store_true',
                        help='递归处理子目录（用于查找重复/重命名）')
    # ===== v2.8.0 新增参数 =====
    parser.add_argument('--waveform', metavar='FILE', help='生成音频波形图PNG')
    parser.add_argument('--cover', metavar='FILE', help='提取嵌入的封面/海报图片')
    parser.add_argument('--gain', type=float, metavar='DB',
                        help='音量增益(dB)（操作 args.files，支持批量）')
    parser.add_argument('--ringtone', nargs='+', metavar=('FILE', 'START'),
                        help='生成铃声 [--ringtone FILE [START [DURATION]]]')
    parser.add_argument('--channels', type=int, metavar='N',
                        help='转换声道数 1(单声道)/2(立体声)（操作 args.files）')
    parser.add_argument('--resample', type=int, metavar='RATE',
                        help='转换采样率(Hz)（操作 args.files，支持批量）')
    parser.add_argument('--mux', nargs=2, metavar=('VIDEO', 'AUDIO'),
                        help='将音频合并到视频（替换原音轨）')
    parser.add_argument('--fade-sec', type=float, default=2.0, dest='fade_sec',
                        help='铃声淡入淡出时长（秒，默认2.0）')
    # ===== v2.9.0 新增参数 =====
    parser.add_argument('--health-check', action='store_true', dest='health_check',
                        help='媒体健康检查（操作 args.files，检测是否损坏）')
    parser.add_argument('--silence-detect', metavar='FILE', dest='silence_detect',
                        help='检测音频/视频中的静音段')
    parser.add_argument('--silence-cut', metavar='FILE', dest='silence_cut',
                        help='自动裁剪音频中的静音段')
    parser.add_argument('--silence-threshold', type=float, default=-30.0,
                        dest='silence_threshold',
                        help='静音检测阈值（dB，默认 -30.0）')
    parser.add_argument('--silence-duration', type=float, default=0.5,
                        dest='silence_duration',
                        help='静音最短时长（秒，默认 0.5）')
    parser.add_argument('--split', nargs=2, metavar=('FILE', 'SPEC'),
                        help='媒体分段: --split FILE N(段数) 或 FILE 时长(如 60 / 01:30)')
    parser.add_argument('--export-csv', metavar='OUTPUT', dest='export_csv',
                        help='批量导出元数据到 CSV（操作 args.files）')
    parser.add_argument('--fingerprint', action='store_true', dest='fingerprint',
                        help='生成音频指纹并比对相似度（操作 args.files）')
    parser.add_argument('--volume-ramp', nargs=2, metavar=('START_DB', 'END_DB'),
                        dest='volume_ramp',
                        help='音量渐变: --volume-ramp START_DB END_DB FILE（渐强/渐弱）')
    parser.add_argument('--ascii-art', metavar='VIDEO', dest='ascii_art',
                        help='将视频导出为 ASCII 文本动画')
    parser.add_argument('--ascii-width', type=int, default=80, dest='ascii_width',
                        help='ASCII 艺术宽度（字符数，默认 80）')
    parser.add_argument('--ascii-fps', type=int, default=10, dest='ascii_fps',
                        help='ASCII 艺术帧率（默认 10）')
    # ===== v2.10.0 新增参数 =====
    parser.add_argument('--mix', nargs='+', metavar=('OUTPUT', 'FILE'),
                        dest='mix',
                        help='音频混音: --mix OUTPUT FILE1 FILE2 [FILE3...]')
    parser.add_argument('--vconcat', nargs='+', metavar=('OUTPUT', 'FILE'),
                        dest='vconcat',
                        help='视频拼接: --vconcat OUTPUT FILE1 FILE2 [FILE3...]')
    parser.add_argument('--scale', nargs=2, metavar=('VIDEO', 'WxH'),
                        dest='scale',
                        help='视频缩放: --scale VIDEO WIDTHxHEIGHT (如 1280x720)')
    parser.add_argument('--rotate', nargs=2, metavar=('VIDEO', 'DEGREE'),
                        dest='rotate',
                        help='视频旋转: --rotate VIDEO 90|180|270 (顺时针)')
    parser.add_argument('--crop', nargs=2, metavar=('VIDEO', 'W:H:X:Y'),
                        dest='crop',
                        help='视频画面裁剪: --crop VIDEO W:H:X:Y (如 640:480:100:50)')
    parser.add_argument('--fps', nargs=2, metavar=('VIDEO', 'FPS'),
                        dest='fps',
                        help='视频帧率转换: --fps VIDEO FPS (1~240)')
    parser.add_argument('--strip-metadata', action='store_true', dest='strip_metadata',
                        help='剥离元数据（操作 args.files，支持批量）')
    parser.add_argument('--repeat', nargs=4, metavar=('FILE', 'START', 'END', 'N'),
                        dest='repeat',
                        help='片段重复: --repeat FILE START END N (重复 N 次后接尾段)')
    # ===== 仅下载歌词 =====
    parser.add_argument('--lyrics', metavar='TARGET', dest='lyrics', nargs='+',
                        help='仅下载歌词不播放。TARGET 为媒体文件路径（用其元数据/文件名搜索）或关键词字符串；支持多个目标批量下载（如 --lyrics ./*）')
    parser.add_argument('--lyrics-interactive', action='store_true', dest='lyrics_interactive',
                        help='与 --lyrics 配合：交互式选择候选歌词')
    parser.add_argument('--lyrics-output', metavar='PATH', dest='lyrics_output',
                        help='与 --lyrics 配合：指定输出 .lrc 路径（默认同名 .lrc 或 关键词.lrc）')
    # ===== 歌曲下载 =====
    parser.add_argument('--download', nargs='?', const='__interactive__', metavar='KEYWORD',
                        dest='download',
                        help='在线搜索并下载歌曲（含歌词）。无参数时交互式搜索，带关键词时自动下载最佳匹配')
    parser.add_argument('--download-output', metavar='DIR', dest='download_output',
                        help='与 --download 配合：指定下载输出目录（默认当前目录）')
    parser.add_argument('files', nargs='*', help='媒体文件路径')
    
    args = parser.parse_args()

    if args.help:
        show_help()
        sys.exit(0)

    if args.version:
        print(f"mp {__version__}")
        sys.exit(0)

    if args.update:
        print(f"当前版本: v{__version__}")
        print("正在检查更新...")
        check_for_update(force=True)
        sys.exit(0)

    # 加载配置
    config = Config()
    
    # 处理收藏播放
    if args.favorites:
        favorites_manager = FavoritesManager()
        fav_files = favorites_manager.get_all()
        if not fav_files:
            print("收藏列表为空")
            sys.exit(0)
        
        print(f"播放收藏列表 ({len(fav_files)} 首)")
        playlist = Playlist()
        for f in fav_files:
            playlist.add_file(f)
        
        if args.shuffle:
            playlist.shuffle()
        
        play_playlist(playlist, config, args.loop, explicit_loop=bool(args.loop))
        sys.exit(0)
    
    # 处理历史记录
    if args.history:
        history_manager = HistoryManager()
        history_manager.display()
        sys.exit(0)
    
    if args.clear_history:
        history_manager = HistoryManager()
        history_manager.clear()
        sys.exit(0)
    
    # 处理统计相关命令
    if args.stats:
        stats_manager = StatisticsManager()
        stats_manager.display()
        sys.exit(0)
    
    if args.clear_stats:
        stats_manager = StatisticsManager()
        stats_manager.clear()
        sys.exit(0)
    
    # 处理均衡器预设列表
    if args.eq_list:
        eq = Equalizer()
        eq.list_presets()
        sys.exit(0)
    
    # 处理电台相关命令
    radio_manager = RadioManager()
    
    if args.radio_list:
        radio_manager.list_stations()
        sys.exit(0)
    
    if args.radio_add:
        name, url = args.radio_add
        radio_manager.add_station(name, url)
        sys.exit(0)
    
    if args.radio_del:
        radio_manager.remove_station(args.radio_del)
        sys.exit(0)
    
    if args.radio:
        url = radio_manager.get_station_url(args.radio)
        if not url:
            print(f"电台不存在: {args.radio}")
            print("使用 'mp --radio-list' 查看可用电台")
            sys.exit(1)
        
        print(f"正在播放电台: {args.radio}")
        print(f"URL: {url}")
        print("按 Ctrl+C 停止播放\n")
        
        # 使用 ffplay 播放流媒体
        cmd = [
            'ffplay',
            '-nodisp',
            '-autoexit',
            '-loglevel', 'quiet',
            '-hide_banner',
            '-volume', str(config.get('volume', 100)),
            url
        ]
        
        try:
            # 播放为长进程（用户按 Ctrl+C 或 q 停止），不设 timeout 避免被中途终止
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n停止播放")
        sys.exit(0)

    # 处理音频转换命令
    if args.convert:
        if not args.files:
            print("错误: 请指定要转换的音频文件")
            sys.exit(1)

        input_files = [Path(f) for f in args.files]
        output_format = args.convert.lower()

        if len(input_files) == 1:
            # 单文件转换
            AudioConverter.convert(input_files[0], output_format)
        else:
            # 批量转换
            AudioConverter.batch_convert(input_files, output_format)
        sys.exit(0)

    # 处理文件浏览器
    if args.browse:
        browser = FileBrowser()
        selected_files = browser.run()
        if not selected_files:
            print("未选择任何文件")
            sys.exit(0)
        
        if len(selected_files) == 1:
            args.files = [str(selected_files[0])]
        else:
            playlist = Playlist()
            for f in selected_files:
                playlist.add_file(f)
            if args.shuffle:
                playlist.shuffle()
            play_playlist(playlist, config, args.loop, explicit_loop=bool(args.loop))
            sys.exit(0)

    # 处理噪声生成器
    if args.noise:
        noise_gen = NoiseGenerator()
        if args.noise == 'interactive':
            noise_gen.run_interactive()
        else:
            noise_gen.set_type(args.noise)
            noise_gen.run_interactive()
        sys.exit(0)

    # 处理元数据编辑
    if args.edit_tags:
        file_path = Path(args.edit_tags)
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.edit_tags}")
            sys.exit(1)
        MetadataEditor.run_interactive(file_path)
        sys.exit(0)

    # ===== v2.5.0 新增功能 =====

    # 音频录制
    if args.record:
        if args.record == 'interactive':
            AudioRecorder.run_interactive()
        else:
            AudioRecorder.record(Path(args.record))
        sys.exit(0)

    # 从视频提取音频
    if args.extract_audio:
        video_path = Path(args.extract_audio)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.extract_audio}")
            sys.exit(1)
        out_format = (args.fmt or 'mp3').lstrip('.')
        if args.files:
            # 多个视频文件批量提取
            video_files = [video_path] + [Path(f) for f in args.files]
            AudioExtractor.batch_extract(video_files, out_format)
        else:
            AudioExtractor.extract(video_path, out_format)
        sys.exit(0)

    # 视频转GIF
    if args.to_gif:
        video_path = Path(args.to_gif)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.to_gif}")
            sys.exit(1)
        GifConverter.convert(
            video_path,
            output_path=None,
            start=args.gif_start,
            duration=args.gif_duration,
            width=args.gif_width,
            fps=args.gif_fps,
        )
        sys.exit(0)

    # 视频截图
    if args.screenshot:
        video_path = Path(args.screenshot)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.screenshot}")
            sys.exit(1)
        if args.count > 1:
            ScreenshotCapture.capture_multi(video_path, args.count)
        else:
            ScreenshotCapture.capture(video_path, args.at)
        sys.exit(0)

    # 音频归一化
    if args.normalize:
        if not args.files:
            print("错误: 请指定要归一化的音频文件")
            sys.exit(1)
        method = (args.fmt or 'loudnorm').lower()
        files = [Path(f) for f in args.files]
        if len(files) == 1:
            AudioNormalizer.normalize(files[0], method)
        else:
            AudioNormalizer.batch_normalize(files, method)
        sys.exit(0)

    # 导出M3U播放列表
    if args.export_m3u:
        if not args.files:
            print("错误: 请指定要导出的媒体文件")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        PlaylistIO.export_m3u(files, Path(args.export_m3u))
        sys.exit(0)

    # 导入M3U播放列表
    if args.import_m3u:
        m3u_path = Path(args.import_m3u)
        if not m3u_path.exists():
            print(f"错误: 文件不存在 {args.import_m3u}")
            sys.exit(1)
        files = PlaylistIO.import_m3u(m3u_path)
        if not files:
            print("播放列表为空")
            sys.exit(0)
        playlist = Playlist()
        for f in files:
            playlist.add_file(f)
        if args.shuffle:
            playlist.shuffle()
        play_playlist(playlist, config, args.loop, explicit_loop=bool(args.loop))
        sys.exit(0)

    # 媒体库扫描
    if args.library_scan:
        library = MediaLibrary()
        library.scan(Path(args.library_scan))
        sys.exit(0)

    # 媒体库搜索
    if args.library_search:
        library = MediaLibrary()
        if not library.library['files']:
            print("媒体库为空，请先使用 'mp --library-scan <目录>' 扫描")
            sys.exit(0)
        results = library.search(args.library_search)
        library.display_results(results)
        sys.exit(0)

    # 媒体库统计
    if args.library_stats:
        library = MediaLibrary()
        library.display_stats()
        sys.exit(0)

    # 清空媒体库
    if args.library_clear:
        library = MediaLibrary()
        library.clear()
        sys.exit(0)

    # ===== v2.7.0 新增命令处理 =====

    # 媒体裁剪
    if args.trim:
        if len(args.trim) < 2:
            print("错误: 用法 --trim FILE START [END]")
            sys.exit(1)
        file_path = Path(args.trim[0])
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.trim[0]}")
            sys.exit(1)
        try:
            start = float(args.trim[1])
        except ValueError:
            print(f"错误: 起始时间无效: {args.trim[1]}")
            sys.exit(1)
        end = None
        if len(args.trim) >= 3:
            try:
                end = float(args.trim[2])
            except ValueError:
                print(f"错误: 结束时间无效: {args.trim[2]}")
                sys.exit(1)
        AudioTrimmer.trim(file_path, start, end)
        sys.exit(0)

    # 音频合并
    if args.merge:
        if len(args.merge) < 3:
            print("错误: 用法 --merge OUTPUT FILE [FILE...]")
            print("至少需要 1 个输出文件 + 2 个输入文件")
            sys.exit(1)
        output_path = Path(args.merge[0])
        input_files = [Path(f) for f in args.merge[1:]]
        output_fmt = args.fmt
        AudioMerger.merge(input_files, output_path, output_fmt)
        sys.exit(0)

    # 反向音频
    if args.reverse:
        if not args.files:
            print("错误: 请指定要反向的音频文件")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        if len(files) == 1:
            AudioReverser.reverse(files[0])
        else:
            AudioReverser.batch_reverse(files)
        sys.exit(0)

    # 淡入淡出
    if args.fade:
        if len(args.fade) < 2:
            print("错误: 用法 --fade FILE IN_SEC [OUT_SEC]")
            sys.exit(1)
        file_path = Path(args.fade[0])
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.fade[0]}")
            sys.exit(1)
        try:
            fade_in = float(args.fade[1])
        except ValueError:
            print(f"错误: 淡入时长无效: {args.fade[1]}")
            sys.exit(1)
        fade_out = 0.0
        if len(args.fade) >= 3:
            try:
                fade_out = float(args.fade[2])
            except ValueError:
                print(f"错误: 淡出时长无效: {args.fade[2]}")
                sys.exit(1)
        # OUT_SEC 也可能来自 --at
        if fade_out == 0.0 and args.at > 0:
            fade_out = args.at
        FadeEffect.apply_fade(file_path, fade_in, fade_out)
        sys.exit(0)

    # 混响预设列表
    if args.reverb_list or args.reverb == '__list__':
        ReverbEffect.list_presets()
        sys.exit(0)

    # 应用混响
    if args.reverb and args.reverb != '__list__':
        if not args.files:
            print("错误: 请指定要应用混响的音频文件")
            sys.exit(1)
        preset = args.reverb
        for f in args.files:
            ReverbEffect.apply_reverb(Path(f), preset)
        sys.exit(0)

    # 提取字幕
    if args.extract_subtitles:
        video_path = Path(args.extract_subtitles)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.extract_subtitles}")
            sys.exit(1)
        out_fmt = (args.fmt or 'srt').lower()
        SubtitleExtractor.extract(video_path, stream_index=None,
                                  output_format=out_fmt)
        sys.exit(0)

    # BPM 检测
    if args.bpm:
        if not args.files:
            print("错误: 请指定要检测的音频文件")
            sys.exit(1)
        for f in args.files:
            BPMDetector.detect_and_display(Path(f))
        sys.exit(0)

    # 视频缩略图组合
    if args.contact_sheet:
        video_path = Path(args.contact_sheet)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.contact_sheet}")
            sys.exit(1)
        ContactSheet.generate(video_path, rows=args.rows, cols=args.cols)
        sys.exit(0)

    # 查找重复文件
    if args.find_duplicates:
        directory = Path(args.find_duplicates)
        DuplicateFinder.find_and_display(directory, recursive=args.recursive)
        sys.exit(0)

    # 备份配置
    if args.backup_config:
        if args.backup_config == '__default__':
            output = None
        else:
            output = Path(args.backup_config)
        ConfigBackup.backup(output)
        sys.exit(0)

    # 恢复配置
    if args.restore_config:
        ConfigBackup.restore(Path(args.restore_config))
        sys.exit(0)

    # 批量重命名
    if args.rename:
        pattern, directory = args.rename
        BatchRenamer.rename_in_directory(
            Path(directory), pattern,
            recursive=args.recursive,
            dry_run=args.dry_run
        )
        sys.exit(0)

    # 频谱图
    if args.spectrogram:
        file_path = Path(args.spectrogram)
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.spectrogram}")
            sys.exit(1)
        duration = args.gif_duration if args.gif_duration is not None else None
        SpectrogramGenerator.generate(file_path,
                                      start=args.at,
                                      duration=duration)
        sys.exit(0)

    # ===== v2.8.0 新增命令处理 =====

    # 波形图
    if args.waveform:
        file_path = Path(args.waveform)
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.waveform}")
            sys.exit(1)
        duration = args.gif_duration if args.gif_duration is not None else None
        WaveformGenerator.generate(file_path,
                                   start=args.at,
                                   duration=duration)
        sys.exit(0)

    # 封面提取
    if args.cover:
        file_path = Path(args.cover)
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.cover}")
            sys.exit(1)
        CoverExtractor.extract(file_path)
        sys.exit(0)

    # 音量增益
    if args.gain is not None:
        if not args.files:
            print("错误: 请指定要调整音量的音频文件")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        if len(files) == 1:
            VolumeGain.apply(files[0], args.gain)
        else:
            VolumeGain.batch_apply(files, args.gain)
        sys.exit(0)

    # 铃声生成
    if args.ringtone:
        if not args.ringtone:
            print("错误: 用法 --ringtone FILE [START [DURATION]]")
            sys.exit(1)
        file_path = Path(args.ringtone[0])
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.ringtone[0]}")
            sys.exit(1)
        start = 0.0
        duration = None
        try:
            if len(args.ringtone) >= 2:
                start = float(args.ringtone[1])
            if len(args.ringtone) >= 3:
                duration = float(args.ringtone[2])
        except ValueError:
            print("错误: START/DURATION 必须为数字（秒）")
            sys.exit(1)
        RingtoneMaker.make(file_path, start=start, duration=duration,
                           fade=args.fade_sec)
        sys.exit(0)

    # 声道转换
    if args.channels is not None:
        if not args.files:
            print("错误: 请指定要转换声道的音频文件")
            sys.exit(1)
        if args.channels not in (1, 2):
            print(f"错误: 声道数仅支持 1(单声道) 或 2(立体声)，当前: {args.channels}")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        if len(files) == 1:
            ChannelConverter.convert(files[0], args.channels)
        else:
            ChannelConverter.batch_convert(files, args.channels)
        sys.exit(0)

    # 采样率转换
    if args.resample is not None:
        if not args.files:
            print("错误: 请指定要转换采样率的音频文件")
            sys.exit(1)
        if args.resample < 1000 or args.resample > 384000:
            print(f"错误: 采样率超出范围 (1000 ~ 384000 Hz): {args.resample}")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        if len(files) == 1:
            SampleRateConverter.convert(files[0], args.resample)
        else:
            SampleRateConverter.batch_convert(files, args.resample)
        sys.exit(0)

    # 音视频合成
    if args.mux:
        video_path = Path(args.mux[0])
        audio_path = Path(args.mux[1])
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.mux[0]}")
            sys.exit(1)
        if not audio_path.exists():
            print(f"错误: 音频文件不存在 {args.mux[1]}")
            sys.exit(1)
        AVMuxer.mux(video_path, audio_path, replace=True)
        sys.exit(0)

    # ===== v2.9.0 新增命令处理 =====

    # 媒体健康检查
    if args.health_check:
        if not args.files:
            print("错误: 请指定要检查的媒体文件")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        abnormal = MediaHealthChecker.check_and_display(files)
        sys.exit(1 if abnormal > 0 else 0)

    # 静音检测
    if args.silence_detect:
        file_path = Path(args.silence_detect)
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.silence_detect}")
            sys.exit(1)
        SilenceCutter.detect_and_display(
            file_path,
            threshold_db=args.silence_threshold,
            min_duration=args.silence_duration
        )
        sys.exit(0)

    # 静音裁剪
    if args.silence_cut:
        file_path = Path(args.silence_cut)
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.silence_cut}")
            sys.exit(1)
        SilenceCutter.cut(
            file_path,
            threshold_db=args.silence_threshold,
            min_duration=args.silence_duration
        )
        sys.exit(0)

    # 媒体分段
    if args.split:
        file_path = Path(args.split[0])
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.split[0]}")
            sys.exit(1)
        MediaSplitter.split(file_path, args.split[1])
        sys.exit(0)

    # 元数据批量导出 CSV
    if args.export_csv:
        if not args.files:
            print("错误: 请指定要导出元数据的媒体文件")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        MetadataExporter.export(files, Path(args.export_csv))
        sys.exit(0)

    # 音频指纹识别与比对
    if args.fingerprint:
        if not args.files:
            print("错误: 请指定要生成指纹的音频文件（至少 1 个）")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        AudioFingerprinter.compare_and_display(files)
        sys.exit(0)

    # 音量渐变
    if args.volume_ramp:
        # 选项参数为 START_DB / END_DB，文件从位置参数 args.files 获取
        if not args.files:
            print("错误: 用法 --volume-ramp START_DB END_DB FILE")
            sys.exit(1)
        file_path = Path(args.files[0])
        if not file_path.exists():
            print(f"错误: 文件不存在 {args.files[0]}")
            sys.exit(1)
        try:
            start_db = float(args.volume_ramp[0])
            end_db = float(args.volume_ramp[1])
        except ValueError:
            print("错误: START_DB / END_DB 必须为数字（分贝）")
            sys.exit(1)
        if start_db < -60 or start_db > 30 or end_db < -60 or end_db > 30:
            print("错误: dB 范围超出限制 (-60 ~ +30 dB)")
            sys.exit(1)
        VolumeRamp.apply(file_path, start_db, end_db)
        sys.exit(0)

    # 视频 ASCII 艺术导出
    if args.ascii_art:
        video_path = Path(args.ascii_art)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {args.ascii_art}")
            sys.exit(1)
        if args.ascii_width < 20 or args.ascii_width > 400:
            print(f"错误: ASCII 宽度超出范围 (20 ~ 400): {args.ascii_width}")
            sys.exit(1)
        if args.ascii_fps < 1 or args.ascii_fps > 30:
            print(f"错误: ASCII 帧率超出范围 (1 ~ 30): {args.ascii_fps}")
            sys.exit(1)
        duration = args.gif_duration if args.gif_duration is not None else None
        AsciiArtExporter.export(
            video_path,
            width=args.ascii_width,
            fps=args.ascii_fps,
            max_duration=duration
        )
        sys.exit(0)

    # ===== v2.10.0 新增命令处理 =====
    # 音频混音
    if args.mix:
        if len(args.mix) < 3:
            print("错误: 用法 --mix OUTPUT FILE1 FILE2 [FILE3...]")
            print("      至少需要 1 个输出 + 2 个输入文件")
            sys.exit(1)
        output_path = Path(args.mix[0])
        input_files = [Path(f) for f in args.mix[1:]]
        AudioMixMixer.mix(input_files, output_path, output_format=args.fmt)
        sys.exit(0)

    # 视频拼接
    if args.vconcat:
        if len(args.vconcat) < 3:
            print("错误: 用法 --vconcat OUTPUT FILE1 FILE2 [FILE3...]")
            print("      至少需要 1 个输出 + 2 个输入文件")
            sys.exit(1)
        output_path = Path(args.vconcat[0])
        input_files = [Path(f) for f in args.vconcat[1:]]
        VideoConcat.concat(input_files, output_path)
        sys.exit(0)

    # 视频缩放
    if args.scale:
        video_arg, res_arg = args.scale
        video_path = Path(video_arg)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {video_arg}")
            sys.exit(1)
        res = res_arg.replace('x', 'X').replace(':', 'X')
        parts = res.split('X')
        if len(parts) != 2:
            print(f"错误: 分辨率格式应为 WxH 或 W:H (如 1280x720): {res_arg}")
            sys.exit(1)
        try:
            width = int(parts[0])
            height = int(parts[1])
        except ValueError:
            print(f"错误: 宽高必须为整数: {res_arg}")
            sys.exit(1)
        VideoScaler.scale(video_path, width, height)
        sys.exit(0)

    # 视频旋转
    if args.rotate:
        video_arg, deg_arg = args.rotate
        video_path = Path(video_arg)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {video_arg}")
            sys.exit(1)
        try:
            degrees = int(deg_arg)
        except ValueError:
            print(f"错误: 旋转角度必须为整数: {deg_arg}")
            sys.exit(1)
        VideoRotator.rotate(video_path, degrees)
        sys.exit(0)

    # 视频画面裁剪
    if args.crop:
        video_arg, geom_arg = args.crop
        video_path = Path(video_arg)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {video_arg}")
            sys.exit(1)
        parts = geom_arg.split(':')
        if len(parts) != 4:
            print(f"错误: 裁剪参数格式应为 W:H:X:Y (如 640:480:100:50): {geom_arg}")
            sys.exit(1)
        try:
            w, h, x, y = [int(p) for p in parts]
        except ValueError:
            print(f"错误: 裁剪参数必须为整数: {geom_arg}")
            sys.exit(1)
        VideoCropper.crop(video_path, w, h, x, y)
        sys.exit(0)

    # 视频帧率转换
    if args.fps:
        video_arg, fps_arg = args.fps
        video_path = Path(video_arg)
        if not video_path.exists():
            print(f"错误: 视频文件不存在 {video_arg}")
            sys.exit(1)
        try:
            fps = float(fps_arg)
        except ValueError:
            print(f"错误: 帧率必须为数字: {fps_arg}")
            sys.exit(1)
        FpsConverter.convert(video_path, fps)
        sys.exit(0)

    # 元数据剥离（批量）
    if args.strip_metadata:
        if not args.files:
            print("错误: 请指定要剥离元数据的文件")
            sys.exit(1)
        files = [Path(f) for f in args.files]
        MetadataStripper.batch_strip(files)
        sys.exit(0)

    # 片段重复
    if args.repeat:
        file_arg, start_arg, end_arg, n_arg = args.repeat
        file_path = Path(file_arg)
        if not file_path.exists():
            print(f"错误: 文件不存在 {file_arg}")
            sys.exit(1)
        try:
            start = float(start_arg)
            end = float(end_arg)
        except ValueError:
            print("错误: START / END 必须为数字（秒）")
            sys.exit(1)
        try:
            times = int(n_arg)
        except ValueError:
            print("错误: 重复次数 N 必须为整数")
            sys.exit(1)
        SegmentRepeater.repeat(file_path, start, end, times)
        sys.exit(0)

    # ===== 仅下载歌词 =====
    if args.lyrics:
        targets = args.lyrics  # 现在是列表
        fetcher = OnlineLyricsFetcher()
        src_name_map = {"qq": "QQ音乐", "netease": "网易云", "kugou": "酷狗"}

        # 媒体文件扩展名集合（用于批量模式过滤非媒体文件）
        media_exts = {
            '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.opus', '.m4b',
            '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v',
        }

        def _download_one(target, out_override=None, interactive=False):
            """下载单个目标的歌词，返回 (成功?, 跳过原因或来源标签, 行数)"""
            target_path = Path(target)
            is_file = target_path.exists() and target_path.is_file()

            if is_file:
                # 媒体文件：用元数据/文件名构造关键词
                keyword = LyricsDisplay.build_search_keyword(target_path)
                if out_override:
                    out_path = Path(out_override)
                else:
                    out_path = target_path.with_suffix('.lrc')
                print(f"文件: {target_path.name}")
                print(f"搜索关键词: {keyword}")
            else:
                # 关键词字符串
                keyword = target
                if out_override:
                    out_path = Path(out_override)
                else:
                    safe_name = re.sub(r'[\\/:*?"<>|]', '_', keyword)
                    out_path = Path(f"{safe_name}.lrc")
                print(f"搜索关键词: {keyword}")

            if out_path.exists():
                print(f"提示: {out_path} 已存在，将覆盖")

            if interactive:
                print("正在搜索...")
                candidates = fetcher.search_candidates(keyword, top_n=10)
                if not candidates:
                    print("未找到候选结果")
                    return False, "no_result", 0
                print(f"\n找到 {len(candidates)} 首候选:")
                for i, (name, artist, source, _) in enumerate(candidates):
                    src_label = src_name_map.get(source, source)
                    print(f"  [{i + 1}] {name} - {artist or '未知'}  ({src_label})")
                print("  [0] 取消")
                try:
                    choice = input("\n选择序号: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n已取消")
                    return False, "cancelled", 0
                if not choice or choice == '0':
                    print("已取消")
                    return False, "cancelled", 0
                try:
                    idx = int(choice) - 1
                except ValueError:
                    print("错误: 请输入数字序号")
                    return False, "invalid_input", 0
                if idx < 0 or idx >= len(candidates):
                    print("错误: 序号超出范围")
                    return False, "out_of_range", 0
                cand = candidates[idx]
                lrc = fetcher._fetch_lyric_by_candidate(cand)
                if not fetcher._has_timeline(lrc):
                    print(f"该候选无有效歌词（无时间轴或纯音乐占位）")
                    return False, "no_timeline", 0
                source = cand[2]
                src_label = src_name_map.get(source, source)
            else:
                print("正在搜索（QQ音乐 + 网易云 + 酷狗 聚合）...")
                status, lrc, source = fetcher.search_first(keyword)
                if status != "ok":
                    if status == "no_result":
                        print("未找到匹配结果")
                    elif status == "no_timeline":
                        print("找到候选但无带时间轴的歌词（可能为纯音乐）")
                    elif status == "network_error":
                        print("网络请求失败，请检查网络连接")
                    return False, status, 0
                src_label = src_name_map.get(source, source)

            out_path.write_text(lrc, encoding='utf-8')
            line_count = len([l for l in lrc.split('\n') if l.strip()])
            print(f"\n已保存歌词到: {out_path}")
            print(f"来源: {src_label}")
            print(f"行数: {line_count}")
            return True, src_label, line_count

        if len(targets) == 1:
            # 单目标模式：保持原有完整行为
            _download_one(targets[0], out_override=args.lyrics_output,
                          interactive=args.lyrics_interactive)
            sys.exit(0)
        else:
            # 批量模式
            print(f"批量下载歌词：共 {len(targets)} 个目标")
            if args.lyrics_output:
                print("提示: --lyrics-output 在批量模式下不适用，已忽略")
            if args.lyrics_interactive:
                print("提示: --lyrics-interactive 在批量模式下不适用，已忽略")

            # 过滤：仅处理存在的媒体文件
            valid_files = []
            skipped = []
            for t in targets:
                tp = Path(t)
                if not tp.exists():
                    skipped.append((t, "文件不存在"))
                    continue
                if not tp.is_file():
                    skipped.append((t, "非文件"))
                    continue
                ext = tp.suffix.lower()
                if ext not in media_exts:
                    skipped.append((t, f"非媒体文件({ext})"))
                    continue
                # 注：.lrc 不在 media_exts 中，已被上一个判断拦截，无需重复判断
                valid_files.append(t)

            if skipped:
                print(f"\n跳过 {len(skipped)} 个目标:")
                for t, reason in skipped:
                    print(f"  - {t} ({reason})")

            if not valid_files:
                print("\n错误: 没有有效的媒体文件可处理")
                sys.exit(1)

            print(f"\n开始处理 {len(valid_files)} 个媒体文件...\n")
            success_count = 0
            fail_count = 0
            results = []  # (文件名, 状态, 来源/原因, 行数)
            for i, f in enumerate(valid_files, 1):
                fp = Path(f)
                print(f"[{i}/{len(valid_files)}] === {fp.name} ===")
                ok, info, lines = _download_one(f, interactive=False)
                if ok:
                    success_count += 1
                    results.append((fp.name, "成功", info, lines))
                else:
                    fail_count += 1
                    results.append((fp.name, "失败", info, 0))
                print()

            # 汇总报告
            print("=" * 50)
            print("批量下载完成")
            print("=" * 50)
            print(f"总数: {len(valid_files)}  成功: {success_count}  失败: {fail_count}")
            print(f"跳过: {len(skipped)}")
            print("\n详细:")
            for name, status, info, lines in results:
                if status == "成功":
                    print(f"  ✓ {name} - {info} ({lines} 行)")
                else:
                    reason_map = {
                        "no_result": "未找到结果",
                        "no_timeline": "无时间轴歌词",
                        "network_error": "网络错误",
                    }
                    reason = reason_map.get(info, info)
                    print(f"  ✗ {name} - {reason}")
            sys.exit(0 if fail_count == 0 else 1)

    # ===== 歌曲下载模式 =====
    if args.download is not None:
        download_song_interactive(config, args.download, args.download_output)
        sys.exit(0)

    if not args.files:
        # 无文件参数时默认使用当前目录（v2.11.9 引入）
        args.files = ['.']
    
    # 加载配置
    config = Config()
    
    # 应用命令行参数
    if args.volume is not None:
        config.set('volume', max(0, min(100, args.volume)))
    if args.speed is not None:
        config.set('playback_speed', max(0.5, min(2.0, args.speed)))
    if args.loop:
        config.set('loop_mode', args.loop)
    
    # 媒体信息模式
    if args.info:
        for file_path in args.files:
            path = Path(file_path)
            if path.exists():
                info = MediaInfo.get_info(path)
                MediaInfo.display_info(info)
            else:
                print(f"文件不存在: {file_path}")
        sys.exit(0)
    
    # 检查是否是目录
    paths = [Path(f) for f in args.files]
    first_path = paths[0]
    
    if first_path.is_dir() or args.playlist or len(paths) > 1:
        # 播放列表模式
        playlist = Playlist()
        
        for path in paths:
            if path.is_dir():
                playlist.add_directory(path, recursive=True)
            elif path.exists():
                playlist.add_file(path)
        
        if args.shuffle:
            playlist.shuffle()
        
        play_playlist(playlist, config, args.loop, explicit_loop=bool(args.loop))
    else:
        # 单文件模式
        file_ext = first_path.suffix.lower()
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv', '.m4v'}
        
        # 创建播放器实例
        if file_ext in video_extensions:
            # 视频文件
            player = VideoPlayer(first_path, config)
            
            # 设置信号处理
            def signal_handler(sig, frame):
                print("\n退出播放")
                player.stop()
                sys.exit(0)
            
            signal.signal(signal.SIGINT, signal_handler)
            
            # 运行视频播放器
            try:
                player.play()
            except KeyboardInterrupt:
                print("\n退出播放")
                player.stop()
                sys.exit(0)
        else:
            # 音频文件
            player = AudioPlayer(first_path, config)

            # 应用均衡器预设
            if args.eq:
                if player.equalizer.set_preset(args.eq.lower()):
                    player.equalizer.enabled = True
                    print(f"均衡器预设: {args.eq}")
                else:
                    print(f"未知的均衡器预设: {args.eq}")
                    print("使用 'mp --eq-list' 查看可用预设")

            # 设置信号处理
            def signal_handler(sig, frame):
                print("\n退出播放")
                player.stop()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)

            # 运行音频播放器
            try:
                player.run()
            except KeyboardInterrupt:
                print("\n退出播放")
                player.stop()
                sys.exit(0)


if __name__ == "__main__":
    check_for_update()
    main()
