#!/usr/bin/env python3
"""123 云盘 Android API 上传脚本（规则 10）

上传 /tmp/2.11.10.zip 和 /tmp/2.11.10releases.zip 到
/github/media-on-terminal/ 目录

端点来源：Qxyz17/123pan 源码（已验证可用）
- 域名：https://www.123pan.cn（注意 .cn 不是 .com）
- 登录：POST /b/api/user/sign_in（code=200 成功，token 在 data.token）
- 文件列表：GET  /api/file/list/new（code=0 成功）
- 文件夹创建：POST /a/api/file/upload_request（body 含 type:1，code=0 成功）
- 文件上传请求：POST /b/api/file/upload_request（body 含 etag:md5, type:0，code=0 成功）
- 上传流程：upload_request → s3_list_upload_parts → s3_repare_upload_parts_batch → PUT → s3_list_upload_parts → s3_complete_multipart_upload → upload_complete
"""
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error

# --- 配置（规则 10）---
PASSPORT = "17345783878"
PASSWORD = "Hy123456"

BASE = "https://www.123pan.cn"
LOGIN_BASE = "https://www.123pan.cn"  # 登录也走 www.123pan.cn/b/api/user/sign_in


# Android API 公共请求头（规则 10）
def android_headers(token=None):
    h = {
        "user-agent": "123pan/v2.4.0(Android_11;Xiaomi)",
        "content-type": "application/json",
        "platform": "android",
        "devicetype": "M2004J19C",
        "osversion": "Android_11",
        "app-version": "61",
        "x-app-version": "2.4.0",
        "host": "www.123pan.cn",
    }
    if token:
        h["authorization"] = f"Bearer {token}"
    return h


def api_post(url, body, headers, timeout=30):
    """POST JSON 请求"""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        print(f"  HTTPError {e.code}: {body_text[:500]}")
        try:
            return json.loads(body_text)
        except Exception:
            return {"code": e.code, "message": body_text}
    except Exception as e:
        print(f"  请求异常: {e}")
        return {"code": -1, "message": str(e)}


def api_get(url, headers, timeout=30):
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        print(f"  HTTPError {e.code}: {body_text[:500]}")
        try:
            return json.loads(body_text)
        except Exception:
            return {"code": e.code, "message": body_text}
    except Exception as e:
        print(f"  请求异常: {e}")
        return {"code": -1, "message": str(e)}


def login():
    """登录获取 token"""
    print("[1/5] 登录 123 云盘...")
    url = f"{LOGIN_BASE}/b/api/user/sign_in"
    body = {"type": 1, "passport": PASSPORT, "password": PASSWORD, "remember": True}
    resp = api_post(url, body, android_headers())
    print(f"  响应 code={resp.get('code')}, message={resp.get('message', '')}")
    # 登录接口 code=200 表示成功
    if resp.get("code") != 200:
        print(f"  登录失败: {resp}")
        return None
    data = resp.get("data", {})
    token = data.get("token")
    if token:
        print(f"  登录成功，token 长度={len(token)}")
    return token


def list_dir(token, parent_file_id=0, limit=100):
    """列出目录下的文件/文件夹（/api/file/list/new，code=0 成功）"""
    url = (
        f"{BASE}/api/file/list/new?driveId=0&limit={limit}&next=0"
        f"&orderBy=file_id&orderDirection=desc&parentFileId={parent_file_id}"
        f"&trashed=false&SearchData=&Page=1&OnlyLookAbnormalFile=false"
    )
    return api_get(url, android_headers(token))


