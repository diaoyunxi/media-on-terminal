# Contributing to media-on-terminal (mp)

感谢你对 media-on-terminal 项目的关注！

## 如何贡献

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 代码规范

- Python 代码遵循 PEP 8
- 终端 UI 使用 curses 标准库
- 提交信息使用中文或英文均可

## 项目架构

\`\`\`
media-on-terminal/
├── mp/main.py        # 主入口
├── mp/player.py      # 播放器核心
├── mp/download.py    # 下载模块
├── mp/lyrics.py      # 歌词获取
└── mp/metadata.py    # 元数据解析
\`\`\`
