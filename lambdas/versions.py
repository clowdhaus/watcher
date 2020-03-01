# -*- coding: utf-8 -*-
"""
    Versions
    ---------

    Module used for responding to GitHub tag events

"""

import json
import re
from typing import Dict

import github

from lambdas import hub, sns
from lambdas.hub import GithubEventType


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

    metadata_repo = hub.get_github_repo('clowdhaus/metadata')
    updated_repo = hub.get_github_repo(msg.get('repository', {}).get('full_name'))

    data = _get_tag_data(metadata_repo=metadata_repo, updated_repo=updated_repo)
    _update_readme_tags(repo=metadata_repo, data=data)


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
