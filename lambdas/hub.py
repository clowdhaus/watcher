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


@functools.lru_cache()
def _get_github_repo(repo: str) -> github.Repository:
    """
    Get GitHub repository object.

    :param repo: full name of GitHub repository to retrieve
    :returns: GitHub repository object
    """
    token = _get_github_user_token()
    git = Github(token)
    return git.get_repo(repo)


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
    key, topic_arn = '', ''
    if payload.get('ref_type') == 'tag':
        key = 'tag'
        topic_arn = f'{SNS_TOPIC_BASE}-Tag'
    if payload.get('pull_request'):
        key = 'pull_request'
        topic_arn = f'{SNS_TOPIC_BASE}-Pull-Request'

    if key and topic_arn:
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


def _get_tag_data(metadata_repo: github.Repository, updated_repo: github.Repository) -> Dict:
    """
    Extract tag data from event, persist in metatdata repo json files before returning.

    :param metadata_repo: repository where overall data objects are stored
    :param updated_repo: repository that triggered change
    :returns: overall tag data object
    """
    #: Load existing data from metadata repo
    key = GithubEventType.tag.value
    data_filepath = f'data/{key}.json'
    update_repo_fullname = updated_repo.full_name
    data_file = metadata_repo.get_contents(data_filepath)
    data = json.loads(data_file.decoded_content)

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
    for module, tags in sorted(data.items()):
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
    result = f'<!-- Tag Start -->\n{result}\n<!-- Tag End -->'
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
    msg = sns.get_sns_msg(event=event, msg_key=GithubEventType.tag.value)
    print(json.dumps(msg))

    metadata_repo = _get_github_repo('clowdhaus/metadata')
    updated_repo = _get_github_repo(msg.get('repository', {}).get('full_name'))

    data = _get_tag_data(metadata_repo=metadata_repo, updated_repo=updated_repo, event_type=GithubEventType.tag)
    _update_readme_tags(repo=metadata_repo, data=data)


def _get_pull_request_data(metadata_repo: github.Repository, payload: Dict) -> Dict:
    """
    Extract pull request data from event, persist in metatdata repo json files before returning.

    :param metadata_repo: repository where overall data objects are stored
    :param payload: pull request event payload
    :returns: overall pull request data object
    """
    #: Load existing data from metadata repo
    key = GithubEventType.pull_request.value
    data_filepath = f'data/{key}.json'
    data_file = metadata_repo.get_contents(data_filepath)
    data = json.loads(data_file.decoded_content)

    repo_full_name = payload.get('repository', {}).get('full_name')
    pr = payload.get('pull_request')
    pr_number = pr.get('number')
    key = f'{repo_full_name}/{pr_number}'

    repo_data = data.get(repo_full_name, {})
    if payload.get('action') in ['opened', 'synchronize', 'reopened']:
        print(f'PAYLOAD IS: {payload.get("action")}')
        updated_data = {
            'pr': pr_number,
            'url': pr.get('html_url'),
            'user': pr.get('user', {}).get('login'),
            'date': pr.get('created_at').split('T')[0],
            'branch': pr.get('head', {}).get('ref'),
            'mergeable': pr.get('mergeable'),
            'mergeable_state': pr.get('mergeable_state'),
        }
        repo_data.update({key: updated_data})
    elif payload.get('action') == 'closed':
        try:
            del repo_data[key]
        except KeyError:
            pass

    print(json.dumps({repo_full_name: repo_data}))
    data.update({repo_full_name: repo_data})

    #: Write back to metadata repository for storage
    metadata_repo.update_file(
        path=data_filepath,
        message=f'{repo_full_name} {key.replace("_", "-")} #{pr_number} added',
        content=json.dumps(data),
        sha=data_file.sha,
    )
    return data


def _update_readme_pull_requests(repo: github.Repository, data: Dict):
    """
    Update metdata pull request section of README file.

    :param repo: metadata repository object
    :param data: data object containing tag data
    :returns: None
    """
    readme = 'README.md'
    file = repo.get_contents(readme)
    header = '| Repository | PR | Branch | User | Days Old |\n| --- | --- | --- | --- | --- |\n'
    rows = ''

    #: Create a row per pull request
    for repository, prs in sorted(data.items()):
        for pr, data in sorted(prs.items()):
            days = (datetime.now() - datetime.strptime(data.get('date'), '%Y-%m-%d')).days
            row = f"|{repository}|[#{data.get('pr')}]({data.get('url')})|{data.get('branch')}|{data.get('user')}|{days}|\n"
            rows += row

    final = header + rows
    #: Make sure tags are put back for next update
    result = f'<!-- PR Start -->\n{final}\n<!-- PR End -->\n'
    final_content = re.sub(
        '<!-- PR Start -->.*?<!-- PR End -->', result, file.decoded_content.decode('utf-8'), flags=re.DOTALL
    )
    repo.update_file(path=readme, message='Pull request section updated in README', content=final_content, sha=file.sha)


def pull_request(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function that responds to pull request events.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key=GithubEventType.pull_request.value)
    print(json.dumps(msg))

    metadata_repo = _get_github_repo('clowdhaus/metadata')

    if msg.get('action') in ['opened', 'synchronize', 'reopened', 'closed']:
        data = _get_pull_request_data(metadata_repo=metadata_repo, payload=msg)
        _update_readme_pull_requests(repo=metadata_repo, data=data)
