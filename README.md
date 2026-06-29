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
- ✂️ **媒体裁剪** - 截取音频/视频指定时间片段（流复制或重编码）
- 🔗 **音频合并** - 将多个音频文件拼接为一个
- ⏪ **音频反向** - 反转音频播放方向
- 🌊 **淡入淡出** - 为音频添加淡入/淡出效果
- 🏛️ **混响效果** - 7 种预设（房间/音乐厅/大教堂/板式/弹簧/洞穴/体育场）
- 💬 **字幕提取** - 从视频提取 SRT/ASS 字幕轨道
- 🥁 **BPM 检测** - 基于自相关算法检测音频节拍速度
- 🖼️ **接触印片** - 生成视频缩略图组合（行列可调）
- 🔍 **重复文件查找** - 基于 SHA-256 哈希查找重复媒体，可释放空间统计
- 💾 **配置备份** - 一键备份/恢复 mp 配置（zip 格式，防 zip slip）
- 🏷️ **批量重命名** - 基于元数据按模式重命名（支持 `{title}` `{artist}` `{album}` `{year}` `{track}` 占位符）
- 📊 **频谱图生成** - 生成音频频谱图 PNG 图片
- 🌊 **波形图生成** - 生成音频波形图 PNG 图片（分声道展示）
- 🖼️ **封面提取** - 从音频/视频文件提取嵌入的封面或海报图片
- 🔊 **音量增益** - 以分贝(dB)为单位调整音量，支持批量
- 📱 **铃声生成** - 截取片段并添加淡入淡出，生成铃声（默认30秒）
- 🔈 **声道转换** - 单声道/立体声互转，支持批量
- 🎚️ **采样率转换** - 转换音频采样率（Hz），支持批量
- 🎞️ **音视频合成** - 将音频合并到视频（替换原音轨）

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

### 媒体裁剪

```bash
mp --trim song.mp3 30 60              # 截取 30-60 秒片段
mp --trim song.mp3 30                # 从 30 秒截到结尾
mp --trim video.mp4 0 10             # 截取视频前 10 秒
```

### 音频合并

```bash
mp --merge out.mp3 a.mp3 b.mp3 c.mp3     # 合并 3 个文件为 MP3
mp --merge out.wav a.wav b.wav --fmt wav # 指定输出格式
```

### 反向音频

```bash
mp --reverse song.mp3                 # 反向音频
mp --reverse a.mp3 b.mp3 c.mp3         # 批量反向
```

### 淡入淡出

```bash
mp --fade song.mp3 2                   # 仅 2 秒淡入
mp --fade song.mp3 2 3                 # 2 秒淡入 + 3 秒淡出
```

### 混响效果

```bash
mp --reverb hall song.mp3              # 应用音乐厅混响
mp --reverb cathedral *.mp3            # 批量应用大教堂混响
mp --reverb-list                       # 显示所有预设
```

可用预设：`room`（房间）, `hall`（音乐厅）, `cathedral`（大教堂）, `plate`（板式）, `spring`（弹簧）, `cave`（洞穴）, `stadium`（体育场）

### 字幕提取

```bash
mp --extract-subtitles movie.mkv                 # 提取字幕为 SRT
mp --extract-subtitles movie.mkv --fmt ass       # 提取为 ASS
```

### BPM 检测

```bash
mp --bpm song.mp3                      # 检测 BPM
mp --bpm *.mp3                         # 批量检测
```

输出包含 BPM 数值和速度描述（慢板/中板/快板等）。

### 视频缩略图组合

```bash
mp --contact-sheet movie.mp4           # 生成 4x4 缩略图组合
mp --contact-sheet movie.mp4 --rows 3 --cols 5   # 3 行 5 列
```

### 重复文件查找

```bash
mp --find-duplicates ~/Music           # 查找重复（仅顶层）
mp --find-duplicates ~/Music --recursive  # 递归子目录
```

输出包含重复组数、文件路径和可释放空间统计。

### 配置备份与恢复

