# Kajin, a Jinka wrapper

## Overview

Kajin is a wrapper for the Jinka API ([https://www.jinka.fr/]). It directly authentificates with a Jinka account and grabs the list of appartments found on configured alerts, then returns a dataset as a CSV and an Excel file. The dataset contains various pieces of data such as the area, the rent or the price per square meter.

This project was created during a period of strong demand on Paris for flats, which made navigation difficult on the website. This app aims to tackle this issue by generating a dataset which can then be used on a visualisation tool such as Data Studio, Tableau or PowerBI.

It also adds a cleaning functionality to Jinka, as the script automatically detects the list of expired offers and removes them from the Jinka website by sending a POST call to the website.

The application is intended to be used locally.

For the moment, the app has only been tested with the renting offer of Jinka.


# Installation

Python 3.9+ and [uv](https://docs.astral.sh/uv/) are required.

Install all dependencies with:

```
uv sync
```

# Use

You can launch the application from the project root by running:

```
uv run src/main.py
```

which will open the GUI.

If you prefer to use the application on a command line, the app supports the following flags:

| Flag | Short | Description |
|------|-------|-------------|
| `--email` | `-e` | Jinka account email |
| `--password` | `-p` | Jinka password (**insecure**: visible in `ps aux`). Prefer `KAJIN_PASSWORD` env var |
| `--load` | `-l` | Load saved credentials from system keyring |
| `--save` | `-s` | Save provided credentials to system keyring |
| `--expired` | `-x` | Remove expired offers (slower: checks all active offers) |
| `--upload` | `-u` | Upload results to Google Sheets |

Providing any flag bypasses the GUI. Run `uv run src/main.py --help` for the full reference.

Examples:

- Loading saved credentials and removing expired offers:
```
uv run src/main.py --load --expired
```

- Writing new credentials, saving them, skipping expiry check:
```
KAJIN_PASSWORD='mypassword' uv run src/main.py -e 'john.doe@gmail.com' --save
```

## Credential storage

When credentials are saved (GUI "Save credentials" button or `-s` flag), the email is stored in `databases/credentials.json` and the password is stored in the **system keyring** (macOS Keychain, Windows Credential Manager, or a compatible Linux keyring such as GNOME Keyring / KWallet). No password is written to disk in plaintext.

## Google Sheets upload

The Google Sheets upload feature requires two environment variables:

- `KAJIN_SPREADSHEET_ID` — the ID of the target Google Sheet
- `KAJIN_GSHEETS_CREDS_PATH` — path to the directory containing `secret_client.json` and `token.json` (defaults to `../../gsheets_credentials` relative to the project root)

# Disclaimer

This project is not affiliated in any way with the Jinka team. Even though I had no issues with my account so far, I am not responsible for any action taken by Jinka against a given account as the script can adopt a suspicious behavior, especially during the cleaning of expired offers.
