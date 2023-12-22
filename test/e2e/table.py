# Copyright Amazon.com Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"). You may
# not use this file except in compliance with the License. A copy of the
# License is located at
#
#	 http://aws.amazon.com/apache2.0/
#
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

"""Utilities for working with Table resources"""

import datetime
import time
import typing
import logging

import boto3
import pytest

from acktest.aws.identity import get_region

DEFAULT_WAIT_UNTIL_TIMEOUT_SECONDS = 60
DEFAULT_WAIT_UNTIL_INTERVAL_SECONDS = 5

TableMatchFunc = typing.NewType(
    'TableMatchFunc',
    typing.Callable[[dict], bool],
)

class StatusMatcher:
    def __init__(self, status):
        self.match_on = status

    def __call__(self, record: dict) -> bool:
        return ('TableStatus' in record
                and record['TableStatus'] == self.match_on)


def status_matches(status: str) -> TableMatchFunc:
    return StatusMatcher(status)

class ThroughputModeMatcher:
    def __init__(self, mode: str):
        self.mode = mode

    def __call__(self, record: dict) -> bool:
        return ('ThroughputModeSummary' in record
                and record["ThroughputModeSummary"]["ThroughputMode"] == self.mode)


def throughput_mode_matcher(mode: str) -> TableMatchFunc:
    return ThroughputModeMatcher(mode)


class CapacitySpecificationMatcher:
    def __init__(self, read_capacity_units: int, write_capacity_units: int):
        self.read_capacity_units = read_capacity_units
        self.write_capacity_units = write_capacity_units

    def __call__(self, record: dict) -> bool:
        return ('capacitySpecification' in record
                and record["capacitySpecification"]["ReadCapacityUnits"] == self.read_capacity_units
                and record["capacitySpecification"]["WriteCapacityUnits"] == self.write_capacity_units
        )

def capacity_specification_matcher(read_capacity_units: int, write_capacity_units: int)-> TableMatchFunc:
    return CapacitySpecificationMatcher(read_capacity_units, write_capacity_units)


def wait_until(
        keyspace_name: str,
        table_name: str,
        match_fn: TableMatchFunc,
        timeout_seconds: int = DEFAULT_WAIT_UNTIL_TIMEOUT_SECONDS,
        interval_seconds: int = DEFAULT_WAIT_UNTIL_INTERVAL_SECONDS,
    ) -> None:
    """Waits until a Table with a supplied name is returned from the Keyspaces
    API and the matching functor returns True.

    Usage:
        from e2e.table import wait_until, status_matches

        wait_until(
            table_name,
            status_matches("ACTIVE"),
        )

    Raises:
        pytest.fail upon timeout
    """
    now = datetime.datetime.now()
    timeout = now + datetime.timedelta(seconds=timeout_seconds)

    while not match_fn(get(keyspace_name, table_name)):
        if datetime.datetime.now() >= timeout:
            pytest.fail("failed to match table before timeout")
        time.sleep(interval_seconds)


def get(keyspace_name,table_name):
    """Returns a dict containing the Role record from the keyspaces API.

    If no such Table exists, returns None.
    """
    c = boto3.client('keyspaces', region_name=get_region())
    try:
        resp = c.get_table(keyspaceName=keyspace_name, tableName=table_name)
        return resp['tableName']
    except c.exceptions.ResourceNotFoundException:
        logging.info("Table %s not found", table_name)
        return None
    except c.exceptions.ValidationException:
        logging.info(
          "Couldn't verify %s exists. Here's why: %s",
          table_name,
          c.exceptions
        )
        return None