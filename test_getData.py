# JRA（日本中央競馬会）のレース結果をスクレイピングし、CSVファイルとして保存します。
#
# 動作概要:
# 1. netkeiba.comのレース結果ページにアクセスし、指定された期間のレース結果を取得します。
#    - レース結果は年と月を指定して取得（例：2024年1月から3月まで）
#    - サイトへの負荷を考慮し、100件ごとに30分の待機時間を設定
#    - 複数のブラウザタイプを模倣し、自然なアクセスパターンを維持
#
# 2. 取得するデータの種類:
#    - 基本情報: レース名、開催日、開催場所、ラウンド、距離
#    - コンディション: 天候、馬場状態
#    - 出走馬情報: 馬名、騎手名、タイム、人気順、オッズ
#    - 血統情報: 父馬名、母馬名
#
# 3. データの保存形式:
#    - 月ごとにCSVファイルとして保存
#    - 年別のフォルダで管理
#    - ファイル名の形式: YYYY_MM_raceresults.csv
#    - 最後に年間データを統合したファイルも作成
#
# 4. 実行時の注意点:
#    - プログラム実行前にGoogle Chromeのインストールが必要
#    - インターネット接続が必要
#    - 長時間の実行になるため、PCのスリープ設定に注意
#    - サイトの負荷軽減のため、取得間隔を適切に設定
#
# 実行手順:
# 1. 必要なライブラリのインストール:
#    pip install pandas urllib3 requests beautifulsoup4 selenium webdriver_manager filelock tqdm lxml chromedriver_binary
#
# 2. Chromeブラウザのインストール:
#    - 実行環境に合ったGoogle Chromeをインストールしてください
#    - ChromeDriverは webdriver_manager により自動的に管理されます
#
# 3. データ保存用のディレクトリ構造:
#    - プログラムと同じディレクトリに 'data/raceresults' フォルダが自動作成されます
#    - レース結果は年別のフォルダに月ごとのCSVファイルとして保存されます
#
# 4. プログラムの実行:
#    - プログラム末尾の以下のパラメータを必要に応じて変更してください：
#      target_year = 2024      # 取得したい年
#      start_month = 12        # 開始月
#      end_month = 12          # 終了月
#      batch_size = 100        # 一度に処理するURL数
#      wait_minutes = 30       # バッチ処理間の待機時間（分）
#
#    - コマンドラインで以下を実行:
#      python get_raceResults.py
#
# 5. 出力ファイル:
#    - 各月のレース結果: ./data/raceresults/[年]/[年]_[月]_raceresults.csv
#    - 年間統合データ: ./data/raceresults/[年]/[年]_all_raceresults.csv

# ライブラリの読み込み
import pandas as pd
import urllib.parse
import requests
import re
import time
import os
import random
import datetime
from filelock import FileLock, Timeout

from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from bs4 import BeautifulSoup

from selenium.webdriver.chrome.service import Service as ChromeService
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

# プログレスバーを表示するためのライブラリを読み込む
from tqdm import tqdm


def initialize_browser():
    """
    Chromeブラウザを初期化し、browserにインスタンスを設定する。
    ヘッドレスモードでの起動、不要なログ出力を抑制するオプションを追加する。
    :return: browserインスタンス
    :rtype: webdriver.Chrome
    """

    # ロックファイルのパス
    lock_file_path = './data/raceresults/chromedriver_install.lock'

    # FileLockオブジェクトを作成
    lock = FileLock(lock_file_path, timeout=120)    # 120秒のタイムアウトを設定

    try:
        # ロックを取得(ロックファイルが存在しない場合は作成、存在する場合は解放されるのを待つ)
        with lock.acquire():
            # ロックを取得できたら、Chromedriverをインストールする
            chrome_options = webdriver.ChromeOptions()
            # chrome_options.add_argument('--headless')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            browser = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chrome_options)

            return browser
    except Timeout:
        # ロック取得のタイムアウトの場合
        print('ロックの取得に失敗しました。')
        return None


def save_race_results(race_results, race_results_year, race_results_month):
    """
    取得したレース結果をCSVファイルとして保存する。
    引数として与えられたレース結果データフレーム(race_result)を、指定された年(race_results_year)と月(race_results_month)を
    ファイル名に含めてCSVファイルとして保存する。保存先のディレクトリが存在しない場合は、ディレクトリを新規に作成する。
    :param pd.DataFrame race_results: 保存するレース結果のデータフレーム。
    :param int race_results_year: レース結果の年。
    :param str race_results_month: レース結果の月。
    :return: 無し。CSVファイルとしての保存を行う。
    """
    print(race_results_year, '年', race_results_month, '月のレース結果のCSVファイルを作成します。')

    # 基本となるデータディレクトリを作成
    os.makedirs('./data/raceresults', exist_ok=True)

    # 年別のフォルダを作成
    year_dir = f'./data/raceresults/{race_results_year}'
    os.makedirs(year_dir, exist_ok=True)

    # ファイル名と保存パスの設定
    file_name = f'{race_results_year}_{race_results_month}_raceresults.csv'
    file_path = f'{year_dir}/{file_name}'

    # CSVファイルとして保存
    race_results.to_csv(file_path, encoding='shift-jis', header=False, index=False, errors="ignore")


