# Archive

## Setup

Create `.env` in the project root with your Zotero credentials:

```
ZOTERO_API_KEY=<your_api_key>
ZOTERO_LIBRARY_ID=<your_library_id>
```

Get your API key at https://www.zotero.org/settings/keys. Library ID is the numeric part of your Zotero profile URL.

**Development:** `.env` file in the project root (gitignored).

**Production:** `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` repository secrets in GitHub (Settings → Secrets and variables → Actions).
