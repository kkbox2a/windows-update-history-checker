# Windows Update History Checker

**🌐 English** | [繁體中文](README.zh-TW.md)

Windows Update History Checker is an automation project built with **Python, GitHub Actions, and GitHub Pages**.

The project periodically retrieves the Microsoft Windows 11 25H2 update history, parses KB numbers, OS Builds, update types, and x64 MSU download links, saves the results as JSON, and deploys them as a searchable static website with Discord Markdown copy support.

## Live Site

After deployment, the site URL follows this format:

```text
https://<GitHub-account>.github.io/windows-update-history-checker/
```

## System Architecture

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

Component responsibilities:

- **Microsoft Support**: provides Windows 11 25H2 update history, KB numbers, Builds, and update types.
- **Microsoft Update Catalog**: provides x64 MSU download information for the corresponding KB.
- **Python fetcher**: downloads, parses, organizes, and exports JSON data.
- **GitHub Actions**: handles testing, fetching, validation, commits, and Pages deployment.
- **GitHub Pages**: provides the static web interface.

## Main Features

- Parses the latest and historical Windows 11 25H2 updates.
- Extracts release dates, KB numbers, OS Builds, Preview, and Out-of-band types.
- Finds the x64 MSU direct download link matching the selected KB.
- Avoids selecting checkpoint packages or other KB packages from the same Catalog item.
- Displays the latest release and historical update list.
- Supports searching and filtering by KB, Build, date, and update type.
- Provides one-click Discord Markdown copying.
- Uses `<URL>` syntax in Markdown links to prevent Discord link preview cards.
- Creates an automatic commit only when update data actually changes.
- Preserves every data change in Git commit history.

## GitHub Actions Workflow

Workflow file:

```text
.github/workflows/update-and-deploy.yml
```

### Triggers

The workflow currently supports:

- **Scheduled run**: every Wednesday at 08:30 Taiwan time.
- **Manual run**: click `Run workflow` from the GitHub Actions page.
- **Push to main**: runs tests and redeploys when files other than the generated JSON data are changed.

The schedule is expressed in UTC:

```yaml
schedule:
  - cron: "30 0 * * 3"
```

### Execution Flow

1. Check out the latest `main` branch.
2. Set up Python 3.12.
3. Install `requirements.txt` dependencies and pytest.
4. Run parser tests.
5. Run `scripts/fetch_updates.py` to retrieve Microsoft data.
6. Run `scripts/validate_data.py` to validate the output.
7. Compare `data/updates.json` and `docs/data/updates.json`.
8. Automatically commit and push to `main` when data changes.
9. Package `docs/` as a GitHub Pages artifact.
10. Deploy to GitHub Pages.

Automatic commits use the GitHub Actions Bot:

```text
github-actions[bot]
```

Commit message format:

```text
data: refresh Windows 11 25H2 history (KBxxxxxxx)
```

## Project Structure

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

## Data Output

Fetched results are written to two locations:

```text
data/updates.json
```

Used for version control, data inspection, and external program access.

```text
docs/data/updates.json
```

Used by the GitHub Pages frontend.

Both files should contain identical data.

Example data structure:

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

## Local Development

### Requirements

- Python 3.12 or a compatible version
- Git

### Create an Environment

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
```

Linux / macOS:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pytest
```

### Run Tests

```bash
python -m pytest -q
```

### Fetch Data Manually

```bash
python scripts/fetch_updates.py
```

### Validate JSON

```bash
python scripts/validate_data.py
```

### Start the Local Website

```bash
python -m http.server 8000 --directory docs
```

Open in a browser:

```text
http://localhost:8000
```

Do not open `docs/index.html` directly by double-clicking it, because browser local-file security restrictions may block JavaScript from loading the JSON file.

## Deployment Configuration

### GitHub Pages

Open the repository settings:

```text
Settings → Pages → Build and deployment → Source
```

Select:

```text
GitHub Actions
```

### Workflow Permissions

GitHub Actions must be able to commit the updated JSON files back to the repository.

Open:

```text
Settings → Actions → General → Workflow permissions
```

Select:

```text
Read and write permissions
```

The workflow uses these permissions:

```yaml
permissions:
  contents: write
  pages: write
  id-token: write
```

## Run a Deployment Manually

1. Open the repository's `Actions` tab.
2. Select `Update Windows history and deploy Pages`.
3. Click `Run workflow`.
4. Select the `main` branch.
5. Wait until every step shows a green check mark.

The main steps should include:

```text
Run parser tests
Fetch Microsoft update history
Validate generated data
Commit data changes
Configure Pages
Upload Pages artifact
Deploy Pages
```

## Development Notes

### Microsoft Page Structure

The fetcher depends on the HTML structure of Microsoft Support and Microsoft Update Catalog. If Microsoft changes either site, the following parts may require updates:

- Update title parsing
- KB and Build extraction
- Preview / Out-of-band detection
- Catalog search-result parsing
- MSU download URL parsing

### MSU Link Matching

A single Update Catalog item may contain multiple MSU packages, such as checkpoint packages or prerequisite updates.

The program must verify that the KB number in the MSU filename exactly matches the target KB. It must not simply select the first x64 link returned by the download window.

### Git Push Conflicts

The workflow may update `main` at the same time as a manual commit. The current workflow handles this by:

1. Fetching the latest remote branch.
2. Rebasing onto `origin/main`.
3. Retrying the push up to three times if necessary.

Before pushing local changes, it is still recommended to run:

```bash
git pull --rebase origin main
```

Then run:

```bash
git push
```

### No Data Changes

If the Microsoft update data has not changed, the workflow does not create an empty commit, but it still redeploys the current `docs/` content.

### Schedule Delays

GitHub Actions scheduled workflows are not guaranteed to start at the exact configured minute. Delays of several minutes can occur when the platform is busy.

## Troubleshooting

### Workflow Cannot Push

Verify that:

```text
Settings → Actions → General → Workflow permissions
```

is set to `Read and write permissions`.

### Pages Deployment Succeeds but the Site Has Not Updated

- Wait a few minutes and refresh the page.
- Perform a hard refresh with `Ctrl + F5`.
- Confirm that `docs/data/updates.json` was updated.
- Confirm that `Deploy Pages` succeeded in the latest Actions run.

### MSU Link Is Missing

Possible causes:

- Microsoft Catalog is temporarily unavailable.
- The KB does not yet provide an x64 MSU package.
- The Catalog HTML or download-window format has changed.

The update-history record is still preserved, and the frontend can indicate that the MSU link is not yet available.

## License

See [LICENSE](LICENSE).
