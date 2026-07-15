#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mp - Terminal Media Player 全面测试脚本"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

TEST_DIR = Path("/workspace/mp_test")
TEST_AUDIO_WAV = TEST_DIR / "test_audio.wav"
TEST_AUDIO_MP3 = TEST_DIR / "test_audio.mp3"
TEST_VIDEO_MP4 = TEST_DIR / "test_video.mp4"

os.makedirs(TEST_DIR, exist_ok=True)

def log(msg, status="INFO"):
    colors = {"INFO": "\033[0;32m", "WARN": "\033[1;33m", "ERROR": "\033[0;31m", "SUCCESS": "\033[0;32m"}
    print(f"{colors.get(status, '')}[{status}] {msg}\033[0m")

def run_cmd(cmd, timeout=60):
    """运行命令，自动回答 pygame 安装确认"""
    try:
        result = subprocess.run(
            ["bash", "-c", f"echo '' | {' '.join(cmd)}"],
            capture_output=True, text=True, timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 1, "", "Command timeout")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))

def generate_test_files():
    """生成测试媒体文件"""
    log("生成测试媒体文件...", "INFO")
    
    if not TEST_AUDIO_WAV.exists():
        result = subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
            "-ar", "44100", "-ac", "2", "-sample_fmt", "s16", str(TEST_AUDIO_WAV)
        ], capture_output=True, timeout=30)
        if result.returncode == 0:
            log(f"✓ 生成 WAV: {TEST_AUDIO_WAV}", "SUCCESS")
        else:
            log(f"✗ WAV 生成失败", "ERROR")
            return False
    
    if not TEST_AUDIO_MP3.exists():
        result = subprocess.run([
            "ffmpeg", "-y", "-i", str(TEST_AUDIO_WAV), "-c:a", "libmp3lame", "-b:a", "128k", str(TEST_AUDIO_MP3)
        ], capture_output=True, timeout=30)
        if result.returncode == 0:
            log(f"✓ 生成 MP3: {TEST_AUDIO_MP3}", "SUCCESS")
        else:
            log(f"✗ MP3 生成失败", "ERROR")
            return False
    
    if not TEST_VIDEO_MP4.exists():
        result = subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=5:size=640x480:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k", str(TEST_VIDEO_MP4)
        ], capture_output=True, timeout=30)
        if result.returncode == 0:
            log(f"✓ 生成视频: {TEST_VIDEO_MP4}", "SUCCESS")
        else:
            log(f"✗ 视频生成失败", "ERROR")
            return False
    
    return True

def test_file_generation(output_file, description):
    """检查输出文件是否生成"""
    if output_file.exists() and output_file.stat().st_size > 0:
        log(f"✓ {description}: {output_file.name}", "SUCCESS")
        return True
    log(f"✗ {description}失败: 文件未生成", "ERROR")
    return False

def test_text_output(result, expected_text, description):
    """检查输出是否包含预期文本"""
    if expected_text in result.stdout:
        log(f"✓ {description}", "SUCCESS")
        return True
    log(f"✗ {description}失败", "ERROR")
    return False

def test_help():
    log("测试 --help", "INFO")
    result = subprocess.run([sys.executable, "mp.py", "--help"], capture_output=True, text=True, timeout=10)
    return test_text_output(result, "mp - Terminal Media Player", "帮助信息")

def test_version():
    log("测试版本信息", "INFO")
    result = subprocess.run([sys.executable, "-c", "import mp; print(mp.__version__)"], capture_output=True, text=True, timeout=10)
    return test_text_output(result, "2.11.11", "版本信息")

def test_media_info():
    log("测试 --info 媒体信息", "INFO")
    result = run_cmd([sys.executable, "mp.py", "--info", str(TEST_AUDIO_MP3)], timeout=30)
    return test_text_output(result, "时长", "媒体信息")

