# -*- coding: utf-8 -*-
"""
    Sync
    ----

    Module used for syncrhonizing GitHub data

"""

import json
from typing import Dict

import github

from lambdas import hub, sns
from lambdas.hub import SNS_TOPIC_BASE


def get_repositories_for_sync(_e: Dict, _c: Dict):
    """
    Lambda function that collects all source repositories and sends repository full name
        over SNS topic for syncing/updating metadata

    :param _e: lambda expected event object (unused)
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    token = hub.get_github_user_token()
    git = github.Github(token)
    repos = git.get_repos(type='sources', sort='updated')

    for repo in repos:
        sns.emit_sns_msg(message={'repository': repo.full_name}, topic_arn=f'{SNS_TOPIC_BASE}-Sync-Repository')


def sync_repository_data(event: Dict, _c: Dict):
    """
    Lambda function that updates/syncrhonizes the repository metadata for the
        repository recevied via SNS message

    :param event: lambda expected event object
    :param _c: lambda expected context object (unused)
    :returns: none
    """
    msg = sns.get_sns_msg(event=event, msg_key='repository')
    print(json.dumps(msg))
