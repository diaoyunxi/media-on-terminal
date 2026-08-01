#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全局常量定义

路径常量集中管理，避免循环导入。
所有需要这些常量的模块应从 mp.constants 导入。
"""

import os
from pathlib import Path

# 配置文件路径
CONFIG_DIR = Path.home() / '.config' / 'mp'
CONFIG_FILE = CONFIG_DIR / 'config.json'
PLAYLIST_DIR = CONFIG_DIR / 'playlists'
FAVORITES_FILE = CONFIG_DIR / 'favorites.json'
HISTORY_FILE = CONFIG_DIR / 'history.json'
RADIO_FILE = CONFIG_DIR / 'radio.json'

# GitHub 版本检查缓存（避免速率限制，bug #14）
UPDATE_CACHE_FILE = CONFIG_DIR / 'update_cache.json'

# GitHub 仓库信息
GITHUB_REPO = "diaoyunxi/media-on-terminal"

# GitHub 镜像站（通过环境变量配置）
_GITHUB_MIRROR = os.environ.get('GITHUB_MIRROR', '').strip().rstrip('/')
