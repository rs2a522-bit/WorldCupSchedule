```python
import json
import requests
from bs4 import BeautifulSoup
import re
import os

# --- 国名・表記ゆれ変換マッパー ---
# ニュースメディアごとの表記ゆれ（例：「パラグアイ共和国」「USA」など）を吸収し、matches.jsonと正確に一致させます。
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
    """不要な空白や改行をクレンジングするヘルパー"""
    return " ".join(text.split())

def scrape_broadcasters_and_commentators():
    json_path = 'matches.json'
    if not os.path.exists(json_path):
        print("Error: matches.json not found.")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        matches = json.load(f)

    # 巡回先メディアリスト（ABEMA TIMES、サンスポ特設、NHK番組表まとめ等）
    # 大会中、最も更新が早く、テレビ解説者を一覧表でまとめる大手サイトを網羅します
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

    scraped_commentaries = {} # キー: (Home, Away) -> 値: 解説実況テキスト

    for src in SOURCES:
        try:
            print(f"🔍 {src['name']} をクローリング中...")
            res = requests.get(src['url'], headers=headers, timeout=15)
            if res.status_code != 200:
                print(f"⚠️ {src['name']} 接続失敗 (Status Code: {res.status_code})")
                continue

            res.encoding = 'utf-8'
            soup = BeautifulSoup(res.text, 'lxml')

            # ページ内のテキスト段落(p)、表の行(tr)、リスト(li)を全走査してパターンをマッチング
            elements = soup.select('.article-body p, table tr, .article-body li, .entry-content p')
            for el in elements:
                text = el.text.strip()
                if not text:
                    continue

                # 「解説」または「実況」または「ナビゲーター」を含む行のみを抽出
                if any(x in text for x in ["解説", "実況", "ゲスト", "ナビゲーター", "出演"]):
                    # 対戦カードパターン（例: 「日本対オランダ」「日本vsスウェーデン」「メキシコ×南アフリカ」等）を検出
                    match_teams = []
                    for raw_name, clean_name in TEAM_MAP.items():
                        if raw_name in text:
                            if clean_name not in match_teams:
                                match_teams.append(clean_name)

                    # 行の中にちょうど2つの国名が検出された場合、それは特定の試合の解説行である可能性が極めて高い
                    if len(match_teams) == 2:
                        team_key = tuple(sorted(match_teams))
                        info_text = clean_text(text)
                        
                        # すでに情報が格納されている場合は、文字数が多い（詳細な）方を優先
                        if team_key not in scraped_commentaries or len(info_text) > len(scraped_commentaries[team_key]):
                            scraped_commentaries[team_key] = info_text
                            print(f"🎯 抽出成功 [{team_key[0]} vs {team_key[1]}]: {info_text[:40]}...")

        except Exception as e:
            print(f"❌ {src['name']} クロールエラー: {e}")

    # --- matches.json へのマッピング処理 ---
    updated_count = 0
    for m in matches:
        home = m.get('home')
        away = m.get('away')
        
        # データベース内の国名で検索
        team_key = tuple(sorted([home, away]))
        
        if team_key in scraped_commentaries:
            new_commentary = scraped_commentaries[team_key]
            
            # デフォルトテキスト、または未確定状態のテキストから更新
            if m.get('commentary') != new_commentary:
                m['commentary'] = new_commentary
                updated_count += 1
                print(f"⚡ [マッピング適用] 試合No.{m['no']} ({home} vs {away}) -> 解説情報を更新しました")

    # 安全な上書き保存（一時ファイル書き込み後にリプレイス）
    if updated_count > 0:
        temp_path = 'matches_temp.json'
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(matches, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, json_path)
            print(f"💾 同期完了: 計 {updated_count} 試合の解説・中継テキストを自動マッピングしました。")
        except Exception as e:
            print(f"❌ 保存時エラー: {e}")
    else:
        print("ℹ️ 新たな解説・実況の更新はありませんでした。既存のデータベースを維持します。")

if __name__ == "__main__":
    scrape_broadcasters_and_commentators()

```
