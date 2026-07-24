# Windows Update History Checker

[🌐 English](README.md) | **繁體中文**

Windows Update History Checker 是一個以 **Python、GitHub Actions 與 GitHub Pages** 建置的自動化專案。

專案會定期擷取 Microsoft Windows 11 25H2 更新紀錄，解析 KB、OS Build、更新類型與 x64 MSU 下載連結，將結果保存為 JSON，再部署成可搜尋與複製 Discord Markdown 的靜態網頁。

## Live Site

部署完成後，網站網址格式如下：

```text
https://<GitHub帳號>.github.io/windows-update-history-checker/
```

## 系統架構

```text
Microsoft Support / Update Catalog
                │
                ▼
       scripts/fetch_updates.py
                │
                ▼
     data/updates.json
     docs/data/updates.json
                │
                ▼
          GitHub Pages
```

各元件職責：

- **Microsoft Support**：提供 Windows 11 25H2 更新歷史、KB、Build 與更新類型。
- **Microsoft Update Catalog**：提供對應 KB 的 x64 MSU 下載資訊。
- **Python 抓取程式**：下載、解析、整理並輸出 JSON。
- **GitHub Actions**：負責測試、抓取、驗證、Commit 與 Pages 部署。
- **GitHub Pages**：提供靜態網頁介面。

## 主要功能

- 解析 Windows 11 25H2 最新與歷史更新。
- 擷取日期、KB、OS Build、Preview 與 Out-of-band 類型。
- 查找與所選 KB 相符的 x64 MSU 直接下載連結。
- 避免誤選同一 Catalog 項目中的 checkpoint 或其他 KB 套件。
- 顯示最新版本與歷史版本清單。
- 支援 KB、Build、日期與更新類型搜尋及篩選。
- 一鍵複製 Discord Markdown。
- Markdown 連結使用 `<URL>` 格式，避免 Discord 自動產生預覽卡片。
- 只有更新資料真正變更時才建立自動 Commit。
- 將每次資料異動保存在 Git Commit 歷史中。

## GitHub Actions 工作流程

工作流程檔案：

```text
.github/workflows/update-and-deploy.yml
```

### 觸發方式

目前支援以下觸發方式：

- **排程執行**：每週三台灣時間上午 08:30。
- **手動執行**：從 GitHub Actions 頁面按下 `Run workflow`。
- **推送程式碼到 main**：當非資料 JSON 檔案變更時執行測試與重新部署。

排程使用 UTC：

```yaml
schedule:
  - cron: "30 0 * * 3"
```

### 執行流程

1. Checkout 最新的 `main` 分支。
2. 建立 Python 3.12 環境。
3. 安裝 `requirements.txt` 與 pytest。
4. 執行 parser 測試。
5. 執行 `scripts/fetch_updates.py` 抓取 Microsoft 資料。
6. 執行 `scripts/validate_data.py` 驗證輸出。
7. 比對 `data/updates.json` 與 `docs/data/updates.json`。
8. 資料有異動時，自動 Commit 並 Push 回 `main`。
9. 將 `docs/` 打包為 GitHub Pages artifact。
10. 部署到 GitHub Pages。

自動 Commit 使用 GitHub Actions Bot：

```text
github-actions[bot]
```

Commit 訊息格式：

```text
data: refresh Windows 11 25H2 history (KBxxxxxxx)
```

## 專案結構

```text
.
├─ .github/
│  └─ workflows/
│     └─ update-and-deploy.yml
├─ scripts/
│  ├─ __init__.py
│  ├─ fetch_updates.py
│  └─ validate_data.py
├─ tests/
│  ├─ __init__.py
│  └─ test_parser.py
├─ data/
│  └─ updates.json
├─ docs/
│  ├─ index.html
│  ├─ style.css
│  ├─ app.js
│  ├─ .nojekyll
│  ├─ assets/
│  │  └─ app_icon.png
│  └─ data/
│     └─ updates.json
├─ requirements.txt
├─ README.md
└─ LICENSE
```

## 資料輸出

抓取結果同時寫入兩個位置：

```text
data/updates.json
```

供版本控管、資料檢查與其他程式使用。

```text
docs/data/updates.json
```

供 GitHub Pages 前端讀取。

兩個檔案應保持相同內容。

資料格式範例：

