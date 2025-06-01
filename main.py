# main.py
# -*- coding: utf-8 -*-
import os
import random
import requests
import json
from datetime import datetime, timedelta # timeはscheduleで使っていたが、ここでは不要になるかも
import time # time.sleep は残す
from moviepy.editor import *
from PIL import Image, ImageDraw, ImageFont
import googleapiclient.discovery
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request # 追加
# from google_auth_oauthlib.flow import Flow # 初回認証用なので削除、代わりにCredentials.from_authorized_user_info
# import threading # threading は使われていないので削除
from gtts import gTTS
# import schedule # GitHub Actionsで実行するので不要
# from python_crontab import CronTab # GitHub Actionsで実行するので不要

print("✅ ライブラリインポート完了!")

# --- グローバル設定 ---
# APIキーは環境変数から取得
PIXABAY_API_KEY = os.environ.get("PIXABAY_API_KEY")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY")

if not PIXABAY_API_KEY:
    print("⚠️ 警告: PIXABAY_API_KEY 環境変数が設定されていません。画像取得に失敗する可能性があります。")
if not UNSPLASH_ACCESS_KEY:
    print("ℹ️ INFO: UNSPLASH_ACCESS_KEY 環境変数が設定されていません。Unsplashからのフォールバック画像取得は行われません。")

# ファイルパス設定 (GitHub Actionsのワークスペースルートを基準)
CREDENTIALS_PATH = 'credentials.json'  # GitHub ActionsワークフローでSecretから作成される
YOUTUBE_TOKEN_JSON_PATH = 'youtube_token.json' # GitHub ActionsワークフローでSecretから作成される
CONTENT_LIST_PATH = 'content_list.txt' # リポジトリのルートに配置
OUTPUT_FOLDER = 'generated_videos'     # 一時的な動画保存フォルダ

# 出力フォルダが存在しない場合は作成
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)
    print(f"📂 出力フォルダ '{OUTPUT_FOLDER}' を作成しました。")

print("✅ APIキー・ファイルパス設定完了!")


