import logging
import os
import re
import requests
import typing

from dotenv import load_dotenv
from xml.etree import ElementTree as ET
from requests.packages.urllib3.exceptions import InsecureRequestWarning

load_dotenv()
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

URL = os.getenv('URL')
LOGIN = os.getenv('LOGIN')
PASSWORD = os.getenv('PASSWORD')

AUTH = '/auth'
TOKEN = '/openapi/auth'
DEVICES = '/restapi/v1.0/rms/devices/'
DEVICE = '/restapi/v1.0/rms/devices/{}'
SETUP = '/restapi/v1.0/rms/devices/{}/setup'
GENERAL = '/restapi/v1.0/rms/devices/{}/general'
TIME_INFO = '/restapi/v1.0/rms/devices/{}/time'
RESTART = '/openapi/open'

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
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*"
        }

        self.devices_list = []
        self.devices_list_updated = []

        self.get_api_key()
        self.get_token()

    # @property
    # def headers(self) -> dict:
    #     return {
    #         "Content-Type": "application/json",
    #         "Accept": "application/json, text/plain, */*",
    #         "api_key": self.api_key
    #     }

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
            print(f'{request.text}')

    def get_api_key(self) -> None:
        logging.debug("Authentication swagger")
        data = {'username': self.login, 'password': self.password}
        _request = self.my_request(AUTH, 'POST', json=data)

        if _request:
            self.api_key = _request['token']
            self.headers.update({"api_key": self.api_key})

    def get_token(self) -> None:
        logging.debug("Getting token OpenAPI")
        params = {
            'cmd': 'getAuthToken',
            'id': self.login,
            'pw': self.password
        }
        _request = self.my_request(TOKEN, 'GET', params=params, text=True)

        if _request:
            tree = ET.fromstring(_request)
            self.token = list(tree.itertext())[1]

    def get_devices_list(self, start_index: int = 0, page_size: int = 9999) -> None:
        logging.debug("Getting devices list")

        params = {'startIndex': start_index, 'pageSize': page_size}
        self.devices_list = self.my_request(DEVICES, 'GET', params=params)['items']

    def check_power(self, device_id: str) -> bool:
        logging.debug(f"Checking display {device_id} power")

        _request = self.my_request(DEVICE.format(device_id), 'GET')
        if _request:
            return bool(_request['items']['power'])

    def get_server_url(self, device_id: str) -> dict:
        logging.debug("Getting MagicInfo server")

        _request = self.my_request(SETUP.format(device_id), 'GET')

        if _request:
            return _request

    def set_new_server_url(self, device_id: str, url: str) -> typing.Union[bool, None]:
        logging.debug("Updating MagicInfo server")

        json = {'magicinfoServerUrl': url}
        _request = self.my_request(SETUP.format(device_id), 'PUT', json=json)

        if _request:
            return True

    def restart(self, device_id: str) -> typing.Union[bool, None]:
        self.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        params = {'token': self.token}
        data = {'service': 'PremiumDeviceService.restartDevice', 'deviceId': device_id}
        _request = self.my_request(RESTART, 'POST', params=params, data=data, text=True)
        self.headers.update({"Content-Type": "application/json"})

        if _request:
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

for device in kfc.devices_list:
    for key, value in kfc.get_server_url(device.deviceId)['items'].items():
        if not hasattr(device, key):
            setattr(device, key, value)

    if device.magicinfoServerUrl != kfc.url:
        print(f'{device.deviceId}: меняю {device.magicinfoServerUrl} на {kfc.url}')
        request = kfc.set_new_server_url(device.deviceId, kfc.url)

        if request:
            print(f'{device.deviceId} перезагружаю')
            request = kfc.restart(device.deviceId)

            if request:
                kfc.devices_list_updated.append(device)
                print(f'{device.deviceId} готово!')
            else:
                print(f'{device.deviceId} ошибка перезагрузки')
        else:
            print(f'{device.deviceId} ошибка настройки адреса сервера')

    else:
        print(f'{device.deviceId}: адрес уже {device.magicinfoServerUrl}')

print('\n', '=' * 10, 'РЕЗУЛЬТАТЫ', '=' * 10, end='\n')

print('\nНедоступны (выключен или нет на сервере):')
for device in set(devices_list) ^ set(kfc.devices_list):
    print(f'{device.deviceId}')

print('\nДоступны, но не обновлены:')
for device in set(kfc.devices_list) ^ set(kfc.devices_list_updated):
    print(f'{device.deviceId}')

print('\nOбновлены:')
for device in kfc.devices_list_updated:
    print(f'{device.deviceId}')
