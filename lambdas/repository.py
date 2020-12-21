# -*- coding: utf-8 -*-
"""
    Repository
    ----------

    Module used for configuring GitHub repositories

"""

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.tracing import Tracer
from github.Repository import Repository

import functools
import json
import os
import yaml
from itertools import filterfalse
from lambdas import hub, sns
from lambdas.hub import GithubEvent
from typing import Dict

#: GitHub Organization to collect data from
ORGANIZATION = os.environ.get('GITHUB_ORGANIZATION')

#: Tracing via X-Ray
tracer = Tracer()
logger = Logger()


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


def _repo_settings_sync(repo: Repository):
    """
    Sync repository settings to settings in config file.

    :param repo: Github repository object to sync settings
    :returns: None
    """
    config = _load_config(repo=repo.name)
    default_branch = config.get('default_branch', {})
    default_branch_name = default_branch.get('name')

    repo.edit(
        private=config.get('private'),
        has_issues=config.get('has_issues'),
        has_projects=config.get('has_projects'),
        has_wiki=config.get('has_wiki'),
        default_branch=default_branch_name,
        allow_squash_merge=config.get('allow_squash_merge'),
        allow_merge_commit=config.get('allow_merge_commit'),
        allow_rebase_merge=config.get('allow_rebase_merge'),
        delete_branch_on_merge=config.get('delete_branch_on_merge'),
    )
    #: Vulnerability alerting and remediation
    if config.get('enable_vulnerability_alert'):
        repo.enable_vulnerability_alert()
    else:
        repo.disable_vulnerability_alert()
    if config.get('enable_automated_security_fixes'):
        repo.enable_automated_security_fixes()
    else:
        repo.disable_automated_security_fixes()

    #: Set branch protection on default branch
    branch = repo.get_branch(branch=default_branch_name)
    branch.edit_protection(
        require_code_owner_reviews=default_branch.get('require_code_owner_reviews'),
        required_approving_review_count=default_branch.get('required_approving_review_count'),
    )


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def update(event: Dict, _c: Dict):
    """
    Lambda function that responds to repository events.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key=GithubEvent.repository.value)
    logger.info({'operation': 'update', 'sns_payload': msg})

    if msg.get('action') not in {'deleted', 'archived'}:
        full_name = msg.get('repository', {}).get('full_name')
        repo = hub.get_github_repo(repo=full_name)
        _repo_settings_sync(repo=repo)


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def sync(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function to sync all repository's settings to config settings.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    logger.info({'operation': 'sync'})
    for repo in hub.get_github_repos(org=ORGANIZATION):
        #: `sync` not a Github event but will trigger sync/update via `update()` lambda
        sns.emit_sns_msg(
            message={GithubEvent.repository.value: {'action': 'sync', 'repository': {'full_name': repo.full_name}}}
        )


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
        finally:
            repo.create_label(name=diff['name'], color=diff['color'], description=diff['description'])


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def update_labels(event: Dict, _c: Dict):
    """
    Lambda function to update repository labels to match config settings.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    logger.info({'operation': 'update_labels'})
    msg = sns.get_sns_msg(event=event, msg_key='label')
    repo = hub.get_github_repo(repo=msg.get('full_name'))
    _label_sync(repo=repo)


@tracer.capture_lambda_handler
@logger.inject_lambda_context
def sync_labels(event: Dict, _c: Dict) -> Dict:
    """
    Lambda function to sync all repository labels to config settings.

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    logger.info({'operation': 'sync_labels'})
    for repo in hub.get_github_repos(org=ORGANIZATION):
        sns.emit_sns_msg(message={'label': {'full_name': repo.full_name}})