def wait_for_random_time(min, max):
    """
    minとmaxの範囲内でランダムな時間だけ待機する。
    :param int min: 最小待機時間(秒)
    :param int max: 最大待機時間(秒)
    :return: 無し。
    """
    time.sleep(random.uniform(min, max))


def scroll_webpage(browser, pixel):
    """
    Webページを指定されたピクセル分だけ縦方向にスクロールする。
    :param webdriver.Chrome browser: スクロール対象のブラウザオブジェクト。
    :param int pixel: スクロールするピクセル数(正の整数でWebページ下部へ、負の整数でWebページ上部へスクロール)
    :return: 無し。
    """
    # 画面を下にスクロールする
    browser.execute_script(f'window.scrollTo(0, {pixel});')


class RaceResultsScraper:
    def __init__(self, year, start_month, end_month):
        """
        RaceResultsScraperクラスの初期化
        :param int year: レース結果取得の年
        :param int start_month: レース結果取得の開始月
        :param int end_month: レース結果取得の終了月
        """
        # 現在の日付、月、年を取得
        self.current_date = datetime.date.today()
        self.current_year = self.current_date.year
        self.current_month = self.current_date.month

        # プログラムの開始時刻を取得する
        self.start_time = time.time()

        # レース結果取得の年を設定する
        self.target_year = year

        # レース結果取得の始まりと終わりの月を設定する
        self.start_month = start_month
        self.end_month = end_month

    def create_month_range(self, year_to_generate_month_range):
        """
        指定された年における月の範囲を生成する。
        :param int year_to_generate_month_range: 月の範囲を生成する年。
        :return: 月のリスト, 終了月
        :rtype: tuple
        """
        # 入力値の検証
        if year_to_generate_month_range > self.current_year:
            raise ValueError("指定された年が現在の年より未来です")

        if self.start_month > self.end_month:
            raise ValueError("開始月は終了月より後にできません")

        if year_to_generate_month_range == self.current_year:
            # 現在の年の場合、指定された月が現在の月を超えていないかチェック
            if self.end_month > self.current_month:
                raise ValueError("指定された終了月が現在の月より未来です")

        # 月のリストを作成
        month_list = range(self.start_month, self.end_month + 1)
        return month_list, self.end_month

    def generate_year_month_pairs(self, year_to_generate_year_month_pairs):
        """
        指定された年に対して、その年の月のペアを生成する。
        :param int year_to_generate_year_month_pairs: 年と月のペアを生成する年。
        :return: 指定された年とそれに対応する月のペアのリスト。
        :rtype: tuple
        """
        # 月のリストを作成する
        month_list, end_month = self.create_month_range(year_to_generate_year_month_pairs)

        # 年と月のペアを作成する
        year_month_pairs = [(year_to_generate_year_month_pairs, str(month)) for month in month_list]

        return year_month_pairs, end_month

    def collect_race_links(self, browser):
        """
        レース詳細Webページのリンクを集める。
        :param webdriver.Chrome browser: レース結果を集めるためのブラウザオブジェクト。
        :return: レース詳細Webページへのリンクが含まれるリスト
        :rtype: list
        """
        link_list = []  # リンクWebページのURLリスト
        no_click_next = 0  # 0:次のWebページ無し、1:次のWebページ有り
        count_click_next = 0  # 0:検索結果の1ページ目、1以上:検索結果の2ページ目以上

        # count = 0
        while no_click_next == 0:
            # count += 1
            # if count > 1:
            #     browser.quit()
            #     break
            # レース結果のリンクWebページのURLを取得する
            link_list = self.make_race_url_list(browser, link_list)

            # 「次」をクリックし、「次」の有無とクリックした回数を返す
            no_click_next, count_click_next = self.click_next_btn(browser, count_click_next)

        # chromeを閉じる
        browser.quit()

        return link_list

    def fetch_race_results(self, link_list, year, month, batch_size=100, wait_minutes=30):
        """
        与えられたURLのリスト（link_list）を使用して、各レースの詳細結果を取得する。
        batch_sizeごとに待機時間を入れて、サイトへの負荷を抑制する。
        取得した結果はDataFrameに結合され、最終的にこの結合されたDataFrameが戻り値として返される。
        ただし、日本国外のレース（URLにアルファベットが含まれているもの）は無視される。

        :param list link_list: レース結果の詳細WebページへのURLを含むリスト。
        :param int year: 取得対象の年。
        :param str month: 取得対象の月。
        :param int batch_size: 一度に処理するURL数。デフォルトは100。
        :param int wait_minutes: バッチ間の待機時間（分）。デフォルトは30。
        :return: 取得したレース結果のDataFrame。各レースの詳細情報を含む。
        :rtype: pd.DataFrame
        """
        # レース結果を保存するデータフレームを用意する
        race_results = pd.DataFrame()

        print('年:', year, '月:', month, 'のレース結果の詳細を取得します')

        # URLをbatch_sizeごとのバッチに分割
        for i in range(0, len(link_list), batch_size):
            # 現在のバッチのURLを取得
            batch_urls = link_list[i:i + batch_size]

            print(
                f'{year}年{month}月 URLバッチ {i // batch_size + 1}/{(len(link_list) + batch_size - 1) // batch_size} の処理を開始します')

            # バッチ内のURLを処理
            for url in tqdm(batch_urls):
                if url.split('/')[-2].isdecimal():
                    detail_race_results = self.get_detail_race_results(url)
                    if isinstance(detail_race_results, str):
                        print('年:', year, '月:', month, 'のレース情報の取得に失敗しました:', url)
                    else:
                        race_results = pd.concat([race_results, detail_race_results], axis=0)

            # バッチ処理完了後、次のバッチまでの待機（最後のバッチを除く）
            if i + batch_size < len(link_list):
                next_batch_time = datetime.datetime.now() + datetime.timedelta(minutes=wait_minutes)
                print(f'\n情報取得先の負荷軽減のため{wait_minutes}分間待機します...')
                print(f'次回の取得開始時刻: {next_batch_time.strftime("%Y-%m-%d %H:%M:%S")}')
                time.sleep(wait_minutes * 60)

        return race_results

    def scrape_race_details(self, year, month):
        """
        指定された年と月のレース詳細情報をスクレイピングする。
        netkeiba.comから指定された年と月のレース結果の詳細情報を取得し、CSVファイルとして保存する。
        レース結果のリンクWebページにアクセスし、日本のレース結果のみを取得する。
        :param int year: スクレイピングするレースの年。
        :param str month: スクレイピングするレースの月
        :return: None 処理を正常に完了するとNoneを返す。
        """
        # chromeを起動する
        browser = initialize_browser()

        # 競馬データベースを開く
        browser.get('https://db.netkeiba.com/?pid=race_search_detail')
        browser.implicitly_wait(10)  # 指定した要素が見つかるまでの待ち時間を10秒と設定する

        print(f'{year}年{month}月の情報取得')
        self.search_race(browser, year, month)  # 検索条件を設定して検索する

        # レース詳細Webページのリンクを集める
        link_list = self.collect_race_links(browser)

        # レース結果のリンクWebページにアクセスして、レース結果を取得する
        race_results = self.fetch_race_results(link_list, year, month)

        # CSVにレース結果を保存する
        save_race_results(race_results, year, month)

    def search_race(self, browser, year, month):
        """
        指定された年と月に基づいてレースの検索を行う。
        netkeiba.comのレース検索Webページにアクセスし、与えられた年(year)と月(month)に該当するレース情報を検索する。
        検索条件を設定し、検索結果のWebページへ遷移する処理を担当する。
        :param webdriver.Chrome browser: 検索を行うためのブラウザオブジェクト。
        :param int year: 検索するレースの年。
        :param str month: 検索するレースの月。
        :return: 無し。
        """
        wait_for_random_time(2, 5)
        self.set_race_conditions(browser)
        self.set_search_period(browser, str(year), str(month))
        scroll_webpage(browser, 400)
        self.set_display_options(browser, str(100))
        self.submit_search(browser)

    def set_race_conditions(self, browser):
        """
        netkeiba.comのレース検索条件の競争種別で「芝」と「ダート」にチェックを入れる。
        :param webdriver.Chrome browser: 検索を行うためのブラウザオブジェクト。
        :return: 無し。
        """
        # 競争種別で「芝」と「ダート」にチェックを入れる
        elem_check_track_1 = browser.find_element(By.ID, value='check_track_1')
        elem_check_track_2 = browser.find_element(By.ID, value='check_track_2')

        elem_check_track_1.click()
        elem_check_track_2.click()

    def set_search_period(self, browser, year, month):
        """
        netkeiba.comのレース検索条件の期間で「年」と「月」にyearとmonthで指定した値を入れる。
        :param webdriver.Chrome browser: 検索を行うためのブラウザオブジェクト。
        :param str year: 検索するレースの年。
        :param str month: 検索するレースの月。
        :return: 無し。
        """
        # 期間を設定する
        elem_start_year = browser.find_element(By.NAME, value='start_year')
        elem_start_year_select = Select(elem_start_year)
        elem_start_year_select.select_by_value(year)

        # 月を指定する場合は、select_by_valueで月数を指定する
        elem_start_month = browser.find_element(By.NAME, value='start_mon')
        elem_start_month_select = Select(elem_start_month)
        elem_start_month_select.select_by_value(month)

        elem_end_year = browser.find_element(By.NAME, value='end_year')
        elem_end_year_select = Select(elem_end_year)
        elem_end_year_select.select_by_value(year)

        # 月を指定する場合は、select_by_valueで月数を指定する
        elem_end_month = browser.find_element(By.NAME, value='end_mon')
        elem_end_month_select = Select(elem_end_month)
        elem_end_month_select.select_by_value(month)

    def set_display_options(self, browser, num):
        """
        netkeiba.comのレース検索条件の表示件数にnumで指定した値を入れる。
        指定できる値は、20、50、100。
        :param webdriver.Chrome browser: 検索を行うためのブラウザオブジェクト。
        :param str num: 表示する項目の数。
        :return: 無し。
        """
        elem_list = browser.find_element(By.NAME, value='list')
        elem_list_select = Select(elem_list)
        elem_list_select.select_by_value(num)

    def submit_search(self, browser):
        """
        netkeiba.comのレース検索条件で検索をクリックする。
        :param webdriver.Chrome browser: 検索を行うためのブラウザオブジェクト。
        :return: 無し。
        """
        elem_search = browser.find_element(By.CLASS_NAME, value='search_detail_submit')
        wait_for_random_time(2, 5)
        elem_search.submit()

    def make_race_url_list(self, browser, link_list):
        """
        取得したHTMLからレース結果のURLを抽出し、URLリストを作成する。
        :param webdriver.Chrome browser: HTMLを取得するためのブラウザオブジェクト。
        :param list link_list: 収集したレース結果のリンクのURLリスト
        :return: 更新されたリンクのURLリスト
        :rtype: list
        """
        html_content = self.get_page_html(browser)
        soup = BeautifulSoup(html_content, 'html.parser')

        try:
            table_data = soup.find(class_='nk_tb_common')
            if not table_data:
                raise ValueError("テーブルデータが見つかりません")

            for link in table_data.find_all('a'):
                href = link.get('href')
                if self.is_race_link(href):
                    absolute_url = self.get_absolute_url(href)
                    link_list.append(absolute_url)

            return link_list

        except Exception as e:
            print(f"エラーが発生しました: {e}")
            return []

    def get_page_html(self, browser):
        """
        WebページのHTMLを取得する。
        :param webdriver.Chrome browser: HTMLを取得するためのブラウザオブジェクト。
        :return: 取得したページのHTMLコンテンツ
        :rtype: str
        """
        return browser.page_source.encode('utf-8')

    def get_absolute_url(self, relative_url):
        """
        相対URLから絶対URLを生成する。
        スクレイピング中に取得される相対URL(例: '/race/202010010811/')を
        完全なURL形式(例: 'https://db.netkeiba.com/race/202010010811/')に変換するために使用する。
        :param str relative_url: 変換する相対URL。
        :return: 生成された絶対URL。
        :rtype: str
        """
        return urllib.parse.urljoin('https://db.netkeiba.com', relative_url)

    def is_race_link(self, url):
        """
        与えられたURLがレース結果のリンクであるかどうかを判断する。
        スクレイピング中に取得されるURLがレース詳細のWebページに関連するものか、
        それとも他のWebページ(例: 馬や騎手のプロフィールWebページ)に関連するものかを識別するために使用される。

        URLに特定のキーワード(例:「horse」や「jockey」など)が含まれていないことを確認し、
        さらにURLがJavaScriptリンク（javascriptを含む）でないことも確認する。
        このチェックを通過したURLは、レース結果に関連するリンクとして扱われる。
        :param str url: 判定するURL。
        :return: URLがレース結果のリンクであればTrue、そうでなければFalse
        :rtype: bool
        """
        if 'javascript' in url:
            return False

        excluded_words = ['horse', 'jockey', 'result', 'sum', 'list', 'movie']
        return not any(word in url for word in excluded_words)

    def click_next_btn(self, browser, count_click_next):
        """
        画面下にスクロールして「次」をクリックする。
        :param webdriver.Chrome browser: 「次」をクリックするためのブラウザオブジェクト。
        :param int count_click_next: 「次へ」をクリックした回数をカウントする。
        :return: 次のWebページが存在しない場合は1、存在する場合は0と、次のWebページに遷移した後の「次へ」ボタンのクリック回数をtupleで返す。
        :rtype: tuple
        """
        # 画面を下にスクロールする
        wait_for_random_time(1, 3)
        scroll_webpage(browser, 2500)
        wait_for_random_time(1, 3)

        # 次をクリックする
        # 検索1Webページ目のxpathは2Webページ以降とは異なるため、count_click_nextで検索1Webページ目なのかを判定している
        if count_click_next == 0:
            xpath = '//*[@id="contents_liquid"]/div[2]/ul[1]/li[14]/a/span/span'
            elem_search = browser.find_element(By.XPATH, value=xpath)
            elem_search.click()
            no_click_next = 0
        else:
            # 検索最後のWebページで次をクリックしようとすると例外処理が発生する
            # exceptで例外処理を取得し、no_click_nextに1を代入する
            try:
                xpath = '//*[@id="contents_liquid"]/div[2]/ul[1]/li[14]/a/span/span'
                elem_search = browser.find_element(By.XPATH, value=xpath)
                wait_for_random_time(2, 5)
                elem_search.click()
                no_click_next = 0
            except:
                print('次のWebページ無し')
                no_click_next = 1

        count_click_next += 1  # Webページ数を判別するためのフラグに1を加算する

        return no_click_next, count_click_next

    def get_race_page_html(self, url):
        """
        指定されたURLのWebページからHTMLを取得する。
        :param str url: HTMLを取得するWebページのURL。
        :return: WebページのHTML。
        :rtype: BeautifulSoup or None
        """
        # 指定したURLからデータを取得する
        res = self.retry_request(url, max_retries=5, retry_delay=5)
        if not res:
            print("リクエスト失敗:", url)
            return None

        soup = BeautifulSoup(res.content, 'lxml')  # content形式で取得したデータをlxml形式で分割する

        return soup

    def prepare_dataframe_to_save_race_results(self, soup):
        """
        スクレイピングしたHTMLからレース結果をデータフレームに整形する。
        :param BeautifulSoup soup: レース結果のWebページのHTMLコンテンツを解析したBeautifulSoupオブジェクト。
        :return: レース結果が整形されたデータフレーム。
        :rtype: pd.DataFrame
        """
        # tableデータを抽出する
        tables = soup.find('table', attrs={'class': 'race_table_01'})
        tables = tables.find_all('tr')

        # レース情報/結果を取得する
        race_results = pd.DataFrame()

        for table in tables[1:]:
            race_results_row = table.text.split('\n')
            race_results_row = pd.Series(race_results_row)
            race_results = pd.concat([race_results, race_results_row], axis=1)

        # 学習に必要な情報のみを抽出する
        # 着順:要素No.1、馬名:要素No.5、性齢:要素No.7、斤量:要素No.8、騎手:要素No.10、
        # タイム:要素No.12、上り:要素No.21、単勝:要素No.23、人気:要素No.24、馬体重:要素No.25の情報を抽出する
        race_results_extracted_columns = pd.DataFrame()

        # レース結果のテーブルが異なることがあるので、必要なカラム列の番号をそれぞれで用意する
        columns_list1 = [1, 5, 7, 8, 10, 12, 21, 23, 24, 25]
        columns_list2 = [1, 5, 7, 8, 10, 12, 18, 20, 21, 22]

        # テーブルの状態次第で必要なカラム列の番号を変える
        # 17列は「通過」の情報が記録されているが、テーブルによって'**'となっている場合となっていない場合の2種類のテーブルが存在している
        # 17列が'**'となっている場合は、カラム列はcolumns_list1を使用する
        speed_index = race_results.iloc[17]
        if speed_index.values[0] == '**':
            for i in columns_list1:
                extracted_columns = race_results.iloc[i]
                race_results_extracted_columns = pd.concat([race_results_extracted_columns,
                                                            extracted_columns], axis=1)
        else:
            for i in columns_list2:
                extracted_columns = race_results.iloc[i]
                race_results_extracted_columns = pd.concat([race_results_extracted_columns,
                                                            extracted_columns], axis=1)

        # カラム名を設定する
        columns_list = ['着順', '馬名', '性齢', '斤量', '騎手', 'タイム', '上り', '単勝', '人気', '馬体重']
        columns = pd.Series(columns_list)
        race_results_extracted_columns.columns = columns  # index名を設定する

        return race_results_extracted_columns

    def format_race_results_table(self, race_results_extracted_columns, soup):
        """
        スクレイピングしたHTMLから取得したレース結果データを整形し、保存用のデータフレームを作成する。
        抽出されたレース結果データ（pandas.DataFrame）と、レース情報が含まれるBeautifulSoupオブジェクトを受け取り、
        必要な追加情報（距離、天候、馬場状態など）をデータフレームに組み込んで最終的な形式を整える。
        :param pd.DataFrame race_results_extracted_columns: 抽出されたレース結果のデータフレーム
        :param BeautifulSoup soup: レースWebページのHTMLコンテンツを解析したBeautifulSoupオブジェクト
        :return: 整形されたレース結果のデータフレーム
        :rtype: pd.DataFrame
        """
        # 整形したレース情報を保存するデータフレームを用意する
        formatted_race_results = pd.DataFrame()

        try:
            male_horse_pedigree_list, female_horse_pedigree_list = self.get_horse_parents_name(soup)
            # 距離、天候、馬場、状態、開催日、レース名、開催場所、ラウンド、父親、母親の列を追加する
            race_results_extracted_columns['距離'] = self.get_race_distance(soup)
            race_results_extracted_columns['天候'] = self.get_race_weather(soup)[1]
            race_results_extracted_columns['馬場'] = self.get_race_condition(soup)[0]
            race_results_extracted_columns['状態'] = self.get_race_condition(soup)[1]
            race_results_extracted_columns['開催日'] = self.get_race_date(soup)
            race_results_extracted_columns['レース名'] = self.get_race_name(soup)
            race_results_extracted_columns['開催場所'] = self.get_race_place(soup)
            race_results_extracted_columns['ラウンド'] = self.get_race_round(soup)
            race_results_extracted_columns['父親'] = male_horse_pedigree_list
            race_results_extracted_columns['母親'] = female_horse_pedigree_list

            # 説明変数として使用しない列を削除する
            race_results_extracted_columns.drop(['着順', '上り'], axis=1, inplace=True)

            # 目的変数にするタイムを1列に変更する
            formatted_race_results = race_results_extracted_columns.reindex(columns=['タイム', '馬名', '父親', '母親',
                                                                                     '性齢', '斤量', '騎手', '単勝',
                                                                                     '人気', '馬体重', '距離', '天候',
                                                                                     '馬場', '状態', '開催日',
                                                                                     'レース名',
                                                                                     '開催場所', 'ラウンド'])
        except:
            print('レース情報を取得できませんでした')

        return formatted_race_results

    def get_detail_race_results(self, url):
        """
        指定されたURLからレースの詳細結果を取得し、整形されたデータフレームを返す。
        レース詳細のWebページのURLを受け取り、そのWebページからレース結果のデータをスクレイピングする。
        スクレイピングされたデータはまず `prepare_dataframe_to_save_race_results`によって整形され、
        その後 `format_race_results_table`でさらに詳細な情報が追加される。
        最終的に整形されたデータフレームが戻り値として返される。
        :param str url: レースの詳細WebページのURL。
        :return: 整形されたレース結果のデータフレーム。
        :rtype: pd.DataFrame
        """
        # 指定したurlのWebページからHTMLを取得する
        soup = self.get_race_page_html(url)

        # スクレイピングしたHTMLからレース結果をデータフレームに整形する
        race_results_extracted_columns = self.prepare_dataframe_to_save_race_results(soup)

        # スクレイピングしたHTMLから取得したレース結果データを整形し、保存用のデータフレームを作成する。
        formatted_race_results_table = self.format_race_results_table(race_results_extracted_columns, soup)

        return formatted_race_results_table

    def get_horse_parents_name(self, soup):
        """
        出走馬の血統情報（父馬と母馬の名前）を取得する。
        BeautifulSoupオブジェクトとして渡されたHTMLから、出走馬の血統情報を抽出するために使用する。
        各出走馬の詳細ページへのリンクをたどり、それぞれの馬の父馬と母馬の名前を取得してリストに格納する。
        :param BeautifulSoup soup:レース情報のHTMLを解析したBeautifulSoupオブジェクト
        :return: 各出走馬の父馬と母馬の名前のリストを含むタプル（(父馬のリスト, 母馬のリスト)）
        :rtype: tuple
        """
        race_table_data = soup.find(class_='race_table_01 nk_tb_common')  # 検索結果のテーブルを取得する
        male_horse_pedigree_list = []  # 各出走馬の父親の名前を保持するリスト
        female_horse_pedigree_list = []  # 各出走馬の母親の名前を保持するリスト

        link_url = self.get_horse_links(race_table_data)
        for link in link_url:
            soup_blood_table = self.get_race_page_html(link)
            male_horse_pedigree_list.append(self.get_horse_father_name(soup_blood_table))
            female_horse_pedigree_list.append(self.get_horse_mother_name(soup_blood_table))

        return male_horse_pedigree_list, female_horse_pedigree_list

    def get_horse_links(self, race_table_data):
        """
        レースの結果テーブルから出走馬の詳細Webページへのリンクを取得する。
        :param BeautifulSoup race_table_data: レース結果テーブルのHTMLコンテンツを解析したBeautifulSoupオブジェクト。
        :return: 出走馬の詳細Webページへのリンクのリスト。
        :rtype: list
        """
        link_url = []
        href_list = race_table_data.find_all('a')
        for href_link in href_list:
            if '/horse/' in href_link.get('href'):
                # 出走馬情報のリンクWebページを作成する
                link_url.append(self.get_absolute_url(href_link.get('href')))

        return link_url

    def get_horse_father_name(self, soup_blood_table):
        """
        BeautifulSoupオブジェクトから馬の父親の名前を取得する。
        :param BeautifulSoup soup_blood_table: 血統情報を含むHTMLテーブルのBeautifulSoupオブジェクト
        :return: 馬の父親の名前。
        :rtype: str or None
        """
        try:
            blood_table = soup_blood_table.find('table', class_='blood_table')
            if not blood_table:
                print('血統テーブルが見つかりません。')
                return None

            father_row = blood_table.find_all('tr')[0]  # インデックス0が1行目（父親の行）
            father_cell = father_row.find('td', class_='b_ml')

            if not father_cell:
                print('父親の名前の要素が見つかりません。')
                return None

            father_link = father_cell.find('a')
            if father_link:
                return father_link.text.replace('\n', '')
            else:
                return father_cell.text.replace('\n', '')

        except Exception as e:
            print(f'父親の名前の取得中にエラーが発生しました: {e}')
            return None

    def get_horse_mother_name(self, soup_blood_table):
        """
        BeautifulSoupオブジェクトから馬の母親の名前を取得する。
        :param BeautifulSoup soup_blood_table: 血統情報を含むHTMLテーブルのBeautifulSoupオブジェクト
        :return: 馬の母親の名前。
        :rtype: str or None
        """
        try:
            # 血統テーブルを特定
            blood_table = soup_blood_table.find('table', class_='blood_table')
            if not blood_table:
                print('血統テーブルが見つかりません。')
                return None

            # 血統テーブルの3行目（母親の行）を特定し、最初のセルにある b_fml クラスの要素を取得
            # これが直接の母親を指す要素になります
            mother_row = blood_table.find_all('tr')[2]  # インデックス2が3行目
            mother_cell = mother_row.find('td', class_='b_fml')

            if not mother_cell:
                print('母親の名前の要素が見つかりません。')
                return None

            # リンク内のテキストを取得（リンクがない場合はそのままテキスト）
            mother_link = mother_cell.find('a')
            if mother_link:
                return mother_link.text.replace('\n', '')
            else:
                return mother_cell.text.replace('\n', '')

        except Exception as e:
            print(f'母親の名前の取得中にエラーが発生しました: {e}')
            return None

    def retry_request(self, url, max_retries=3, retry_delay=1):
        """
        指定されたURLに対してリクエストを行い、必要に応じてリトライを実行する。
        :param str url: リクエストを送信するURL。
        :param int max_retries: リクエストの最大リトライ回数。デフォルトは3回。
        :param int retry_delay: リトライの間隔(秒)。デフォルトは1秒。
        :return: 成功した場合はリクエストのレスポンス、失敗した場合はNoneを返す。
        :rtype: requests.Response or None
        """

        user_agent = [
            # Chrome (Windows & Mac)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",

            # Firefox (Windows & Mac)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",

            # Safari (Mac)
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",

            # Microsoft Edge (Windows & Mac)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",

            # Opera (Windows & Mac)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 OPR/107.0.0.0",

            # Brave (Windows & Mac)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Brave/1.51.110",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Brave/1.51.110"
        ]

        # ブラウザのUser-Agentを設定
        headers = {
            "User-Agent": random.choice(user_agent),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

        retries = 0
        while retries < max_retries:
            try:
                res = requests.get(url, headers=headers)
                return res
            except requests.exceptions.RequestException:
                # リクエストエラーが発生した場合はリトライする
                retries += 1
                time.sleep(retry_delay)
        return None

    def get_race_name(self, soup):
        """
        指定されたBeautifulSoupオブジェクトからレース名を取得する。
        :param BeautifulSoup soup: レース情報が含まれているWebページのHTMLコンテンツを解析したBeautifulSoupオブジェクト。
        :return: レース名を文字列で返す。レース名が見つからない場合は空文字を返す。
        :rtype: str
        """
        race_name = soup.find_all('h1')
        race_name = race_name[1].text

        return race_name

    def get_race_round(self, soup):
        """
        指定されたBeautifulSoupオブジェクトからレースのラウンド数を取得する。
        :param BeautifulSoup soup: レース情報が含まれているWebページのHTMLコンテンツを解析したBeautifulSoupオブジェクト。
        :return: レースのラウンド数を文字列で返す。ラウンド数が見つからない場合は空文字を返す。
        :rtype: str
        """
        race_round = soup.find('dl', attrs={'class': 'racedata fc'})
        race_round = race_round.find_all('dt')
        race_round = race_round[0].text
        race_round = race_round.replace('\n', '')

        return race_round

    def get_race_date(self, soup):
        """
        指定されたBeautifulSoupオブジェクトからレースの開催日を取得する。
        :param BeautifulSoup soup: レース情報が含まれているWebページのHTMLコンテンツを解析したBeautifulSoupオブジェクト。
        :return: レースの開催日を文字列で返す。開催日が見つからない場合は空文字を返す。
        :rtype: str
        """
        # 開催日を取得する
        race_base_info = soup.find('p', attrs={'class': 'smalltxt'})
        rase_base_info_text = race_base_info.text.replace(u'\xa0', u' ')
        words = rase_base_info_text.split(' ')
        race_date = words[0]

        return race_date

    def get_race_place(self, soup):
        """
        指定されたBeautifulSoupオブジェクトからレースの開催場所を取得する。
        :param BeautifulSoup soup: レース情報が含まれているWebページのHTMLコンテンツを解析したBeautifulSoupオブジェクト。
        :return: レースの開催場所を文字列で返す。開催場所が見つからない場合は空文字を返す。
        :rtype: str
        """
        race_base_info = soup.find('p', attrs={'class': 'smalltxt'})
        rase_base_info_text = race_base_info.text.replace(u'\xa0', u' ')
        words = rase_base_info_text.split(' ')
        race_place = words[1]

        return race_place

    def get_race_distance(self, soup):
        """
        指定されたBeautifulSoupオブジェクトからレースの距離を取得する。
        :param BeautifulSoup soup: レース情報が含まれているWebページのHTMLコンテンツを解析したBeautifulSoupオブジェクト。
        :return: レースの距離を整数値で返す。距離が見つからない場合はNoneを返す。
        :rtype: int or None
        """
        race_info = soup.find('diary_snap_cut')
        race_info_text = race_info.text.replace(u'\xa0', u' ')  # ノーブレークスペースを削除
        race_info_text = race_info.text.replace(u'\xa5', u' ')  # Webページの文字参照を削除
        words = race_info_text.split('/')

        words[0] = re.sub(r'2周', '', words[0])  # レース情報の'2周'を空文字に置き換える
        race_distance = int(re.sub(r'\D', '', words[0]))  # レース距離だけを取り出してint型で保存する

        return race_distance

    def get_race_weather(self, soup):
        """
        指定されたBeautifulSoupオブジェクトからレースの開催時の天候を取得する。
        :param BeautifulSoup soup: レース情報が含まれているWebページのHTMLコンテンツを解析したBeautifulSoupオブジェクト。
        :return: レースの開催時の天候を文字列で返す。天候が見つからない場合は空文字を返す。
        :rtype: str
        """
        race_info = soup.find('diary_snap_cut')
        race_info_text = race_info.text.replace(u'\xa0', u' ')  # ノーブレークスペースを削除
        race_info_text = race_info.text.replace(u'\xa5', u' ')  # Webページの文字参照を削除
        words = race_info_text.split('/')
        race_weather = words[1].split(':')

        return race_weather

    def get_race_condition(self, soup):
        """
        指定されたBeautifulSoupオブジェクトからレースの開催時の馬場状態を取得する。
        :param BeautifulSoup soup: レース情報が含まれているWebページのHTMLコンテンツを解析したBeautifulSoupオブジェクト。
        :return: レースの開催時の馬場状態を文字列で返す。馬場状態が見つからない場合は空文字を返す。
        :rtype: str
        """
        race_info = soup.find('diary_snap_cut')
        race_info_text = race_info.text.replace(u'\xa0', u' ')  # ノーブレークスペースを削除
        race_info_text = race_info.text.replace(u'\xa5', u' ')  # Webページの文字参照を削除
        words = race_info_text.split('/')
        race_condition = words[2].split(':')

        return race_condition

    def combine_race_result(self, year, race_results_path):
        """
        指定された年のフォルダ内に存在する全ての月別レース結果のCSVファイルを結合する。
        月ごとのCSVファイルは保持したまま、月の降順で結合したファイルを作成する。
        :param int year: 結合するレース結果の年。
        :param str race_results_path: レース結果のCSVファイルが保存されているパス。
        :return: 結合されたレース結果のデータフレーム。
        :rtype: pandas.DataFrame
        """
        # 取得したレース結果を結合するためのデータフレーム
        combined_data = pd.DataFrame()

        # 年別フォルダのパス
        year_dir = f"{race_results_path}{year}"

        # CSVファイルの一覧を取得
        if os.path.exists(year_dir):
            # フォルダ内の月別CSVファイルのみを取得（_all_raceresults.csvを除外）
            csv_files = [f for f in os.listdir(year_dir)
                         if f.endswith('_raceresults.csv') and not f.endswith('all_raceresults.csv')]

            # ファイル名から月を抽出してソート（例: "2024_3_raceresults.csv" → 3）
            def extract_month(filename):
                try:
                    return int(filename.split('_')[1])
                except (IndexError, ValueError):
                    return 0

            csv_files.sort(key=extract_month, reverse=True)

            # 各ファイルを読み込んで結合
            for csv_file in csv_files:
                file_path = os.path.join(year_dir, csv_file)
                try:
                    # CSVファイルを読み込む
                    df_read_csv = pd.read_csv(
                        file_path,
                        header=None,
                        encoding='shift-jis',
                        names=['タイム', '馬名', '父親', '母親', '性齢', '斤量', '騎手',
                               '単勝', '人気', '馬体重', '距離', '天候', '馬場', '状態',
                               '開催日', 'レース名', '開催場所', 'ラウンド']
                    )
                    combined_data = pd.concat([combined_data, df_read_csv], ignore_index=True)
                    month = csv_file.split('_')[1]
                    print(f'{year}年{month}月のデータを結合しました')
                except Exception as e:
                    print(f'ファイル {file_path} の読み込み中にエラーが発生しました: {str(e)}')
                    continue

        return combined_data


if __name__ == "__main__":
    # 取得したいレース結果の年と月の範囲を指定
    target_year = 2024
    start_month = 12
    end_month = 12

    # バッチサイズと待機時間の設定
    batch_size = 100  # 一度に処理するURL数
    wait_minutes = 30  # 待機時間（分）

    # RaceResultsScraperクラスのインスタンスを作成する
    scraper = RaceResultsScraper(target_year, start_month, end_month)

    year_month_pairs_result = scraper.generate_year_month_pairs(target_year)

    # 戻り値がNoneでないことを確認
    if year_month_pairs_result is None:
        print(f"年月のペアを生成できませんでした: {target_year}")
    else:
        year_month_pairs, end_month = year_month_pairs_result
        total_months = len(year_month_pairs)

        # 開始時刻を記録
        start_time = time.time()
        print(f"処理開始時刻: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 各月のデータを逐次的に取得
        for i, (year, month) in enumerate(year_month_pairs):
            month_start_time = time.time()

            # 現在の月のデータを取得（batch_sizeとwait_minutesを指定）
            print(f"\n{year}年{month}月のデータ取得を開始します ({i + 1}/{total_months}月目)")
            scraper.scrape_race_details(year, month)

            # 1月あたりの処理時間を計算
            month_process_time = time.time() - month_start_time

            # 残りの処理時間を予測
            remaining_months = total_months - (i + 1)
            if i == 0:
                estimated_total_time = month_process_time * total_months + (wait_minutes * 60 * (total_months - 1))
                estimated_end_time = datetime.datetime.now() + datetime.timedelta(seconds=estimated_total_time)
                print(f"\n予想終了時刻: {estimated_end_time.strftime('%Y-%m-%d %H:%M:%S')}")

            # 最後の月でなければ待ち時間を設ける
            if i < len(year_month_pairs) - 1:
                next_month_time = datetime.datetime.now() + datetime.timedelta(minutes=wait_minutes)
                print(f'\n情報取得先の負荷軽減のため{wait_minutes}分間待機します...')
                print(f'次の月の取得開始時刻: {next_month_time.strftime("%Y-%m-%d %H:%M:%S")}')

                # 更新された予想終了時刻を表示
                remaining_time = (month_process_time * remaining_months) + (wait_minutes * 60 * (remaining_months - 1))
                updated_end_time = datetime.datetime.now() + datetime.timedelta(seconds=remaining_time)
                print(f'更新された予想終了時刻: {updated_end_time.strftime("%Y-%m-%d %H:%M:%S")}')

                time.sleep(wait_minutes * 60)

        # 取得したレース結果のパス
        race_results_path = './data/raceresults/'
        year_dir = f'{race_results_path}{target_year}'

        print("\nレース結果の結合処理を開始します...")
        # 取得した全ての月のレース結果を結合する
        combined_data = scraper.combine_race_result(target_year, race_results_path)

        # 結合したデータを年別フォルダ内に保存する
        if not combined_data.empty:
            csv_combined_data_path = f'{year_dir}/{target_year}_all_raceresults.csv'
            os.makedirs(os.path.dirname(csv_combined_data_path), exist_ok=True)
            combined_data.to_csv(csv_combined_data_path, encoding='shift-jis', header=False, index=False,
                                 errors='ignore')
            print(f'レース結果を結合し、{csv_combined_data_path}に保存しました。')
        else:
            print('結合するレース結果が存在しませんでした。')

        # プログラムの実行時間を表示する
        run_time = time.time() - start_time
        print(f'\n処理開始時刻: {datetime.datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'処理終了時刻: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        print('実行時間: {:.2f}秒 ({:.2f}分)'.format(run_time, run_time / 60))