# 著作権フリー素材取得システム（株式投資テーマ特化版）
class FreeAssetCollector:
    def __init__(self):
        self.pixabay_key = PIXABAY_API_KEY
        self.unsplash_key = UNSPLASH_ACCESS_KEY
        self.used_images = set()  # 使用済み画像URLを記録

        self.financial_keywords = [
            "stock+market+chart+bull", "financial+graph+rising+trend", "trading+screen+computer+monitor",
            "investment+portfolio+growth", "stock+exchange+floor+trading", "bull+market+green+arrow+up",
            "candlestick+chart+analysis", "dividend+income+calculator", "cryptocurrency+bitcoin+chart",
            "forex+currency+trading+pairs", "financial+advisor+planning", "retirement+401k+investment",
            "mutual+funds+etf+diversification", "bear+market+red+declining", "penny+stocks+small+cap",
            "blue+chip+stocks+stable", "market+volatility+risk", "technical+analysis+indicators",
            "fundamental+analysis+research", "day+trading+scalping+profit"
        ]
        self.required_financial_terms = [
            'business', 'finance', 'money', 'stock', 'market', 'chart', 'graph', 'trading', 
            'investment', 'financial', 'economy', 'banking', 'currency', 'profit', 'growth', 
            'analysis', 'portfolio', 'dividend', 'bull', 'bear', 'exchange'
        ]

    def get_stock_related_image(self, attempt=0):
        if not self.pixabay_key:
            print("⚠️ Pixabay APIキーが設定されていないため、画像を取得できません。")
            return self.get_fallback_unsplash_image() # Unsplashを試す

        if attempt >= len(self.financial_keywords):
            if len(self.used_images) > 0:
                print("🔄 使用済み画像をリセットして再試行...")
                self.used_images.clear()
                return self.get_stock_related_image(0)
            else:
                print("⚠️ 全キーワードを試行しました")
                return self.get_fallback_unsplash_image()

        available_keywords = self.financial_keywords.copy()
        random.shuffle(available_keywords)
        keyword = available_keywords[attempt % len(available_keywords)]
        print(f"🔍 株式投資画像検索 (Pixabay - {attempt+1}/{len(self.financial_keywords)}): {keyword.replace('+', ' ')}")
        
        random_page = random.randint(1, 3)
        url = (f"https://pixabay.com/api/"
               f"?key={self.pixabay_key}"
               f"&q={keyword}"
               f"&image_type=photo&orientation=horizontal&category=business"
               f"&min_width=1920&min_height=1080&per_page=20&page={random_page}"
               f"&safesearch=true&order={random.choice(['popular', 'latest'])}")

        try:
            response = requests.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                hits = data.get('hits', [])
                print(f"📊 {len(hits)}件の候補画像が見つかりました")
                if hits:
                    financial_images = []
                    for img in hits:
                        image_url = img.get('largeImageURL') or img.get('webformatURL')
                        if image_url in self.used_images: continue
                        if self.is_finance_related(img):
                            score = self.calculate_finance_score(img)
                            financial_images.append((score, img))
                    
                    if not financial_images:
                        print("⚠️ 株式投資関連画像が見つかりませんでした - 次のキーワードで再試行")
                        return self.get_stock_related_image(attempt + 1)

                    financial_images.sort(reverse=True, key=lambda x: x[0])
                    print(f"✅ {len(financial_images)}件の株式投資関連画像を発見")
                    top_images = financial_images[:min(5, len(financial_images))]
                    selected_score, selected_img = random.choice(top_images)
                    image_url = selected_img.get('largeImageURL') or selected_img.get('webformatURL')
                    print(f"🎯 株式投資画像選択 (関連度スコア: {selected_score:.0f}) - タグ: {selected_img.get('tags', 'N/A')}")
                    self.used_images.add(image_url)
                    return image_url
            else:
                print(f"⚠️ Pixabay API応答エラー: {response.status_code}")
        except Exception as e:
            print(f"⚠️ Pixabay検索エラー: {e}")
        
        print("🔄 次の株式投資キーワードで再試行...")
        return self.get_stock_related_image(attempt + 1)

    def is_finance_related(self, img_data):
        tags = img_data.get('tags', '').lower()
        finance_tag_count = sum(1 for term in self.required_financial_terms if term in tags)
        if finance_tag_count >= 2:
            # print(f"   ✅ 金融関連度: {finance_tag_count}個のタグがマッチ") # ログが多すぎるのでコメントアウト
            return True
        # print(f"   ❌ 金融関連度不足: {finance_tag_count}個のタグのみ") # ログが多すぎるのでコメントアウト
        return False

    def calculate_finance_score(self, img_data):
        base_score = (img_data.get('downloads', 0) * 0.3 + img_data.get('likes', 0) * 0.4 + img_data.get('views', 0) * 0.0001)
        tags = img_data.get('tags', '').lower()
        high_priority_terms = ['stock', 'trading', 'investment', 'market', 'chart', 'financial']
        medium_priority_terms = ['business', 'money', 'finance', 'economy', 'banking']
        chart_terms = ['chart', 'graph', 'data', 'analysis', 'trend']
        high_priority_bonus = sum(200 for term in high_priority_terms if term in tags)
        medium_priority_bonus = sum(100 for term in medium_priority_terms if term in tags)
        chart_bonus = sum(150 for term in chart_terms if term in tags)
        random_bonus = random.randint(0, 50)
        return base_score + high_priority_bonus + medium_priority_bonus + chart_bonus + random_bonus

    def get_fallback_unsplash_image(self):
        if not self.unsplash_key:
            print("⚠️ Unsplash APIキーが設定されていないため、フォールバック画像を取得できません。")
            return None
        
        print("🔍 Unsplashからフォールバック画像検索中...")
        try:
            stock_keywords = [
                "stock-market-chart", "financial-trading", "investment-growth", "cryptocurrency-trading", 
                "forex-market", "bull-market", "bear-market", "financial-analysis", "trading-floor",
                "stock-exchange", "dividend-investing", "portfolio-management"
            ]
            random.shuffle(stock_keywords)
            for keyword in stock_keywords:
                random_page = random.randint(1, 3)
                url = (f"https://api.unsplash.com/search/photos"
                      f"?query={keyword}&orientation=landscape&per_page=10&page={random_page}")
                headers = {"Authorization": f"Client-ID {self.unsplash_key}"}
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    results = data.get('results', [])
                    if results:
                        random.shuffle(results)
                        for img in results:
                            description = (img.get('description', '') or img.get('alt_description', '')).lower()
                            if any(term in description for term in ['stock', 'market', 'trading', 'investment', 'financial']):
                                image_url = img['urls']['full']
                                if image_url not in self.used_images:
                                    print(f"✅ Unsplash株式投資画像: {keyword}")
                                    self.used_images.add(image_url)
                                    return image_url
                        for img in results: # 関連キーワードが無くても高解像度なら
                            image_url = img['urls']['regular']
                            if image_url not in self.used_images and img['width'] >= 1920 and img['height'] >= 1080:
                                print(f"✅ Unsplash高解像度画像: {keyword}")
                                self.used_images.add(image_url)
                                return image_url
        except Exception as e:
            print(f"⚠️ Unsplash API エラー: {e}")
        print("⚠️ Unsplashからも適切な画像が見つかりませんでした。")
        return None

    def download_image(self, url, filename):
        if not url:
            print("❌ 画像URLが無効です")
            return False
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            print(f"📥 株式投資画像ダウンロード中: {url[:70]}...")
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) < 10000: # 10KB
                print("❌ ファイルサイズが小さすぎます (10KB未満)")
                return False
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
            return self.validate_and_optimize_image(filename)
        except Exception as e:
            print(f"❌ 画像ダウンロードエラー: {e}")
            return False

    def validate_and_optimize_image(self, filename):
        try:
            with Image.open(filename) as img:
                print(f"📊 元画像サイズ: {img.size}, モード: {img.mode}")
                if img.width < 1080 or img.height < 720:
                    print(f"❌ 画像サイズが小さすぎます ({img.size})。最低1080x720が必要です。")
                    return False
                
                img_rgb = img
                if img.mode != 'RGB':
                    print(f"🖼️ 画像モードをRGBに変換中 (元: {img.mode})")
                    img_rgb = img.convert('RGB')

                target_width = 1920
                # アスペクト比16:9を維持
                target_height = int(target_width * 9 / 16) # 1920x1080 になるように

                # 元画像のアスペクト比を計算
                original_aspect_ratio = img_rgb.width / img_rgb.height
                target_aspect_ratio = 16 / 9

                # 16:9 にクロップまたはリサイズ
                # まずは1920幅にリサイズし、高さが1080より大きい場合はクロップ、小さい場合はレターボックスを避けるためそのまま使う
                # ショート動画は縦長 (1080x1920) なので、それに合わせる
                final_width, final_height = 1080, 1920 # ショート動画の解像度

                # 元画像を一旦リサイズして、中央からクロップ
                img_rgb.thumbnail((final_width * 1.5, final_height * 1.5), Image.Resampling.LANCZOS) # 少し大きめにリサイズ

                left = (img_rgb.width - final_width) / 2
                top = (img_rgb.height - final_height) / 2
                right = (img_rgb.width + final_width) / 2
                bottom = (img_rgb.height + final_height) / 2
                
                img_cropped = img_rgb.crop((left, top, right, bottom))
                
                img_cropped.save(filename, 'JPEG', quality=90, optimize=True) # 品質を少し落としてファイルサイズを抑える
                print(f"✅ 株式投資画像最適化完了 (クロップ後): {img_cropped.size} -> {filename}")
                return True
        except Exception as e:
            print(f"❌ 画像検証/最適化エラー: {e}")
            # Pillowが対応していないフォーマットの場合があるのでエラー処理
            if "cannot identify image file" in str(e).lower():
                print("   ファイル形式がPillowで非対応の可能性があります。")
            return False

