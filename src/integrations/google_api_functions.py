import os
import json
from datetime import date

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

from config import authorized_ids, bot


def update_employees_in_sheet(spreadsheet_id, sheet_name, DatabaseConnection):
    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    range_name = f'{sheet_name}!A:I'
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    headers = values[0] if values else []

    sheet.values().clear(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        body={}
    ).execute()

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT emp.name, dep.name, inter.name, sub.name, position, telegram_username, email, phone, date_of_birth '
            'FROM employees emp '
            'JOIN sub_departments sub ON emp.sub_department_id = sub.id '
            'JOIN departments dep ON sub.department_id = dep.id '
            'LEFT JOIN intermediate_departments inter ON sub.intermediate_department_id = inter.id '
            'ORDER BY dep.name, sub.name'
        )
        employees_info = cursor.fetchall()

    processed_info = [
        [cell.strftime('%Y-%m-%d') if isinstance(cell, date) else (cell if cell is not None else ' ') for cell in row]
        for row in employees_info
    ]

    body = {
        'values': [headers] + processed_info
    }
    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

    print(f'Data updated in sheet {sheet_name}')


def update_bot_users_in_sheet(spreadsheet_id, sheet_name, DatabaseConnection):
    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds)

    user_list = []

    sheet = service.spreadsheets()
    range_name = f'{sheet_name}!A:C'
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    headers = values[0] if values else []

    sheet.values().clear(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        body={}
    ).execute()

    with DatabaseConnection() as (conn, cursor):
        for id in authorized_ids['users']:
            try:
                bot.get_chat(id)
            except Exception as e:
                cursor.execute('SELECT name, telegram_username FROM employees WHERE telegram_user_id = %s', (id,))
                user_info = cursor.fetchone()
                if user_info:
                    user_list.append(user_info + (id,))

    processed_info = [
        [cell if cell is not None else ' ' for cell in row] for row in user_list
    ]

    body = {
        'values': [headers] + processed_info if headers else processed_info
    }
    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

    print(f'Data updated in sheet {sheet_name}')


def update_commendations_in_sheet(spreadsheet_id, sheet_name, DatabaseConnection):
    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    range_name = f'{sheet_name}!A:E'
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    headers = values[0] if values else []

    sheet.values().clear(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        body={}
    ).execute()

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT e_from.name, e_to.name, comm.commendation_text, value.name, comm.commendation_date '
            'FROM commendations comm '
            'JOIN employees e_from ON comm.employee_from_id = e_from.id '
            'JOIN employees e_to ON comm.employee_to_id = e_to.id '
            'LEFT JOIN commendation_values value ON comm.value_id = value.id '
            'ORDER BY comm.id'
        )
        commendations_info = cursor.fetchall()

    processed_info = [
        [cell.strftime('%Y-%m-%d') if isinstance(cell, date) else (cell if cell is not None else ' ') for cell in row]
        for row in commendations_info
    ]

    body = {
        'values': [headers] + processed_info if headers else processed_info
    }
    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

    print(f'Data updated in sheet {sheet_name}')


def update_commendations_mod_in_sheet(spreadsheet_id, sheet_name, DatabaseConnection, remove_all=False):
    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    range_name = f'{sheet_name}!A:F' if not remove_all else f'{sheet_name}!A:G'
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    headers = values[0] if values else []

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT comm.id, e_from.name, e_to.name, comm.commendation_text, value.name, comm.commendation_date '
            'FROM commendations_mod comm '
            'JOIN employees e_from ON comm.employee_from_id = e_from.id '
            'JOIN employees e_to ON comm.employee_to_id = e_to.id '
            'LEFT JOIN commendation_values value ON comm.value_id = value.id '
            'WHERE deleted = FALSE '
            'ORDER BY comm.id'
        )
        commendations_info = cursor.fetchall()

    processed_info = [
        [cell.strftime('%Y-%m-%d') if isinstance(cell, date) else (cell if cell is not None else ' ') for cell in
         row]
        for row in commendations_info
    ]

    body = {
        'values': [headers] + processed_info if headers else processed_info
    }

    sheet.values().clear(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        body={}
    ).execute()

    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

    print(f'Data updated in sheet {sheet_name}')


def update_all_commendations_in_sheet(spreadsheet_id, sheet_name, DatabaseConnection):
    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    range_name = f'{sheet_name}!A:G'
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    headers = values[0] if values else []

    sheet.values().clear(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        body={}
    ).execute()

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT comm.id, e_from.name, e_to.name, comm.commendation_text, value.name, comm.commendation_date, '
            'comm.deleted '
            'FROM commendations_mod comm '
            'JOIN employees e_from ON comm.employee_from_id = e_from.id '
            'JOIN employees e_to ON comm.employee_to_id = e_to.id '
            'LEFT JOIN commendation_values value ON comm.value_id = value.id '
            'ORDER BY comm.id'
        )
        commendations_info = cursor.fetchall()

    processed_info = [
        [cell.strftime('%Y-%m-%d') if isinstance(cell, date) else (cell if cell is not None else ' ') for cell in row]
        for row in commendations_info
    ]

    body = {
        'values': [headers] + processed_info if headers else processed_info
    }
    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

    print(f'Data updated in sheet {sheet_name}')


def approve_and_parse_to_database(spreadsheet_id, sheet_name, DatabaseConnection):
    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(
        creds_info,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    range_name = f'{sheet_name}!A:G'
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    if not values:
        return False

    commendation_info = values[1:]
    ids_to_approve = [row[0] for row in commendation_info if row[-1].upper() == 'TRUE']

    if not ids_to_approve:
        return False

    placeholders = ','.join(['%s'] * len(ids_to_approve))
    select_query = f'''
        SELECT commendation_text, commendation_date, employee_to_id, employee_from_id, position, value_id
        FROM commendations_mod
        WHERE id IN ({placeholders}) AND deleted = FALSE
    '''

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(select_query, ids_to_approve)
        commendations_info = cursor.fetchall()

        if not commendations_info:
            return False

        insert_query = '''
                       INSERT INTO commendations
                       (commendation_text, commendation_date, employee_to_id, employee_from_id, position, value_id)
                       VALUES (%s, %s, %s, %s, %s, %s) \
                       '''

        cursor.executemany(insert_query, commendations_info)
        cursor.execute('UPDATE commendations_mod SET deleted = TRUE')
        conn.commit()

    sheet.values().clear(
        spreadsheetId=spreadsheet_id,
        range=f'{sheet_name}!A2:G',
        body={}
    ).execute()

    return ids_to_approve


def read_credentials_from_sheet(spreadsheet_id, sheet_name, telegram_username):
    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds)

    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f'{sheet_name}!D:D'
    ).execute()
    usernames = result.get('values', [])

    user_row_index = None
    for i, row in enumerate(usernames):
        if row and row[0].strip() == telegram_username.strip():
            user_row_index = i + 1
            break

    if user_row_index is None:
        print(f'Username {telegram_username} not found.')
        return None

    columns = {
        'OVPN ID': 'E',
        'OVPN PASS': 'F',
        'RD LOGIN': 'H',
        'RD PASS': 'I',
        'NEXTCLOUD LOGIN': 'K',
        'NEXTCLOUD PASS': 'L'
    }
    user_data = {}

    for key, col in columns.items():
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!{col}{user_row_index}'
        ).execute()
        values = result.get('values', [])
        user_data[key] = values[0][0] if values else ''

    print('Found user data:', user_data)
    return user_data
