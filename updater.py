import collections
import logging
import os
from datetime import datetime

import requests

from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

URL = os.getenv('URL')
LOGIN = os.getenv('LOGIN')
PASSWORD = os.getenv('PASSWORD')

AUTH = '/auth'
DEVICES = '/restapi/v1.0/rms/devices/'
DEVICE = '/restapi/v1.0/rms/devices/{}'
SETUP = '/restapi/v1.0/rms/devices/{}/setup'
GENERAL = '/restapi/v1.0/rms/devices/{}/general'
TIME_INFO = 'GET /restapi/v1.0/rms/devices/{}/time'




DID = '84-a4-66-a3-52-d4'


class MiApi(object):
    def __init__(self, url: str, login: str, password: str):
        self.url = url
        self.login = login
        self.password = password
        self.token = None
        self.session = requests.session()
        self.devices_list = []

        self.get_api_key()

    @property
    def headers(self):
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "api_key": self.token
        }

    def my_request(self, path: str, method: str, params: dict = None, json: dict = None) -> dict:
        set_method = {
            'GET': self.session.get,
            'POST': self.session.post,
            'PUT': self.session.put
        }

        url = self.url + path
        request = set_method[method](url, headers=self.headers, json=json, params=params)

        if request.status_code == 200:
            logging.debug('Got response!')
            return request.json()
        else:
            logging.debug(f'Got response code {request.status_code}')

    def get_api_key(self):
        logging.debug("Authentication")
        data = {'username': self.login, 'password': self.password}
        request = self.my_request(AUTH, 'POST', json=data)

        if request:
            self.token = request['token']

    def get_devices_list(self, start_index: int = 0, page_size: int = 9999) -> None:
        logging.debug("Getting devices list")

        params = {'startIndex': start_index, 'pageSize': page_size}
        self.devices_list = self.my_request(DEVICES, 'GET', params=params)['items']

    def check_power(self, _id: str) -> bool:
        logging.debug(f"Checking display {_id} power")

        request = self.my_request(DEVICE.format(_id), 'GET')
        if request:
            return request['items']['power']

    def get_server_url(self, _id: str) -> list:
        logging.debug("Getting MagicInfo server")

        request = self.my_request(SETUP.format(_id), 'GET')
        columns = ('deviceId', 'deviceName', 'deviceModelName', 'magicinfoServerUrl')

        return [request['items'][key] for key in columns]


kfc = MiApi(URL, LOGIN, PASSWORD)
kfc.get_devices_list()
dmd = kfc.devices_list[1809]
print(kfc.check_power(dmd['deviceId']))