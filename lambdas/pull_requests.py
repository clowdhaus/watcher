# -*- coding: utf-8 -*-
"""
    Pull Requests
    -------------

    Module used for responding to GitHub pull request events

"""

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.tracing import Tracer
from github.Repository import Repository

import os
import re
from datetime import datetime
from lambdas import dynamodb, hub, sns
from lambdas.hub import GithubEvent
from typing import Dict, List

#: DynamoDB table for pull requests
PR_TABLE = os.environ.get('PULL_REQUEST_TABLE')
#: Datetime format
DATE_FORMAT = '%Y-%m-%d'
#: Name of repository where metadata will be displayed
METADATA_REPO = os.environ.get('GITHUB_METADATA_REPO')
#: GitHub Organization to collect data from
ORGANIZATION = os.environ.get('GITHUB_ORGANIZATION')

#: Tracing via X-Ray
tracer = Tracer()
logger = Logger()


def _get_pull_request_data(payload: Dict) -> Dict:
    """
    Extract pull request data from triggered event.

    :param payload: pull request event payload
    :returns: pull request data object
    """
    repo_full_name = payload.get('repository', {}).get('full_name')
    pr = payload.get('pull_request')

    return {
        'repository': repo_full_name,
        'pull_request': pr.get('number'),
        'url': pr.get('html_url'),
        'user': pr.get('user', {}).get('login'),
        'date': pr.get('created_at').split('T')[0],
        'branch': pr.get('head', {}).get('ref'),
        'mergeable': pr.get('mergeable'),
        'mergeable_state': pr.get('mergeable_state'),
    }


def _get_repository_pull_requests(repo: Repository) -> List[Dict]:
    """
    Get pull request data from repository provided.

    :param repo: Github repository object
    :returns: array of pull request data objects for given repository
    """
    repo_full_name = repo.full_name
    prs = repo.get_pulls(state='open', sort='created')
    return [
        {
            'repository': repo_full_name,
            'pull_request': pr.number,
            'url': pr.url,
            'user': pr.user.login,
            'date': pr.created_at.strftime(DATE_FORMAT),
            'branch': pr.head.ref,
            'mergeable': pr.mergeable,
            'mergeable_state': pr.mergeable_state,
        }
        for pr in prs
    ]


def _update_pull_request_table(action: str, data: dict):
    """
    Update pull request dynamodb table based on action and data provided.

    :param action: event action type, determines table modification action
    :param data: data to add/update within table
    :returns: None
    """
    #: Evaluate record action - delete, update, add
    if action in {'closed'}:
        key = {'repository': data.get('repository'), 'pull_request': data.get('pull_request')}
        dynamodb.delete_item(key=key, table=PR_TABLE)
    else:
        age = (datetime.now() - datetime.strptime(data.get('date'), DATE_FORMAT)).days
        dynamodb.put_item(item={**data, 'age': age}, table=PR_TABLE)


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def pull_request(event: Dict, _c: Dict):
    """
    Lambda function that responds to pull request events.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key=GithubEvent.pull_request.value)
    logger.info({'operation': 'pull_request', 'sns_payload': msg})

    #: Extract data and update DynamoDB table
    action = msg.get('action')
    data = _get_pull_request_data(payload=msg)
    _update_pull_request_table(action=action, data=data)

    #: No message payload, just triggering update to pull request section of README
    sns.emit_sns_msg(message={})


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def update_readme(event: Dict, _c: Dict):
    """
    Lambda function to update pull request section of metadata repo README file.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    logger.info({'operation': 'update_readme'})
    readme = 'README.md'
    meta_repo = hub.get_github_repo(METADATA_REPO)
    file = meta_repo.get_contents(readme)

    #: Output is rendered as markdown table
    header = '| Repository | PR | Branch | User | Age (days) |\n| --- | --- | --- | --- | --- |\n'
    rows = ''

    #: Create a row per record/pull request
    paginator = dynamodb.CLIENT.get_paginator('scan')
    iterator = paginator.paginate(TableName=PR_TABLE)
    for itr in iterator:
        items = itr.get('Items')
        for item in items:
            data = dynamodb.deserialize(item)
            days = (datetime.now() - datetime.strptime(data.get('date'), '%Y-%m-%d')).days
            repo, pr = data.get('repository'), data.get('pull_request')
            row = f"|{repo}|[#{pr}]({data.get('url')})|{data.get('branch')}|{data.get('user')}|{days}|\n"
            rows += row
    final = header + rows

    #: Make sure target replacement tags are put back for next update
    result = f'<!-- PR Start -->\n{final}\n<!-- PR End -->'
    final_content = re.sub(
        '<!-- PR Start -->.*?<!-- PR End -->', result, file.decoded_content.decode('utf-8'), flags=re.DOTALL
    )
    meta_repo.update_file(
        path=readme, message='Pull request section updated in README', content=final_content, sha=file.sha
    )


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def sync(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function to sync all repository pull requests.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    logger.info({'operation': 'sync'})
    #: Purge table first before re-populating
    dynamodb.delete_all_items(key_ids=['repository', 'pull_request'], table=PR_TABLE)

    for repo in hub.get_github_repos(org=ORGANIZATION):
        #: Extract data and update DynamoDB table
        for data in _get_repository_pull_requests(repo=repo):
            _update_pull_request_table(action='sync', data=data)

    #: No message payload, just triggering update to versions section of README
    sns.emit_sns_msg(message={})
