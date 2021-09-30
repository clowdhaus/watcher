# -*- coding: utf-8 -*-
"""
    Hub
    ---

    Module used for interacting with GitHub

"""

import boto3
import github
from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.tracing import Tracer
from github import Github
from github.Repository import Repository

import functools
import hashlib
import hmac
import json
import os
from enum import Enum
from lambdas import sns
from typing import Dict, List

REGION = os.environ.get('REGION', 'us-east-1')
SSM_CLIENT = boto3.client('ssm', region_name=REGION)
JSON_CONTENT = {'Content-Type': 'application/json; charset=utf-8'}

#: Common SNS topic base (prefix)
SNS_TOPIC_BASE = f'{os.environ.get("SNS_ARN_PREFIX")}:Watcher'

#: Tracing via X-Ray
tracer = Tracer()
logger = Logger()


class GithubEvent(Enum):
    """Collection of GitHub events"""

    tag = 'tag'
    pull_request = 'pull_request'
    repository = 'repository'

    @property
    def topic_arn(self) -> str:
        """Returns event full SNS topic ARN"""
        topic = ''.join([x.title() for x in self.value.split('_')])
        return f'{SNS_TOPIC_BASE}-{topic}'


@functools.lru_cache()
def _get_github_secret() -> str:
    """
    Get GitHub webhook secret from SSM parameter store.

    :returns: GitHub webhook secret value
    """
    response = SSM_CLIENT.get_parameter(Name='/watcher/github_webhook_secret', WithDecryption=True)
    return response.get('Parameter', {}).get('Value', '')


@functools.lru_cache()
def get_github_user_token() -> str:
    """
    Get GitHub user access token from SSM parameter store.

    :returns: GitHub user access token value
    """
    response = SSM_CLIENT.get_parameter(Name='/watcher/github_user_token', WithDecryption=True)
    return response.get('Parameter', {}).get('Value', '')


@functools.lru_cache()
def get_github_repo(repo: str) -> Repository:
    """
    Get GitHub repository object.

    :param repo: full name of GitHub repository to retrieve
    :returns: GitHub repository object
    """
    token = get_github_user_token()
    git = Github(token)
    return git.get_repo(repo)


@functools.lru_cache()
def get_github_repos(org: str) -> List[Repository]:
    """
    Get GitHub organization's repository objects.
        Note: we are only getting sources as these are the ones we can control

    :param repo: name of GitHub organization to retrieve repositories from
    :returns: array of GitHub repository objects
    """
    org = get_github_org(org)
    return org.get_repos(type='sources', sort='updated', direction='desc')


@functools.lru_cache()
def get_github_org(org: str) -> github.Organization:
    """
    Get GitHub organization object.

    :param repo: name of GitHub organization to retrieve
    :returns: GitHub organization object
    """
    token = get_github_user_token()
    git = Github(token)
    return git.get_organization(org)


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
        logger.exception(
            {'operation': '_valid_signature', 'expected': signature_parts[1], 'computed': computed_signature}
        )
        return False
    return True


def _distribute_payload(payload: Dict):
    """
    Send payload over appropriate SNS topic based on Github event type.

    :param payload: GitHub webhook event payload body
    :returns: None
    """
    event = None

    if payload.get('repository'):
        event = GithubEvent.repository
    if payload.get('ref_type') == 'tag':
        event = GithubEvent.tag
    if payload.get('pull_request') and payload.get('number'):
        event = GithubEvent.pull_request

    if event:
        logger.info(f'Topic Arn: {event.topic_arn}')
        sns.emit_sns_msg(message={event.value: payload}, topic_arn=event.topic_arn)


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def receive(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function to receive and validate GitHub webhooks before passing along payload.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    raw = event.get('body')
    body = json.loads(raw)
    logger.info('Webhook received')

    #: Add in webhook "name"
    body.update({'X-GitHub-Event': event.get('headers', {}).get('X-GitHub-Event')})

    if _valid_signature(headers=event.get('headers'), body=raw):
        _distribute_payload(payload=body)
        return {
            'statusCode': 202,
            'body': 'GitHub signature verified',
            'headers': {**JSON_CONTENT, 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Credentials': True},
        }
    err = {
        'statusCode': 403,
        'body': 'GitHub signature does not match',
        'headers': {**JSON_CONTENT},
    }
    logger.exception(err)
    return err
