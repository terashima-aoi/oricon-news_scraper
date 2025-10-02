from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import os
from urllib.parse import urljoin, urlparse
import time
import shutil

app = Flask(__name__)

STATIC_DIR = 'static'
DOWNLOAD_DIR = os.path.join(STATIC_DIR, 'downloads')

def scrape_general_images(target_url):
    """
    任意のURLからimgタグの画像を抽出する汎用ロジック（高速版）
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    found_urls = set()
    try:
        response = requests.get(target_url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for img in soup.select('img'):
            src = img.get('data-src') or img.get('src')
            if src and not src.startswith('data:'):
                found_urls.add(urljoin(target_url, src))
    except Exception as e:
        print(f"汎用モードでの解析中にエラーが発生: {e}")

    # 見つかった順に最大30件までを対象とする
    return list(found_urls)[:30]

def scrape_oricon_images(target_url, headers):
    """
    Oricon News専用の高解像度画像抽出ロジック
    """
    print("Oricon NewsのURLを検出しました。高解像度モードで実行します。")
    response = requests.get(target_url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    link_tags = soup.select('div.inner-photo a, section.block-photo-preview a')
    
    photo_page_urls = set()
    for link in link_tags:
        href = link.get('href')
        if href and 'photo' in href:
            photo_page_urls.add(urljoin(target_url, href))
    
    high_res_urls = []
    for page_url in sorted(list(photo_page_urls)):
        time.sleep(0.2)
        page_res = requests.get(page_url, headers=headers, timeout=10)
        page_soup = BeautifulSoup(page_res.text, 'html.parser')
        meta_tag = page_soup.select_one('meta[property="og:image"]')
        if meta_tag and meta_tag.get('content') and "_p_o_" in meta_tag.get('content'):
            high_res_urls.append(meta_tag.get('content'))
    return high_res_urls


@app.route('/', methods=['GET', 'POST'])
def index():
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR)

    if request.method == 'POST':
        # ▼▼▼ 修正箇所 ▼▼▼
        raw_url = request.form.get('url')
        if not raw_url:
            return render_template('index.html', error="URLを入力してください。")

        # モバイルブラウザの特殊な挙動で複数のURLが結合される場合への対策
        # 文字列をスペースで分割し、最後の有効なURLらしきものを取得する
        url_parts = raw_url.strip().split()
        url = ""
        for part in reversed(url_parts):
            if part.startswith('http'):
                url = part
                break
        
        if not url:
            return render_template('index.html', error=f"有効なURLを抽出できませんでした: {raw_url}", url=raw_url)
        # ▲▲▲ 修正箇所 ▲▲▲
        
        print(f"URLを受け取りました (修正後): {url}")
        
        image_urls_to_download = []
        try:
            if "oricon.co.jp/news/" in url:
                image_urls_to_download = scrape_oricon_images(url, {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                })
            else:
                image_urls_to_download = scrape_general_images(url)
        except Exception as e:
            print(f"スクレイピング処理中にエラー: {e}")
            return render_template('index.html', error=f"エラーが発生しました: {e}", url=url)

        # 画像のダウンロード処理
        downloaded_files = []
        for image_url in image_urls_to_download:
            try:
                time.sleep(0.1)
                image_res = requests.get(image_url, stream=True, timeout=10)
                image_res.raise_for_status()
                image_name = os.path.basename(urlparse(image_url).path)
                if not image_name: continue

                save_path = os.path.join(DOWNLOAD_DIR, image_name)
                with open(save_path, 'wb') as f:
                    for chunk in image_res.iter_content(8192):
                        f.write(chunk)
                
                web_path = os.path.join('downloads', image_name).replace('\\', '/')
                downloaded_files.append(web_path)
                print(f"保存しました: {image_name}")
            except Exception as e:
                print(f"ダウンロード失敗: {image_url}, {e}")

        return render_template('index.html', results=downloaded_files, url=url)

    return render_template('index.html')