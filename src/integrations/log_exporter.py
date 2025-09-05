import os
import json
import pandas as pd
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from database import DatabaseConnection


def write_to_sheet(service, spreadsheet_id, sheet_name, df):
    sheet = service.spreadsheets()
    range_name = f"{sheet_name}!A1"

    sheet.values().clear(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        body={}
    ).execute()

    values = [df.columns.tolist()] + df.astype(str).values.tolist()

    body = {"values": values}
    sheet.values().update(
        spreadsheetId=spreadsheet_id,
        range=range_name,
        valueInputOption="RAW",
        body=body
    ).execute()
    print(f"Updated sheet: {sheet_name}")


def update_google_stats(spreadsheet_id):
    creds_info = json.loads(os.getenv("GOOGLE_API_CREDENTIALS"))
    creds = Credentials.from_service_account_info(
        creds_info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds)

    with DatabaseConnection() as (conn, cursor):
        cursor.execute('''
                       SELECT e.name, func.description, ua.action_timestamp
                       FROM user_actions as ua
                                JOIN employees as e ON ua.user_id = e.id
                                JOIN functions as func ON ua.function_id = func.id
                       ''')
        df = pd.DataFrame(cursor.fetchall(), columns=["Employee Name", "Function Description", "Action Timestamp"])

    df["Action Timestamp"] = pd.to_datetime(df["Action Timestamp"])
    df["Date"] = df["Action Timestamp"].dt.date
    df["Hour"] = df["Action Timestamp"].dt.hour

    top_employees = df["Employee Name"].value_counts().reset_index()
    top_employees.columns = ["Employee", "Actions"]

    top_functions = df["Function Description"].value_counts().reset_index()
    top_functions.columns = ["Function", "Actions"]

    daily_activity = df.groupby("Date").size().reset_index(name="Actions")

    df["YearMonth"] = df["Action Timestamp"].dt.to_period("M").astype(str)
    monthly_activity = df.groupby("YearMonth").size().reset_index(name="Actions")

    write_to_sheet(service, spreadsheet_id, "Raw Data", df)
    write_to_sheet(service, spreadsheet_id, "Top Employees", top_employees)
    write_to_sheet(service, spreadsheet_id, "Top Functions", top_functions)
    write_to_sheet(service, spreadsheet_id, "Daily Activity", daily_activity)
    write_to_sheet(service, spreadsheet_id, "Monthly Activity", monthly_activity)
