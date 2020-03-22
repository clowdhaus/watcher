# -*- coding: utf-8 -*-
"""
    Repository
    ----------

    Module used for configuring GitHub repositories

"""

import functools
import json
import os
import time
from itertools import filterfalse
from typing import Dict, Optional

import yaml
from github.Repository import Repository

from lambdas import hub, sns
from lambdas.hub import GithubEvent
from lambdas.log import log

#: GitHub Organization to collect data from
ORGANIZATION = os.environ.get('GITHUB_ORGANIZATION')

# - Sync repository labels (delete those not in config, add those in config not in repo)
# - Repository settings (porjects, private, squash merge, etc.)


@functools.lru_cache()
def _load_config(repo: str) -> Dict:
    """
    Load GitHub configuration from `config.yml` file.

    :returns: GitHub configuration
    """
    with open('lambdas/config.yml', 'r') as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    try:
        #: Attempt to update using repo overrides in config
        config['default'].update(config[repo])
    except KeyError:
        pass
    return config['default']


def _label_sync(repo: Repository):
    """
    Sync labels to settings in config file.

    :param repo: Github repository object to sync labels
    :returns: None
    """
    config = _load_config(repo=repo.name)
    base_labels = [x for x in config['labels']]
    repo_labels = [{'name': x.name, 'color': x.color, 'description': x.description} for x in repo.get_labels()]

    #: smart sync only changes that are necessary (add or delete)
    for diff in list(filterfalse(lambda x: x in base_labels, repo_labels)) + list(
        filterfalse(lambda x: x in repo_labels, base_labels)
    ):
        try:
            repo.get_label(name=diff['name']).delete()
        except Exception:
            print(json.dumps(diff))
            pass
        finally:
            repo.create_label(name=diff['name'], color=diff['color'], description=diff['description'])


def _repo_settings_sync(repo: Repository):
    """
    Sync repository settings to settings in config file.

    :param repo: Github repository object to sync settings
    :returns: None
    """
    config = _load_config(repo=repo.name)
    default_branch = config.get('default_branch', {})

    repo.edit(
        private=config.get('private'),
        has_issues=config.get('has_issues'),
        has_projects=config.get('has_projects'),
        has_wiki=config.get('has_wiki'),
        default_branch=default_branch.get('name'),
        allow_squash_merge=config.get('allow_squash_merge'),
        allow_merge_commit=config.get('allow_merge_commit'),
        allow_rebase_merge=config.get('allow_rebase_merge'),
        delete_branch_on_merge=config.get('delete_branch_on_merge'),
    )
    if config.get('enable_vulnerability_alert'):
        repo.enable_vulnerability_alert()
    else:
        repo.disable_vulnerability_alert()

    if config.get('enable_automated_security_fixes'):
        repo.enable_automated_security_fixes()
    else:
        repo.disable_automated_security_fixes()


def update(event: Dict, _c: Dict):
    """
    Lambda function that responds to repository events.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key=GithubEvent.repository.value)
    # log.info(msg)
    print(json.dumps(msg))
    action = msg.get('action')

    if action not in {'deleted', 'archived'}:
        full_name = msg.get('repository', {}).get('full_name')
        repo = hub.get_github_repo(repo=full_name)

        if action in {'created', 'unarchived', 'edited'}:
            time.sleep(5)
            _label_sync(repo=repo)

        _repo_settings_sync(repo=repo)
