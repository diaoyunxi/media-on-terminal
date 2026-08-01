#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""帮助信息"""

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

def show_help():
    """显示帮助信息"""
    help_text = """
╔═══════════════════════════════════════════════════════════════╗
║                    mp - Terminal Media Player                 ║
╚═══════════════════════════════════════════════════════════════╝

一个轻量级的终端媒体播放器，支持音频和视频格式。

用法:
    mp [选项] <媒体文件/目录/播放列表>
    mp --info <媒体文件>              显示媒体信息
    mp --playlist <文件列表...>       播放多个文件
    mp --favorites                    播放收藏列表
    mp --history                      显示播放历史

选项:
    -h, --help          显示此帮助信息
    -V, --version       显示当前版本号
    --update            检查并更新到最新版本
    -i, --info          显示媒体文件详细信息
    -p, --playlist      播放列表模式
    -s, --shuffle       随机播放
    -l, --loop          循环模式 (single/all)
    -v, --volume N      设置音量 (0-100)
    --speed N           设置播放速度 (0.5-2.0)
    --favorites         播放收藏列表
    --history           显示播放历史
    --clear-history     清空播放历史
    --stats             显示播放统计
    --clear-stats       清空播放统计
    --convert FMT       转换音频格式 (mp3/wav/ogg/m4a/flac/aac/opus)
    --eq PRESET         使用均衡器预设播放
    --radio NAME        播放网络电台
    --radio-list        显示电台列表
    --radio-add N URL   添加电台
    --radio-del NAME    删除电台
    --browse            打开文件浏览器选择文件
    --noise [TYPE]      播放噪声 (white/pink/brown/rain/ocean)
    --edit-tags FILE    编辑媒体文件元数据
    --record [FILE]     录制麦克风音频 (wav/mp3/ogg/m4a/flac)
    --extract-audio 视频  从视频提取音轨 (默认mp3)
    --to-gif 视频       将视频片段转为GIF动画
    --screenshot 视频   从视频捕获画面帧
    --normalize FILE    音频音量归一化 (loudnorm/dynaudnorm)
    --export-m3u 输出 文件...  导出M3U播放列表
    --import-m3u FILE   导入M3U播放列表并播放
    --library-scan 目录 扫描目录建立媒体库索引
    --library-search 关键词  搜索媒体库
    --library-stats     显示媒体库统计
    --library-clear     清空媒体库
    --trim FILE START [END] 裁剪媒体文件指定时间段
    --merge OUTPUT FILE... 合并多个音频文件
    --reverse FILE...   反向音频（支持批量）
    --fade FILE IN [OUT] 添加淡入淡出效果（秒）
    --reverb [PRESET]   应用混响预设（需要先指定文件）
    --reverb-list       显示混响预设列表
    --extract-subtitles 视频  从视频提取字幕（srt/ass）
    --bpm FILE...       检测音频节拍速度 BPM（支持批量）
    --contact-sheet 视频  生成视频缩略图组合
    --find-duplicates 目录  查找重复媒体文件
    --backup-config [输出] 备份配置到zip
    --restore-config 输入  从zip恢复配置
    --rename PATTERN 目录  按元数据批量重命名文件
    --spectrogram FILE  生成音频频谱图PNG
    --waveform FILE     生成音频波形图PNG
    --cover FILE        提取嵌入的封面/海报图片
    --gain DB FILE...   音量增益(dB)，支持批量
    --ringtone FILE [START [DURATION]]  生成铃声（默认30秒，带淡入淡出）
    --channels N FILE... 转换声道数 1(单声道)/2(立体声)
    --resample RATE FILE... 转换采样率(Hz)
    --mux VIDEO AUDIO   将音频合并到视频（替换原音轨）
    --fade-sec N        铃声淡入淡出时长（秒，默认2.0）
    --health-check FILE...  媒体健康检查（检测文件是否损坏、可解码）
    --silence-detect FILE   检测音频/视频中的静音段
    --silence-cut FILE  自动裁剪音频中的静音段
    --silence-threshold DB  静音检测阈值（dB，默认 -30）
    --silence-duration SEC  静音最短时长（秒，默认 0.5）
    --split FILE SPEC   媒体分段（SPEC 为段数或时长如 60 / 01:30）
    --export-csv OUT FILE...  批量导出元数据到 CSV
    --fingerprint FILE... 生成音频指纹并比对相似度
    --volume-ramp START_DB END_DB FILE  音量渐变（渐强/渐弱）
    --ascii-art VIDEO   将视频导出为 ASCII 文本动画
    --ascii-width N     ASCII 艺术宽度（字符数，默认 80）
    --ascii-fps N       ASCII 艺术帧率（默认 10）
    --lyrics TARGET...  仅下载歌词不播放。TARGET 为媒体文件路径（用其元数据/文件名搜索）
                        或关键词字符串；支持多个目标批量下载（如 --lyrics ./*）
    --lyrics-interactive 与 --lyrics 配合：交互式选择候选歌词（仅单目标）
    --lyrics-output PATH 与 --lyrics 配合：指定输出 .lrc 路径（仅单目标，默认同名 .lrc 或 关键词.lrc）
    --download [KEYWORD] 在线搜索并下载歌曲（含歌词）。无参数时进入交互式搜索，带关键词时自动搜索
    --download-output DIR 与 --download 配合：指定下载输出目录（默认当前目录）

支持格式:
    音频: MP3, WAV, OGG, M4A, FLAC, AAC, OPUS 等
    视频: MP4, MKV, AVI, MOV, WEBM 等

示例:
    mp song.mp3                         # 播放音乐
    mp video.mp4                        # 播放视频（字符渲染）
    mp "music/歌曲.flac"                # 支持带空格的路径
    mp --info song.mp3                  # 显示媒体信息
    mp -p *.mp3                         # 播放所有MP3文件
    mp -p --shuffle *.mp3               # 随机播放所有MP3
    mp -l single song.mp3               # 单曲循环
    mp -v 50 song.mp3                   # 设置50%音量
    mp --speed 1.5 song.mp3             # 1.5倍速播放
    mp ~/Music                          # 播放目录中所有媒体
    mp --favorites                      # 播放收藏列表
    mp --history                        # 查看播放历史
    mp --clear-history                  # 清空播放历史
    mp --stats                          # 查看播放统计
    mp --clear-stats                    # 清空播放统计
    mp --eq rock song.mp3               # 使用摇滚均衡器预设播放
    mp --eq-list                        # 显示均衡器预设列表
    mp --convert mp3 song.flac          # 将FLAC转换为MP3
    mp --convert ogg *.wav              # 批量将WAV转换为OGG
    mp --browse                         # 打开文件浏览器选择文件
    mp --noise rain                     # 播放雨声噪声
    mp --noise                          # 交互式噪声生成器
    mp --edit-tags song.mp3             # 编辑歌曲元数据
    mp --record                         # 交互式录制麦克风音频
    mp --record voice.mp3               # 录制并保存为MP3
    mp --extract-audio video.mp4        # 从视频提取MP3音轨
    mp --extract-audio video.mkv --fmt wav  # 提取为WAV
    mp --to-gif video.mp4               # 视频转GIF（默认前5秒）
    mp --to-gif video.mp4 --gif-start 30 --gif-duration 3
    mp --screenshot video.mp4           # 截取视频开头画面
    mp --screenshot video.mp4 --at 60   # 在60秒处截图
    mp --screenshot video.mp4 --at 90 --count 4  # 批量截图
    mp --normalize song.mp3             # 响度归一化
    mp --normalize *.mp3 --fmt dynaudnorm  # 批量动态归一化
    mp --export-m3u my.m3u *.mp3        # 导出M3U播放列表
    mp --import-m3u playlist.m3u       # 导入并播放M3U
    mp --library-scan ~/Music           # 扫描建立媒体库
    mp --library-search "周杰伦"        # 搜索媒体库
    mp --library-stats                  # 媒体库统计
    mp --trim song.mp3 30 60            # 截取 30-60 秒片段
    mp --trim video.mp4 0 10            # 截取视频前10秒
    mp --merge out.mp3 a.mp3 b.mp3 c.mp3  # 合并三个文件
    mp --reverse song.mp3               # 反向音频
    mp --fade song.mp3 2 3              # 2秒淡入 + 3秒淡出
    mp --reverb hall song.mp3           # 应用音乐厅混响
    mp --reverb-list                    # 显示混响预设
    mp --extract-subtitles movie.mkv    # 提取字幕
    mp --extract-subtitles movie.mkv --fmt ass  # 提取为ASS
    mp --bpm song.mp3                   # 检测BPM
    mp --contact-sheet movie.mp4        # 生成4x4缩略图
    mp --contact-sheet movie.mp4 --rows 3 --cols 5
    mp --find-duplicates ~/Music        # 查找重复音频
    mp --backup-config                  # 备份配置到 ~/mp_config_backup_*.zip
    mp --restore-config backup.zip      # 恢复配置
    mp --rename "{artist} - {title}" ~/Music  # 按元数据重命名
    mp --rename "{track}. {title}" . --dry-run  # 演练模式
    mp --spectrogram song.mp3           # 生成频谱图
    mp --waveform song.mp3              # 生成波形图
    mp --cover song.mp3                 # 提取嵌入封面
    mp --gain 3 song.mp3                # 音量增益 +3dB
    mp --gain -2 *.mp3                  # 批量降低音量
    mp --ringtone song.mp3              # 生成30秒铃声（从头开始）
    mp --ringtone song.mp3 30 20        # 从30秒起截取20秒铃声
    mp --channels 1 song.mp3            # 转为单声道
    mp --channels 2 *.mp3               # 批量转立体声
    mp --resample 44100 song.mp3        # 转换采样率为44100Hz
    mp --mux video.mp4 bgm.mp3          # 用bgm替换视频音轨
    mp --health-check *.mp3             # 检查音频文件是否损坏
    mp --silence-detect song.mp3        # 检测静音段
    mp --silence-cut song.mp3           # 自动裁剪静音段
    mp --silence-cut song.mp3 --silence-threshold -40 --silence-duration 1
    mp --split song.mp3 4               # 按段数切分为 4 段
    mp --split song.mp3 01:30           # 按每段 90 秒切分
    mp --export-csv info.csv *.mp3      # 批量导出元数据到 CSV
    mp --fingerprint a.mp3 b.mp3        # 生成指纹并比对相似度
    mp --volume-ramp -6 6 song.mp3      # 从 -6dB 渐变到 +6dB
    mp --ascii-art video.mp4            # 视频转 ASCII 文本动画
    mp --ascii-art video.mp4 --ascii-width 100 --ascii-fps 15
    mp --mix mix.mp3 vocal.mp3 bgm.mp3  # 混音（vocal + 背景乐）
    mp --vconcat out.mp4 a.mp4 b.mp4 c.mp4  # 拼接多个视频
    mp --scale video.mp4 1280 720       # 缩放视频到 720p
    mp --scale video.mp4 1920 1080      # 缩放视频到 1080p
    mp --rotate video.mp4 90            # 顺时针旋转 90 度
    mp --crop video.mp4 640 480 100 50  # 从 (100,50) 起裁取 640x480
    mp --fps video.mp4 60               # 转换为 60 fps
    mp --strip-metadata song.mp3        # 剥离所有元数据
    mp --strip-metadata *.mp3           # 批量剥离元数据
    mp --repeat song.mp3 30 60 3        # 重复 30-60 秒片段 3 次后接尾段
    mp --lyrics song.mp3                # 用 song.mp3 的元数据/文件名搜索歌词并保存为 song.lrc
    mp --lyrics "陈奕迅 浮夸"           # 用关键词直接搜索歌词，保存为 陈奕迅 浮夸.lrc
    mp --lyrics song.mp3 --lyrics-interactive  # 交互式从候选列表中选择
    mp --lyrics song.mp3 --lyrics-output /tmp/浮夸.lrc  # 指定输出路径
    mp --lyrics ./*.mp3                 # 批量下载当前目录所有 mp3 的歌词
    mp --lyrics a.mp3 b.mp3 c.flac      # 批量下载多个文件
    mp --download                        # 交互式搜索并下载歌曲（含歌词）
    mp --download "陈奕迅 浮夸"          # 搜索并下载指定歌曲及歌词
    mp --download --download-output ~/Music  # 下载到指定目录

播放控制:
    空格键              暂停/继续
    ← 左箭头            后退10秒（仅音频）
    → 右箭头            前进10秒（仅音频）
    ↑ 上箭头            增加音量
    ↓ 下箭头            降低音量
    < 或 ,              降低播放速度（仅音频）
    > 或 .              增加播放速度（仅音频）
    l                   切换循环模式（仅音频）
    i                   显示媒体信息
    n                   下一首（播放列表模式）
    p                   上一首（播放列表模式）
    s                   切换随机播放（播放列表模式）
    q 或 Ctrl+C         退出播放

音频增强功能:
    v                   切换音频可视化器
    b                   保存当前播放位置为书签
    r                   从书签恢复播放
    o                   切换歌词显示（本地.lrc或在线搜索缓存）
    N                   在线搜索歌词（QQ音乐+网易云+酷狗聚合，手动选择候选）
    f                   收藏/取消收藏当前歌曲
    a                   设置AB循环（按两次设置A点和B点）
    t                   设置定时停止（睡眠定时器）
    h                   显示播放历史
    e                   切换均衡器开关
    E                   显示均衡器预设列表
    Q                   显示播放队列
    S                   显示播放统计
    c                   转换当前音频格式
    m                   编辑当前文件元数据
    p/P                 降低/升高音调（半音）
    X                   重置音调
    x                   切换交叉淡入淡出
    F                   打开文件浏览器

提示:
    • 播放器会自动安装ffmpeg和pygame依赖
    • 视频播放使用ASCII字符渲染，需要支持256色的终端
    • 支持带空格的路径，请使用引号括起来
    • 配置保存在 ~/.config/mp/config.json
    • 书签保存在 ~/.config/mp/bookmarks.json
    • 收藏保存在 ~/.config/mp/favorites.json
    • 历史保存在 ~/.config/mp/history.json
    • 媒体库索引保存在 ~/.config/mp/library.json
    • 歌词文件需与音频文件同名（.lrc格式）
    • 在线歌词：本地无.lrc时自动搜索（QQ音乐+网易云+酷狗聚合），按 N 手动搜索
    • 搜索关键词优先使用元数据(title+artist)，无元数据时回退清洗后的文件名
    • 在线歌词成功后自动缓存为同名.lrc，下次播放直接读取本地
    • 录制/转换/截图/归一化/GIF等工具命令无需播放即可独立使用
"""
    print(help_text)


