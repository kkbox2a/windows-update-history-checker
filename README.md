# Windows Update History Checker — GitHub Pages

自動抓取 Microsoft 的 Windows 11 25H2 更新紀錄，保存為 JSON，並發布成 GitHub Pages 網頁。

## 功能

- GitHub Actions 每天自動檢查 4 次，也可手動執行
- 有新 KB、Build、類型或 MSU 連結變化時才自動 Commit
- 列出最新版與過往版本
- 搜尋 KB、Build、日期並篩選更新類型
- 取得 Microsoft Update Catalog 的 x64 MSU 直接下載連結
- 一鍵複製 Discord Markdown，連結使用 `<URL>` 避免 Discord 預覽卡片
- JSON 同時保存於 `data/updates.json` 與網頁使用的 `docs/data/updates.json`

## 建立 GitHub Repository

1. 在 GitHub 建立新的 Repository，建議名稱：`windows-update-history-checker`。
2. 將本專案所有檔案上傳到 Repository 根目錄並 Commit 到 `main`。
3. 開啟 Repository 的 **Settings → Pages**。
4. 在 **Build and deployment → Source** 選擇 **GitHub Actions**。
5. 開啟 **Actions**，執行 `Update Windows history and deploy Pages`，或等待排程執行。
6. 完成後 Pages 網址通常為：

   `https://<GitHub帳號>.github.io/windows-update-history-checker/`

## Actions 權限

若自動 Commit 顯示權限錯誤：

1. Settings → Actions → General
2. Workflow permissions 選擇 **Read and write permissions**
3. 儲存後重新執行 Workflow

工作流程本身已宣告最小需求：`contents: write`、`pages: write`、`id-token: write`。

## 手動測試

```bash
python -m pip install -r requirements.txt pytest
pytest -q
python scripts/fetch_updates.py
python scripts/validate_data.py
python -m http.server 8000 --directory docs
```

接著開啟 `http://localhost:8000`。

## 專案結構

```text
.github/workflows/update-and-deploy.yml  # 排程、Commit、部署
scripts/fetch_updates.py                 # Microsoft Support/Catalog 抓取
scripts/validate_data.py                 # JSON 驗證
data/updates.json                        # 原始資料
docs/                                    # GitHub Pages 網站
```

## 注意事項

Microsoft 若調整 Support 或 Update Catalog HTML 結構，抓取腳本可能需要更新。即使 Catalog 暫時抓不到 MSU，更新歷史仍會保留，網頁會標示下載連結尚未取得。
