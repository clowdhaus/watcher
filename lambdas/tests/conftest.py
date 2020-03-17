# -*- coding: utf-8 -*-

import json
import os
import sys
from typing import Dict

import boto3
import moto
from _pytest.monkeypatch import MonkeyPatch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

REGION = 'us-east-1'
SECRET_NAME = os.environ.get('SLACK_SECRET_NAME', 'slack-security-bot')
SECRET_PAYLOAD = {
    'client_id': 123,
    'client_secret': 'xyz',
    'signing_secret': 'abc',
    'verification_token': 999,
    'oauth_access_token': '123abc',
    'bot_user_oauth_access_token': 'abc123',
    'elevate_access_channel_webhook': 'http://127.0.0.1:9000',
}


def secret_client():
    with moto.mock_secretsmanager():
        session = boto3.session.Session(region_name=REGION)
        return session.client(
            service_name='secretsmanager', endpoint_url=f'https://secretsmanager.{REGION}.amazonaws.com'
        )


def create_secret(name: str = SECRET_NAME, payload: Dict = SECRET_PAYLOAD):
    with moto.mock_secretsmanager():
        client = secret_client()
        client.create_secret(Name=name, Description='My cool test secret', SecretString=json.dumps(payload))


def pytest_generate_tests(metafunc):
    monkeypatch = MonkeyPatch()
    monkeypatch.setitem(os.environ, 'SLACK_SECRET_NAME', 'slack-security-bot')
    create_secret()
