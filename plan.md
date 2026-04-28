# Kajin — Next Steps

## 1. Fix deprecated pandas API (blocking)

`DataFrame.append()` was removed in pandas 2.0. Every call in `api_utils.py` and `processing_utils.py` needs to be replaced with `pd.concat()`.

Affected locations:
- `api_utils.py` — `get_apparts`, `get_all_apparts`, `get_all_links`
- `processing_utils.py` — `append_history_df`, `update_history_df`

## 2. Expand expired-listing detection

`expired_checker` in `api_utils.py` has many sources that are no-ops (`pass`). Sources to implement:
- `explorimmo`, `stephaneplaza`, `flatlooker`, `bienici`, `guyhoquet`, `parisattitude`, `erafrance`

## 3. Add a config file

Credentials path, database paths, and Google Sheets IDs are all hardcoded in `main.py`. Move them to a `config.json` or `config.toml` at the project root so users don't need to edit source code.

## 4. Add basic tests

No tests exist. Minimum coverage:
- `cleaner` and `features_engineering` in `processing_utils.py` (pure functions, easy to unit test with fixture DataFrames)
- `authenticate` with a mocked `requests.Session`

## 5. Improve retry / rate-limiting in `get_all_links`

The current retry is a single 30 s sleep on any exception. Replace it with exponential backoff and surface the error type in the log.

## 6. Package the project

Add a `pyproject.toml` (or `setup.py`) so the app can be installed with `pip install -e .` and run as `kajin` from anywhere, removing the need to `cd src` before running.

## 7. Optional — scheduling

Add a `--schedule` flag (or a cron-ready entry point) so the scraper can run automatically at a set interval without requiring the GUI.