```json
{
  "last_checked": "2026-07-24T00:30:00Z",
  "latest_kb": "KB5121767",
  "updates": [
    {
      "date": "July 18, 2026",
      "kb": "KB5121767",
      "builds": [
        "26200.8894",
        "26100.8894"
      ],
      "update_type": "Out-of-band",
      "msu_x64": "https://catalog.sf.dl.delivery.mp.microsoft.com/...",
      "technical_documentation": "https://support.microsoft.com/en-us/help/5121767"
    }
  ]
}
```

## 本機開發

### 需求

- Python 3.12 或相容版本
- Git

### 建立環境

```bash
python -m venv .venv
```

Windows：

```bat
.venv\Scripts\activate
```

Linux / macOS：

```bash
source .venv/bin/activate
```

安裝依賴：

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
```

### 執行測試

```bash
python -m pytest -q
```

### 手動抓取資料

```bash
python scripts/fetch_updates.py
```

### 驗證 JSON

```bash
python scripts/validate_data.py
```

### 啟動本機網頁

```bash
python -m http.server 8000 --directory docs
```

瀏覽器開啟：

```text
http://localhost:8000
```

請不要直接雙擊 `docs/index.html`，因為瀏覽器可能因本機檔案安全性限制而阻擋 JavaScript 載入 JSON。

## 部署設定

### GitHub Pages

進入 Repository：

```text
Settings → Pages → Build and deployment → Source
```

選擇：

```text
GitHub Actions
```

### Workflow 權限

GitHub Actions 需要將更新後的 JSON Commit 回 Repository。

進入：

```text
Settings → Actions → General → Workflow permissions
```

選擇：

```text
Read and write permissions
```

Workflow 使用以下權限：

```yaml
permissions:
  contents: write
  pages: write
  id-token: write
```

## 手動執行部署

1. 進入 Repository 的 `Actions`。
2. 選擇 `Update Windows history and deploy Pages`。
3. 按下 `Run workflow`。
4. 選擇 `main` 分支。
5. 等待所有步驟顯示綠色勾勾。

主要步驟應包含：

```text
Run parser tests
Fetch Microsoft update history
Validate generated data
Commit data changes
Configure Pages
Upload Pages artifact
Deploy Pages
```

## 開發注意事項

### Microsoft 頁面結構

抓取程式依賴 Microsoft Support 與 Update Catalog 的 HTML 結構。若 Microsoft 改版，以下功能可能需要調整：

- 更新標題解析
- KB 與 Build 擷取
- Preview / Out-of-band 判斷
- Catalog 搜尋結果解析
- MSU 下載網址解析

### MSU 連結比對

同一個 Update Catalog 項目可能包含多個 MSU，例如 checkpoint 套件或相依更新。

程式必須確認 MSU 檔名中的 KB 編號與目標 KB 完全一致，不能只取下載視窗中的第一個 x64 連結。

### Git Push 衝突

Workflow 可能與人工 Commit 同時更新 `main`。目前流程會：

1. Fetch 最新遠端分支。
2. Rebase 到 `origin/main`。
3. Push 失敗時最多重試 3 次。

本機提交前仍建議先執行：

```bash
git pull --rebase origin main
```

再執行：

```bash
git push
```

### 無資料變更

若 Microsoft 更新資料沒有任何變更，Workflow 不會產生空 Commit，但仍會重新部署目前的 `docs/`。

### 排程延遲

GitHub Actions 的排程不保證在指定分鐘精準開始。平台忙碌時可能延遲數分鐘，屬正常現象。

## Troubleshooting

### Workflow 無法 Push

確認：

```text
Settings → Actions → General → Workflow permissions
```

已選擇 `Read and write permissions`。

### Pages 部署成功但網站尚未更新

- 等待數分鐘後重新整理。
- 使用強制重新整理：`Ctrl + F5`。
- 確認 `docs/data/updates.json` 已更新。
- 確認最新 Actions Run 的 `Deploy Pages` 成功。

### MSU 連結未取得

可能原因：

- Microsoft Catalog 暫時無法存取。
- 該 KB 尚未提供 x64 MSU。
- Catalog HTML 或下載視窗格式改變。

更新歷史仍會保存，前端可顯示 MSU 連結尚未取得。

## License

請參閱 [LICENSE](LICENSE)。