def find_or_create_folder(token, parent_file_id, folder_name):
    """在 parent_file_id 下查找或创建文件夹，返回 folder 的 file_id"""
    # 先查找
    resp = list_dir(token, parent_file_id)
    if resp.get("code") == 0:
        items = resp.get("data", {}).get("InfoList", [])
        for it in items:
            if it.get("Type") == 1 and it.get("FileName") == folder_name:
                print(f"  目录已存在: {folder_name} (file_id={it.get('FileId')})")
                return it.get("FileId")
    else:
        print(f"  列目录失败: code={resp.get('code')}, msg={resp.get('message', '')}")
    # 未找到，创建（文件夹用 /a/api/ 前缀）
    print(f"  创建目录: {folder_name} (parent={parent_file_id})")
    url = f"{BASE}/a/api/file/upload_request"
    body = {
        "driveId": 0,
        "duplicate": 2,  # 2=保留两者
        "etag": "",
        "fileName": folder_name,
        "parentFileId": parent_file_id,
        "size": 0,
        "type": 1,  # 1=文件夹
        "NotReuseShared": True,
        "ContainShare": True,
    }
    resp = api_post(url, body, android_headers(token))
    if resp.get("code") == 0:
        data = resp.get("data", {})
        # 文件夹创建：data 中含 FileInfo.FileId
        file_id = data.get("fileId") or data.get("FileId")
        if file_id:
            print(f"  目录创建成功: {folder_name} (file_id={file_id})")
            return file_id
        info = data.get("FileInfo") or {}
        if info.get("FileId"):
            print(f"  目录创建成功: {folder_name} (file_id={info.get('FileId')})")
            return info.get("FileId")
        print(f"  目录创建响应 data keys: {list(data.keys())}")
        print(f"  响应: {json.dumps(data, ensure_ascii=False)[:300]}")
        return None
    print(f"  目录创建失败: code={resp.get('code')}, msg={resp.get('message', '')}")
    print(f"  完整响应: {json.dumps(resp, ensure_ascii=False)[:400]}")
    return None


def compute_md5(file_path):
    """计算文件 MD5"""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(64 * 1024)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()


def upload_file(token, parent_file_id, file_path, file_name):
    """上传文件（基于 Qxyz17/123pan upload_service.py 完整流程）

    流程：
    1. POST /b/api/file/upload_request 获取上传凭证（含 Bucket/Key/UploadId/FileId 或 Reuse 秒传）
    2. POST /b/api/file/s3_list_upload_parts 初始化上传会话
    3. 循环分块：POST /b/api/file/s3_repare_upload_parts_batch 获取 presignedUrls → PUT 上传
    4. POST /b/api/file/s3_list_upload_parts 完成确认
    5. POST /b/api/file/s3_complete_multipart_upload 合并
    6. POST /b/api/file/upload_complete 完成上传
    """
    size = os.path.getsize(file_path)
    print(f"\n  上传文件: {file_name} (size={size} bytes)")

    # 计算 MD5
    print(f"  [a] 计算 MD5...")
    file_md5 = compute_md5(file_path)
    print(f"    MD5={file_md5}")

    # 步骤1: upload_request（文件用 /b/api/ 前缀，body 含 etag:md5）
    print(f"  [b] upload_request...")
    url = f"{BASE}/b/api/file/upload_request"
    body = {
        "driveId": 0,
        "etag": file_md5,
        "fileName": file_name,
        "parentFileId": parent_file_id,
        "size": size,
        "type": 0,  # 0=文件
        "duplicate": 0,
    }
    resp = api_post(url, body, android_headers(token))
    code = resp.get("code", -1)
    print(f"    code={code}")

    # 重复文件 code 5060，需要重新请求带 duplicate 参数
    if code == 5060:
        print(f"    重复文件，重新请求带 duplicate=2...")
        body["duplicate"] = 2  # 2=保留两者
        resp = api_post(url, body, android_headers(token))
        code = resp.get("code", -1)
        print(f"    重试 code={code}")

    if code != 0:
        print(f"    upload_request 失败: {json.dumps(resp, ensure_ascii=False)[:500]}")
        return False

    data = resp.get("data", {})

    # 秒传：Reuse=True
    if data.get("Reuse", False):
        up_file_id = data.get("FileId")
        print(f"  ✓ {file_name} 秒传成功 (file_id={up_file_id})")
        return True

    # 获取上传凭证
    bucket = data.get("Bucket")
    storage_node = data.get("StorageNode")
    upload_key = data.get("Key")
    upload_id = data.get("UploadId")
    up_file_id = data.get("FileId")
    print(f"    Bucket={bucket}, Key={upload_key}, UploadId={upload_id}, FileId={up_file_id}")

    # 步骤2: 初始化上传会话
    print(f"  [c] s3_list_upload_parts (初始化)...")
    start_data = {
        "bucket": bucket,
        "key": upload_key,
        "uploadId": upload_id,
        "storageNode": storage_node,
    }
    resp_start = api_post(
        f"{BASE}/b/api/file/s3_list_upload_parts",
        start_data, android_headers(token),
    )
    if resp_start.get("code", -1) != 0:
        print(f"    初始化失败: {json.dumps(resp_start, ensure_ascii=False)[:500]}")
        return False
    print(f"    初始化成功")

    # 步骤3: 分块上传（5MB 一块）
    block_size = 5242880  # 5MB
    total_sent = 0
    part_number = 1
    with open(file_path, "rb") as f:
        while True:
            data_chunk = f.read(block_size)
            if not data_chunk:
                break

            # 获取 presigned URL
            print(f"  [d-{part_number}] s3_repare_upload_parts_batch...")
            get_link_data = {
                "bucket": bucket,
                "key": upload_key,
                "partNumberEnd": part_number + 1,  # 开区间上界
                "partNumberStart": part_number,
                "uploadId": upload_id,
                "StorageNode": storage_node,
            }
            resp_link = api_post(
                f"{BASE}/b/api/file/s3_repare_upload_parts_batch",
                get_link_data, android_headers(token),
            )
            if resp_link.get("code", -1) != 0:
                print(f"    获取链接失败: {json.dumps(resp_link, ensure_ascii=False)[:500]}")
                return False
            presigned_url = resp_link["data"]["presignedUrls"][str(part_number)]

            # PUT 上传分块
            print(f"  [e-{part_number}] PUT 分块 ({len(data_chunk)} bytes)...")
            req = urllib.request.Request(presigned_url, data=data_chunk, method="PUT")
            req.add_header("Content-Type", "application/octet-stream")
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    print(f"    PUT 状态: {r.status}")
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")[:300]
                print(f"    PUT HTTPError {e.code}: {err_body}")
                return False
            except Exception as e:
                print(f"    PUT 异常: {e}")
                return False

            total_sent += len(data_chunk)
            part_number += 1

    print(f"    分块上传完成: {total_sent}/{size} bytes, {part_number-1} 块")

    # 步骤4: 完成确认 s3_list_upload_parts
    print(f"  [f] s3_list_upload_parts (完成确认)...")
    api_post(
        f"{BASE}/b/api/file/s3_list_upload_parts",
        start_data, android_headers(token),
    )

    # 步骤5: 合并 s3_complete_multipart_upload
    print(f"  [g] s3_complete_multipart_upload...")
    resp_complete = api_post(
        f"{BASE}/b/api/file/s3_complete_multipart_upload",
        start_data, android_headers(token),
    )
    if resp_complete.get("code", -1) != 0:
        print(f"    合并失败: {json.dumps(resp_complete, ensure_ascii=False)[:500]}")
        return False

    # 大文件等待 3 秒
    if size > 64 * 1024 * 1024:
        print(f"    大文件等待 3 秒...")
        time.sleep(3)

    # 步骤6: upload_complete
    print(f"  [h] upload_complete...")
    close_data = {"fileId": up_file_id}
    resp_close = api_post(
        f"{BASE}/b/api/file/upload_complete",
        close_data, android_headers(token),
    )
    if resp_close.get("code", -1) != 0:
        print(f"    完成确认失败: {json.dumps(resp_close, ensure_ascii=False)[:500]}")
        return False

    print(f"  ✓ {file_name} 上传成功 (file_id={up_file_id})")
    return True


