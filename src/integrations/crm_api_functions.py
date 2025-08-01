import requests
import os

CRM_URL = os.getenv('CRM_URL')
CRM_KEY = os.getenv('CRM_KEY')


def get_employee_pass_from_crm(crm_user_id):
    payload = {
        'key': CRM_KEY,
        'action': 'getPass',
        'id': crm_user_id
    }

    response = requests.post(CRM_URL, json=payload)

    if response.status_code == 200:
        data = response.json()
        try:
            employee_crm_id = data.get('data').get('pass')
            return employee_crm_id
        except AttributeError:
            print(f'Error {response.status_code}: {response.text}')
            return


def add_employee_to_crm(name, phone, position, telegram_user_id, telegram_username, email):
    payload = {
        'key': CRM_KEY,
        'action': 'add',
        'name': name,
        'phone': phone,
        'position': position,
        'telegram_user_id': telegram_user_id,
        'telegram_username': telegram_username,
        'email': email
    }

    response = requests.post(CRM_URL, json=payload)

    if response.status_code == 200:
        data = response.json()
        try:
            employee_crm_id = data.get('data').get('employee').get('id')
            print(f'Employee {name} added to CRM with id {employee_crm_id}')
            return employee_crm_id
        except AttributeError:
            print(f'Error {response.status_code}: {response.text}')
            return
    else:
        print(f'Error {response.status_code}: {response.text}')
        return None


def delete_employee_from_crm(crm_user_id):
    payload = {
        'key': CRM_KEY,
        'action': 'delete',
        'id': crm_user_id
    }

    response = requests.post(CRM_URL, json=payload)

    if response.status_code == 200:
        data = response.json()
        try:
            response_message = data.get('data')
            print(response_message)
            return
        except AttributeError:
            print(f'Error {response.status_code}: {response.text}')
            return


def update_employee_in_crm(crm_user_id, name, phone, position, telegram_user_id, telegram_username, email):
    payload = {
        'key': CRM_KEY,
        'action': 'update',
        'id': crm_user_id,
        'name': name,
        'phone': phone,
        'position': position,
        'telegram_user_id': telegram_user_id,
        'telegram_username': telegram_username,
        'email': email
    }

    response = requests.post(CRM_URL, json=payload)

    if response.status_code == 200:
        data = response.json()
        try:
            response_message = data.get('data')
            print(response_message)
            return
        except AttributeError:
            print(f'Error {response.status_code}: {response.text}')
            return
    else:
        print(f'Error {response.status_code}: {response.text}')
        return None


def send_rating_to_crm(ticket_id, rating):
    payload = {
        'key': CRM_KEY,
        'action': 'rate',
        'idTicket': ticket_id,
        'rating': rating
    }

    response = requests.post(CRM_URL, json=payload)

    if response.status_code == 200:
        data = response.json()
        try:
            response_message = data.get('data')
            print(response_message)
            return response_message
        except AttributeError:
            print(f'Error {response.status_code}: {response.text}')
            return None
    else:
        print(f'Error {response.status_code}: {response.text}')
        return None