```bash
mp --backup-config                     # 备份到默认位置 (~/mp_config_backup_*.zip)
mp --backup-config ~/my_backup.zip     # 备份到指定路径
mp --restore-config ~/my_backup.zip    # 从 zip 恢复配置
```

### 批量重命名

```bash
mp --rename "{artist} - {title}" ~/Music        # 按元数据重命名
mp --rename "{track}. {title}" ~/Music          # 带音轨号
mp --rename "{artist}/{album}/{title}" ~/Music --recursive  # 递归
mp --rename "{artist} - {title}" . --dry-run    # 演练模式（不实际操作）
```

可用占位符：`{title}` `{artist}` `{album}` `{year}` `{track}`，非法字符自动替换为下划线。

### 频谱图生成

```bash
mp --spectrogram song.mp3                       # 生成频谱图 PNG
mp --spectrogram song.mp3 --at 30 --gif-duration 10  # 指定起始时间和时长
```

### 波形图生成

```bash
mp --waveform song.mp3                          # 生成波形图 PNG
mp --waveform song.mp3 --at 30 --gif-duration 10  # 指定起始时间和时长
```

### 封面提取

```bash
mp --cover song.mp3                             # 提取嵌入的封面图片
mp --cover movie.mkv                            # 提取视频海报
```

### 音量增益

```bash
mp --gain 3 song.mp3                            # 音量增益 +3 dB
mp --gain -2 song.mp3                           # 音量降低 -2 dB
mp --gain 5 *.mp3                               # 批量增益 +5 dB
```

增益范围 -60 ~ +30 dB，输出 `*_gainp{N}dB` / `*_gainn{N}dB` 文件，不覆盖原文件。

### 铃声生成

```bash
mp --ringtone song.mp3                          # 从头截取30秒铃声
mp --ringtone song.mp3 45                       # 从45秒起截取30秒
mp --ringtone song.mp3 45 20                    # 从45秒起截取20秒
mp --ringtone song.mp3 0 30 --fade-sec 1.5      # 1.5秒淡入淡出
```

默认 30 秒、2 秒淡入淡出，输出 `*_ringtone` 文件。

### 声道转换

```bash
mp --channels 1 song.mp3                        # 转为单声道
mp --channels 2 song.mp3                        # 转为立体声
mp --channels 1 *.mp3                           # 批量转单声道
```

仅支持 `1`（单声道）/ `2`（立体声），输出 `*_mono` / `*_stereo` 文件。

### 采样率转换

```bash
mp --resample 44100 song.mp3                    # 转换为 44100 Hz
mp --resample 48000 *.mp3                       # 批量转换为 48000 Hz
```

常用采样率：8000 / 16000 / 22050 / 32000 / 44100 / 48000 / 96000 / 192000，输出 `*_{RATE}Hz` 文件。

### 音视频合成

```bash
mp --mux video.mp4 bgm.mp3                      # 用 bgm 替换视频原音轨
```

视频流复制（无损），音频重编码为 AAC 192k，输出 `*_muxed` 文件。

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
    --trim FILE START [END] 裁剪媒体文件指定时间段
    --merge OUTPUT FILE... 合并多个音频文件
    --reverse FILE...   反向音频（支持批量）
    --fade FILE IN [OUT] 添加淡入淡出效果（秒）
    --reverb [PRESET]   应用混响预设（不带参数则列出）
    --reverb-list       显示混响预设列表
    --extract-subtitles 视频  从视频提取字幕（srt/ass）
    --bpm FILE...       检测音频节拍速度 BPM
    --contact-sheet 视频  生成视频缩略图组合
    --find-duplicates DIR  查找重复媒体文件
    --backup-config [OUTPUT] 备份配置到zip
    --restore-config INPUT  从zip恢复配置
    --rename PATTERN DIR  按元数据批量重命名文件
    --spectrogram FILE  生成音频频谱图PNG
    --waveform FILE     生成音频波形图PNG
    --cover FILE        提取嵌入的封面/海报图片
    --gain DB FILE...   音量增益(dB)，支持批量
    --ringtone FILE [START [DURATION]]  生成铃声（默认30秒，带淡入淡出）
    --channels N FILE... 转换声道数 1(单声道)/2(立体声)
    --resample RATE FILE... 转换采样率(Hz)，支持批量
    --mux VIDEO AUDIO   将音频合并到视频（替换原音轨）
    --fade-sec N        铃声淡入淡出时长（秒，默认2.0）
    --fmt FMT           指定输出格式（提取/归一化/合并/混响）
    --at N              截图时间点（秒）
    --count N           批量截图数量
    --gif-start N       GIF起始时间（秒）
    --gif-duration N    GIF时长（秒，亦用于频谱图时长）
    --gif-width N       GIF宽度（像素）
    --gif-fps N         GIF帧率
    --rows N            接触印片行数（默认4）
    --cols N            接触印片列数（默认4）
    --recursive         递归处理子目录（查找重复/重命名）
    --dry-run           演练模式（仅重命名）
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

