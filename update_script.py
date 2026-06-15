```python
import json
import requests
from bs4 import BeautifulSoup
import re
import os

# --- 国名・表記ゆれ変換マッパー ---
TEAM_MAP = {
    "メキシコ合衆国": "メキシコ", "メキシコ": "メキシコ",
    "南アフリカ共和国": "南アフリカ", "南アフリカ": "南アフリカ",
    "大韓民国": "韓国", "韓国": "韓国",
    "チェコ共和国": "チェコ", "チェコ": "チェコ",
    "ボスニア": "ボスニア・ヘルツェゴビナ", "ボスニアヘルツェゴビナ": "ボスニア・ヘルツェゴビナ", "ボスニア・ヘルツェゴビナ": "ボスニア・ヘルツェゴビナ",
    "カナダ": "カナダ", "カタール": "カタール", "スイス": "スイス",
    "ブラジル": "ブラジル", "モロッコ": "モロッコ", "ハイチ": "ハイチ", "スコットランド": "スコットランド",
    "アメリカ": "アメリカ", "アメリカ合衆国": "アメリカ", "USA": "アメリカ",
    "パラグアイ": "パラグアイ", "オーストラリア": "オーストラリア", "トルコ": "トルコ", "テュルキエ": "トルコ",
    "ドイツ": "ドイツ", "キュラソー": "キュラソー", "コートジボワール": "コートジボワール", "エクアドル": "エクアドル",
    "オランダ": "オランダ", "日本": "日本", "スウェーデン": "スウェーデン", "チュニジア": "チュニジア",
    "ベルギー": "ベルギー", "エジプト": "エジプト", "イラン": "イラン", "ニュージーランド": "ニュージーランド",
    "スペイン": "スペイン", "カーボベルデ": "カーボベルデ", "サウジアラビア": "サウジアラビア", "ウルグアイ": "ウルグアイ",
    "フランス": "フランス", "セネガル": "セネガル", "イラク": "イラク", "ノルウェー": "ノルウェー",
    "アルゼンチン": "アルゼンチン", "アルジェリア": "アルジェリア", "オーストリア": "オーストリア", "ヨルダン": "ヨルダン",
    "ポルトガル": "ポルトガル", "コンゴ民主共和国": "コンゴ民主共和国", "コンゴ": "コンゴ民主共和国", "ウズベキスタン": "ウズベキスタン", "コロンビア": "コロンビア",
    "イングランド": "イングランド", "クロアチア": "クロアチア", "ガーナ": "ガーナ", "パナマ": "パナマ"
}

def clean_text(text):
    return " ".join(text.split())

def scrape_broadcasters_and_commentators():
    json_path = 'matches.json'
    
    # matches.jsonが存在しない、または空の場合の自動修復・防御ロジック
    if not os.path.exists(json_path) or os.path.getsize(json_path) == 0:
        print("⚠️ matches.json が存在しないか空です。初期空データを生成します。")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump([], f)
        
    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            matches = json.load(f)
        except Exception as e:
            print(f"⚠️ JSONの読み込みに失敗しました（データ破損の疑い）: {e}")
            matches = []

    if not matches:
        print("データが空です。処理をスキップします。")
        return

    # 巡回ソース
    SOURCES = [
        {
            "url": "https://times.abema.tv/articles/-/10243707",
            "name": "ABEMA TIMES"
        },
        {
            "url": "https://www.goal.com/jp/%E3%83%AA%E3%82%B9%E3%83%88/2026-world-cup-all-tv-guide/blt70f25e7f12788cd5",
            "name": "Goal.com Japan"
        }
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
    }

    scraped_commentaries = {}

    for src in SOURCES:
        try:
            print(f"🔍 {src['name']} クローリング開始: {src['url']}")
            res = requests.get(src['url'], headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"⚠️ {src['name']} 通信失敗 (ステータス: {res.status_code})")
                continue

            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'lxml')

            elements = soup.select('.article-body p, table tr, .article-body li, .entry-content p')
            for el in elements:
                text = el.text.strip()
                if not text:
                    continue

                if any(x in text for x in ["解説", "実況", "ゲスト", "ナビゲーター", "出演"]):
                    match_teams = []
                    for raw_name, clean_name in TEAM_MAP.items():
                        if raw_name in text:
                            if clean_name not in match_teams:
                                match_teams.append(clean_name)

                    if len(match_teams) == 2:
                        team_key = tuple(sorted(match_teams))
                        info_text = clean_text(text)
                        
                        if team_key not in scraped_commentaries or len(info_text) > len(scraped_commentaries[team_key]):
                            scraped_commentaries[team_key] = info_text
                            print(f"🎯 抽出成功 [{team_key[0]} vs {team_key[1]}]: {info_text[:40]}...")

        except Exception as e:
            print(f"❌ {src['name']} 処理中にエラーが発生しましたが、次のソースに移行します: {e}")

    # データのアップデート適用
    updated_count = 0
    for m in matches:
        home = m.get('home')
        away = m.get('away')
        if not home or not away:
            continue
        
        team_key = tuple(sorted([home, away]))
        
        if team_key in scraped_commentaries:
            new_commentary = scraped_commentaries[team_key]
            if m.get('commentary') != new_commentary:
                m['commentary'] = new_commentary
                updated_count += 1
                print(f"⚡ No.{m['no']} ({home} vs {away}) の解説・実況を更新")

    # 安全なファイル上書き（テンポラリファイルを介したアトミックライト）
    if updated_count > 0:
        temp_path = 'matches_temp.json'
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(matches, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, json_path)
            print(f"💾 同期完了: 計 {updated_count} 試合のデータを更新しました。")
        except Exception as e:
            print(f"❌ ファイル保存失敗: {e}")
    else:
        print("ℹ️ 新しい差分はありませんでした。")

if __name__ == "__main__":
    scrape_broadcasters_and_commentators()

```
