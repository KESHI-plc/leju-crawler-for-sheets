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
# GDRIVE_FOLDER_ID is no longer the primary target, but we keep it for reference
# folder_id = os.environ.get('GDRIVE_FOLDER_ID') 
target_file_id = os.environ.get('GDRIVE_FILE_ID') # <--- 我們現在用這個
creds_json_str = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')

if not all([target_url, target_file_id, creds_json_str]):
    raise ValueError("Missing one or more required environment variables (TARGET_URL, GDRIVE_FILE_ID, GOOGLE_SHEETS_CREDENTIALS)")

# --- 2. 核心爬蟲與下載邏輯 (這部分不變) ---
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
        
        # 增加一個明確的等待，希望能繞過 "Just a moment..."
        print("等待頁面初步載入...")
        time.sleep(10) # 靜態等待10秒
        
        html_content = driver.page_source
        title = driver.title
        print(f"成功獲取頁面內容，標題為: {title}")

    except Exception as e:
        print(f"處理頁面時發生錯誤: {e}")
    finally:
        if driver:
            driver.quit()
    
    return html_content, title

# --- 3. 【全新】更新 Google Drive 檔案內容的邏輯 ---
def update_drive_file(file_id, file_content, creds_info):
    if not file_content:
        print("沒有內容可以更新，跳過。")
        return

    print(f"準備更新檔案 ID: {file_id}")
    try:
        scopes = ['https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(creds_info, scopes=scopes)
        drive_service = build('drive', 'v3', credentials=credentials)
        
        from io import BytesIO
        fh = BytesIO(file_content.encode('utf-8'))
        media = MediaIoBaseUpload(fh, mimetype='text/html', resumable=True)

        # 執行更新，而不是建立
        updated_file = drive_service.files().update(
            fileId=file_id,
            media_body=media
        ).execute()
        
        print(f"檔案內容更新成功！")

    except Exception as e:
        print(f"更新 Google Drive 檔案時發生錯誤: {e}")


# --- 4. 主執行流程 ---
if __name__ == "__main__":
    html_string, page_title = download_html_from_url(target_url)
    
    creds_dict = json.loads(creds_json_str)
    
    # 我們不再上傳新檔案，而是更新那個固定的樣板檔案
    update_drive_file(target_file_id, html_string, creds_dict)
    
    print("--- 任務執行完畢 ---")
