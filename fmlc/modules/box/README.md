# Box Integration Setup

## Installation

This module requires the Box Python SDK, which is **not** included in the core FMLC
dependencies. Install it from [PyPI](https://pypi.org/project/box-sdk-gen/) with:

```bash
pip install -r fmlc/modules/box/requirements.txt
```

## Generating credentials (config.json)

1. Go to the Box Developer Console: https://app.box.com/developers/console
2. Create a new app and select **Custom App → OAuth 2.0**.
3. Change the Redirect URL to `http://localhost`.
4. Copy the **Client ID** and **Client Secret** into your `credentials.json`:

```json
{
  "clientID": "<your-client-id>",
  "clientSecret": "<your-client-secret>"
}
```

5. Run the bootstrap script to obtain tokens:

```bash
python -m fmlc.modules.box.auth credentials.json box_tokens.json
```

6. Follow the printed URL in your browser, authenticate, and paste the returned
   `code=...` value when prompted (or add it as `"authCode"` in `credentials.json`
   before running the script).

The script writes `access_token` and `refresh_token` to `box_tokens.json`.
Tokens are refreshed automatically by the eFMU modules during operation.

## Module inputs

### BoxCsvReader

| Key | Description |
|---|---|
| `credentials-file` | Path to the credentials JSON file |
| `token-file` | Path to the token JSON file |
| `folder-id` | Box folder ID containing the target file |
| `file-name` | Name of the CSV file to download |

### BoxCsvWriter

| Key | Description |
|---|---|
| `input-data` | JSON-serialised DataFrame (from an upstream module) |
| `credentials-file` | Path to the credentials JSON file |
| `token-file` | Path to the token JSON file |
| `folder-id` | Box folder ID containing the target file |
| `file-name` | Name of the CSV file to upload |
| `delete-old-versions` | If truthy, delete previous file versions after upload |
| `append-to-existing` | If truthy, download and prepend the existing file before uploading |
