# Windows Update History Checker

這是一個用來整理 Windows 11 更新資訊的小型自動化專案。

它會從 Microsoft 官方頁面取得更新紀錄，整理成 JSON，再由 GitHub Pages 顯示成可搜尋的網頁。目前追蹤 Windows 11 最新 H2 正式版，以及 Windows Insider Experimental Build。

網站：

https://kkbox2a.github.io/windows-update-history-checker/

## 目前追蹤的版本

| 頻道 | 內容 | MSU |
|---|---|---|
| Windows 11 正式版 | 自動辨識目前最新 H2 正式版的累積更新、Preview、Out-of-band 更新 | 嘗試取得對應的 x64 直接下載連結 |
| Windows Insider Experimental | Experimental Build | 通常不提供獨立 MSU，主要保留 Build 與 Release Notes |

正式版不再固定綁定 25H2 或 26200 Build。程式會從 Microsoft Support 自動尋找目前最新的 Windows 11 H2 更新歷程頁面，因此當主流正式版由 25H2 移至 26H2 時，可自動切換到新的版本與 Build 系列。

目前 25H2 仍會記錄 KB、OS Build、發布日期、更新類型、Release Notes 與 x64 MSU 下載網址；未來 26H2 正式版上線後會使用相同方式處理。

Experimental 也不綁定固定 Build prefix，會依 Microsoft Learn 的 Experimental Release Notes 自動追蹤目前的 Build 系列。

## 資料來源

本專案只使用 Microsoft 官方來源：

- Microsoft Support：Windows 11 正式版更新歷程
- Microsoft Update Catalog：x64 MSU 套件資訊
- Microsoft Learn：Windows Insider / Experimental Release Notes
- Windows Insider Blog：Experimental Build 官方公告與備援來源

MSU 解析時會檢查目標 KB 與架構，避免把 ARM64、checkpoint package 或同一 Catalog 項目中的其他套件當成 x64 下載檔。

## 執行流程

資料更新大致分成五個步驟：

1. GitHub Actions 啟動更新工作。
2. Python 抓取 Microsoft 官方資料。
3. 驗證 KB、Build、頻道與輸出格式。
4. 將結果寫入 `data/updates.json` 與 `docs/data/updates.json`。
5. GitHub Pages 重新部署網站。

主要抓取入口為：

```text
scripts/fetch_updates_v3.py
```

產生的兩份 JSON 用途不同：

```text
data/updates.json
```

保留在 Repository 中，方便版本追蹤與其他程式讀取。

```text
docs/data/updates.json
```

由 GitHub Pages 前端直接載入。

## 網站功能

網頁目前提供：

- Windows 11 最新正式版與 Windows Insider Experimental 頻道切換
- 正式版版本自動辨識，例如 25H2 → 26H2
- KB、Build、日期與更新類型搜尋
- 最新版本與歷史版本瀏覽
- 正式版 x64 MSU 直接下載
- MSU 尚未取得時前往 Microsoft Update Catalog 搜尋
- 開啟 Microsoft Release Notes
- 複製單筆更新的 Markdown 內容
- 顯示最後一次完整檢查時間

## 自動更新

Workflow 位於：

```text
.github/workflows/update-and-deploy.yml
```

目前有三種觸發方式：

- 手動：從 Actions 頁面執行 `Run workflow`
- Push：程式或網站檔案變更時執行測試與部署
- 排程：每週三執行兩次，第二次作為備援

台灣時間排程：

```text
08:47
09:17
```

對應 UTC cron：

```yaml
schedule:
  - cron: "47 0 * * 3"
  - cron: "17 1 * * 3"
```

GitHub Actions 的 scheduled workflow 不保證在指定分鐘立即開始，因此實際啟動時間可能稍有延遲。

每次完整檢查完成後，`last_checked_at` 都會更新。即使 Microsoft 當週沒有發布新 KB 或新 Build，也可以從網站上的最後檢查時間確認排程是否真的執行過。

## Repository 結構

```text
.
├─ .github/
│  └─ workflows/
│     └─ update-and-deploy.yml
├─ scripts/
│  ├─ fetch_updates.py
│  ├─ fetch_updates_v2.py
│  ├─ fetch_updates_v3.py
│  └─ validate_data.py
├─ tests/
├─ data/
│  └─ updates.json
├─ docs/
│  ├─ index.html
│  ├─ style.css
│  ├─ app.js
│  ├─ assets/
│  └─ data/
│     └─ updates.json
├─ requirements.txt
├─ README.md
└─ LICENSE
```

## 本機測試

建議使用 Python 3.12。

建立虛擬環境：

```bash
python -m venv .venv
```

Windows：

```bat
.venv\Scripts\activate
```

安裝依賴：

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
```

執行測試：

```bash
python -m pytest -q
```

手動重新抓取資料：

```bash
python scripts/fetch_updates_v3.py
```

驗證輸出：

```bash
python scripts/validate_data.py
```

在本機啟動網站：

```bash
python -m http.server 8000 --directory docs
```

接著開啟：

```text
http://localhost:8000
```

不建議直接雙擊 `docs/index.html`，因為瀏覽器對 `file://` 的限制可能使 JavaScript 無法讀取 JSON。

## 維護時需要注意的地方

Microsoft 網頁並不是固定 API，部分資料仍需解析網站內容。因此 Microsoft Support、Update Catalog、Learn 或 Insider Blog 改版時，抓取規則可能需要同步調整。

正式版的版本辨識會優先尋找較新的 H2 更新歷程頁面。若 Microsoft 尚未建立新年度 H2 頁面，程式會繼續使用上一個可用的 H2 正式版本，不會因為年份改變就誤切換。

特別需要注意以下幾項：

- Microsoft Support 的 Windows 版本與更新歷程網址格式
- KB 與 OS Build 的解析格式
- Preview / Out-of-band 類型判斷
- Experimental Build 的排序與官方公告來源
- Update Catalog 搜尋結果中的 x64 / ARM64 架構
- MSU 下載視窗中的實際檔名與 KB
- Microsoft 頁面暫時無法存取時的備援資料

如果 MSU 直接連結暫時無法取得，更新紀錄仍會保留，網站會改提供 Microsoft Update Catalog 搜尋入口，不會因單一下載網址失敗而丟失整筆更新資訊。

## GitHub Pages 設定

Repository 的 Pages Source 應設為：

```text
Settings → Pages → Build and deployment → GitHub Actions
```

Actions 需要寫回 JSON，因此 Workflow permissions 應允許讀寫：

```text
Settings → Actions → General → Workflow permissions → Read and write permissions
```

Workflow 使用的主要權限：

```yaml
permissions:
  contents: write
  pages: write
  id-token: write
```

## License

授權內容請參閱 [LICENSE](LICENSE)。
