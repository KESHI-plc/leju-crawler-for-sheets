# ==================【請修改以下設定】==================
# 您要操作的 Google Sheets 文件名稱
GOOGLE_SHEET_NAME = '1c3KU75m4E0lksE_Q7TDKzUkZKVVCJCPvegkUq0-DKn4'
# 您要寫入資料的工作表名稱
WORKSHEET_NAME = '桃園市'
# =======================================================

import os
import time
import gspread
import pandas as pd
from gspread_dataframe import set_with_dataframe
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def get_google_creds():
    # 從 GitHub Secrets 獲取憑證內容
    creds_json_str = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
    if not creds_json_str:
        raise ValueError("Google Sheets credentials not found in GitHub Secrets!")
    
    import json
    return json.loads(creds_json_str)

def scrape_leju():
    print("--- 啟動爬蟲程式 ---")
    
    city_code = 'H' # 桃園市
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") # 在虛擬環境中必須使用無頭模式
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    all_projects = []
    page = 1
    
    while True:
        if page > 20: # 安全機制，避免無限迴圈
             print("已達到20頁上限，自動停止。")
             break
        
        url = f"https://www.leju.com.tw/sales_list?city={city_code}&is_new=1&p={page}"
        print(f"\n正在處理頁面: {url}")
        driver.get(url)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "build-item"))
            )
            build_items = driver.find_elements(By.CLASS_NAME, "build-item")
            
            if not build_items:
                print("在此頁面找不到任何建案，判斷為最後一頁。")
                break

            print(f"在第 {page} 頁找到 {len(build_items)} 個建案項目。")
            
            for item in build_items:
                try:
                    name = item.find_element(By.CSS_SELECTOR, ".build-name a").text
                    price = item.find_element(By.CSS_SELECTOR, ".build-price").text.replace('\n', ' ').replace('萬/坪', '').strip()
                    address = item.find_element(By.CSS_SELECTOR, ".build-address").text
                    
                    info_elements = item.find_elements(By.CSS_SELECTOR, ".build-info li")
                    total_households = info_elements[0].text.replace('總戶數', '').strip() if len(info_elements) > 0 else ''
                    completion_date = info_elements[1].text.replace('屋齡', '').replace('完工日', '').strip() if len(info_elements) > 1 else ''
                    public_facility = info_elements[2].text.replace('公設比', '').strip() if len(info_elements) > 2 else ''
                    
                    room_elements = item.find_elements(By.CSS_SELECTOR, ".build-rooms .room-item")
                    
                    project_data = {
                        "建案名稱": name, "總戶數": total_households, "完工日期": completion_date,
                        "開價(坪)": price, "區域": address.split(' ')[0] if address else '',
                        "路段": address.split(' ')[1] if ' ' in address else '', "公設": public_facility,
                        "開放式": room_elements[0].text.strip() if len(room_elements) > 0 else '--',
                        "1房": room_elements[1].text.strip().replace('\n', ' ') if len(room_elements) > 1 else '--',
                        "2房": room_elements[2].text.strip().replace('\n', ' ') if len(room_elements) > 2 else '--',
                        "3房": room_elements[3].text.strip().replace('\n', ' ') if len(room_elements) > 3 else '--',
                        "4房+": room_elements[4].text.strip().replace('\n', ' ') if len(room_elements) > 4 else '--',
                    }
                    all_projects.append(project_data)
                    print(f"  - 已抓取: {name}")

                except Exception as e:
                    print(f"    -> 抓取某個項目時出錯: {e}")
                    continue

            page += 1
            time.sleep(2)

        except Exception as e:
            print(f"處理頁面時發生嚴重錯誤: {e}")
            break
            
    driver.quit()
    print("\n--- 爬取完成，共抓取到", len(all_projects), "筆資料 ---")
    return all_projects

def update_google_sheet(data):
    if not data:
        print("沒有抓取到新資料，無需更新 Google Sheet。")
        return
        
    print("\n--- 開始更新 Google Sheet ---")
    try:
        new_df = pd.DataFrame(data)
        
        # 使用從 secrets 讀取到的憑證
        creds = get_google_creds()
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open(GOOGLE_SHEET_NAME)
        worksheet = sh.worksheet(WORKSHEET_NAME)
        print(f"成功連接到工作表: '{WORKSHEET_NAME}'")

        existing_data = worksheet.get_all_records()
        if existing_data:
            existing_df = pd.DataFrame(existing_data)
            existing_names = set(existing_df['建案名稱'])
            print(f"工作表中已存在 {len(existing_names)} 筆資料。")
            
            unique_new_df = new_df[~new_df['建案名稱'].isin(existing_names)]
            
            if unique_new_df.empty:
                print("所有抓取的資料都已存在，無需新增。")
                return
            else:
                print(f"找到 {len(unique_new_df)} 筆需要新增的資料。")
                next_row = len(existing_data) + 2 
                set_with_dataframe(worksheet, unique_new_df, row=next_row, col=5, include_header=False)
        else:
            print("工作表為空，將寫入所有新資料。")
            worksheet.update('E1', [new_df.columns.values.tolist()])
            set_with_dataframe(worksheet, new_df, row=2, col=5, include_header=False)
            
        print("--- Google Sheet 更新成功！ ---")
        
    except Exception as e:
        print(f"更新 Google Sheet 時發生錯誤: {e}")

if __name__ == "__main__":
    scraped_data = scrape_leju()
    update_google_sheet(scraped_data)
