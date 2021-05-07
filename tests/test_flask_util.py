import ipaddress

import pytest
from flask import Flask, request

from util.flask_util import (
    is_public_ipv4_address,
    originating_ip,
)


@pytest.fixture
def generic_app_obj():
    return Flask(__name__)


class TestFlaskUtil:
    @pytest.mark.parametrize(
        "fwd4_value,remote_addr,result",
        [
            pytest.param('64.234.82.200', '64.234.82.201', '64.234.82.200', id="ip_from_Fwd4_header"),
            pytest.param('10.0.0.1', '64.234.82.200', '64.234.82.200', id="ip_from_remote_addr"),
            pytest.param('10.0.0.1', '10.0.0.2', None, id="no_public_ip_provided"),
            pytest.param('64.234.82.200, 10.0.0.1', '64.234.82.201', '64.234.82.200', id="multival_Fwd4"),
        ]
    )
    def test_originating_ip(self, generic_app_obj, fwd4_value, remote_addr, result):
        """
        GIVEN: A request object with values in the 'X-Forwarded-For' header and remote_addr
        WHEN:  originating_ip() is called
        THEN:  The appropriate value (an IP address or None) should be returned
        """
        fwd4_header = 'X-Forwarded-For'
        headers = {fwd4_header.upper(): fwd4_value}
        env_base = {'REMOTE_ADDR': remote_addr}
        with generic_app_obj.test_request_context(headers=headers, environ_base=env_base):
            assert request.headers.get(fwd4_header) == fwd4_value
            assert request.remote_addr == remote_addr

            if result is None or isinstance(result, bool):
                assert originating_ip() is result
            else:
                assert originating_ip() == result

    @pytest.mark.parametrize(
        "address,result", [
            (ipaddress.ip_address('64.234.82.200'), True),  # IPv4Address object arg
            ('not an ip address', None),    # Bad input
            ('10.0.0.1', False),            # Private
            ('224.0.0.3', False),           # Multicast
            ('0.0.0.0', False),             # Unspecified
            ('240.0.0.1', False),           # Reserved
            ('127.0.0.1', False),           # Loopback
            ('169.254.0.1', False),         # Link local
            ('255.255.255.255', False),     # Broadcast
            ('64.234.82.200', True),        # Public
        ]
    )
    def test_is_public_ipv4_address(self, address, result):
        """
        GIVEN: A string representation of an IPv4 address
        WHEN:  is_public_ipv4_address() is called on that string
        THEN:  The appropriate boolean response should be returned
        """
        if not result or isinstance(result, bool):
            assert is_public_ipv4_address(address) is result
        else:
            assert is_public_ipv4_address(address) == result