print("✅ 株式投資テーマ特化画像選択システム準備完了!")


class VideoGenerator:
    def __init__(self, asset_collector):
        self.asset_collector = asset_collector
        self.used_content = set()
        # 一時ファイル用のディレクトリ (コンストラクタで一度だけ定義)
        self.temp_dir = os.path.join(OUTPUT_FOLDER, "temp_files")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def load_content_list(self, file_path, delimiter="---"):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
            content_list = []
            lines = content.split('\n')
            current_content = []
            for line in lines:
                line = line.strip()
                if line.startswith('##') or line == delimiter:
                    if current_content:
                        clean_content = '\n'.join(current_content).replace('##', '').strip()
                        if clean_content: content_list.append(clean_content)
                        current_content = []
                    if line.startswith('##'):
                        clean_line = line.replace('##', '').strip()
                        if clean_line: current_content.append(clean_line)
                elif line:
                    current_content.append(line)
            if current_content:
                clean_content = '\n'.join(current_content).replace('##', '').strip()
                if clean_content: content_list.append(clean_content)
            
            content_list = list(set(filter(None, content_list))) # 空の要素を除去
            if content_list:
                print(f"✅ {len(content_list)}個のネタを読み込みました（##記号対応）")
            else:
                print(f"⚠️ ネタが読み込めませんでした。'{file_path}' の内容を確認してください。")
            return content_list
        except FileNotFoundError:
            print(f"❌ コンテンツリストファイルが見つかりません: {file_path}")
            return []
        except Exception as e:
            print(f"❌ ファイル読み込みエラー ({file_path}): {e}")
            return []

    def select_unused_content(self, content_list):
        if not content_list:
            print("⚠️ コンテンツリストが空のため、ネタを選択できません。")
            return None
        unused_content = [c for c in content_list if c not in self.used_content]
        if not unused_content:
            self.used_content.clear()
            unused_content = content_list
            print("🔄 全ネタ使用済み - リセットしました")
        
        if not unused_content: # リセット後も空なら元々空
             print("⚠️ リセット後もコンテンツリストが空です。")
             return None

        selected = random.choice(unused_content)
        self.used_content.add(selected)
        print(f"📝 選択されたネタ: {selected[:40]}...")
        return selected

    def generate_voice(self, text, output_path):
        try:
            from pydub import AudioSegment
            # from pydub.effects import normalize # apply_cute_effects内でインポート
            print("🎤 かわいい音声生成開始...")
            voice_engines = [{'tld': 'co.jp', 'slow': False}, {'tld': 'com', 'slow': False}]
            best_audio = None
            for engine_config in voice_engines:
                # temp_path = f'/content/temp_voice_{engine_config["tld"].replace(".", "_")}.mp3' # Colabパス
                temp_path = os.path.join(self.temp_dir, f'temp_voice_{engine_config["tld"].replace(".", "_")}.mp3')
                
                print(f"🔊 音声エンジン {engine_config['tld']} で生成中...")
                try:
                    tts = gTTS(text=text, lang='ja', tld=engine_config['tld'], slow=engine_config['slow'])
                    tts.save(temp_path)
                    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 1000: # 1KB以上
                        audio = AudioSegment.from_file(temp_path)
                        if len(audio) > 500:  # 0.5秒以上の音声
                            best_audio = audio
                            print(f"✅ 音声生成成功: {engine_config['tld']}")
                            if os.path.exists(temp_path): os.remove(temp_path)
                            break
                        else:
                            print(f"⚠️ 音声が短すぎます (<0.5s): {engine_config['tld']}")
                    else:
                        print(f"⚠️ 音声ファイル生成失敗または小さすぎます: {engine_config['tld']}")
                    if os.path.exists(temp_path): os.remove(temp_path)
                except Exception as e_tts:
                    print(f"⚠️ エンジン {engine_config['tld']} 失敗: {e_tts}")
                    if os.path.exists(temp_path): os.remove(temp_path)
                    continue
            
            if best_audio is None:
                print("❌ 全ての音声エンジンで失敗 - 基本モードで再試行")
                return self.generate_voice_basic(text, output_path)

            print("✨ かわいい効果を適用中...")
            enhanced_audio = self.apply_cute_effects(best_audio)
            enhanced_audio.export(output_path, format="mp3", bitrate="128k")
            print(f"✅ かわいい高品質音声生成完了: {output_path}")
            return True
        except Exception as e:
            print(f"❌ 高品質音声生成エラー: {e}")
            print("🔄 基本モードで再試行...")
            return self.generate_voice_basic(text, output_path)

    def apply_cute_effects(self, audio):
        try:
            from pydub.effects import normalize
            print("🎵 ピッチ調整 & 音量調整中...")
            # 1. ピッチを少し上げる（かわいい声の基本） - 10-15%高速化でピッチも上がる
            faster_audio = audio.speedup(playback_speed=1.12) 
            # 2. 音量の正規化
            normalized_audio = normalize(faster_audio)
            # 3. 少し音量を下げる (オプション)
            soft_audio = normalized_audio # - 1 # 1dB下げる (必要に応じて調整)
            # 4. 高周波を少し強調（クリアさアップ）- 低音カット
            try:
                # librosaが使えるならより高度な処理も可能だが、pydubのみでシンプルに
                enhanced_audio = soft_audio.high_pass_filter(80, order=4) # orderでフィルタの鋭さを調整
            except Exception as filter_e:
                print(f"⚠️ High pass filter 適用エラー: {filter_e}。フィルターなしの音声を使用します。")
                enhanced_audio = soft_audio
            print("✅ かわいい効果適用完了!")
            return enhanced_audio
        except Exception as e:
            print(f"⚠️ 音声効果適用エラー: {e}")
            return audio

    def generate_voice_basic(self, text, output_path):
        try:
            print("🎤 基本音声生成中...")
            tts = gTTS(text=text, lang='ja', slow=False, tld='co.jp')
            tts.save(output_path)
            print(f"✅ 基本音声生成完了: {output_path}")
            return True
        except Exception as e:
            print(f"❌ 基本音声生成エラー: {e}")
            return False

    def create_short_video(self, content_text):
        print("🎬 動画生成開始...")
        # bg_image_path = '/content/temp_bg.jpg' # Colabパス
        bg_image_path = os.path.join(self.temp_dir, 'temp_bg.jpg')
        image_success = False
        for attempt in range(3):
            print(f"🔍 背景画像取得試行 {attempt + 1}/3")
            bg_image_url = self.asset_collector.get_stock_related_image()
            if bg_image_url and self.asset_collector.download_image(bg_image_url, bg_image_path):
                if self.validate_image_file_size(bg_image_path): # Pillowでの検証前にファイルサイズチェック
                    print("✅ 背景画像ダウンロード & 基本検証完了")
                    image_success = True
                    break
                else:
                    print("⚠️ 画像ファイルサイズが小さすぎるか無効なため再試行")
            time.sleep(1)
        
        if not image_success:
            print("⚠️ 外部画像取得失敗 - プロ仕様のデフォルト背景を生成")
            self.create_professional_financial_background(bg_image_path) # デフォルト背景を生成
            if not os.path.exists(bg_image_path) or os.path.getsize(bg_image_path) < 1000:
                print("❌ デフォルト背景の生成にも失敗しました。")
                return None

        # voice_path = '/content/voice.mp3' # Colabパス
        voice_path = os.path.join(self.temp_dir, 'voice.mp3')
        print("🎤 高品質音声生成中...")
        if self.generate_voice(content_text, voice_path):
            if not os.path.exists(voice_path) or os.path.getsize(voice_path) < 1000:
                 print("❌ 音声ファイルが生成されなかったか、サイズが小さすぎます。")
                 return None
            print("✅ 高品質音声生成完了")
        else:
            print("❌ 音声生成に失敗しました")
            return None
        
        return self.compose_video(content_text, bg_image_path, voice_path)

    def validate_image_file_size(self, image_path):
        """Pillowで開く前の基本的なファイルサイズ検証"""
        try:
            if not os.path.exists(image_path):
                print(f"❌ 検証対象の画像ファイルが存在しません: {image_path}")
                return False
            file_size = os.path.getsize(image_path)
            if file_size < 10000:  # 10KB未満は低品質または破損の可能性
                print(f"❌ 画像ファイルサイズが小さすぎます ({file_size} bytes)。破損または低品質の可能性があります。")
                return False
            return True
        except Exception as e:
            print(f"❌ 画像ファイルサイズ検証エラー: {e}")
            return False

    def create_professional_financial_background(self, output_path):
        print("🎨 プロ仕様の金融背景を生成中...")
        width, height = 1080, 1920 # ショート動画用
        try:
            canvas = Image.new('RGB', (width, height))
            draw = ImageDraw.Draw(canvas)
            for y_coord in range(height): # 変数名をyから変更
                ratio = y_coord / height
                r = int(8 + (15 - 8) * ratio)
                g = int(25 + (45 - 25) * ratio)
                b = int(50 + (25 - 50) * ratio) # bチャンネルの計算修正
                draw.line([(0, y_coord), (width, y_coord)], fill=(r, g, b))
            self.add_chart_decorations(draw, width, height)
            self.add_financial_decorations(draw, width, height)
            canvas.save(output_path, "JPEG", quality=85)
            print(f"✅ プロ仕様背景生成完了: {output_path}")
        except Exception as e:
            print(f"❌ プロ仕様背景生成エラー: {e}")


    def add_chart_decorations(self, draw, width, height):
        colors = [(0, 255, 100, 60), (255, 215, 0, 60), (100, 150, 255, 60)]
        for color in colors:
            points = []
            start_y = random.randint(height//4, 3*height//4)
            trend = random.choice([-1, 1]) 
            for x_coord in range(0, width + 100, 80): # 変数名をxから変更
                variation = random.randint(-80, 80)
                trend_effect = trend * (x_coord / width) * 200
                y_coord = start_y + variation + trend_effect
                y_coord = max(100, min(height-100, y_coord))
                points.append((x_coord, y_coord))
            for i in range(len(points)-1):
                draw.line([points[i], points[i+1]], fill=color, width=3)

    def add_financial_decorations(self, draw, width, height):
        grid_color = (255, 255, 255, 20)
        for x_coord in range(0, width, 120): draw.line([(x_coord, 0), (x_coord, height)], fill=grid_color, width=1)
        for y_coord in range(0, height, 150): draw.line([(0, y_coord), (width, y_coord)], fill=grid_color, width=1)
        corner_color = (255, 215, 0, 40)
        draw.polygon([(0, 0), (100, 0), (0, 100)], fill=corner_color)
        draw.polygon([(width, height), (width-100, height), (width, height-100)], fill=corner_color)

    def compose_video(self, content_text, bg_image_path, voice_path):
        try:
            print("🎬 動画合成を開始します...")
            # resized_bg_path = '/content/resized_bg.jpg' # Colabパス
            resized_bg_path = os.path.join(self.temp_dir, 'resized_bg.jpg')

            try:
                bg_image = Image.open(bg_image_path)
                # ショート動画は縦長 1080x1920
                target_size = (1080, 1920) 
                
                # アスペクト比を保ちつつ、ターゲットサイズに合うようにリサイズ＆クロップ
                img_ratio = bg_image.width / bg_image.height
                target_ratio = target_size[0] / target_size[1]

                if img_ratio > target_ratio: # 元画像がターゲットより横長 -> 高さをターゲットに合わせ、幅をクロップ
                    new_height = target_size[1]
                    new_width = int(new_height * img_ratio)
                else: # 元画像がターゲットより縦長 (または同じ) -> 幅をターゲットに合わせ、高さをクロップ
                    new_width = target_size[0]
                    new_height = int(new_width / img_ratio)
                
                bg_image_resized = bg_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # 中央からクロップ
                left = (bg_image_resized.width - target_size[0]) / 2
                top = (bg_image_resized.height - target_size[1]) / 2
                right = (bg_image_resized.width + target_size[0]) / 2
                bottom = (bg_image_resized.height + target_size[1]) / 2
                
                bg_image_final = bg_image_resized.crop((left, top, right, bottom))
                bg_image_final.save(resized_bg_path, 'JPEG', quality=90)
                
                bg_clip = ImageClip(resized_bg_path)
                print(f"✅ 背景画像処理完了: {resized_bg_path}")
            except Exception as e:
                print(f"背景画像エラー: {e}. デフォルトカラークリップを使用します。")
                bg_clip = ColorClip(size=(1080, 1920), color=(15, 30, 50), ismask=False)

            audio_clip = None
            video_duration = 15 # デフォルト
            try:
                audio_clip = AudioFileClip(voice_path)
                # ショート動画は最大60秒。音声+バッファ。最小10秒。
                video_duration = min(58, max(10, audio_clip.duration + 1.5)) 
                print(f"✅ 高品質音声長: {audio_clip.duration:.1f}秒 -> 動画長: {video_duration:.1f}秒")
            except Exception as e:
                print(f"音声ファイル '{voice_path}' の読み込みエラー: {e}")
                # audio_clip が None のままなので、音声なし動画になるか、エラーになる

            bg_clip = bg_clip.set_duration(video_duration)
            
            # テキスト表示は無効化（元コードの通り）
            txt_clip = None 
            print("ℹ️ テキスト処理は無効化されています。")

            clips_to_compose = [bg_clip]
            # if txt_clip: clips_to_compose.append(txt_clip) # txt_clipがNoneなので実行されない

            video = CompositeVideoClip(clips_to_compose, size=(1080,1920)) # サイズを明示
            if audio_clip:
                video = video.set_audio(audio_clip)
            else: # 音声がない場合はエラーにするか、無音動画を許容するか
                print("⚠️ 音声クリップがありません。無音の動画が生成される可能性があります。")
                # return None # 音声なしはアップロードしない場合

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # スラッシュをアンダースコアに置換してファイル名問題を回避
            safe_content_prefix = content_text[:15].replace('/', '_').replace('\\', '_').replace(':', '_')
            output_filename = f"financial_video_{safe_content_prefix}_{timestamp}.mp4"
            final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)

            # MoviePyの一時オーディオファイル名も指定
            temp_audiofile_path = os.path.join(self.temp_dir, f"temp-audio-{timestamp}.m4a")

            video.write_videofile(
                final_output_path,
                fps=24,
                codec='libx264', # H.264
                audio_codec='aac' if audio_clip else None, # 音声がある場合のみaac
                bitrate='3000k', # ショート動画なので少しビットレートを抑える
                temp_audiofile=temp_audiofile_path,
                remove_temp=True,
                verbose=False, # ログが多すぎるのでFalse
                logger=None, # logger=None でMoviePyの出力を抑制
                threads=2 # GitHub Actionsのコア数に合わせて調整 (通常2コア)
            )
            print(f"✅ 高品質動画生成完了: {final_output_path}")

            # リソース解放
            if audio_clip: audio_clip.close()
            if hasattr(bg_clip, 'close'): bg_clip.close()
            if hasattr(video, 'close'): video.close()
            # CompositeVideoClip内のクリップも解放されるはずだが念のため

            if os.path.exists(resized_bg_path): os.remove(resized_bg_path)
            return final_output_path
        except Exception as e:
            print(f"❌ 動画合成全体でエラー発生: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # MoviePyが稀にロックファイルを残すことがあるので、手動でクリーンアップ試行
            lock_file_path = os.path.join(self.temp_dir, f"temp-audio-{timestamp}.m4a.lock")
            if os.path.exists(lock_file_path):
                try:
                    os.remove(lock_file_path)
                    print(f"🧹 一時ロックファイル削除: {lock_file_path}")
                except Exception as e_lock:
                    print(f"⚠️ 一時ロックファイル削除失敗: {e_lock}")


print("✅ 修正版VideoGeneratorクラス準備完了!")


class YouTubeUploader:
    def __init__(self, credentials_file_path, token_file_path):
        self.credentials_file_path = credentials_file_path # credentials.json
        self.token_file_path = token_file_path           # youtube_token.json
        self.youtube = None
        self.scopes = ['https://www.googleapis.com/auth/youtube.upload']

    def authenticate(self):
        creds = None
        if os.path.exists(self.token_file_path):
            try:
                # トークンファイルから認証情報を読み込む
                # encoding='utf-8' を指定して読み込む
                with open(self.token_file_path, 'r', encoding='utf-8') as token_file:
                    token_info = json.load(token_file)
                creds = Credentials.from_authorized_user_info(token_info, self.scopes)
            except Exception as e:
                print(f"⚠️ トークンファイル '{self.token_file_path}' からの認証情報読み込みに失敗: {e}")
                creds = None
        
        if creds and creds.expired and creds.refresh_token:
            print("⏳ アクセストークンが期限切れです。リフレッシュしています...")
            try:
                creds.refresh(Request())
                # 更新されたトークン情報を保存 (GitHub Actionsでは一時的だが、次回実行が早ければ使える)
                with open(self.token_file_path, 'w', encoding='utf-8') as token_file:
                    token_data = {
                        'token': creds.token, 'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri, 'client_id': creds.client_id,
                        'client_secret': creds.client_secret, 'scopes': creds.scopes
                    }
                    json.dump(token_data, token_file, indent=2)
                print("✅ アクセストークンをリフレッシュしました。")
            except Exception as e:
                print(f"❌ トークンのリフレッシュに失敗: {e}")
                print("   GitHub Secret 'YOUTUBE_TOKEN_JSON' をローカルで再生成して更新してください。")
                return False # リフレッシュ失敗は致命的

        if not creds or not creds.valid:
            print("❌ 有効な認証情報が見つかりません。")
            if not os.path.exists(self.token_file_path):
                 print(f"   トークンファイル '{self.token_file_path}' が存在しません。")
            print(f"   ローカルで初回認証を実行し、生成されたトークン情報を GitHub Secret 'YOUTUBE_TOKEN_JSON' に設定してください。")
            return False

        try:
            self.youtube = googleapiclient.discovery.build('youtube', 'v3', credentials=creds, cache_discovery=False)
            print("✅ YouTube API認証完了!")
            return True
        except Exception as e:
            print(f"❌ YouTube APIクライアントのビルドに失敗: {e}")
            return False

    def upload_video(self, video_path, title, description, tags):
        if not self.youtube:
            print("❌ YouTube APIが認証されていません。アップロードできません。")
            if not self.authenticate(): # 再認証を試みる
                 print("❌ 再認証にも失敗しました。")
                 return None
            # 再認証成功後、再度self.youtubeがセットされていることを期待

        if not os.path.exists(video_path):
            print(f"❌ アップロードする動画ファイルが見つかりません: {video_path}")
            return None

        try:
            body = {
                'snippet': {
                    'title': title, 'description': description, 'tags': tags,
                    'categoryId': '25',  # News & Politics (必要に応じて変更: 27=Education, 28=Science & Technology)
                    'defaultLanguage': 'ja'
                },
                'status': {
                    'privacyStatus': 'public', # 'private' or 'unlisted' for testing
                    'selfDeclaredMadeForKids': False,
                    'madeForKids': False # 明示的にFalse
                }
            }
            media_body = googleapiclient.http.MediaFileUpload(
                video_path, chunksize=-1, resumable=True, mimetype='video/mp4'
            )
            request = self.youtube.videos().insert(
                part='snippet,status', body=body, media_body=media_body
            )
            print(f"📤 動画アップロード中: {video_path} (タイトル: {title})")
            
            # プログレス表示のためのループ (オプション)
            response = None
            retry_count = 0
            max_retries = 3
            while response is None:
                try:
                    status, response = request.next_chunk()
                    if status:
                        print(f"   アップロード進行状況: {int(status.progress() * 100)}%")
                except googleapiclient.errors.HttpError as e:
                    if e.resp.status in [500, 502, 503, 504] and retry_count < max_retries:
                        retry_count += 1
                        sleep_time = (2 ** retry_count) + random.random()
                        print(f"   サーバーエラー ({e.resp.status})。リトライ {retry_count}/{max_retries} ({sleep_time:.1f}秒後)...")
                        time.sleep(sleep_time)
                    else:
                        print(f"   HttpError: {e}")
                        raise # 致命的なエラーとして再送出
                except Exception as e_chunk: # requests.exceptions.ConnectionError など
                    print(f"   Chunk upload error: {e_chunk}")
                    if retry_count < max_retries:
                        retry_count += 1
                        sleep_time = (2 ** retry_count) + random.random()
                        print(f"   リトライ {retry_count}/{max_retries} ({sleep_time:.1f}秒後)...")
                        time.sleep(sleep_time)
                    else:
                         raise

            video_id = response['id']
            video_url = f"https://youtube.com/watch?v={video_id}"
            print(f"✅ アップロード完了!")
            print(f"🎥 動画URL: {video_url}")
            return video_id
        except Exception as e:
            print(f"❌ アップロードエラー: {e}")
            import traceback
            traceback.print_exc()
            return None

print("✅ YouTube投稿システム準備完了!")


class AutoUploadScheduler:
    def __init__(self):
        print("🚀 システム初期化中...")
        self.asset_collector = FreeAssetCollector()
        self.video_generator = VideoGenerator(self.asset_collector)
        # YouTubeUploaderのインスタンスはrun_onceの認証時に作成・保持する
        self.youtube_uploader = None 
        self.content_list = self.video_generator.load_content_list(CONTENT_LIST_PATH)
        if not self.content_list:
            print("❌ コンテンツリストの読み込みに失敗しました。処理を続行できません。")
            # ここで終了処理を入れるか、run_onceでチェックする
        print("✅ システム初期化完了!")

    def create_and_upload_video(self):
        try:
            print("=" * 50)
            print(f"🎬 新しい動画の作成を開始します ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
            print("=" * 50)

            if not self.content_list:
                print("❌ コンテンツリストが空または読み込めませんでした。処理を中止します。")
                return False

            content = self.video_generator.select_unused_content(self.content_list)
            if not content:
                print("❌ ネタの選択に失敗しました。")
                return False

            video_path = self.video_generator.create_short_video(content)
            if not video_path or not os.path.exists(video_path):
                print("❌ 動画生成に失敗しました")
                return False

            title = f"【株式投資の知恵袋】{content[:20]}... #Shorts #{random.choice(['豆知識','学び','格言'])}"
            description = f"""知って得する株式投資の雑学・豆知識をお届けします！
今回のテーマ：{content}

📊 投資のヒントや面白い情報で、あなたの投資ライフをサポート。
スキマ時間でサクッと学べるショート動画です。
チャンネル登録お願いします！

#株式投資 #投資初心者 #資産運用 #副業 #お金の勉強 #投資戦略 #テクニカル分析 #ファンダメンタルズ分析 #NISA #iDeCo #Shorts #マネーリテラシー #経済ニュース解説 #株主優待 #高配当株 #成長株 #テンバガー #投資の科学 #金融リテラシー #ファイナンス豆知識"""
            tags = ['株式投資', '投資', '雑学', 'Shorts', 'マネー', '資産運用', 'ファイナンス', '豆知識', 'お金の勉強', '投資初心者向け']
            tags = list(set(tags)) # 重複削除

            if not self.youtube_uploader:
                print("❌ YouTube Uploaderが初期化されていません。")
                return False

            video_id = self.youtube_uploader.upload_video(video_path, title, description, tags)
            if video_id:
                print("🎉 処理完了!")
                # 生成した動画ファイルを削除
                if os.path.exists(video_path):
                    try:
                        os.remove(video_path)
                        print(f"🗑️ アップロード済み動画ファイル削除: {video_path}")
                    except Exception as e_rm:
                        print(f"⚠️ アップロード済み動画ファイル削除失敗: {e_rm}")
                return True
            else:
                print("❌ アップロードに失敗しました")
                return False
        except Exception as e:
            print(f"❌ create_and_upload_video でエラー発生: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run_once(self):
        print("🚀 GitHub Actions 実行モード (1回実行)")
        
        # YouTube認証
        uploader = YouTubeUploader(CREDENTIALS_PATH, YOUTUBE_TOKEN_JSON_PATH)
        if not uploader.authenticate():
            print("❌ YouTube認証に失敗しました。処理を中止します。")
            return False
        self.youtube_uploader = uploader # 認証成功後にインスタンス変数にセット
        
        return self.create_and_upload_video()

print("✅ 修正版メインシステム統合完了!")


# --- メイン実行部分 ---
if __name__ == "__main__":
    print("=" * 60)
    print(f"🎉 YouTube自動投稿システム (GitHub Actions版) 開始 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # クリーンアップ: 古い一時ファイルがあれば削除 (起動時)
    temp_dir_main = os.path.join(OUTPUT_FOLDER, "temp_files")
    if os.path.exists(temp_dir_main):
        for item in os.listdir(temp_dir_main):
            item_path = os.path.join(temp_dir_main, item)
            try:
                if os.path.isfile(item_path) or os.path.islink(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    import shutil
                    shutil.rmtree(item_path)
            except Exception as e_clean:
                print(f"⚠️ 古い一時ファイル/ディレクトリの削除失敗 ({item_path}): {e_clean}")
    
    scheduler = AutoUploadScheduler()
    success = scheduler.run_once()

    if success:
        print("✅ すべての処理が正常に完了しました。")
        # GitHub Actionsでは正常終了は exit code 0
    else:
        print("❌ 処理中にエラーが発生しました。詳細はログを確認してください。")
        import sys
        sys.exit(1) # GitHub Actions にエラーを伝える