import os
import time
import json
import gspread
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- 1. 從環境變數讀取所有必要的資訊 ---
target_url = os.environ.get('TARGET_URL')
folder_id = os.environ.get('GDRIVE_FOLDER_ID')
creds_json_str = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')

if not all([target_url, folder_id, creds_json_str]):
    raise ValueError("Missing one or more required environment variables (TARGET_URL, GDRIVE_FOLDER_ID, GOOGLE_SHEETS_CREDENTIALS)")

# --- 2. 核心爬蟲與下載邏輯 ---
def download_html_from_url(url):
    driver = None
    html_content = ""
    title = ""
    print(f"--- 開始處理網址: {url} ---")
    try:
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        print("正在初始化 uc driver...")
        driver = uc.Chrome(options=options, use_subprocess=False)
        print("Driver 初始化成功。")
        
        driver.get(url)
        
        # 等待頁面標題出現，這是最基本的載入成功信號
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "title")))
        
        # 額外等待幾秒，讓動態內容充分渲染
        time.sleep(5)
        
        html_content = driver.page_source
        title = driver.title
        print(f"成功獲取頁面內容，標題為: {title}")

    except Exception as e:
        print(f"處理頁面時發生錯誤: {e}")
    finally:
        if driver:
            driver.quit()
    
    return html_content, title

# --- 3. 上傳到 Google Drive 的邏輯 ---
def upload_to_drive(file_name, file_content, folder_id, creds_info):
    if not file_content:
        print("沒有內容可以上傳，跳過。")
        return

    print(f"準備將檔案 '{file_name}' 上傳到資料夾 ID: {folder_id}")
    try:
        # 準備 Google API 憑證
        scopes = ['https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
        
        # 建立 Drive API 服務
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # 準備檔案元數據
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        # 將字串內容轉為可上傳的格式
        from io import BytesIO
        fh = BytesIO(file_content.encode('utf-8'))
        media = MediaIoBaseUpload(fh, mimetype='text/html', resumable=True)

        # 執行上傳
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        print(f"檔案上傳成功！ File ID: {file.get('id')}")

    except Exception as e:
        print(f"上傳到 Google Drive 時發生錯誤: {e}")

# --- 4. 主執行流程 ---
if __name__ == "__main__":
    html_string, page_title = download_html_from_url(target_url)
    
    # 從頁面標題提取縣市名稱作為檔名
    city_name = page_title.split('【')[1].split('新建案】')[0] if '新建案】' in page_title else "unknown_city"
    output_filename = f"{city_name}.html"
    
    # 將爬取到的 HTML 上傳
    creds_dict = json.loads(creds_json_str)
    upload_to_drive(output_filename, html_string, folder_id, creds_dict)
    
    print("--- 任務執行完畢 ---")
