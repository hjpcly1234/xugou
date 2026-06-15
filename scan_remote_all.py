import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json

# ========== 扫描配置 ==========
BASE_URL = "https://emby-data.ymschh.top/每日更新/"
BACKUP_URLS = [
    "https://embyxiaoya.laogl.top/每日更新/",
    "https://emby.xiaoya.pro/每日更新/",
    "https://emby-data.neversay.eu.org/每日更新/",
    "https://emby.raydoom.tk/每日更新/"
]

MAX_SCAN_THREADS = 40  # GitHub Actions 的带宽和算力极大，线程可以直接拉大到 40
TIMEOUT = 12
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 输出文件名（保存在当前仓库根目录）
REMOTE_LIST_FILE = "remote_list.txt"
CACHE_METADATA_FILE = "remote_cache_metadata.json"

def get_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session

def list_dir(session, url):
    try:
        resp = session.get(url, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        html = resp.text
    except Exception:
        return []
        
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a"):
        href = a.get("href")
        if not href or href in ("../", "?C=N;O=D", "?C=M;O=A"):
            continue
        full = urljoin(url, href)
        links.append(full)
    return links

def fast_recursive_scan(base_url, session):
    visited, all_files = set(), []
    to_scan = [base_url]
    print(f"🚀 开始并发扫描网站目录: {base_url}")
    
    with ThreadPoolExecutor(max_workers=MAX_SCAN_THREADS) as ex:
        while to_scan:
            futures = {ex.submit(list_dir, session, url): url for url in to_scan}
            to_scan = []
            for fut in as_completed(futures):
                try:
                    result = fut.result()
                    for u in result:
                        if u.endswith("/"):
                            if u not in visited:
                                visited.add(u)
                                to_scan.append(u)
                        else:
                            all_files.append(u)
                except Exception:
                    pass
    return all_files

def get_remote_hash(files):
    content = "\n".join(sorted(files)).encode('utf-8')
    return hashlib.md5(content).hexdigest()

def main():
    session = get_session()
    urls_to_try = [BASE_URL] + BACKUP_URLS
    
    for url in urls_to_try:
        print(f"🔍 尝试扫描站点: {url}")
        files = fast_recursive_scan(url, session)
        if files:
            remote_hash = get_remote_hash(files)
            
            # 写入清单
            with open(REMOTE_LIST_FILE, "w", encoding="utf-8") as f:
                for file_url in sorted(files):
                    f.write(file_url + "\n")
                    
            # 写入元数据元数据
            metadata = {'hash': remote_hash, 'base_url': url}
            with open(CACHE_METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(metadata, f)
                
            print(f"✅ 全站扫描成功！共发现 {len(files)} 个文件。Hash: {remote_hash}")
            return
        else:
            print(f"⚠️ 站点 {url} 返回空，尝试下一个。")
            
    print("❌ 所有URL均无法扫描到文件，本次扫描失败。")
    exit(1)

if __name__ == "__main__":
    main()
