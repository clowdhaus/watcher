# -*- coding: utf-8 -*-
"""
    SNS
    ---

    Module contains shared functionality for working with the AWS SNS (Simple Notification Service) API

"""

import boto3
from aws_lambda_powertools.logging import Logger
from botocore.exceptions import ClientError

import json
import os
from typing import Dict, Optional, Union

#: Base SNS message topic ARN
SNS_ARN_PREFIX = os.environ.get('SNS_ARN_PREFIX')

#: SNS message topic ARN where messages should be published
EMIT_MESSAGE_TOPIC = os.environ.get('EMIT_MESSAGE_TOPIC')
REGION = os.environ.get('REGION', 'us-east-1')
SNS_CLIENT = boto3.client('sns', region_name=REGION)

logger = Logger()


def emit_sns_msg(message: Union[str, Dict], topic_arn: str = EMIT_MESSAGE_TOPIC, **kwargs):
    """
    Emit a message to a given SNS topic ARN.

    :param message: JSON serializable Python object
    :param topic_arn: the topic arn to which to emit the message to
    :returns: None
    """
    msg = message if isinstance(message, str) else json.dumps(message)
    try:
        SNS_CLIENT.publish(Message=msg, TopicArn=topic_arn, **kwargs)
    except ClientError as err:
        logger.exception(f'Unable to publish SNS message {message} to topic `{topic_arn}`')
        raise


def get_sns_msg(event: Dict, msg_key: str) -> Optional[Dict]:
    """
    Extract message object from AWS SNS event.

    :param event: AWS event object
    :returns: JSON serialized SNS message object
    """

    event_msg = json.loads(event['Records'][0]['Sns']['Message'])
    try:
        return event_msg[msg_key]
    except KeyError:
        logger.exception({'operation': 'get_sns_msg', 'event_message': event_msg})
        raise
