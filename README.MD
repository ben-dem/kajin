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

If you prefer to use the application on a command line, the app supports the following arguments:

``` -e --email ``` -> a string containing the email  
``` -p --password ``` -> the Jinka account password (**insecure**: visible in process lists via `ps aux`). Prefer the `KAJIN_PASSWORD` environment variable.  
``` -l --load ``` -> 1 to load existing credentials, 0 not to load them. If 0 is specified, the email and password arguments must be filled  
``` -s --save ```-> 1 to save the credentials specified in the email and password fields  
``` -x --expired ``` -> 1 to clean all of the expired offers, 0 not to do it. This operation can be long to run as the script checks all of the active offers for expiration.  

Entering any argument will bypass the GUI. By default, load, save and expired are equal to 0.

Examples :

- Loading existing credentials and removing expired offers :
``` uv run src/main.py -l 1 -x 1 ```

- Writing new credentials, saving them and avoiding a check for expired offers:

``` KAJIN_PASSWORD='mypassword' uv run src/main.py -e 'john.doe@gmail.com' -s 1 ```

## Credential storage

When credentials are saved (GUI "Save credentials" button or `-s` flag), the email is stored in `databases/credentials.json` and the password is stored in the **system keyring** (macOS Keychain, Windows Credential Manager, or a compatible Linux keyring such as GNOME Keyring / KWallet). No password is written to disk in plaintext.

## Google Sheets upload

The Google Sheets upload feature requires two environment variables:

- `KAJIN_SPREADSHEET_ID` — the ID of the target Google Sheet
- `KAJIN_GSHEETS_CREDS_PATH` — path to the directory containing `secret_client.json` and `token.json` (defaults to `../../gsheets_credentials` relative to the project root)

# Disclaimer

This project is not affiliated in any way with the Jinka team. Even though I had no issues with my account so far, I am not responsible for any action taken by Jinka against a given account as the script can adopt a suspicious behavior, especially during the cleaning of expired offers.
