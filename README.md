# media-on-terminal
# mp - Terminal Audio Player

一个轻量级的终端音频播放器，支持多种音频格式，可在终端中直接播放音乐。

## ✨ 特性

- 🎵 支持多种音频格式：MP3、WAV、OGG、M4A、FLAC、AAC、OPUS 等
- 🖥️ 终端内播放，无需图形界面
- 📊 实时显示播放进度条
- 🎮 快捷键控制播放
- 📦 自动安装依赖（ffmpeg 和 pygame）
- 🔧 跨平台支持（Linux / macOS）

## 🚀 快速安装

### 一键安装

```bash
curl -fsSL https://raw.githubusercontent.com/diaoyunxi/media-on-terminal/main/install.sh | bash
```

或下载后运行：

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

## 📖 使用方法

```bash
mp <音频文件>
```

### 示例

```bash
mp song.mp3                    # 播放音乐
mp "music/歌曲.flac"           # 支持带空格的路径
mp --help                      # 显示帮助
```

### 播放控制

| 按键 | 功能 |
|------|------|
| 空格键 | 暂停/继续 |
| ← 左箭头 | 后退 10 秒 |
| → 右箭头 | 前进 10 秒 |
| q 或 Ctrl+C | 退出播放 |

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

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
