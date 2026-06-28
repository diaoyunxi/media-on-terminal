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
- 📊 **音频可视化器** - 终端频谱可视化显示
- 🔖 **书签/断点续播** - 保存和恢复播放位置
- 📝 **歌词显示** - 支持LRC格式歌词同步显示
- ❤️ **收藏功能** - 管理喜欢的歌曲，快速播放收藏列表
- 📜 **播放历史** - 记录最近播放的歌曲
- ⏰ **定时停止** - 睡眠定时器，设定时间后自动停止
- 🔁 **AB循环** - 设置区间循环，反复播放指定片段
- 📻 **网络电台** - 支持在线流媒体电台播放和管理
- 🎵 **队列管理** - 动态管理播放队列，支持添加、删除、重新排序
- 🔄 **音频转换** - 在不同格式间转换音频文件（支持单文件和批量转换）
- 📊 **播放统计** - 详细的播放统计和分析（总时长、格式分布、最常播放、每日统计）
- 🎛️ **均衡器** - 10频段均衡器，支持多种预设（摇滚、流行、爵士、古典等）
- 📂 **文件浏览器** - 交互式文件浏览器，可视化选择媒体文件
- 🎼 **音调控制** - 独立于播放速度的音调调整（±12半音）
- 🔇 **噪声生成器** - 白噪声/粉红噪声/棕噪声/雨声/海浪，助眠专注
- 🏷️ **元数据编辑** - 编辑媒体文件的标签信息（标题、艺术家、专辑等）
- 🔀 **交叉淡入淡出** - 播放列表曲目间平滑过渡
- 🎙️ **音频录制** - 从麦克风录制音频，支持 WAV/MP3/OGG/M4A/FLAC
- 🎬 **视频转GIF** - 将视频片段转换为高质量GIF动画（调色板两步法）
- 🎵 **音频提取** - 从视频文件提取音轨（支持批量）
- 📸 **视频截图** - 捕获指定时间点的画面帧，支持批量均匀采样
- 🔉 **音频归一化** - 统一音量水平（EBU R128 / 动态 / 峰值）
- 📋 **播放列表导入导出** - M3U/M3U8 格式互转
- 🗄️ **媒体库** - 扫描本地目录建立索引，按名称/艺术家/专辑搜索

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

### 收藏和历史

```bash
mp --favorites                      # 播放收藏列表
mp --history                        # 查看播放历史
mp --clear-history                  # 清空播放历史
```

### 网络电台

```bash
mp --radio-list                     # 显示电台列表
mp --radio "经典音乐"               # 播放指定电台
mp --radio-add "我的电台" URL       # 添加新电台
mp --radio-del "电台名称"           # 删除电台
```

### 均衡器

```bash
mp --eq rock song.mp3               # 使用摇滚预设播放
mp --eq-list                        # 显示所有均衡器预设
```

可用预设：`flat`, `rock`, `pop`, `jazz`, `classical`, `bass`, `treble`, `vocal`, `electronic`

### 音频转换

```bash
mp --convert mp3 song.flac          # 将FLAC转换为MP3
mp --convert ogg *.wav              # 批量将WAV转换为OGG
mp --convert m4a song.mp3 -o output/ # 转换到指定目录
```

### 统计信息

```bash
mp --stats                          # 查看播放统计
mp --clear-stats                    # 清空统计数据
```

### 文件浏览器

```bash
mp --browse                         # 打开交互式文件浏览器
```

### 噪声生成器

```bash
mp --noise                          # 交互式噪声生成器
mp --noise white                    # 播放白噪声
mp --noise pink                     # 播放粉红噪声
mp --noise brown                    # 播放棕噪声
mp --noise rain                     # 播放雨声
mp --noise ocean                    # 播放海浪声
```

### 元数据编辑

```bash
mp --edit-tags song.mp3             # 编辑歌曲元数据
```

### 音频录制

```bash
mp --record                         # 交互式录制（提示文件名和时长）
mp --record voice.mp3               # 录制并保存为MP3（Ctrl+C 停止）
mp --record clip.wav                # 录制为WAV
```

