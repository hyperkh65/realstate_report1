import streamlit as st
import pandas as pd
from io import BytesIO
import requests
import json
from bs4 import BeautifulSoup
import matplotlib.pyplot as plt
import seaborn as sns

# JSON 파일에서 법정동 코드 가져오기
def get_dong_codes_for_city(city_name, sigungu_name=None, json_path='district.json'):
    try:
        with open(json_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except FileNotFoundError:
        st.error(f"Error: The file at {json_path} was not found.")
        return None, None

    for si_do in data:
        if si_do['si_do_name'] == city_name:
            if sigungu_name and sigungu_name != '전체':
                for sigungu in si_do['sigungu']:
                    if sigungu['sigungu_name'] == sigungu_name:
                        return [sigungu['sigungu_code']], [
                            {'code': dong['code'], 'name': dong['name']} for dong in sigungu['eup_myeon_dong']
                        ]
            else:
                sigungu_codes = [sigungu['sigungu_code'] for sigungu in si_do['sigungu']]
                dong_codes = [
                    {'code': dong['code'], 'name': dong['name']}
                    for sigungu in si_do['sigungu']
                    for dong in sigungu['eup_myeon_dong']
                ]
                return sigungu_codes, dong_codes
    return None, None

# 아파트 코드 리스트 가져오기
def get_apt_list(dong_code):
    down_url = f'https://new.land.naver.com/api/regions/complexes?cortarNo={dong_code}&realEstateType=APT&order='
    header = {
        "Accept-Encoding": "gzip",
        "Host": "new.land.naver.com",
        "Referer": "https://new.land.naver.com/complexes/102378",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        r = requests.get(down_url, headers=header)
        r.encoding = "utf-8-sig"
        data = r.json()

        if 'complexList' in data and isinstance(data['complexList'], list):
            df = pd.DataFrame(data['complexList'])
            required_columns = ['complexNo', 'complexName', 'buildYear', 'totalHouseholdCount', 'areaSize', 'price', 'address', 'floor']

            for col in required_columns:
                if col not in df.columns:
                    df[col] = None

            return df[required_columns]
        else:
            st.warning(f"No data found for {dong_code}.")
            return pd.DataFrame(columns=required_columns)

    except Exception as e:
        st.error(f"Error fetching data for {dong_code}: {e}")
        return pd.DataFrame(columns=required_columns)

# 아파트 코드로 상세 정보 가져오기
def get_apt_details(apt_code):
    details_url = f'https://fin.land.naver.com/complexes/{apt_code}?tab=complex-info'
    article_url = f'https://fin.land.naver.com/complexes/{apt_code}?tab=article&tradeTypes=A1'
    
    header = {
        "Accept-Encoding": "gzip",
        "Host": "fin.land.naver.com",
        "Referer": "https://fin.land.naver.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0"
    }
    
    try:
        # 기본 정보 가져오기
        r_details = requests.get(details_url, headers=header)
        r_details.encoding = "utf-8-sig"
        soup_details = BeautifulSoup(r_details.content, 'html.parser')
        
        apt_name_tag = soup_details.find('span', class_='ComplexSummary_name__vX3IN')
        apt_name = apt_name_tag.text.strip() if apt_name_tag else 'Unknown'
        detail_dict = {'complexNo': apt_code, 'complexName': apt_name}
        
        detail_items = soup_details.find_all('li', class_='DataList_item__T1hMR')
        for item in detail_items:
            term = item.find('div', class_='DataList_term__Tks7l').text.strip()
            definition = item.find('div', class_='DataList_definition__d9KY1').text.strip()
            if term in ['공급면적', '전용면적', '해당면적 세대수', '현관구조', '방/욕실', '위치', '사용승인일', '세대수', '난방', '주차', '전기차 충전시설', '용적률/건폐율', '관리사무소 전화', '건설사']:
                detail_dict[term] = definition

        # 매물 정보 가져오기
        r_article = requests.get(article_url, headers=header)
        r_article.encoding = "utf-8-sig"
        soup_article = BeautifulSoup(r_article.content, 'html.parser')
        
        listings = []
        for item in soup_article.find_all('li', class_='ComplexArticleItem_item__L5o7k'):
            listing = {}
            name_tag = item.find('span', class_='ComplexArticleItem_name__4h3AA')
            listing['매물명'] = name_tag.text.strip() if name_tag else 'Unknown'
            price_tag = item.find('span', class_='ComplexArticleItem_price__DFeIb')
            listing['매매가'] = price_tag.text.strip() if price_tag else 'Unknown'
            
            summary_items = item.find_all('li', class_='ComplexArticleItem_item-summary__oHSwl')
            if len(summary_items) >= 4:
                listing['면적'] = summary_items[1].text.strip() if len(summary_items) > 1 else 'Unknown'
                listing['층수'] = summary_items[2].text.strip() if len(summary_items) > 2 else 'Unknown'
                listing['방향'] = summary_items[3].text.strip() if len(summary_items) > 3 else 'Unknown'
            
            image_tag = item.find('img')
            listing['이미지'] = image_tag['src'] if image_tag else 'No image'
            comment_tag = item.find('p', class_='ComplexArticleItem_comment__zN_dK')
            listing['코멘트'] = comment_tag.text.strip() if comment_tag else 'No comment'
            
            combined_listing = {**detail_dict, **listing}
            listings.append(combined_listing)
        
        return listings
    
    except Exception as e:
        st.error(f"Error fetching details for {apt_code}: {e}")
        return []

# 가격 문자열을 정수로 변환
def parse_price(price_str):
    if price_str:
        price_str = price_str.replace('억', '00000000').replace('천', '0000').replace(',', '')
        try:
            return int(price_str)
        except ValueError:
            return None
    return None

# 가격 구간으로 나누기
def categorize_price(price):
    if price is None:
        return 'Unknown'
    elif price < 1e8:
        return '<1억'
    elif price < 3e8:
        return '1억~3억'
    elif price < 5e8:
        return '3억~5억'
    elif price < 7e8:
        return '5억~7억'
    else:
        return '7억 이상'

# 아파트 정보를 수집하는 함수
def collect_apt_info_for_city(city_name, sigungu_name, dong_name=None, json_path='district.json'):
    sigungu_codes, dong_list = get_dong_codes_for_city(city_name, sigungu_name, json_path)

    if dong_list is None:
        st.error(f"Error: {city_name} or {sigungu_name} not found.")
        return
    
    st.write(f"수집된 동: {dong_list}")
    
    all_data = []
    for dong in dong_list:
        st.write(f"Fetching data for {dong['name']}")
        df = get_apt_list(dong['code'])
        if not df.empty:
            all_data.append(df)
    
    if not all_data:
        st.warning("No data available.")
        return pd.DataFrame()
    
    df_all = pd.concat(all_data, ignore_index=True)
    df_all['price'] = df_all['price'].apply(parse_price)
    df_all['price_category'] = df_all['price'].apply(categorize_price)
    
    return df_all

# Streamlit UI
st.title("아파트 정보 시각화 및 분석")

city_name = st.selectbox("시/도 선택", ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"])
sigungu_name = st.selectbox("구/군/구 선택", ["전체"] + ["서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시", "경기도", "강원도", "충청북도", "충청남도", "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"])
dong_name = st.selectbox("동 선택 (옵션)", [None] + ["동1", "동2", "동3"])  # 이곳에 실제 동 데이터를 넣어야 함

if st.button("데이터 수집 및 시각화"):
    data = collect_apt_info_for_city(city_name, sigungu_name, dong_name)
    
    if not data.empty:
        st.write("아파트 데이터", data)

        # 데이터 다운로드
        towrite = BytesIO()
        data.to_csv(towrite, encoding='utf-8', index=False)
        towrite.seek(0)
        st.download_button(label="CSV 파일 다운로드", data=towrite, file_name='apt_data.csv', mime='text/csv')
        
        # 시각화
        fig, axs = plt.subplots(2, 2, figsize=(14, 10))
        
        # 가격 분포 그래프
        sns.histplot(data['price'].dropna(), bins=30, ax=axs[0, 0])
        axs[0, 0].set_title('가격 분포')
        
        # 가격 구간별 아파트 수
        sns.countplot(data=data, x='price_category', ax=axs[0, 1])
        axs[0, 1].set_title('가격 구간별 아파트 수')
        axs[0, 1].tick_params(axis='x', rotation=45)
        
        # 연도별 아파트 수
        sns.countplot(data=data, x='buildYear', ax=axs[1, 0])
        axs[1, 0].set_title('연도별 아파트 수')
        axs[1, 0].tick_params(axis='x', rotation=45)
        
        # 면적 구간별 아파트 수
        data['areaSize_category'] = pd.cut(data['areaSize'].astype(float), bins=[0, 40, 60, 80, 100, 120, 140, 160, 200, float('inf')], labels=['<40㎡', '40~60㎡', '60~80㎡', '80~100㎡', '100~120㎡', '120~140㎡', '140~160㎡', '160~200㎡', '200㎡ 이상'])
        sns.countplot(data=data, x='areaSize_category', ax=axs[1, 1])
        axs[1, 1].set_title('면적 구간별 아파트 수')
        axs[1, 1].tick_params(axis='x', rotation=45)
        
        st.pyplot(fig)
    else:
        st.warning("No data available.")
