# media-on-terminal
# mp - Terminal Media Player

一个轻量级的终端媒体播放器，支持多种音频和视频格式，可在终端中直接播放音乐和视频。

## ✨ 特性

- 🎵 支持多种音频格式：MP3、WAV、OGG、M4A、FLAC、AAC、OPUS 等
- 🎬 支持多种视频格式：MP4、MKV、AVI、MOV、WEBM 等
- 🖥️ 终端内播放，无需图形界面
- 📊 音频播放实时显示进度条
- 🎥 视频播放使用 ASCII 字符渲染画面
- 🎮 快捷键控制播放
- 📦 自动安装依赖（ffmpeg 和 pygame）
- 🔧 跨平台支持（Linux / macOS）

### 🆕 新增功能

- 📝 **播放列表** - 支持播放多个文件和目录
- 🔊 **音量控制** - 实时调整音量（↑/↓ 键）
- 🔄 **循环播放** - 单曲循环、列表循环
- ⚡ **播放速度** - 0.5x ~ 2.0x 变速播放
- 📋 **媒体信息** - 显示详细的文件信息
- 🔀 **随机播放** - 打乱播放顺序
- 💾 **配置保存** - 自动记住音量、速度等设置

## 🚀 快速安装

### 一键安装

下载后运行：

```bash
chmod +x install.sh
./install.sh
```

### 手动安装

1. 确保已安装 Python 3.7+
2. 安装依赖：
```bash
pip install pygame
```
3. 安装 ffmpeg：
   - **macOS**: `brew install ffmpeg`
   - **Ubuntu/Debian**: `sudo apt install ffmpeg`
   - **Arch**: `sudo pacman -S ffmpeg`
4. 将mp.py加入系统目录

## 📖 使用方法

### 基本用法

```bash
mp <媒体文件>
```

### 示例

```bash
mp song.mp3                         # 播放音乐
mp video.mp4                        # 播放视频（字符渲染）
mp "music/歌曲.flac"                # 支持带空格的路径
mp --help                           # 显示帮助
```

### 播放列表

```bash
mp -p *.mp3                         # 播放所有MP3文件
mp -p --shuffle *.mp3               # 随机播放所有MP3
mp ~/Music                          # 播放目录中所有媒体
mp -p song1.mp3 song2.mp3 song3.mp3 # 播放多个文件
```

### 媒体信息

```bash
mp --info song.mp3                  # 显示媒体详细信息
mp -i video.mp4                     # 显示视频信息
```

### 播放选项

```bash
mp -v 50 song.mp3                   # 设置50%音量
mp --speed 1.5 song.mp3             # 1.5倍速播放
mp -l single song.mp3               # 单曲循环
mp -l all -p *.mp3                  # 列表循环播放
mp -s -p *.mp3                      # 随机播放
```

## 🎮 播放控制

### 音频播放控制

| 按键 | 功能 |
|------|------|
| 空格键 | 暂停/继续 |
| ← 左箭头 | 后退 10 秒 |
| → 右箭头 | 前进 10 秒 |
| ↑ 上箭头 | 增加音量 (+5%) |
| ↓ 下箭头 | 降低音量 (-5%) |
| < 或 , | 降低播放速度 |
| > 或 . | 增加播放速度 |
| l | 切换循环模式 |
| i | 显示媒体信息 |
| q 或 Ctrl+C | 退出播放 |

### 视频播放控制

| 按键 | 功能 |
|------|------|
| 空格键 | 暂停/继续 |
| ↑ 上箭头 | 增加音量 |
| ↓ 下箭头 | 降低音量 |
| i | 显示媒体信息 |
| q 或 Ctrl+C | 退出播放 |

## 📋 命令行选项

```
用法:
    mp [选项] <媒体文件/目录/播放列表>

选项:
    -h, --help          显示帮助信息
    -i, --info          显示媒体文件详细信息
    -p, --playlist      播放列表模式
    -s, --shuffle       随机播放
    -l, --loop          循环模式 (single/all)
    -v, --volume N      设置音量 (0-100)
    --speed N           设置播放速度 (0.5-2.0)
```

## 🗑️ 卸载

```bash
./install.sh --uninstall
```

或

```bash
mp-uninstall
```

## 📁 安装位置

- 主程序：`~/.local/share/mp/mp.py`
- 可执行文件：`~/.local/bin/mp`
- 配置文件：`~/.config/mp/config.json`
- 播放列表：`~/.config/mp/playlists/`
- 自动补全：`~/.bash_completion.d/mp` 或对应 shell 目录

## 🔧 系统要求

- Python 3.7 或更高版本
- ffmpeg（会自动安装）
- pygame（会自动安装）

### Linux 额外依赖

- libsdl2-2.0-0
- libsdl2-mixer-2.0-0

## ❓ 常见问题

### 1. 提示 "mp: command not found"

将 `~/.local/bin` 添加到 PATH：
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### 2. 没有声音或播放失败

确保 ffmpeg 正确安装：
```bash
ffmpeg -version
```

### 3. pygame 安装失败

尝试手动安装：
```bash
pip install --user pygame
```

或使用系统包管理器：
- **Ubuntu**: `sudo apt install python3-pygame`
- **Arch**: `sudo pacman -S python-pygame`

### 4. 视频播放卡顿

视频播放使用 ASCII 字符渲染，性能取决于终端和系统。建议：
- 使用较小的视频分辨率
- 使用支持 256 色的终端
- 减小终端窗口大小

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📝 更新日志

### v2.0.0
- ✨ 新增播放列表功能
- ✨ 新增音量控制（↑/↓ 键）
- ✨ 新增循环播放模式（单曲/列表）
- ✨ 新增播放速度控制（0.5x ~ 2.0x）
- ✨ 新增媒体信息显示（--info）
- ✨ 新增随机播放功能（--shuffle）
- ✨ 新增配置保存功能
- 🐛 修复多个已知问题
- 📝 更新文档
