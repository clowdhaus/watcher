# -*- coding: utf-8 -*-
"""
    GitHub
    ------

    Module used for interacting with GitHub

"""

import functools
import hashlib
import hmac
import json
import os
import time
from typing import Dict

import boto3

from lambdas import sns
from lambdas.log import log

REGION = os.environ.get('REGION', 'us-east-1')
SSM_CLIENT = boto3.client('ssm', region_name=REGION)

#: JSON content type
JSON_CONTENT = {'Content-Type': 'application/json; charset=utf-8'}

SNS_TOPIC_BASE = f'{os.environ.get("SNS_ARN_PREFIX")}:Watcher'


@functools.lru_cache()
def _get_github_secret() -> str:
    """
    Get GitHub webhook secret from SSM parameter store.

    :returns: GitHub webhook secret value
    """
    response = SSM_CLIENT.get_parameter(Name='/watcher/github_webhook_secret', WithDecryption=True)
    return response.get('Parameter', {}).get('Value', '')


def _valid_signature(headers: Dict, body: str) -> bool:
    """
    Determine if request signature is valid.

    :param headers: dictionary of request headers
    :param body: json encoded webhook body
    :returns: boolean depicting validity of signature received
    """
    signing_secret = _get_github_secret().encode('utf-8')
    signature_parts = headers.get('X-Hub-Signature', '').split('=', 1)
    computed_signature = hmac.new(signing_secret, body.encode('utf-8'), digestmod=hashlib.sha1).hexdigest()

    if not hmac.compare_digest(signature_parts[1], computed_signature):
        log.error('GitHub signature does not match', expected=signature_parts[1], computed=computed_signature)
        return False
    return True


def _distribute_payload(payload: Dict):
    if payload.get('ref_type') == 'tag':
        topic_arn = f'{SNS_TOPIC_BASE}-Tag'

    sns.emit_sns_msg(message={'tag': payload}, topic_arn=topic_arn)


def receive(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function to receive and validate GitHub webhooks before passing along payload.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    body = event.get('body')
    if _valid_signature(headers=event.get('headers'), body=body):
        print(body)
        _distribute_payload(payload=json.loads(body))
        return {
            'statusCode': 202,
            'body': 'GitHub signature verified',
            'headers': {**JSON_CONTENT, 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Credentials': True},
        }
    return {
        'statusCode': 403,
        'body': 'GitHub signature does not match',
        'headers': {**JSON_CONTENT},
    }


def new_tag(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function that responds to new tag events.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key='tag')
    log.info(message=msg)


if __name__ == '__main__':
    with open('event.json', 'r') as infile:
        event = json.load(infile)
    receive(event, {})
