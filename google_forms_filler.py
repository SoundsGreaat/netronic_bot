from gforms import Form
from fake_useragent import FakeUserAgent
import requests
import os


class FormFiller:
    def __init__(self, url):
        self.url = url
        self.sess = requests.session()
        self.ua = FakeUserAgent()
        self.sess.headers['User-Agent'] = self.ua.chrome
        self.form = Form()
        self.form.load(url=self.url, session=self.sess)

    def callback(self, element, page_index, element_index):
        ans = input(f'{element.name}: ')
        return ans

    def fill_form(self, callback=None):
        self.form.fill(callback)
        self.form.submit(emulate_history=True)

    def name(self):
        return self.form.name

    def description(self):
        return self.form.description

    def title(self):
        return self.form.title


def main():
    form_url = os.getenv('FORM_URL')
    form_filler = FormFiller(form_url)
    form_filler.fill_form(form_filler.callback)
    print('Form filled successfully')


if __name__ == "__main__":
    main()