### v2.8.0
- 🌊 新增波形图生成 - 通过 ffmpeg `showwavespic` 生成音频波形图 PNG（分声道展示）
- 🖼️ 新增封面提取 - 自动识别 attached_pic/单帧视频流，从音频/视频提取封面或海报
- 🔊 新增音量增益 - 以分贝(dB)为单位调整音量（-60~+30 dB），支持批量
- 📱 新增铃声生成 - 截取指定片段并添加淡入淡出，默认 30 秒，可自定义起始/时长/淡入淡出
- 🔈 新增声道转换 - 单声道/立体声互转，支持批量
- 🎚️ 新增采样率转换 - 转换音频采样率（Hz），支持批量
- 🎞️ 新增音视频合成 - 将音频合并到视频（视频流复制无损，音频重编码 AAC 192k）
- ✨ 新增命令行选项 `--waveform`, `--cover`, `--gain`, `--ringtone`, `--channels`, `--resample`, `--mux`, `--fade-sec`
- 🐛 修复多个已知问题

### v2.7.0
- ✂️ 新增媒体裁剪 - 截取音频/视频指定时间片段（流复制优先，失败回退重编码）
- 🔗 新增音频合并 - 将多个音频文件拼接为一个（concat filter，支持任意格式输入）
- ⏪ 新增音频反向 - 反转音频播放方向（支持批量）
- 🌊 新增淡入淡出 - 为音频添加淡入/淡出效果
- 🏛️ 新增混响效果 - 7 种预设（房间/音乐厅/大教堂/板式/弹簧/洞穴/体育场）
- 💬 新增字幕提取 - 从视频提取 SRT/ASS 字幕轨道，自动检测语言后缀
- 🥁 新增 BPM 检测 - 基于 PCM 自相关算法检测音频节拍速度（60-200 BPM 范围）
- 🖼️ 新增接触印片 - 生成视频缩略图组合（行列可调，10%-90% 区间均匀采样）
- 🔍 新增重复文件查找 - 基于 SHA-256 哈希，先按大小过滤，统计可释放空间
- 💾 新增配置备份/恢复 - 一键 zip 备份 `~/.config/mp`，恢复时防 zip slip 攻击
- 🏷️ 新增批量重命名 - 基于元数据按模式重命名（支持 `{title}` `{artist}` `{album}` `{year}` `{track}` 占位符），含演练模式
- 📊 新增频谱图生成 - 通过 ffmpeg `showspectrumpic` 生成音频频谱图 PNG
- ✨ 新增命令行选项 `--trim`, `--merge`, `--reverse`, `--fade`, `--reverb`, `--reverb-list`, `--extract-subtitles`, `--bpm`, `--contact-sheet`, `--find-duplicates`, `--backup-config`, `--restore-config`, `--rename`, `--spectrogram`
- ✨ 新增附加参数 `--rows`, `--cols`, `--recursive`, `--dry-run`
- 🐛 修复多个已知问题

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
