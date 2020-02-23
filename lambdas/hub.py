# -*- coding: utf-8 -*-
"""
    Hub
    ---

    Module used for interacting with GitHub

"""

import functools
import hashlib
import hmac
import json
import os
import re
import time
from datetime import datetime
from enum import Enum
from typing import Dict

import boto3
import github
from github import Github

from lambdas import sns
from lambdas.log import log

REGION = os.environ.get('REGION', 'us-east-1')
SSM_CLIENT = boto3.client('ssm', region_name=REGION)

#: JSON content type
JSON_CONTENT = {'Content-Type': 'application/json; charset=utf-8'}

SNS_TOPIC_BASE = f'{os.environ.get("SNS_ARN_PREFIX")}:Watcher'


class GithubEventType(Enum):
    """GitHub event types"""

    tag = 'tag'
    pull_request = 'pull_request'


@functools.lru_cache()
def _get_github_secret() -> str:
    """
    Get GitHub webhook secret from SSM parameter store.

    :returns: GitHub webhook secret value
    """
    response = SSM_CLIENT.get_parameter(Name='/watcher/github_webhook_secret', WithDecryption=True)
    return response.get('Parameter', {}).get('Value', '')


@functools.lru_cache()
def _get_github_user_token() -> str:
    """
    Get GitHub user access token from SSM parameter store.

    :returns: GitHub user access token value
    """
    response = SSM_CLIENT.get_parameter(Name='/watcher/github_user_token', WithDecryption=True)
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
    """
    Send payload over appropriate SNS topic based on Github event type.

    :param payload: GitHub webhook event payload body
    :returns: None
    """
    #: TODO -Depending on other ref_types, could use GithubEventType enum
    if payload.get('ref_type') == 'tag':
        key = 'tag'
        topic_arn = f'{SNS_TOPIC_BASE}-Tag'

    sns.emit_sns_msg(message={key: payload}, topic_arn=topic_arn)


def receive(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function to receive and validate GitHub webhooks before passing along payload.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    body = event.get('body')
    print(body)
    if _valid_signature(headers=event.get('headers'), body=body):
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


def _get_data(metadata_repo: github.Repository, updated_repo: github.Repository, event_type: GithubEventType) -> Dict:
    """
    Extract data from event, persist in metatdata repo json files before returning.

    :param metadata_repo: repository where overall data objects are stored
    :param updated_repo: repository that triggered change
    :param event_type: type of Github event that triggered update
    :returns: overall data object for event type (tag, pull request, etc.)
    """
    #: Load existing data from metadata repo
    data_filepath = f'data/{event_type.value}.json'
    update_repo_fullname = updated_repo.full_name
    data_file = metadata_repo.get_contents(data_filepath)
    data = json.loads(data_file.decoded_content)

    if event_type is GithubEventType.tag:
        key = 'tag'
        tags = updated_repo.get_tags()
        url = f'https://github.com/{update_repo_fullname}/releases/tag'
        updated_values = [{'tag': t.name, 'url': f'{url}/{t.name}'} for t in tags]

    data.update({update_repo_fullname: updated_values})

    #: Write back to metadata repository for storage
    metadata_repo.update_file(
        path=data_filepath,
        message=f'{update_repo_fullname} {key} {updated_values[0].get(key)} added',
        content=json.dumps(data),
        sha=data_file.sha,
    )
    return data


def _update_readme_tags(repo: github.Repository, data: Dict):
    """
    Update metdata tag section of README file.

    :param repo: metadata repository object
    :param data: data object containing tag data
    :returns: None
    """
    readme = 'README.md'
    file = repo.get_contents(readme)
    result = ''

    #: Create a section per module repo
    for module, tags in data.items():
        lis = '\n\t'.join([f'<li><a href="{t.get("url")}">{t.get("tag")}</a></li>' for t in tags])
        content = f'''
#### `{module.split("/")[1]}` : [{tags[0].get("tag")}]({tags[0].get("url")})

<details>
<summary>All Tags</summary>
    <ul>
        {lis}
    </ul>
</details>
    '''
        result += content
    #: Make sure tags are put back for next update
    result = f'<!-- Tag Start -->\n{result}\n<!-- Tag End -->\n'
    final_content = re.sub(
        '<!-- Tag Start -->.*?<!-- Tag End -->', result, file.decoded_content.decode('utf-8'), flags=re.DOTALL
    )
    repo.update_file(path=readme, message='Tag section updated in README', content=final_content, sha=file.sha)


def new_tag(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function that responds to new tag events.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key='tag')
    print(json.dumps(msg))

    token = _get_github_user_token()
    git = Github(token)
    metadata_repo = git.get_repo('clowdhaus/metadata')
    updated_repo = git.get_repo(msg.get('repository', {}).get('full_name'))

    data = _get_data(metadata_repo=metadata_repo, updated_repo=updated_repo, event_type=GithubEventType.tag)
    _update_readme_tags(repo=metadata_repo, data=data)
