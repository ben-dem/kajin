import json
import argparse
import getpass
import os
import warnings
import re

import keyring
import keyring.errors
import PySimpleGUI as sg
from gsheets_uploader import Uploader
from logzero import logger, logfile

from api_utils import authenticate, get_alerts, get_all_apparts, get_all_links, remove_expired
from processing_utils import features_engineering, cleaner, update_history_df, append_history_df
from openpyxl.utils.exceptions import IllegalCharacterError

KEYRING_SERVICE = 'kajin'

parser = argparse.ArgumentParser(description='Override the GUI if needed.')
parser.add_argument('-e', '--email',
                    help='The Jinka account email address')
parser.add_argument('-p', '--password',
                    help='Jinka password. Prefer the KAJIN_PASSWORD environment variable '
                         'to avoid exposing credentials in process lists.')
parser.add_argument('-l', '--load', type=int, nargs='?',
                    help='Whether to load existing credentials: 0 or 1')
parser.add_argument('-s', '--save', type=int, nargs='?',
                    help='Whether to save the credentials. Requires --email.')
parser.add_argument('-x', '--expired', nargs='?', const=1,
                    help='Whether to remove expired offers.')
parser.add_argument('-u', '--upload', nargs='?', const=1,
                    help='Whether to use the gsheets-uploader package to upload to Google Sheets.')

args = parser.parse_args()

current_dir = os.getcwd()
path_list = current_dir.split(os.sep)

if path_list[-1] == 'src':
    current_dir = os.path.join(current_dir, '..')
    os.chdir(current_dir)

# Path to files
CREDENTIALS_FILE = os.path.join(os.getcwd(), 'databases', 'credentials.json')
APPARTS_DB_PATH = os.path.join(os.getcwd(), 'databases', 'appart_links_db.json')
LAST_DELETED_PATH = os.path.join(os.getcwd(), 'databases', 'last_deleted_apparts.json')
HISTORY_PATH = os.path.join(os.getcwd(), 'data', 'history.csv')
APPARTS_CSV_PATH = os.path.join(os.getcwd(), 'data', 'apparts.csv')
APPARTS_XLSX_PATH = os.path.join(os.getcwd(), 'data', 'apparts.xlsx')
LOG_PATH = os.path.join(os.getcwd(), 'databases', 'logs.log')
DATABASES_PATH = os.path.join(os.getcwd(), 'databases')
DATA_PATH = os.path.join(os.getcwd(), 'data')

# Configurable via environment variables to avoid hardcoded sensitive paths/IDs
CREDS_PATH = os.environ.get(
    'KAJIN_GSHEETS_CREDS_PATH',
    os.path.join(os.getcwd(), '..', '..', 'gsheets_credentials')
)
TOKEN_FILE_PATH = os.path.join(CREDS_PATH, 'token.json')
SECRET_CLIENT_PATH = os.path.join(CREDS_PATH, 'secret_client.json')
SPREADSHEET_ID = os.environ.get('KAJIN_SPREADSHEET_ID', '')
EXPORT_CSV_PATH = APPARTS_CSV_PATH

# Guard against symlink attacks on the log file
if os.path.exists(LOG_PATH) and not os.path.islink(LOG_PATH):
    os.remove(LOG_PATH)

if not os.path.exists(DATABASES_PATH):
    os.mkdir(DATABASES_PATH)

if not os.path.exists(DATA_PATH):
    os.mkdir(DATA_PATH)

logfile(LOG_PATH)


def _load_saved_credentials():
    """Return (email, password) from stored credentials, or ('', '') if not found."""
    if not os.path.exists(CREDENTIALS_FILE):
        return '', ''
    with open(CREDENTIALS_FILE, 'r') as f:
        data = json.load(f)
    email = data.get('email', '')
    if not email:
        return '', ''
    try:
        password = keyring.get_password(KEYRING_SERVICE, email) or ''
    except keyring.errors.NoKeyringError:
        logger.warning('No system keyring available. Password not loaded.')
        password = ''
    return email, password


def _save_credentials(email, password):
    with open(CREDENTIALS_FILE, 'w') as f:
        json.dump({'email': email}, f)
    try:
        keyring.set_password(KEYRING_SERVICE, email, password)
    except keyring.errors.NoKeyringError:
        logger.error(
            'No system keyring available. Password not saved. '
            'Use the KAJIN_PASSWORD environment variable instead.'
        )