支持格式：`wav`, `mp3`, `ogg`, `m4a`, `flac`。Linux 使用 pulse，macOS 使用 avfoundation，Windows 使用 dshow。

### 音频提取（视频→音频）

```bash
mp --extract-audio video.mp4              # 从视频提取MP3音轨
mp --extract-audio video.mkv --fmt wav    # 提取为WAV
mp --extract-audio v1.mp4 v2.mp4 --fmt flac  # 批量提取
```

### 视频转GIF

```bash
mp --to-gif video.mp4                      # 默认截取前5秒
mp --to-gif video.mp4 --gif-start 30 --gif-duration 3   # 从30秒起截取3秒
mp --to-gif video.mp4 --gif-width 640 --gif-fps 20      # 自定义宽度与帧率
```

### 视频截图

```bash
mp --screenshot video.mp4                  # 截取开头画面
mp --screenshot video.mp4 --at 60          # 在60秒处截图
mp --screenshot video.mp4 --count 6        # 均匀截取6张到子目录
mp --screenshot video.mp4 --at 90 --count 4  # 批量截图
```

### 音频归一化

```bash
mp --normalize song.mp3                    # EBU R128 响度归一化（推荐）
mp --normalize *.mp3 --fmt dynaudnorm      # 批量动态归一化
mp --normalize song.mp3 --fmt loudnorm_db  # 峰值归一化
```

可用方法：`loudnorm`（-16 LUFS）、`dynaudnorm`（平滑）、`loudnorm_db`（峰值）。默认输出 `*_norm` 文件，不覆盖原文件。

### 播放列表导入导出（M3U）

```bash
mp --export-m3u my.m3u *.mp3               # 导出当前MP3为M3U
mp --export-m3u playlist.m3u ~/Music/*.flac
mp --import-m3u playlist.m3u              # 导入M3U并立即播放
mp -s --import-m3u playlist.m3u           # 导入后随机播放
```

### 媒体库

```bash
mp --library-scan ~/Music                 # 扫描目录建立索引
mp --library-scan ~/Videos                # 再次扫描会增量合并到同一索引
mp --library-search "周杰伦"              # 搜索（匹配名称/艺术家/专辑）
mp --library-stats                        # 查看媒体库统计
mp --library-clear                        # 清空媒体库
```

媒体库索引保存在 `~/.config/mp/library.json`，支持增量扫描（已索引文件自动去重）。

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
| v | 切换音频可视化器 |
| b | 保存书签 |
| r | 恢复书签 |
| o | 切换歌词显示 |
| f | 收藏/取消收藏 |
| a | 设置AB循环 |
| t | 定时停止 |
| h | 显示播放历史 |
| e | 切换均衡器开关 |
| E | 显示均衡器预设列表 |
| Q | 显示播放队列 |
| S | 显示播放统计 |
| c | 转换当前音频格式 |
| m | 编辑当前文件元数据 |
| p / P | 降低/升高音调（半音） |
| X | 重置音调 |
| x | 切换交叉淡入淡出 |
| F | 打开文件浏览器 |
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
    --favorites         播放收藏列表
    --history           显示播放历史
    --clear-history     清空播放历史
    --radio NAME        播放网络电台
    --radio-list        显示电台列表
    --radio-add N URL   添加电台
    --radio-del NAME    删除电台
    --record [FILE]     录制麦克风音频
    --extract-audio VIDEO  从视频提取音轨
    --to-gif VIDEO      视频转GIF动画
    --screenshot VIDEO  视频截图
    --normalize FILE... 音频音量归一化
    --export-m3u OUT FILE...  导出M3U播放列表
    --import-m3u FILE   导入M3U播放列表并播放
    --library-scan DIR  扫描目录建立媒体库索引
    --library-search Q  搜索媒体库
    --library-stats     显示媒体库统计
    --library-clear     清空媒体库
    --fmt FMT           指定输出格式（提取/归一化）
    --at N              截图时间点（秒）
    --count N           批量截图数量
    --gif-start N       GIF起始时间（秒）
    --gif-duration N    GIF时长（秒）
    --gif-width N       GIF宽度（像素）
    --gif-fps N         GIF帧率
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
- 媒体库索引：`~/.config/mp/library.json`
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

