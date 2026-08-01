#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mp - Terminal Media Player 包

将原 9488 行单文件拆分为功能模块的包。
所有公共类和函数通过 __init__.py 重新导出，保持向后兼容。
"""

__version__ = "2.12.0"

# 公共导入
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

from mp.constants import (
    CONFIG_DIR, CONFIG_FILE, PLAYLIST_DIR,
    FAVORITES_FILE, HISTORY_FILE, RADIO_FILE,
    UPDATE_CACHE_FILE, GITHUB_REPO,
)

from mp.utils import (
    _display_width, _truncate_to_width,
    get_pip_install_args, install_system_dependencies,
    check_and_install_dependencies, check_ffmpeg,
)
from mp.config import Config, ConfigBackup
from mp.media_info import MediaInfo
from mp.managers import (
    BookmarkManager, FavoritesManager, HistoryManager,
    SleepTimer, ABLoop, RadioManager, QueueManager, StatisticsManager,
)
from mp.effects import (
    AudioConverter, Equalizer, CrossfadeManager, PitchControl,
    FadeEffect, ReverbEffect, AudioNormalizer, VolumeGain, VolumeRamp,
)
from mp.file_browser import FileBrowser
from mp.noise import NoiseGenerator
from mp.metadata import (
    MetadataEditor, BatchRenamer, MetadataStripper,
    BPMDetector, SubtitleExtractor,
)
from mp.lyrics import LyricsDisplay, OnlineLyricsFetcher
from mp.visual import (
    AudioVisualizer, SpectrogramGenerator, WaveformGenerator,
    CoverExtractor, AsciiArtExporter,
)
from mp.playlist import Playlist, PlaylistIO
from mp.players import AudioPlayer, VideoPlayer
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
from mp.media_library import MediaLibrary
from mp.updater import check_for_update
from mp.download import download_song_interactive
from mp.help_text import show_help

__all__ = [
    "__version__",
    "Config", "ConfigBackup", "MediaInfo",
    "BookmarkManager", "FavoritesManager", "HistoryManager",
    "SleepTimer", "ABLoop", "RadioManager", "QueueManager", "StatisticsManager",
    "AudioConverter", "Equalizer", "CrossfadeManager", "PitchControl",
    "FadeEffect", "ReverbEffect", "AudioNormalizer", "VolumeGain", "VolumeRamp",
    "FileBrowser", "NoiseGenerator",
    "MetadataEditor", "BatchRenamer", "MetadataStripper", "BPMDetector", "SubtitleExtractor",
    "LyricsDisplay", "OnlineLyricsFetcher",
    "AudioVisualizer", "SpectrogramGenerator", "WaveformGenerator", "CoverExtractor", "AsciiArtExporter",
    "Playlist", "PlaylistIO", "AudioPlayer", "VideoPlayer",
    "AudioRecorder", "AudioExtractor", "AudioTrimmer", "AudioMerger", "AudioReverser",
    "ChannelConverter", "SampleRateConverter", "AVMuxer", "AudioMixMixer", "RingtoneMaker",
    "GifConverter", "ScreenshotCapture", "VideoConcat", "VideoScaler",
    "VideoRotator", "VideoCropper", "FpsConverter", "ContactSheet",
    "MediaSplitter", "SilenceCutter", "SegmentRepeater",
    "MediaHealthChecker", "DuplicateFinder", "MetadataExporter", "AudioFingerprinter",
    "MediaLibrary", "check_for_update", "download_song_interactive",
    "show_help",
]
