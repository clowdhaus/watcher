# -*- coding: utf-8 -*-
"""
    Pull Requests
    -------------

    Module used for responding to GitHub pull request events

"""

import json
import os
import re
from datetime import datetime
from typing import Dict

from lambdas import dynamodb, hub, sns
from lambdas.hub import GithubEventType

#: DynamoDB table for pull requests
PR_TABLE = os.environ.get('PULL_REQUEST_TABLE')
#: Name of repository where metadata will be displayed
METADATA_REPO = 'clowdhaus/metadata'


def _get_pull_request_data(payload: Dict) -> Dict:
    """
    Extract pull request data from triggered event.

    :param payload: pull request event payload
    :returns: overall pull request data object
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


def _update_pull_request_table(action: str, data: dict):
    """
    Update pull request dynamodb table based on action and data provided.

    :param action: event action type, determines table modification action
    :param data: data to add/update within table
    :returns: None
    """
    key = {'repository': data.get('repository'), 'pull_request': data.get('pull_request')}

    #: Evaluate record action - delete, update, add
    if action in {'closed'}:
        dynamodb.delete_item(key=key, table=PR_TABLE)
    else:
        age = (datetime.now() - datetime.strptime(data.get('date'), '%Y-%m-%d')).days
        try:
            #: Any dynamic changes to update
            expression = f'SET age = :age'
            attr_values = {
                ':age': age,
            }
            dynamodb.update_item(key=key, expression=expression, attr_values=attr_values)
        except Exception:
            key.update(data)
            dynamodb.put_item(item=key, table=PR_TABLE)


def pull_request(event: Dict, _c: Dict):
    """
    Lambda function that responds to pull request events.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key=GithubEventType.pull_request.value)
    print(json.dumps(msg))

    #: Extract data and update DynamoDB table
    action = msg.get('action')
    data = _get_pull_request_data(payload=msg)
    _update_pull_request_table(action=action, data=data)

    #: No message payload, just triggering update to pull request section of README
    sns.emit_sns_msg(message={})


def update_readme(event: Dict, _c: Dict):
    """
    Lambda function to update pull request section of metadata repo README file.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    readme = 'README.md'
    meta_repo = hub.get_github_repo(METADATA_REPO)
    file = meta_repo.get_contents(readme)

    #: Output is rendered as markdown table
    header = '| Repository | PR | Branch | User | Days Old |\n| --- | --- | --- | --- | --- |\n'
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
    result = f'<!-- PR Start -->\n{final}\n<!-- PR End -->\n'
    final_content = re.sub(
        '<!-- PR Start -->.*?<!-- PR End -->', result, file.decoded_content.decode('utf-8'), flags=re.DOTALL
    )
    meta_repo.update_file(
        path=readme, message='Pull request section updated in README', content=final_content, sha=file.sha
    )
