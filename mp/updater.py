#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub 自动更新"""

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
from mp.constants import CONFIG_DIR, UPDATE_CACHE_FILE, GITHUB_REPO, _GITHUB_MIRROR

def _github_url(url: str) -> str:
    """通过 GITHUB_MIRROR 环境变量转发 GitHub 相关 URL

    若环境变量未设置，返回原始 URL；
    若已设置，将原始完整 URL 拼接在镜像站后，如：
      https://gh.llkk.cc/https://api.github.com/repos/.../releases/latest
    """
    if not _GITHUB_MIRROR or url.startswith(_GITHUB_MIRROR):
        return url
    return f"{_GITHUB_MIRROR}/{url}"



def _fetch_latest_version_github():
    """从 GitHub 获取最新版本号及 Release 信息（优先 Releases，回退 Tags）

    返回: (tag, release_url, assets) 三元组
        tag: 版本号字符串（如 "v2.11.6"），失败为 None
        release_url: Release 页面 URL，失败为 None
        assets: Release Assets 列表 [{name, url, size}, ...]，失败为 []

    为避免 GitHub API 速率限制（未认证 60 次/小时/IP），增加本地缓存（bug #14）：
    - 缓存有效期 24 小时，缓存文件 ~/.config/mp/update_cache.json
    - 缓存有效期内直接返回缓存结果，不再请求 API
    - API 请求失败时（速率限制/网络错误）使用过期缓存兜底，避免完全无返回
    """
    import urllib.request
    import urllib.error

    # --- 缓存读取 ---
    cache = None
    try:
        if UPDATE_CACHE_FILE.exists():
            with open(UPDATE_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
    except Exception:
        cache = None

    CACHE_TTL = 24 * 3600  # 缓存有效期 24 小时
    now = time.time()
    if cache and isinstance(cache, dict):
        ts = cache.get("ts", 0)
        if now - ts < CACHE_TTL:
            # 缓存有效期内，直接返回缓存结果，不请求 API
            # 对缓存中的 URL 也应用镜像（兼容旧缓存未镜像的情况）
            cached_assets = cache.get("assets", []) or []
            for a in cached_assets:
                a["url"] = _github_url(a.get("url", ""))
            return (
                cache.get("tag"),
                _github_url(cache.get("release_url", "")),
                cached_assets,
            )

    # --- 尝试 Releases API（含 assets 下载链接）---
    result = None
    try:
        url = _github_url(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest")
        req = urllib.request.Request(url, headers={"User-Agent": "mp-player"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            tag = data.get("tag_name")
            html_url = _github_url(data.get("html_url", ""))
            assets = []
            for a in data.get("assets", []) or []:
                assets.append({
                    "name": a.get("name", ""),
                    "url": _github_url(a.get("browser_download_url", "")),
                    "size": a.get("size", 0),
                })
            if tag:
                result = (tag, html_url, assets)
    except Exception:
        pass

    # --- 回退到 Tags API（无 assets 信息）---
    if result is None:
        try:
            url = _github_url(f"https://api.github.com/repos/{GITHUB_REPO}/tags")
            req = urllib.request.Request(url, headers={"User-Agent": "mp-player"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data:
                    tag = data[0].get("name")
                    result = (tag, _github_url(f"https://github.com/{GITHUB_REPO}/releases/tag/{tag}"), [])
        except Exception:
            pass

    # --- 缓存写入 / 过期缓存兜底 ---
    if result is not None:
        # 请求成功，更新缓存
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            payload = {
                "tag": result[0],
                "release_url": result[1],
                "assets": result[2],
                "ts": now,
            }
            with open(UPDATE_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False)
        except Exception:
            pass
        return result

    # 请求失败：用过期缓存兜底（即便过期也比无返回好）
    if cache and isinstance(cache, dict) and cache.get("tag"):
        cached_assets = cache.get("assets", []) or []
        for a in cached_assets:
            a["url"] = _github_url(a.get("url", ""))
        return (
            cache.get("tag"),
            _github_url(cache.get("release_url", "")),
            cached_assets,
        )

    return None, None, []




def _compare_versions(v1, v2):
    """比较两个版本号

    支持前缀 v/V（如 v1.2.3 / V1.2.3），仅去除一个前缀字符。
    支持预发布标识：每段分离为数字部分和后缀部分，
    数字不同按数字比较；数字相同时无后缀（正式版）> 有后缀（预发布版）。
    例如 1.2.3-beta < 1.2.3 < 1.2.4。

    复用说明：此函数为通用版本比较工具，符合 SemVer 规范，
    可在自动更新检查、依赖版本对比等场景复用。
    建议后续提取到独立工具模块（如 version_utils.py）供其他项目共享。
    """
    def _strip_v(s):
        # 仅去除一个 v/V 前缀，避免 lstrip('v') 误删多个 v 或忽略大写 V
        if s and s[0] in ('v', 'V'):
            return s[1:]
        return s

    def _parse_part(p):
        """解析版本段，返回 (数字, 后缀字符串)

        如 '3' -> (3, ''), '3-beta' -> (3, '-beta'), 'rc1' -> (0, 'rc1')
        """
        m = re.match(r'^(\d+)(.*)$', p)
        if m:
            return int(m.group(1)), m.group(2)
        return 0, p

    parts1 = _strip_v(v1).split('.')
    parts2 = _strip_v(v2).split('.')
    for i in range(max(len(parts1), len(parts2))):
        p1 = parts1[i] if i < len(parts1) else '0'
        p2 = parts2[i] if i < len(parts2) else '0'
        n1, s1 = _parse_part(p1)
        n2, s2 = _parse_part(p2)
        if n1 > n2:
            return 1
        if n1 < n2:
            return -1
        # 数字相同，比较有后缀的
        # 无后缀（正式版）> 有后缀（预发布版），如 1.2.3 > 1.2.3-beta
        if not s1 and s2:
            return 1
        if s1 and not s2:
            return -1
        if s1 and s2:
            if s1 > s2:
                return 1
            if s1 < s2:
                return -1
    return 0




def _safe_replace_py(content, target_path):
    """安全替换 Python 源文件：先用 py_compile 校验语法完整性，再写回目标路径

    参数:
        content: 字节串，新文件内容
        target_path: 目标文件绝对路径
    返回:
        True 表示校验通过并已替换；False 表示校验失败，原文件保持不变
    """
    import py_compile
    # 写入临时文件做语法校验，避免损坏的下载内容直接覆盖可用文件
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        try:
            py_compile.compile(tmp_path, doraise=True)
        except py_compile.PyCompileError as e:
            print(f"  下载的 {os.path.basename(target_path)} 语法校验失败，已放弃更新避免损坏: {e}")
            return False
        # 校验通过，原子替换（写回原路径）
        with open(target_path, 'wb') as dst:
            dst.write(content)
        return True
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass




def _verify_download_sha256(content, checksum_url, asset_name=""):
    """校验下载内容的 SHA256 完整性（防篡改/防损坏）

    安全机制：在 py_compile 语法校验之外，额外提供 SHA256 签名验证，
    防止下载内容在传输过程中被篡改或注入恶意代码。

    参数:
        content: 字节串，已下载的文件内容
        checksum_url: 校验文件的 URL（如 SHA256SUMS 或 mp.py.sha256）
        asset_name: 资产名称（用于在多文件校验文件中匹配对应行）
    返回:
        True 表示校验通过，或无校验文件可用（降级为仅 py_compile 校验）
        False 表示校验文件存在但哈希不匹配（可能被篡改），应中止更新
    """
    try:
        req = urllib.request.Request(checksum_url, headers={"User-Agent": "mp-player"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            checksum_data = resp.read().decode('utf-8', errors='replace').strip()
        # 计算实际内容的 SHA256
        actual_hash = hashlib.sha256(content).hexdigest()
        # 解析校验文件，格式: <sha256>  <filename>（每行一条）
        for line in checksum_data.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) >= 2:
                expected_hash, fname = parts[0], parts[1].strip()
                # 匹配文件名（支持 * 前缀通配符）
                if asset_name and fname.lstrip('*') in asset_name:
                    if expected_hash.lower() == actual_hash.lower():
                        print("  SHA256 校验通过")
                        return True
                    else:
                        print("  SHA256 校验失败！下载内容可能被篡改")
                        print(f"    期望: {expected_hash}")
                        print(f"    实际: {actual_hash}")
                        return False
            elif len(parts) == 1 and not asset_name:
                # 单行仅含 hash（无文件名）
                if parts[0].lower() == actual_hash.lower():
                    print("  SHA256 校验通过")
                    return True
        # 校验文件存在但未找到匹配的条目
        print(f"  SHA256 校验文件中未找到 {asset_name or '文件'} 的条目，跳过校验（降级）")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # 无校验文件可用，降级为仅 py_compile 校验
            return True
        print(f"  获取 SHA256 校验文件失败: {e}")
        return True
    except Exception as e:
        # 校验过程出错不阻塞更新（降级处理，避免网络问题导致无法更新）
        print(f"  SHA256 校验异常（已降级跳过）: {e}")
        return True




def _apply_zip_update(zip_path, install_root):
    """从 zip 中提取并应用更新（支持 mp/ 包结构）

    适用于 Release Assets zip 和 codeload 仓库 zip 两种来源。
    zip 内部结构可能为平铺（mp.py + mp/）或带顶层目录（repo-main/mp.py + repo-main/mp/），
    本函数自动定位同时包含 mp.py 和 mp/ 子目录的根目录。

    步骤:
    1. 安全解压 zip 到临时目录（防 zip slip 路径遍历攻击）
    2. 定位 zip 中同时包含 mp.py 和 mp/ 子目录的根目录
    3. 收集 mp.py 及 mp/ 目录下所有 .py 文件
    4. 逐个对 .py 文件做 py_compile 语法校验
    5. 全部校验通过后，替换 mp.py、mp/ 目录、install.sh（若有）
    6. 任一文件校验失败则放弃更新，保留原文件不损坏

    :param zip_path: 下载的 zip 临时文件路径
    :param install_root: 安装根目录（mp.py 所在目录，mp/ 包目录的父目录）
    :return: True 表示更新成功；False 表示更新失败
    """
    import py_compile

    # 创建临时解压目录
    extract_dir = tempfile.mkdtemp(prefix="mp_update_")
    try:
        # --- 安全解压：逐成员校验路径，防止 zip slip 路径遍历攻击 ---
        with zipfile.ZipFile(zip_path, 'r') as zf:
            extract_abs = os.path.abspath(extract_dir)
            for member in zf.namelist():
                # 跳过目录条目（仅文件需要解压）
                if member.endswith("/"):
                    continue
                # 拼接并规范化目标路径，校验未越出解压目录
                target = os.path.normpath(os.path.join(extract_dir, member))
                if not (target == extract_abs or target.startswith(extract_abs + os.sep)):
                    print(f"  跳过可疑路径（疑似 zip slip）: {member}")
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(member) as src, open(target, 'wb') as dst:
                    dst.write(src.read())

        # --- 定位 zip 中同时包含 mp.py 和 mp/ 子目录的根目录 ---
        # zip 可能为平铺结构（mp.py 在根）或带顶层目录（如 repo-main/mp.py）
        zip_root = None
        for dirpath, dirnames, filenames in os.walk(extract_dir):
            if "mp.py" in filenames and "mp" in dirnames:
                if os.path.isdir(os.path.join(dirpath, "mp")):
                    zip_root = dirpath
                    break

        if not zip_root:
            print("  zip 中未找到 mp.py 和 mp/ 包目录（可能不是有效的更新包）")
            return False

        new_mp_py = os.path.join(zip_root, "mp.py")
        new_pkg_dir = os.path.join(zip_root, "mp")

        # --- 收集所有需要校验的 .py 文件（mp.py + mp/ 下所有 .py）---
        py_files_to_check = [new_mp_py]
        for dirpath, dirnames, filenames in os.walk(new_pkg_dir):
            # 不递归 __pycache__ 目录
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for fn in filenames:
                if fn.endswith(".py"):
                    py_files_to_check.append(os.path.join(dirpath, fn))

        print(f"  共 {len(py_files_to_check)} 个 .py 文件待校验")

        # --- 逐个对 .py 文件做 py_compile 语法校验 ---
        # 任一文件校验失败则放弃更新，避免损坏文件覆盖可用版本（bug #17）
        for py_file in py_files_to_check:
            try:
                py_compile.compile(py_file, doraise=True)
            except py_compile.PyCompileError as e:
                rel = os.path.relpath(py_file, zip_root)
                print(f"  {rel} 语法校验失败，已放弃更新避免损坏: {e}")
                return False

        print("  全部 .py 文件语法校验通过")

        # --- 校验全部通过，开始替换 ---
        # 1) 替换 mp.py（安装根目录下的启动器）
        target_mp_py = os.path.join(install_root, "mp.py")
        shutil.copy2(new_mp_py, target_mp_py)

        # 2) 替换 mp/ 包目录：先重命名旧目录，再复制新目录，最后删除旧目录
        #    采用重命名中间步骤，确保复制中途失败时可恢复旧目录
        old_pkg_dir = os.path.join(install_root, "mp")
        backup_pkg_dir = old_pkg_dir + ".old"
        # 清理可能残留的上次失败备份
        if os.path.exists(backup_pkg_dir):
            shutil.rmtree(backup_pkg_dir, ignore_errors=True)
        os.rename(old_pkg_dir, backup_pkg_dir)
        try:
            shutil.copytree(new_pkg_dir, old_pkg_dir)
            # 复制成功，删除旧目录备份
            shutil.rmtree(backup_pkg_dir, ignore_errors=True)
        except Exception as e:
            # 复制失败，恢复旧目录
            print(f"  复制 mp/ 目录失败，恢复旧目录: {e}")
            if os.path.exists(old_pkg_dir):
                shutil.rmtree(old_pkg_dir, ignore_errors=True)
            os.rename(backup_pkg_dir, old_pkg_dir)
            return False

        # 3) 替换 install.sh（如果 zip 中包含）
        new_install_sh = os.path.join(zip_root, "install.sh")
        if os.path.isfile(new_install_sh):
            target_install_sh = os.path.join(install_root, "install.sh")
            shutil.copy2(new_install_sh, target_install_sh)

        return True
    finally:
        # 清理临时解压目录
        shutil.rmtree(extract_dir, ignore_errors=True)


def check_for_update(force: bool = False):
    """检查 GitHub 上是否有新版本，如有则询问用户是否更新

    更新策略（按优先级）：
    1. Release Assets 下载 releases zip（最可靠，版本对应，含 mp.py + mp/ 包 + install.sh）
    2. codeload.github.com 下载 main 分支仓库 zip（回退方案，含完整仓库）
    3. git pull（仅当安装根目录有 .git 时）

    v2.12.0 起项目从单文件 mp.py 拆分为 mp.py 启动器 + mp/ 包目录，
    更新逻辑需替换整个包（mp.py + mp/ 目录下所有 .py 文件），不再只替换单个 mp.py。

    所有下载的 .py 文件在替换本地文件前均通过 py_compile 语法校验，
    任一文件校验失败则放弃更新，避免损坏/不完整的下载覆盖可用版本（bug #17）。

    :param force: 为 True 时即使已是最新版也显示版本信息（用于 --update 模式）
    :return: True 表示已更新并退出程序；False 表示未更新或检查失败
    """
    import urllib.request
    import urllib.error

    try:
        latest, release_url, assets = _fetch_latest_version_github()
        if not latest:
            if force:
                print(f"当前版本: v{__version__}")
                print("检查更新失败：无法获取远程版本信息")
            return False

        if _compare_versions(latest, __version__) <= 0:
            if force:
                print(f"当前版本: v{__version__}")
                print("已是最新版本")
            return False

        print(f"\n{'='*50}")
        print(f"  发现新版本！")
        print(f"  当前版本: v{__version__}")
        print(f"  最新版本: {latest}")
        print(f"{'='*50}")
        print(f"更新内容请查看: {release_url}")

        try:
            choice = input("\n是否立即更新？(y/N): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return

        if choice != 'y':
            return

        print("正在更新...")
        # updater.py 位于 mp/ 包目录中，安装根目录是其父目录（mp.py 所在目录）
        updater_file = os.path.abspath(__file__)
        pkg_dir = os.path.dirname(updater_file)
        install_root = os.path.dirname(pkg_dir)
        updated = False

        # 策略1：从 Release Assets 下载 releases zip（优先）
        # 寻找名称包含 "releases" 的 asset，回退到第一个 zip asset
        if not updated and assets:
            releases_asset = None
            for a in assets:
                name = a.get("name", "").lower()
                if "release" in name and name.endswith(".zip"):
                    releases_asset = a
                    break
            # 若没有 releases zip，回退到第一个 zip asset
            if not releases_asset:
                for a in assets:
                    if a.get("name", "").lower().endswith(".zip"):
                        releases_asset = a
                        break

            if releases_asset and releases_asset.get("url"):
                try:
                    asset_url = releases_asset["url"]
                    asset_name = releases_asset.get("name", "asset.zip")
                    print(f"  下载 {asset_name} ...")
                    req = urllib.request.Request(asset_url, headers={"User-Agent": "mp-player"})
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        content = resp.read()
                    # SHA256 完整性校验：尝试从 Release Assets 获取校验文件并验证（防篡改）
                    checksum_asset = None
                    for a in assets:
                        cname = a.get("name", "").lower()
                        if "sha256" in cname or "checksum" in cname:
                            checksum_asset = a
                            break
                    if checksum_asset and checksum_asset.get("url"):
                        if not _verify_download_sha256(content, checksum_asset["url"], asset_name):
                            raise Exception("SHA256 校验失败，下载内容可能被篡改")
                    else:
                        print("  提示: Release 中未提供 SHA256 校验文件，仅做语法校验")
                    # 写入临时 zip 文件，调用 _apply_zip_update 解压校验并替换整个包
                    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name
                    try:
                        if _apply_zip_update(tmp_path, install_root):
                            updated = True
                    finally:
                        try:
                            os.unlink(tmp_path)
                        except OSError:
                            pass
                except Exception as e:
                    print(f"  从 Release Assets 更新失败: {e}")

        # 策略2：codeload.github.com 下载 main 分支仓库 zip（回退）
        # 下载完整仓库 zip，解压后同策略1处理（替换 mp.py + mp/ 包目录）
        if not updated:
            try:
                codeload_url = _github_url(
                    f"https://codeload.github.com/{GITHUB_REPO}/zip/refs/heads/main"
                )
                print(f"  下载 main 分支仓库 zip ...")
                req = urllib.request.Request(codeload_url, headers={"User-Agent": "mp-player"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    content = resp.read()
                # 写入临时 zip 文件，调用 _apply_zip_update 解压校验并替换整个包
                with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    if _apply_zip_update(tmp_path, install_root):
                        updated = True
                finally:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
            except Exception as e:
                print(f"  从仓库 zip 下载失败: {e}")

        # 策略3：git pull（最后回退，仅当安装根目录有 .git）
        if not updated and os.path.isdir(os.path.join(install_root, '.git')):
            try:
                print(f"  尝试 git pull ...")
                result = subprocess.run(
                    ['git', 'pull'],
                    cwd=install_root,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    updated = True
                else:
                    print(f"  git pull 失败: {result.stderr}")
            except Exception as e:
                print(f"  git pull 失败: {e}")

        if updated:
            print("更新成功！请重新运行程序。")
            sys.exit(0)
        else:
            print(f"自动更新失败，请手动访问 {release_url} 下载最新版本")
            return False
    except Exception as e:
        # 更新检查失败不应影响正常使用
        if force:
            print(f"检查更新失败: {e}")
        return False


