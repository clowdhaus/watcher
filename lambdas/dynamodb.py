# -*- coding: utf-8 -*-
"""
    DynamoDB
    --------

    Module contains shared functionality for working with the AWS DynamoDB API

"""

import decimal
import os
from typing import Any, Dict

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError

REGION = os.environ.get('REGION', 'us-east-1')
RESOURCE = boto3.resource('dynamodb', region_name=REGION)
CLIENT = boto3.client('dynamodb', region_name=REGION)


def replace_decimals(obj: Any) -> Any:
    """
    Convert Decimals in arbitrary object to correct numeric type.

    :param obj: arbitrary python object to evaluate
    :returns: object with Decimals replaced with native numeric value
    """
    if isinstance(obj, list):
        for i in range(len(obj)):
            obj[i] = replace_decimals(obj[i])
        return obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            obj[k] = replace_decimals(v)
        return obj
    elif isinstance(obj, set):
        return set(replace_decimals(i) for i in obj)
    elif isinstance(obj, decimal.Decimal):
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj


def deserialize(serialized: Dict) -> Dict:
    """
    Deserialize DynamoDB object into standard python dictionary.

    :param serialized: dicitonary object containing DynamoDB type markup
    :returns: standard python object sans DynamoDB type markup
    """
    deserializer = TypeDeserializer()
    return replace_decimals({key: deserializer.deserialize(val) for key, val in serialized.items()})


def get_item(key: Dict, table: str, **kwargs) -> Dict:
    """
    Get `key` from `table`

    :param key: primary key
    :param table: table name
    :returns: object stored in `table` under `key`
    """
    _table = RESOURCE.Table(table)
    try:
        response = _table.get_item(Key=key, **kwargs)
        try:
            return response['Item']
        except KeyError:
            raise
    except ClientError:
        raise


def put_item(item: Dict, table: str, **kwargs) -> Dict:
    """
    Put `item` into `table`.

    :param item: dictionary object to insert into table
    :param table: table name
    :returns: HTTPStatusCode of inserting `item`
    """
    _table = RESOURCE.Table(table)
    try:
        return _table.put_item(Item=item, **kwargs)
    except ClientError:
        raise


def update_item(key: Dict, expression: str, attr_values: Dict, table: str, **kwargs) -> Dict:
    """
    Update `item` in `table`.

    :param key: primary key
    :param expression: defines one or more attributes to be updated
    :param attr_values: one or more values that can be substituted in an expression
    :param table: table name
    :returns: HTTPStatusCode of inserting `item`
    """
    _table = RESOURCE.Table(table)
    try:
        return _table.update_item(
            Key=key,
            UpdateExpression=expression,
            ExpressionAttributeValues=attr_values,
            ReturnValues='ALL_NEW',
            **kwargs,
        )
    except ClientError:
        raise


def delete_item(key: Dict, table: str, **kwargs) -> Dict:
    """
    Delete object stored under `key` from `table`

    :param key: primary key
    :param table: table name
    :returns: HTTPStatusCode response of deleting `key`
    """
    _table = RESOURCE.Table(table)
    try:
        return _table.delete_item(Key=key, **kwargs)
    except ClientError:
        raise
