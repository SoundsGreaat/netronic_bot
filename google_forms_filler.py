from gforms import Form
from fake_useragent import FakeUserAgent
import requests
import os

url = os.getenv('FORM_URL')

sess = requests.session()
ua = FakeUserAgent()
sess.headers['User-Agent'] = ua.chrome


def callback(element, page_index, element_index):
    ans = input(f'{element.name}: ')
    return ans


form = Form()
form.load(url=url, session=sess)
form.fill(callback)
form.submit(emulate_history=True)
