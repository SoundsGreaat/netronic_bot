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
