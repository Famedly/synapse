# -*- coding: utf-8 -*-
# Copyright 2018 New Vector Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import re

logger = logging.getLogger(__name__)


async def check_3pid_allowed(hs, medium, address, during_registration: bool = False):
    """Checks whether a given format of 3PID is allowed to be used on this HS

    Args:
        hs (synapse.server.HomeServer): server
        medium (str): 3pid medium - e.g. email, msisdn
        address (str): address within that medium (e.g. "wotan@matrix.org")
            msisdns need to first have been canonicalised
        during_registration: Whether this request has been made while registering a new
            user.
    Returns:
        bool: whether the 3PID medium/address is allowed to be added to this HS
    """

    if hs.config.check_is_for_allowed_local_3pids and during_registration:
        # If this 3pid is being approved as part of registering a new user,
        # we'll want to make sure the 3pid has been invited by someone already.
        #
        # We condition on registration so that user 3pids do not require an invite while
        # doing tasks other than registration, such as resetting their password or adding a
        # second email to their account.
        data = await hs.get_simple_http_client().get_json(
            "https://%s%s" % (
                hs.config.check_is_for_allowed_local_3pids,
                "/_matrix/identity/api/v1/internal-info"
            ),
            {'medium': medium, 'address': address}
        )
        logger.info(
            "Received internal-info data for medium '%s', address '%s': %s",
            medium, address, data,
        )

        # Check for invalid response
        if 'hs' not in data and 'shadow_hs' not in data:
            return False

        # Check if this user is intended to register for this homeserver
        if (
            data.get('hs') != hs.config.server_name
            and data.get('shadow_hs') != hs.config.server_name
        ):
            logger.info(
                "%s did not match %s or %s did not match %s",
                data.get("hs"), hs.config.server_name,
                data.get("shadow_hs"), hs.config.server_name,
            )
            return False

        if data.get('requires_invite', False) and not data.get('invited', False):
            # Requires an invite but hasn't been invited
            logger.info(
                "3PID check failed due to 'required_invite' = '%s' and 'invited' = '%s'",
                data.get('required_invite'), data.get("invited"),
            )
            return False

        return True

    if hs.config.allowed_local_3pids:
        for constraint in hs.config.allowed_local_3pids:
            logger.debug(
                "Checking 3PID %s (%s) against %s (%s)",
                address,
                medium,
                constraint["pattern"],
                constraint["medium"],
            )
            if medium == constraint["medium"] and re.match(
                constraint["pattern"], address
            ):
                return True
    else:
        return True

    return False


def canonicalise_email(address: str) -> str:
    """'Canonicalise' email address
    Case folding of local part of email address and lowercase domain part
    See MSC2265, https://github.com/matrix-org/matrix-doc/pull/2265

    Args:
        address: email address to be canonicalised
    Returns:
        The canonical form of the email address
    Raises:
        ValueError if the address could not be parsed.
    """

    address = address.strip()

    parts = address.split("@")
    if len(parts) != 2:
        logger.debug("Couldn't parse email address %s", address)
        raise ValueError("Unable to parse email address")

    return parts[0].casefold() + "@" + parts[1].lower()