def main():
    token = login()
    if not token:
        print("登录失败，退出")
        sys.exit(1)

    # 查找/创建 /github/media-on-terminal/ 目录
    print("\n[2/5] 查找/创建 /github/ 目录...")
    github_id = find_or_create_folder(token, 0, "github")
    if not github_id:
        print("创建 github 目录失败")
        sys.exit(1)

    print("\n[3/5] 查找/创建 /github/media-on-terminal/ 目录...")
    mt_id = find_or_create_folder(token, github_id, "media-on-terminal")
    if not mt_id:
        print("创建 media-on-terminal 目录失败")
        sys.exit(1)

    # 上传两个文件
    print("\n[4/5] 上传 2.11.10.zip...")
    ok1 = upload_file(token, mt_id, "/tmp/2.11.10.zip", "2.11.10.zip")

    print("\n[5/5] 上传 2.11.10releases.zip...")
    ok2 = upload_file(token, mt_id, "/tmp/2.11.10releases.zip", "2.11.10releases.zip")

    print("\n" + "=" * 50)
    print(f"上传结果: 2.11.10.zip={'成功' if ok1 else '失败'}, 2.11.10releases.zip={'成功' if ok2 else '失败'}")
    print("=" * 50)
    sys.exit(0 if (ok1 and ok2) else 1)


if __name__ == "__main__":
    main()
