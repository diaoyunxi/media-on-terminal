#!/usr/bin/env python3
"""mp - Terminal Media Player 包

将原 9488 行单文件拆分为功能模块的包。
所有公共类和函数通过 __init__.py 重新导出，保持向后兼容。
"""

__version__ = "2.12.0"

# 公共导入
import os

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

from mp.audio_tools import (
    AudioExtractor,
    AudioMerger,
    AudioMixMixer,
    AudioRecorder,
    AudioReverser,
    AudioTrimmer,
    AVMuxer,
    ChannelConverter,
    RingtoneMaker,
    SampleRateConverter,
)
from mp.config import Config, ConfigBackup
from mp.constants import (
    CONFIG_DIR,
    CONFIG_FILE,
    FAVORITES_FILE,
    GITHUB_REPO,
    HISTORY_FILE,
    PLAYLIST_DIR,
    RADIO_FILE,
    UPDATE_CACHE_FILE,
)
from mp.download import download_song_interactive
from mp.effects import (
    AudioConverter,
    AudioNormalizer,
    CrossfadeManager,
    Equalizer,
    FadeEffect,
    PitchControl,
    ReverbEffect,
    VolumeGain,
    VolumeRamp,
)
from mp.file_browser import FileBrowser
from mp.help_text import show_help
from mp.lyrics import LyricsDisplay, OnlineLyricsFetcher
from mp.managers import (
    ABLoop,
    BookmarkManager,
    FavoritesManager,
    HistoryManager,
    QueueManager,
    RadioManager,
    SleepTimer,
    StatisticsManager,
)
from mp.media_info import MediaInfo
from mp.media_library import MediaLibrary
from mp.media_tools import (
    AudioFingerprinter,
    DuplicateFinder,
    MediaHealthChecker,
    MediaSplitter,
    MetadataExporter,
    SegmentRepeater,
    SilenceCutter,
)
from mp.metadata import (
    BatchRenamer,
    BPMDetector,
    MetadataEditor,
    MetadataStripper,
    SubtitleExtractor,
)
from mp.noise import NoiseGenerator
from mp.players import AudioPlayer, VideoPlayer
from mp.playlist import Playlist, PlaylistIO
from mp.updater import check_for_update
from mp.utils import (
    _display_width,
    _truncate_to_width,
    check_and_install_dependencies,
    check_ffmpeg,
    get_pip_install_args,
    install_system_dependencies,
)
from mp.video_tools import (
    ContactSheet,
    FpsConverter,
    GifConverter,
    ScreenshotCapture,
    VideoConcat,
    VideoCropper,
    VideoRotator,
    VideoScaler,
)
from mp.visual import (
    AsciiArtExporter,
    AudioVisualizer,
    CoverExtractor,
    SpectrogramGenerator,
    WaveformGenerator,
)

__all__ = [
    "ABLoop",
    "AVMuxer",
    "AsciiArtExporter",
    "AudioConverter",
    "AudioExtractor",
    "AudioFingerprinter",
    "AudioMerger",
    "AudioMixMixer",
    "AudioNormalizer",
    "AudioPlayer",
    "AudioRecorder",
    "AudioReverser",
    "AudioTrimmer",
    "AudioVisualizer",
    "BPMDetector",
    "BatchRenamer",
    "BookmarkManager",
    "ChannelConverter",
    "Config",
    "ConfigBackup",
    "ContactSheet",
    "CoverExtractor",
    "CrossfadeManager",
    "DuplicateFinder",
    "Equalizer",
    "FadeEffect",
    "FavoritesManager",
    "FileBrowser",
    "FpsConverter",
    "GifConverter",
    "HistoryManager",
    "LyricsDisplay",
    "MediaHealthChecker",
    "MediaInfo",
    "MediaLibrary",
    "MediaSplitter",
    "MetadataEditor",
    "MetadataExporter",
    "MetadataStripper",
    "NoiseGenerator",
    "OnlineLyricsFetcher",
    "PitchControl",
    "Playlist",
    "PlaylistIO",
    "QueueManager",
    "RadioManager",
    "ReverbEffect",
    "RingtoneMaker",
    "SampleRateConverter",
    "ScreenshotCapture",
    "SegmentRepeater",
    "SilenceCutter",
    "SleepTimer",
    "SpectrogramGenerator",
    "StatisticsManager",
    "SubtitleExtractor",
    "VideoConcat",
    "VideoCropper",
    "VideoPlayer",
    "VideoRotator",
    "VideoScaler",
    "VolumeGain",
    "VolumeRamp",
    "WaveformGenerator",
    "__version__",
    "check_for_update",
    "download_song_interactive",
    "show_help",
]