### v2.6.0
- ✨ 新增自动更新检查 - 启动时自动从 GitHub 获取最新版本号，发现新版本时提示用户一键更新

### v2.5.0
- 🎙️ 新增音频录制 - 从麦克风录制音频（WAV/MP3/OGG/M4A/FLAC），跨平台音频输入
- 🎬 新增视频转GIF - 调色板两步法生成高质量GIF，可自定义起始时间/时长/宽度/帧率
- 🎵 新增音频提取 - 从视频文件提取音轨（支持批量）
- 📸 新增视频截图 - 捕获指定时间点画面帧，支持批量均匀采样
- 🔉 新增音频归一化 - EBU R128 响度归一化 / 动态归一化 / 峰值归一化（支持批量）
- 📋 新增播放列表导入导出 - M3U/M3U8 格式互转，自动读取元数据
- 🗄️ 新增媒体库 - 扫描本地目录建立可搜索索引，按名称/艺术家/专辑搜索
- ✨ 新增命令行选项 --record, --extract-audio, --to-gif, --screenshot, --normalize, --export-m3u, --import-m3u, --library-scan, --library-search, --library-stats, --library-clear
- ✨ 新增附加参数 --fmt, --at, --count, --gif-start, --gif-duration, --gif-width, --gif-fps
- 🐛 修复多个已知问题

### v2.4.0
- 📂 新增文件浏览器 - 交互式文件浏览器，可视化选择媒体文件
- 🎼 新增音调控制 - 独立于播放速度的音调调整（±12半音）
- 🔇 新增噪声生成器 - 白噪声/粉红噪声/棕噪声/雨声/海浪，助眠专注
- 🏷️ 新增元数据编辑 - 编辑媒体文件的标签信息（标题、艺术家、专辑等）
- 🔀 新增交叉淡入淡出 - 播放列表曲目间平滑过渡
- ✨ 新增命令行选项 --browse, --noise, --edit-tags
- ✨ 新增快捷键 m (元数据), p/P (音调), X (重置音调), x (交叉淡入), F (文件浏览器)
- 🐛 修复多个已知问题

### v2.3.0
- 🎵 新增队列管理 - 动态管理播放队列，支持添加、删除、重新排序
- 🔄 新增音频转换 - 在不同格式间转换音频文件（支持单文件和批量转换）
- 📊 新增播放统计 - 详细的播放统计和分析（总时长、格式分布、最常播放、每日统计）
- 🎛️ 新增均衡器 - 10频段均衡器，支持多种预设（摇滚、流行、爵士、古典等）
- ✨ 新增命令行选项 --stats, --clear-stats, --convert, --eq, --eq-list
- ✨ 新增快捷键 e (均衡器), E (均衡器预设), Q (队列), S (统计), c (转换)
- 🐛 修复多个已知问题

### v2.2.0
- ✨ 新增收藏功能 - 管理喜欢的歌曲，快速播放收藏列表
- ✨ 新增播放历史 - 记录最近播放的歌曲（最多100条）
- ✨ 新增定时停止 - 睡眠定时器，设定时间后自动停止
- ✨ 新增AB循环 - 设置区间循环，反复播放指定片段
- ✨ 新增网络电台 - 支持在线流媒体电台播放和管理
- ✨ 新增命令行选项 --favorites, --history, --clear-history
- ✨ 新增命令行选项 --radio, --radio-list, --radio-add, --radio-del
- ✨ 新增快捷键 f (收藏), a (AB循环), t (定时停止), h (历史)
- 🐛 修复多个已知问题

### v2.1.0
- ✨ 新增音频可视化器 - 终端频谱可视化显示
- ✨ 新增书签功能 - 保存和恢复播放位置
- ✨ 新增歌词显示 - 支持LRC格式歌词同步显示
- ✨ 退出时自动保存书签位置
- ✨ 启动时检测书签并提示恢复
- 🐛 修复多个已知问题

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
