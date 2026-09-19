#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mp - Terminal Media Player 启动器

从 v2.12.0 起拆分为 mp/ 包，此文件仅作为启动入口。
实际代码在 mp/ 包中，通过 from mp.main import main 调用。
"""
import sys
import os

# 将脚本所在目录加入 sys.path，确保能找到 mp/ 包
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from mp.main import main

if __name__ == "__main__":
    main()
