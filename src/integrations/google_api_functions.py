import os
import json
from datetime import date, datetime

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

from config import authorized_ids, bot
from utils.logger import logger


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

    logger.info(f'Data updated in sheet {sheet_name}')


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

    logger.info(f'Data updated in sheet {sheet_name}')


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

    logger.info(f'Data updated in sheet {sheet_name}')


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

    logger.info(f'Data updated in sheet {sheet_name}')


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

    logger.info(f'Data updated in sheet {sheet_name}')


def create_commendation_statistics_sheet(spreadsheet_id, DatabaseConnection):
    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_info,
                                                  scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds)

    now = datetime.now()
    sheet_name = f"{now.strftime('%B')} {now.year}"

    try:
        sheet_body = {
            'requests': [{
                'addSheet': {
                    'properties': {
                        'title': sheet_name
                    }
                }
            }]
        }
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=sheet_body
        ).execute()
    except Exception as e:
        if "already exists" not in str(e):
            raise e

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('''
                       SELECT e.name,
                              COUNT(CASE WHEN c.employee_from_id = e.id THEN 1 END) as sent_count,
                              COUNT(CASE WHEN c.employee_to_id = e.id THEN 1 END)   as received_count
                       FROM employees e
                                INNER JOIN commendations c ON (c.employee_from_id = e.id OR c.employee_to_id = e.id)
                           AND EXTRACT(MONTH FROM c.commendation_date) = %s
                           AND EXTRACT(YEAR FROM c.commendation_date) = %s
                       GROUP BY e.id, e.name
                       ORDER BY sent_count DESC
                       ''', (now.month, now.year))
        statistics = cursor.fetchall()

    headers = ['Employee Name', 'Sent Commendations', 'Received Commendations']
    data = [headers] + [[row[0], row[1], row[2]] for row in statistics]

    range_name = f'{sheet_name}!A:C'
    body = {'values': data}

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

    logger.info(f'Commendation statistics for {sheet_name} created/updated.')


