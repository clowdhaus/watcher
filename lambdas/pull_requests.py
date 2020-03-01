# -*- coding: utf-8 -*-
"""
    Pull Requests
    -------------

    Module used for responding to GitHub pull request events

"""

import json
import re
from datetime import datetime
from typing import Dict

import github

from lambdas import hub, sns
from lambdas.hub import GithubEventType


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


def pull_request(event: Dict, _c: Dict):
    """
    Lambda function that responds to pull request events.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key=GithubEventType.pull_request.value)
    print(json.dumps(msg))

    metadata_repo = hub.get_github_repo('clowdhaus/metadata')

    if msg.get('action') in ['opened', 'synchronize', 'reopened', 'closed']:
        data = _get_pull_request_data(metadata_repo=metadata_repo, payload=msg)
        _update_readme_pull_requests(repo=metadata_repo, data=data)
