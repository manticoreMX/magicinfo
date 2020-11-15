import collections
import logging
import os
import re
import requests
import typing

from datetime import datetime
from dotenv import load_dotenv
from xml.etree import ElementTree as ET

load_dotenv()

URL = os.getenv('URL')
LOGIN = os.getenv('LOGIN')
PASSWORD = os.getenv('PASSWORD')

AUTH = '/auth'
TOKEN = '/openapi/auth'
DEVICES = '/restapi/v1.0/rms/devices/'
DEVICE = '/restapi/v1.0/rms/devices/{}'
SETUP = '/restapi/v1.0/rms/devices/{}/setup'
GENERAL = '/restapi/v1.0/rms/devices/{}/general'
TIME_INFO = 'GET /restapi/v1.0/rms/devices/{}/time'
RESTART = 'openapi/open'

DID = '84-a4-66-a3-52-d4'
MAC_PATTERN = '(([0-9a-f]{2}([-:]?)){5}[0-9a-f]{2})'


class Display(object):
    def __init__(self, kwargs: dict):
        [setattr(self, key, value) for key, value in kwargs.items()]


class MiApi(object):
    def __init__(self, url: str, login: str, password: str):
        self.url = url
        self.login = login
        self.password = password
        self.session = requests.session()
        self.api_key = None
        self.token = None
        self.devices_list = []

        self.get_api_key()
        self.get_token()

    @property
    def headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "api_key": self.api_key
        }

    def my_request(self, path: str, method: str, params: dict = None, json: dict = None, data: dict = None,
                   text: bool = False) -> typing.Union[dict, str, None]:
        set_method = {
            'GET': self.session.get,
            'POST': self.session.post,
            'PUT': self.session.put
        }

        url = self.url + path
        request = set_method[method](url, headers=self.headers, params=params, json=json, data=data, verify=False)

        if request.status_code == 200:
            logging.debug('Got response!')
            return request.text if text else request.json()
        else:
            logging.debug(f'Got response code {request.status_code}')
            print(f'Что-то пошло не так. Код ошибки {request.status_code}')

    def get_api_key(self) -> None:
        logging.debug("Authentication swagger")
        data = {'username': self.login, 'password': self.password}
        request = self.my_request(AUTH, 'POST', json=data)

        if request:
            self.api_key = request['token']

    def get_token(self) -> None:
        logging.debug("Getting token OpenAPI")
        params = {
            'cmd': 'getAuthToken',
            'id': self.login,
            'pw': self.password
        }
        request = self.my_request(TOKEN, 'GET', params=params, text=True)

        if request:
            tree = ET.fromstring(request)
            self.token = list(tree.itertext())[1]

    def get_devices_list(self, start_index: int = 0, page_size: int = 9999) -> None:
        logging.debug("Getting devices list")

        params = {'startIndex': start_index, 'pageSize': page_size}
        self.devices_list = self.my_request(DEVICES, 'GET', params=params)['items']

    def check_power(self, device_id: str) -> bool:
        logging.debug(f"Checking display {device_id} power")

        request = self.my_request(DEVICE.format(device_id), 'GET')
        if request:
            return bool(request['items']['power'])

    def get_server_url(self, device_id: str) -> dict:
        logging.debug("Getting MagicInfo server")

        request = self.my_request(SETUP.format(device_id), 'GET')

        if request:
            return request

    def set_new_server_url(self, device_id: str, url: str) -> typing.Union[bool, None]:
        logging.debug("Updating MagicInfo server")

        data = {'magicinfoServerUrl': url}
        request = self.my_request(SETUP.format(device_id), 'PUT', json=data)

        if request:
            return True

    def restart(self, device_id: str) -> typing.Union[bool, None]:
        self.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        params = {'token': self.token}
        data = {'service': 'PremiumDeviceService.restartDevice', 'deviceId': '84-a4-66-a3-52-d4'}
        request = self.my_request(RESTART, 'POST', params=params, data=data)

        if request:
            return True


kfc = MiApi(URL, LOGIN, PASSWORD)

devices_list = []
with open('mac.txt', 'r', encoding='utf8') as file:
    for mac in file.readlines():
        if re.fullmatch(MAC_PATTERN, mac.strip()):
            devices_list.append(Display({'deviceId': mac.strip()}))
        else:
            print(f'{mac} выглядит неправильным')

for device in devices_list:
    if kfc.check_power(device.deviceId):
        kfc.devices_list.append(device)
    else:
        print(f'{device.deviceId} недоступен (выключен или нет на сервере). Ничего с ним не сделаю.')

for device in devices_list:
    for key, value in kfc.get_server_url(device.deviceId)['items'].items():
        if not hasattr(device, key):
            setattr(device, key, value)

    if device.magicinfoServerUrl != kfc.url:
        print(f'{device.deviceId}: меняю {device.magicinfoServerUrl} на {kfc.url}')
        request = kfc.set_new_server_url(kfc.url, device.deviceId)

        if request:
            print(f'{device.deviceId} перезагружаю')
            request = kfc.restart(device.deviceId)

            if request:
                kfc.devices_list.append(device.deviceId)
                print(f'{device.deviceId} готово!')
            else:
                print(f'{device.deviceId} ошибка перезагрузки')
        else:
            print(f'{device.deviceId} ошибка настройки адреса сервера')

    else:
        print(f'{device.deviceId}: адрес уже {device.magicinfoServerUrl}')




# kfc.get_devices_list()
# dmd = kfc.devices_list[1809]
# print(kfc.check_power(dmd['deviceId']))