def create_monthly_commendation_details_sheet(spreadsheet_id, DatabaseConnection):
    now = datetime.now()
    month_ua = [
        'Січень',
        'Лютий',
        'Березень',
        'Квітень',
        'Травень',
        'Червень',
        'Липень',
        'Серпень',
        'Вересень',
        'Жовтень',
        'Листопад',
        'Грудень'
    ][now.month - 1]

    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_info,
                                                  scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds)
    sheet_name = f"{month_ua} {now.year}"
    try:
        add_sheet_request = {
            'addSheet': {
                'properties': {
                    'title': sheet_name,
                    'index': 0
                }
            }
        }
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [add_sheet_request]}
        ).execute()
        sheet_id = response['replies'][0]['addSheet']['properties']['sheetId']

        format_requests = [
            {
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 0,
                        'endRowIndex': 2,
                        'startColumnIndex': 0,
                        'endColumnIndex': 5
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'wrapStrategy': 'WRAP'
                        }
                    },
                    'fields': 'userEnteredFormat.wrapStrategy'
                }
            },
            {
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 0,
                        'endRowIndex': 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': 5
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'textFormat': {
                                'bold': True,
                                'fontSize': 12
                            },
                            'backgroundColor': {
                                'red': 1.0,
                                'green': 1.0,
                                'blue': 0.0
                            }
                        }
                    },
                    'fields': 'userEnteredFormat.textFormat.bold,userEnteredFormat.textFormat.fontSize,userEnteredFormat.backgroundColor'
                }
            },
            {
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 1,
                        'endRowIndex': 2,
                        'startColumnIndex': 0,
                        'endColumnIndex': 5
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'textFormat': {
                                'bold': True
                            },
                            'backgroundColor': {
                                'red': 0.643,
                                'green': 0.761,
                                'blue': 0.957
                            }
                        }
                    },
                    'fields': 'userEnteredFormat.textFormat.bold,userEnteredFormat.backgroundColor'
                }
            },
            {
                'mergeCells': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 0,
                        'endRowIndex': 1,
                        'startColumnIndex': 0,
                        'endColumnIndex': 5
                    },
                    'mergeType': 'MERGE_ALL'
                }
            },
            {
                'repeatCell': {
                    'range': {
                        'sheetId': sheet_id,
                        'startRowIndex': 0,
                        'endRowIndex': 2,
                        'startColumnIndex': 0,
                        'endColumnIndex': 5
                    },
                    'cell': {
                        'userEnteredFormat': {
                            'horizontalAlignment': 'CENTER',
                            'verticalAlignment': 'MIDDLE'
                        }
                    },
                    'fields': 'userEnteredFormat.horizontalAlignment,userEnteredFormat.verticalAlignment'
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': 0,
                        'endIndex': 1
                    },
                    'properties': {
                        'pixelSize': 120
                    },
                    'fields': 'pixelSize'
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': 1,
                        'endIndex': 2
                    },
                    'properties': {
                        'pixelSize': 420
                    },
                    'fields': 'pixelSize'
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': 2,
                        'endIndex': 3
                    },
                    'properties': {
                        'pixelSize': 420
                    },
                    'fields': 'pixelSize'
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': 3,
                        'endIndex': 4
                    },
                    'properties': {
                        'pixelSize': 230
                    },
                    'fields': 'pixelSize'
                }
            },
            {
                'updateDimensionProperties': {
                    'range': {
                        'sheetId': sheet_id,
                        'dimension': 'COLUMNS',
                        'startIndex': 4,
                        'endIndex': 5
                    },
                    'properties': {
                        'pixelSize': 600
                    },
                    'fields': 'pixelSize'
                }
            }
        ]

        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': format_requests}
        ).execute()

    except Exception as e:
        if "already exists" not in str(e):
            raise e
        else:
            sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            for sheet in sheet_metadata.get('sheets', []):
                if sheet['properties']['title'] == sheet_name:
                    sheet_id = sheet['properties']['sheetId']
                    break

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            '''
            SELECT comm.commendation_date,
                   e_from.name || '\n' || e_from.position,
                   e_to.name || '\n' || e_to.position,
                   value.name,
                   comm.commendation_text
            FROM commendations comm
                     JOIN employees e_from ON comm.employee_from_id = e_from.id
                     JOIN employees e_to ON comm.employee_to_id = e_to.id
                     LEFT JOIN commendation_values value ON comm.value_id = value.id
            WHERE EXTRACT(MONTH FROM comm.commendation_date) = %s
            ORDER BY comm.id
            ''',
            (now.month,)
        )
        commendations_info = cursor.fetchall()

    headers = [
        [month_ua, '', '', '', ''],
        ['Дата', 'Від кого подяка (ПІБ + посада)', 'Кому подяка (ПІБ + посада)', 'Цінність', 'Текст подяки']
    ]
    processed_info = [
        [cell.strftime('%d/%m/%Y') if isinstance(cell, date) else (cell if cell is not None else ' ') for cell in row]
        for row in commendations_info
    ]
    data = headers + processed_info
    range_name = f'{sheet_name}!A:E'
    body = {'values': data}
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption='RAW',
        body=body
    ).execute()

    logger.info(f'Commendation statistics (detailed) for {sheet_name} created/updated.')


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
        SELECT 
            cm.id,
            cm.commendation_text, 
            cm.commendation_date, 
            cm.employee_to_id, 
            cm.employee_from_id, 
            cm.position, 
            cm.value_id,
            csm.sender_name
        FROM commendations_mod cm
        LEFT JOIN commendation_senders_mod csm ON cm.id = csm.commendation_id
        WHERE cm.id IN ({placeholders}) AND cm.deleted = FALSE
    '''

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(select_query, ids_to_approve)
        commendations_info = cursor.fetchall()

        if not commendations_info:
            return False

        commendations_data = [
            (row[1], row[2], row[3], row[4], row[5], row[6])
            for row in commendations_info
        ]

        insert_commendation_query = '''
                                    INSERT INTO commendations
                                    (commendation_text, commendation_date, employee_to_id, employee_from_id, position, \
                                     value_id)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                    RETURNING id \
                                    '''

        commendation_senders_data = []
        for idx, commendation in enumerate(commendations_data):
            cursor.execute(insert_commendation_query, commendation)
            new_commendation_id = cursor.fetchone()[0]

            sender_name = commendations_info[idx][7]
            if sender_name:
                commendation_senders_data.append((new_commendation_id, sender_name))

        if commendation_senders_data:
            insert_sender_query = '''
                                  INSERT INTO commendation_senders
                                      (commendation_id, sender_name)
                                  VALUES (%s, %s) \
                                  '''
            cursor.executemany(insert_sender_query, commendation_senders_data)

        update_query = f'''
            UPDATE commendations_mod 
            SET deleted = TRUE 
            WHERE id IN ({placeholders})
        '''
        cursor.execute(update_query, ids_to_approve)

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
        logger.warning(f'Username {telegram_username} not found.')
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

    logger.info(f'Found user data for {telegram_username}')
    return user_data


def update_secret_santa_sheet(spreadsheet_id, sheet_name, DatabaseConnection):
    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    range_name = f'{sheet_name}!A:F'
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    if values:
        headers = values[0]

        body = {
            'values': [[] for _ in range(len(values) - 1)]
        }
        sheet.values().update(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A2:F',
            valueInputOption='RAW',
            body=body
        ).execute()

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT receiver.name, giver.name, ssi.address, ssi.phone, ssi.request, ssi.aversions '
            'FROM secret_santa_info ssi '
            'LEFT JOIN employees receiver ON ssi.employee_id = receiver.id '
            'LEFT JOIN employees giver ON ssi.secret_santa_id = giver.id '
            'ORDER BY receiver.name'
        )
        employees_info = cursor.fetchall()

    processed_info = [
        [cell if cell is not None else ' ' for cell in row]
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

    logger.info('Secret Santa data updated in sheet.')
