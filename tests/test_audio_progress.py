import io
import os
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from mp.players import AudioPlayer
from mp.utils import _display_width


def make_player(ansi=False):
    """构造不依赖 pygame、音频设备和用户配置目录的播放器。"""
    player = AudioPlayer.__new__(AudioPlayer)
    player.file_path = Path("song.mp3")
    player.current_position = 82_000
    player.total_duration = 230_000
    player.is_paused = False
    player.volume = 100
    player.playback_speed = 1.0
    player.loop_mode = "none"
    player.ab_loop = SimpleNamespace(get_status=lambda: "")
    player.favorites_manager = SimpleNamespace(is_favorite=lambda path: False)
    player.sleep_timer = SimpleNamespace(format_remaining=lambda: "")
    player.visualizer_enabled = False
    player.lyrics = SimpleNamespace(
        enabled=True,
        lyrics=[(0, "歌词")],
        online_source=None,
        get_lyrics_at_time=lambda seconds: (None, None),
    )
    player.equalizer = SimpleNamespace(enabled=False)
    player.pitch_control = SimpleNamespace(get_status=lambda: "")
    player.crossfade = SimpleNamespace(get_status=lambda: "")
    player._last_display_lines = 0
    player._last_term_width = 0
    player._last_progress_width = 0
    player._ansi_supported = ansi
    return player


def render(player, monkeypatch, stream, width):
    # 替换 players 模块持有的引用，避免修改 pytest 自己使用的 os/sys 全局模块。
    monkeypatch.setattr(
        "mp.players.os",
        SimpleNamespace(
            get_terminal_size=lambda fd=None: os.terminal_size((width, 24))
        ),
    )
    monkeypatch.setattr("mp.players.sys", SimpleNamespace(stdout=stream))
    player.display_progress()


def test_progress_bar_cells_use_one_terminal_column():
    assert _display_width("█" * 15 + "─" * 25) == 40


def test_consecutive_frames_rewind_one_line_and_keep_complete_time(monkeypatch):
    player = make_player(ansi=False)
    stream = io.StringIO()

    for position in (82_000, 83_000, 84_000):
        player.current_position = position
        render(player, monkeypatch, stream, width=80)

    output = stream.getvalue()
    assert "\n" not in output
    assert re.findall(r"\d{2}:\d{2}/\d{2}:\d{2}", output) == [
        "01:22/03:50",
        "01:23/03:50",
        "01:24/03:50",
    ]
    assert output.endswith("01:24/03:50")
    assert "📝 歌词" in output
    # 不能再通过补满终端宽度擦除旧内容，否则行尾会自动换行。
    assert " " * 80 not in output

    frames = [frame for frame in output.split("\r") if frame.startswith("▶")]
    assert len(frames) == 3
    assert all(_display_width(frame) <= 79 for frame in frames)


@pytest.mark.parametrize("width", [14, 17, 24, 40, 80, 120])
def test_narrow_terminal_prioritizes_complete_time(monkeypatch, width):
    player = make_player(ansi=False)
    stream = io.StringIO()
    render(player, monkeypatch, stream, width)

    output = stream.getvalue()
    assert output.startswith("\r")
    assert "\n" not in output
    assert output.endswith("| 01:22/03:50")
    assert _display_width(output[1:]) <= width - 1


def test_ansi_terminal_erases_previous_frame_without_newline(monkeypatch):
    player = make_player(ansi=True)
    stream = io.StringIO()

    render(player, monkeypatch, stream, width=80)
    player.current_position = 83_000
    render(player, monkeypatch, stream, width=80)

    output = stream.getvalue()
    assert "\r\033[2K\033[J" in output
    assert "\n" not in output
    assert output.endswith("01:23/03:50")


def test_clearing_legacy_console_line_does_not_pad_full_width(monkeypatch):
    player = make_player(ansi=False)
    stream = io.StringIO()

    render(player, monkeypatch, stream, width=80)
    player._clear_progress_display()

    output = stream.getvalue()
    assert "\n" not in output
    assert output.endswith("\r")
    assert " " * 80 not in output
    assert player._last_display_lines == 0
    assert player._last_progress_width == 0


def test_shrinking_terminal_does_not_wrap_legacy_clear(monkeypatch):
    player = make_player(ansi=False)
    stream = io.StringIO()
    render(player, monkeypatch, stream, width=80)

    stream.seek(0)
    stream.truncate(0)
    player.current_position = 83_000
    render(player, monkeypatch, stream, width=40)

    output = stream.getvalue()
    assert "\n" not in output
    assert " " * 40 not in output
    assert output.endswith("01:23/03:50")
    assert _display_width(output.rsplit("\r", 1)[-1]) <= 39
