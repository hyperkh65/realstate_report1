import streamlit as st
import pandas as pd
from io import BytesIO
import requests
import json
from bs4 import BeautifulSoup

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

# 아파트 정보를 수집하는 함수
def collect_apt_info_for_city(city_name, sigungu_name, dong_name=None, json_path='district.json'):
    sigungu_codes, dong_list = get_dong_codes_for_city(city_name, sigungu_name, json_path)

    if dong_list is None:
        st.error(f"Error: {city_name} not found in JSON.")
        return None

    all_apt_data = []
    dong_code_name_map = {dong['code']: dong['name'] for dong in dong_list}
    
    # 수집 중 표시를 위한 placeholder
    placeholder = st.empty()

    if dong_name and dong_name != '전체':
        dong_code_name_map = {k: v for k, v in dong_code_name_map.items() if v == dong_name}

    for dong_code, dong_name in dong_code_name_map.items():
        placeholder.write(f"{dong_name} ({dong_code}) - 수집중입니다.")
        apt_codes = get_apt_list(dong_code)

        if not apt_codes.empty:
            for _, apt_info in apt_codes.iterrows():
                apt_code = apt_info['complexNo']
                apt_name = apt_info['complexName']
                placeholder.write(f"{apt_name} ({apt_code}) - 수집중입니다.")
                listings = get_apt_details(apt_code)
                
                if listings:
                    for listing in listings:
                        listing['dong_code'] = dong_code
                        listing['dong_name'] = dong_name
                        all_apt_data.append(listing)
        else:
            st.warning(f"No apartment codes found for {dong_code}")

    # 수집이 완료된 후, 수집 중 메시지를 지우기
    placeholder.empty()

    if all_apt_data:
        final_df = pd.DataFrame(all_apt_data)
        final_df['si_do_name'] = city_name
        final_df['sigungu_name'] = sigungu_name
        final_df['dong_name'] = dong_name if dong_name else '전체'
        
        # 데이터프레임 결과 출력
        st.write("아파트 정보 수집 완료:")
        # 이미지와 함께 결과 테이블 표시
        image_cols = ['이미지', '매물명', '매매가', '면적', '층수', '방향', '코멘트']
        final_df['이미지'] = final_df['이미지'].apply(lambda x: f'<img src="{x}" width="100" />' if x != 'No image' else '')
        st.markdown(final_df.to_html(escape=False, index=False, columns=image_cols), unsafe_allow_html=True)

        # 엑셀 파일로 저장
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False)
        output.seek(0)

        # 엑셀 파일 다운로드 버튼
        st.download_button(
            label="Download Excel",
            data=output,
            file_name="apartment_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No apartment data collected.")

# Streamlit UI 구성
st.set_page_config(page_title="아파트 정보 수집기", layout="wide")
st.sidebar.header("옵션")

# 사용자 입력 받기
city_name = st.sidebar.selectbox("시도 선택", ["서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원도", "충청북도", "충청남도", "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"])
sigungu_name = st.sidebar.selectbox("시군구 선택", ["전체", "강남구", "서초구", "송파구"])  # 예시로 몇 개만 추가
dong_name = st.sidebar.selectbox("법정동 선택", ["전체", "역삼동", "잠실동"])  # 예시로 몇 개만 추가

if st.sidebar.button("검색하기"):
    collect_apt_info_for_city(city_name, sigungu_name, dong_name)

