# -*- coding: utf-8 -*-
"""
    Versions
    ---------

    Module used for responding to GitHub tag events

"""

import json
import os
import re
from typing import Dict

from lambdas import dynamodb, hub, sns
from lambdas.hub import GithubEventType

#: DynamoDB table for versions
VERSION_TABLE = os.environ.get('VERSION_TABLE')
#: Name of repository where metadata will be displayed
METADATA_REPO = 'clowdhaus/metadata'


def _get_tag_data(payload: Dict) -> Dict:
    """
    Extract tag data from triggered event.

    :param payload: tag event payload
    :returns: tag data object
    """
    repository = payload.get('repository', {})
    repo_full_name = repository.get('full_name')
    repo = hub.get_github_repo(repo_full_name)
    tags = repo.get_tags()

    return {'repository': repo_full_name, 'versions': [t.name for t in tags]}


def _update_version_table(data: dict):
    """
    Update version dynamodb table based on data provided.

    :param data: data to add/update within table
    :returns: None
    """
    repo_full_name = data.get('repository')
    key = {'repository': repo_full_name}

    try:
        #: Versions added/removed
        expression = f'SET versions = :versions)'
        attr_values = {
            ':versions': data.get('versions'),
        }
        dynamodb.update_item(key=key, expression=expression, attr_values=attr_values)
    except Exception:
        #: Very first version
        key.update(data)
        dynamodb.put_item(item=key, table=VERSION_TABLE)


def new_tag(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function that responds to new tag events.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key=GithubEventType.tag.value)
    print(json.dumps(msg))

    #: Extract data and update DynamoDB table
    data = _get_tag_data(payload=msg)
    _update_version_table(data=data)

    #: No message payload, just triggering update to versions section of README
    sns.emit_sns_msg(message={})


def create_release(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function that responds to new tag events to create a release.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key=GithubEventType.tag.value)
    print(json.dumps(msg))

    if msg.get('X-GitHub-Event') == 'create':
        updated_repo = hub.get_github_repo(msg.get('repository', {}).get('full_name'))
        master = updated_repo.get_branch('master')
        tag_name = msg.get('ref')
        ref = updated_repo.get_git_ref(f'tags/{tag_name}')
        tag = updated_repo.get_git_tag(sha=ref.object.sha)
        message = f'### {tag_name}\n\n- {tag.message.lstrip("-").strip()}\n'

        updated_repo.create_git_release(
            tag=tag_name, name=tag_name, message=message, draft=False, prerelease=False, target_commitish=master
        )


def update_readme(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function to update versions section of metadata repo README file.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    readme = 'README.md'
    meta_repo = hub.get_github_repo(METADATA_REPO)
    file = meta_repo.get_contents(readme)
    result = ''

    #: Iterate over all records
    paginator = dynamodb.CLIENT.get_paginator('scan')
    iterator = paginator.paginate(TableName=VERSION_TABLE)
    for itr in iterator:
        items = itr.get('Items')
        for item in items:
            data = dynamodb.deserialize(item)
            repo, versions = data.get('repository'), data.get('versions')

            #: Create a section per repository with all versions listed under dropdown
            url = lambda v: f'https://github.com/{repo}/releases/tag/{v}'
            lis = '\n\t'.join([f'<li><a href="{url(v)}">{v}</a></li>' for v in versions])
            content = f'''
#### `{repo.split("/")[1]}` : [{versions[0]}]({url(versions[0])})

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
    meta_repo.update_file(path=readme, message='Tag section updated in README', content=final_content, sha=file.sha)
