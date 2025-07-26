from bs4 import BeautifulSoup
import requests

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'  # 確認したユーザーエージェントに置換
}

r = requests.get('https://race.netkeiba.com/race/result.html?race_id=202408060411&rf=race_list', headers=headers)
r.raise_for_status()

soup = BeautifulSoup(r.content, 'lxml')

with open('soup.html', 'w', encoding='utf-8') as f:
    f.write(soup.prettify())