def run_all(email, password, expired, upload=False):
    s, headers = authenticate(email, password)

    if s is None:
        logger.critical('Aborting search, check your credentials.')
        quit()
    df_alerts = get_alerts(s, headers)
    df_apparts, expired_index = get_all_apparts(df_alerts, s, headers)
    df_apparts = cleaner(df_apparts)
    df_apparts = features_engineering(df_apparts)
    df_history = append_history_df(df_apparts, HISTORY_PATH)
    df_apparts = df_apparts.loc[~df_apparts.index.duplicated()]
    df_apparts = get_all_links(s, df_apparts, expired, APPARTS_DB_PATH)
    if expired:
        df_history = update_history_df(df_apparts, df_history, expired_index)
        df_apparts = remove_expired(s, df_apparts, LAST_DELETED_PATH)
    df_apparts.to_csv(APPARTS_CSV_PATH, sep=';', encoding='utf-8')
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            df_apparts.to_excel(APPARTS_XLSX_PATH, encoding='utf-8')
        except IllegalCharacterError:
            logger.warn("Some illegal characters were replaced in the dataframe.")
            ILLEGAL_CHARACTERS_RE = re.compile(r'[\000-\010]|[\013-\014]|[\016-\037]')
            df_apparts.applymap(
                lambda x: ILLEGAL_CHARACTERS_RE.sub(r'', x) if isinstance(x, str) else x
            ).to_excel(APPARTS_XLSX_PATH, encoding='utf-8')

    df_history.to_csv(HISTORY_PATH, sep=';', encoding='utf-8')

    if upload:
        if not SPREADSHEET_ID:
            logger.error(
                'KAJIN_SPREADSHEET_ID environment variable is not set. Skipping upload.'
            )
        else:
            uploader = Uploader(
                credentials_path=CREDS_PATH,
                token_file_path=TOKEN_FILE_PATH,
                secret_client_path=SECRET_CLIENT_PATH
            )
            uploader.push_table(
                df_apparts,
                spreadsheet_id=SPREADSHEET_ID,
                worksheet_name='apparts',
                index=True
            )


def create_main_window():
    sg.theme()
    default_email, default_password = _load_saved_credentials()

    def TextLabel(text, size): return sg.Text(text + ':', justification='r', size=size)

    layout = [
        [sg.T('Kajin')],
        [sg.T('We <3 scrapping')],
        [TextLabel('Login email', size=(25, 1)), sg.InputText(key='-EMAIL-', default_text=default_email)],
        [TextLabel('Password', size=(25, 1)), sg.InputText(key='-PASSWORD-', default_text=default_password, password_char='*')],
        [sg.Checkbox('Clean expired appartments', size=(10, 1), key='-EXPIRED-')],
        [sg.Checkbox('Google Sheets upload', size=(10, 1), key='-UPLOAD-')],
        [sg.B('Run Application'), sg.B('Save credentials'), sg.B('Exit')],
    ]

    return sg.Window('Main Application', layout, size=(500, 200))


if __name__ == '__main__':
    cli_mode = any([args.email, args.password, args.load, args.save, args.expired, args.upload])

    if not cli_mode:
        window = None
        while True:
            if window is None:
                window = create_main_window()
                event, values = window.read()

            if event == 'Run Application':
                logger.info('Launching application')
                password = values['-PASSWORD-']
                email = values['-EMAIL-']
                expired = values['-EXPIRED-']
                upload = values['-UPLOAD-']
                window.close()
                run_all(email, password, expired=expired, upload=upload)
                break

            if event == 'Save credentials':
                _save_credentials(values['-EMAIL-'], values['-PASSWORD-'])
                sg.Popup('Credentials saved', keep_on_top=True)
                window = None

            if event in (sg.WIN_CLOSED, 'Exit'):
                break
    else:
        if args.load:
            email, password = _load_saved_credentials()
            if not password:
                logger.critical('No saved credentials found. Use -e and -p (or KAJIN_PASSWORD) to provide them.')
                quit()
        else:
            email = args.email
            if args.password:
                logger.warning(
                    'Passing passwords via -p exposes them in process lists (ps aux). '
                    'Prefer the KAJIN_PASSWORD environment variable.'
                )
                password = args.password
            else:
                password = os.environ.get('KAJIN_PASSWORD') or getpass.getpass('Jinka password: ')

        if args.save:
            _save_credentials(email, password)

        upload = bool(args.upload)
        run_all(email, password, expired=args.expired, upload=upload)
