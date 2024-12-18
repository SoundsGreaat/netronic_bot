import os
import json
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

from src.database import DatabaseConnection


def update_employees_in_sheet(spreadsheet_id, sheet_name):
    creds_info = json.loads(os.getenv('GOOGLE_API_CREDENTIALS'))
    creds = Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    service = build('sheets', 'v4', credentials=creds)

    sheet = service.spreadsheets()
    range_name = f'{sheet_name}!A:I'
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range=range_name).execute()
    values = result.get('values', [])

    if values:
        headers = values[0]

        body = {
            'values': [[] for _ in range(len(values) - 1)]
        }
        sheet.values().update(
            spreadsheetId=spreadsheet_id,
            range=f'{sheet_name}!A2:I',
            valueInputOption='RAW',
            body=body
        ).execute()

    with DatabaseConnection() as (conn, cursor):
        cursor.execute(
            'SELECT emp.name, dep.name, inter.name, sub.name, position, telegram_username, email, emp.phone, '
            'CASE WHEN ssi.employee_id IS NOT NULL THEN TRUE ELSE FALSE END '
            'FROM employees emp '
            'JOIN sub_departments sub ON emp.sub_department_id = sub.id '
            'JOIN departments dep ON sub.department_id = dep.id '
            'LEFT JOIN intermediate_departments inter ON sub.intermediate_department_id = inter.id '
            'LEFT JOIN public.secret_santa_info ssi ON emp.id = ssi.employee_id '
            'ORDER BY dep.name, sub.name'
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

    print(f'Data updated in sheet {sheet_name}')


if __name__ == "__main__":
    SPREADSHEET_ID = '1UpYnTpYIaEKabvkU18hYZSFEunfvwLQvMgN69R7Ydaw'
    SHEET_NAME = 'BOT AUTOFILL'

    update_employees_in_sheet(SPREADSHEET_ID, SHEET_NAME)