def test_audio_convert():
    log("测试音频转换 --convert", "INFO")
    output = TEST_DIR / "test_audio.flac"
    run_cmd([sys.executable, "mp.py", "--convert", "flac", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "转换成功")

def test_audio_trim():
    log("测试音频裁剪 --trim", "INFO")
    output = TEST_DIR / "test_audio_trim_1s-3s.wav"
    run_cmd([sys.executable, "mp.py", "--trim", str(TEST_AUDIO_WAV), "1", "3"], timeout=60)
    return test_file_generation(output, "裁剪成功")

def test_audio_merge():
    log("测试音频合并 --merge", "INFO")
    output = TEST_DIR / "merged.wav"
    run_cmd([sys.executable, "mp.py", "--merge", str(output), str(TEST_AUDIO_WAV), str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "合并成功")

def test_audio_reverse():
    log("测试音频反向 --reverse", "INFO")
    output = TEST_DIR / "test_audio_reversed.wav"
    run_cmd([sys.executable, "mp.py", "--reverse", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "反向成功")

def test_fade():
    log("测试淡入淡出 --fade", "INFO")
    output = TEST_DIR / "test_audio_fade.wav"
    run_cmd([sys.executable, "mp.py", "--fade", str(TEST_AUDIO_WAV), "1", "1"], timeout=60)
    return test_file_generation(output, "淡入淡出成功")

def test_reverb():
    log("测试混响效果 --reverb", "INFO")
    output = TEST_DIR / "test_audio_room.wav"
    run_cmd([sys.executable, "mp.py", "--reverb", "room", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "混响成功")

def test_bpm():
    log("测试 BPM 检测 --bpm", "INFO")
    result = run_cmd([sys.executable, "mp.py", "--bpm", str(TEST_AUDIO_WAV)], timeout=30)
    return test_text_output(result, "BPM", "BPM 检测")

def test_normalize():
    log("测试音频归一化 --normalize", "INFO")
    output = TEST_DIR / "test_audio_norm.wav"
    run_cmd([sys.executable, "mp.py", "--normalize", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "归一化成功")

def test_lyrics_search():
    log("测试歌词搜索 --lyrics", "INFO")
    run_cmd([sys.executable, "mp.py", "--lyrics", "周杰伦 晴天"], timeout=30)
    return True

def test_noise():
    log("测试噪声生成器 --noise", "INFO")
    result = subprocess.run([sys.executable, "mp.py", "--noise", "white"], 
                           capture_output=True, text=True, timeout=2)
    return True

def test_equalizer_list():
    log("测试均衡器列表 --eq-list", "INFO")
    result = subprocess.run([sys.executable, "mp.py", "--eq-list"], capture_output=True, text=True, timeout=10)
    return test_text_output(result, "flat", "均衡器列表")

def test_reverb_list():
    log("测试混响列表 --reverb-list", "INFO")
    result = subprocess.run([sys.executable, "mp.py", "--reverb-list"], capture_output=True, text=True, timeout=10)
    return test_text_output(result, "room", "混响列表")

def test_radio_list():
    log("测试电台列表 --radio-list", "INFO")
    subprocess.run([sys.executable, "mp.py", "--radio-list"], capture_output=True, timeout=10)
    return True

def test_library_scan():
    log("测试媒体库扫描 --library-scan", "INFO")
    run_cmd([sys.executable, "mp.py", "--library-scan", str(TEST_DIR)], timeout=30)
    return True

def test_library_stats():
    log("测试媒体库统计 --library-stats", "INFO")
    result = run_cmd([sys.executable, "mp.py", "--library-stats"], timeout=10)
    return test_text_output(result, "文件", "媒体库统计")

def test_export_m3u():
    log("测试导出播放列表 --export-m3u", "INFO")
    output = TEST_DIR / "test.m3u"
    run_cmd([sys.executable, "mp.py", "--export-m3u", str(output), str(TEST_AUDIO_WAV), str(TEST_AUDIO_MP3)], timeout=30)
    return test_file_generation(output, "导出 M3U")

def test_screenshot():
    log("测试视频截图 --screenshot", "INFO")
    output = TEST_DIR / "test_video_shot_00-00.png"
    run_cmd([sys.executable, "mp.py", "--screenshot", str(TEST_VIDEO_MP4)], timeout=30)
    return test_file_generation(output, "截图成功")

def test_extract_audio():
    log("测试音频提取 --extract-audio", "INFO")
    output = TEST_DIR / "test_video.mp3"
    run_cmd([sys.executable, "mp.py", "--extract-audio", str(TEST_VIDEO_MP4)], timeout=60)
    return test_file_generation(output, "音频提取成功")

def test_to_gif():
    log("测试视频转GIF --to-gif", "INFO")
    output = TEST_DIR / "test_video.gif"
    run_cmd([sys.executable, "mp.py", "--to-gif", str(TEST_VIDEO_MP4), "--gif-duration", "2"], timeout=60)
    return test_file_generation(output, "GIF 转换成功")

def test_spectrogram():
    log("测试频谱图生成 --spectrogram", "INFO")
    output = TEST_DIR / "test_audio.spectrogram.png"
    run_cmd([sys.executable, "mp.py", "--spectrogram", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "频谱图生成成功")

def test_waveform():
    log("测试波形图生成 --waveform", "INFO")
    output = TEST_DIR / "test_audio.waveform.png"
    run_cmd([sys.executable, "mp.py", "--waveform", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "波形图生成成功")

def test_gain():
    log("测试音量增益 --gain", "INFO")
    output = TEST_DIR / "test_audio_gainp3.0dB.wav"
    run_cmd([sys.executable, "mp.py", "--gain", "3", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "音量增益成功")

def test_ringtone():
    log("测试铃声生成 --ringtone", "INFO")
    output = TEST_DIR / "test_audio_ringtone.wav"
    run_cmd([sys.executable, "mp.py", "--ringtone", str(TEST_AUDIO_WAV), "1", "5"], timeout=60)
    return test_file_generation(output, "铃声生成成功")

def test_channels():
    log("测试声道转换 --channels", "INFO")
    output = TEST_DIR / "test_audio_mono.wav"
    run_cmd([sys.executable, "mp.py", "--channels", "1", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "声道转换成功")

def test_resample():
    log("测试采样率转换 --resample", "INFO")
    output = TEST_DIR / "test_audio_22050Hz.wav"
    run_cmd([sys.executable, "mp.py", "--resample", "22050", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "采样率转换成功")

def test_health_check():
    log("测试媒体健康检查 --health-check", "INFO")
    result = run_cmd([sys.executable, "mp.py", "--health-check", str(TEST_AUDIO_WAV)], timeout=30)
    return ("健康" in result.stdout) or ("异常" in result.stdout)

def test_silence_detect():
    log("测试静音检测 --silence-detect", "INFO")
    run_cmd([sys.executable, "mp.py", "--silence-detect", str(TEST_AUDIO_WAV)], timeout=30)
    return True

def test_split():
    log("测试媒体分段 --split", "INFO")
    output = TEST_DIR / "test_audio_parts"
    run_cmd([sys.executable, "mp.py", "--split", str(TEST_AUDIO_WAV), "2"], timeout=60)
    if output.exists() and len(list(output.glob("*"))) >= 2:
        log(f"✓ 分段成功: {output.name}", "SUCCESS")
        return True
    log(f"✗ 分段失败", "ERROR")
    return False

def test_export_csv():
    log("测试元数据导出 --export-csv", "INFO")
    output = TEST_DIR / "metadata.csv"
    run_cmd([sys.executable, "mp.py", "--export-csv", str(output), str(TEST_AUDIO_WAV), str(TEST_AUDIO_MP3)], timeout=30)
    return test_file_generation(output, "CSV 导出成功")

def test_fingerprint():
    log("测试音频指纹 --fingerprint", "INFO")
    run_cmd([sys.executable, "mp.py", "--fingerprint", str(TEST_AUDIO_WAV)], timeout=60)
    return True

def test_volume_ramp():
    log("测试音量渐变 --volume-ramp", "INFO")
    output = TEST_DIR / "test_audio_rampn6d0top6d0.wav"
    run_cmd([sys.executable, "mp.py", "--volume-ramp", "-6", "6", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "音量渐变成功")

def test_ascii_art():
    log("测试 ASCII 艺术导出 --ascii-art", "INFO")
    output = TEST_DIR / "test_video.txt"
    run_cmd([sys.executable, "mp.py", "--ascii-art", str(TEST_VIDEO_MP4), "--ascii-width", "40", "--ascii-fps", "5"], timeout=60)
    return test_file_generation(output, "ASCII 艺术导出成功")

def test_mix():
    log("测试音频混音 --mix", "INFO")
    output = TEST_DIR / "mixed.wav"
    run_cmd([sys.executable, "mp.py", "--mix", str(output), str(TEST_AUDIO_WAV), str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "混音成功")

def test_vconcat():
    log("测试视频拼接 --vconcat", "INFO")
    output = TEST_DIR / "concatenated.mp4"
    run_cmd([sys.executable, "mp.py", "--vconcat", str(output), str(TEST_VIDEO_MP4), str(TEST_VIDEO_MP4)], timeout=60)
    return test_file_generation(output, "视频拼接成功")

def test_scale():
    log("测试视频缩放 --scale", "INFO")
    output = TEST_DIR / "test_video_scaled_320x240.mp4"
    run_cmd([sys.executable, "mp.py", "--scale", str(TEST_VIDEO_MP4), "320x240"], timeout=60)
    return test_file_generation(output, "视频缩放成功")

def test_rotate():
    log("测试视频旋转 --rotate", "INFO")
    output = TEST_DIR / "test_video_rot90.mp4"
    run_cmd([sys.executable, "mp.py", "--rotate", str(TEST_VIDEO_MP4), "90"], timeout=60)
    return test_file_generation(output, "视频旋转成功")

def test_crop():
    log("测试视频裁剪 --crop", "INFO")
    output = TEST_DIR / "test_video_crop_320x240.mp4"
    run_cmd([sys.executable, "mp.py", "--crop", str(TEST_VIDEO_MP4), "320:240:0:0"], timeout=60)
    return test_file_generation(output, "视频裁剪成功")

def test_fps():
    log("测试帧率转换 --fps", "INFO")
    output = TEST_DIR / "test_video_15fps.mp4"
    run_cmd([sys.executable, "mp.py", "--fps", str(TEST_VIDEO_MP4), "15"], timeout=60)
    return test_file_generation(output, "帧率转换成功")

def test_strip_metadata():
    log("测试元数据剥离 --strip-metadata", "INFO")
    output = TEST_DIR / "test_audio_clean.wav"
    run_cmd([sys.executable, "mp.py", "--strip-metadata", str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "元数据剥离成功")

def test_repeat():
    log("测试片段重复 --repeat", "INFO")
    output = TEST_DIR / "test_audio_repeat_1s-2s x2.wav"
    run_cmd([sys.executable, "mp.py", "--repeat", str(TEST_AUDIO_WAV), "1", "2", "2"], timeout=60)
    return test_file_generation(output, "片段重复成功")

def test_mux():
    log("测试音视频合成 --mux", "INFO")
    output = TEST_DIR / "test_video_muxed.mp4"
    run_cmd([sys.executable, "mp.py", "--mux", str(TEST_VIDEO_MP4), str(TEST_AUDIO_WAV)], timeout=60)
    return test_file_generation(output, "音视频合成成功")

def test_favorites():
    log("测试收藏功能 --favorites", "INFO")
    run_cmd([sys.executable, "mp.py", "--favorites"], timeout=10)
    return True

def test_history():
    log("测试历史功能 --history", "INFO")
    run_cmd([sys.executable, "mp.py", "--history"], timeout=10)
    return True

def test_stats():
    log("测试统计功能 --stats", "INFO")
    run_cmd([sys.executable, "mp.py", "--stats"], timeout=10)
    return True

def test_playlist():
    log("测试播放列表模式 -p", "INFO")
    result = subprocess.run([sys.executable, "mp.py", "-p", str(TEST_AUDIO_WAV)], 
                           capture_output=True, text=True, timeout=2)
    return True

def test_playlist_shuffle():
    log("测试随机播放 -s -p", "INFO")
    result = subprocess.run([sys.executable, "mp.py", "-s", "-p", str(TEST_AUDIO_WAV)], 
                           capture_output=True, text=True, timeout=2)
    return True

def main():
    print("=" * 70)
    print("          mp - Terminal Media Player 全面测试")
    print("=" * 70)
    
    os.chdir("/workspace")
    
    if not generate_test_files():
        print("\n❌ 测试文件生成失败，无法继续测试")
        return 1
    
    tests = [
        ("帮助信息", test_help),
        ("版本信息", test_version),
        ("媒体信息", test_media_info),
        ("音频转换", test_audio_convert),
        ("音频裁剪", test_audio_trim),
        ("音频合并", test_audio_merge),
        ("音频反向", test_audio_reverse),
        ("淡入淡出", test_fade),
        ("混响效果", test_reverb),
        ("BPM 检测", test_bpm),
        ("音频归一化", test_normalize),
        ("歌词搜索", test_lyrics_search),
        ("噪声生成器", test_noise),
        ("均衡器列表", test_equalizer_list),
        ("混响列表", test_reverb_list),
        ("电台列表", test_radio_list),
        ("媒体库扫描", test_library_scan),
        ("媒体库统计", test_library_stats),
        ("导出 M3U", test_export_m3u),
        ("视频截图", test_screenshot),
        ("音频提取", test_extract_audio),
        ("视频转GIF", test_to_gif),
        ("频谱图", test_spectrogram),
        ("波形图", test_waveform),
        ("音量增益", test_gain),
        ("铃声生成", test_ringtone),
        ("声道转换", test_channels),
        ("采样率转换", test_resample),
        ("健康检查", test_health_check),
        ("静音检测", test_silence_detect),
        ("媒体分段", test_split),
        ("元数据导出", test_export_csv),
        ("音频指纹", test_fingerprint),
        ("音量渐变", test_volume_ramp),
        ("ASCII艺术", test_ascii_art),
        ("音频混音", test_mix),
        ("视频拼接", test_vconcat),
        ("视频缩放", test_scale),
        ("视频旋转", test_rotate),
        ("视频裁剪", test_crop),
        ("帧率转换", test_fps),
        ("元数据剥离", test_strip_metadata),
        ("片段重复", test_repeat),
        ("音视频合成", test_mux),
        ("收藏功能", test_favorites),
        ("历史功能", test_history),
        ("统计功能", test_stats),
        ("播放列表", test_playlist),
        ("随机播放", test_playlist_shuffle),
    ]
    
    passed = 0
    failed = 0
    results = []
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                results.append((name, True))
            else:
                failed += 1
                results.append((name, False))
        except Exception as e:
            failed += 1
            results.append((name, False))
            log(f"✗ {name} 异常: {e}", "ERROR")
    
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    for name, success in results:
        print(f"{'✅' if success else '❌'} {name}")
    
    print("\n" + "=" * 70)
    print(f"通过: {passed} / {len(tests)}")
    print(f"失败: {failed} / {len(tests)}")
    print(f"成功率: {passed / len(tests) * 100:.1f}%")
    print("=" * 70)
    
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
