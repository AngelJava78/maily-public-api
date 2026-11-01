"""IP of the client behind trusted proxies (contracts/http-policies.md, research R2)."""

import pytest
from starlette.requests import Request

from src.rate_limit import client_ip

PEER = "10.0.0.1"


def request_with(*forwarded_for: str) -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in forwarded_for]
    return Request({"type": "http", "headers": headers, "client": (PEER, 50000)})


def test_without_trusted_proxies_the_connection_ip() -> None:
    assert client_ip(request_with("203.0.113.9"), trusted_hops=0) == PEER


@pytest.mark.parametrize(("hops", "expected"), [(1, "198.51.100.7"), (2, "203.0.113.9")])
def test_counts_from_the_right(hops: int, expected: str) -> None:
    request = request_with("203.0.113.9, 198.51.100.7")

    assert client_ip(request, trusted_hops=hops) == expected


def test_several_headers_are_joined_in_order() -> None:
    request = request_with("203.0.113.9", "198.51.100.7")

    assert client_ip(request, trusted_hops=1) == "198.51.100.7"
    assert client_ip(request, trusted_hops=2) == "203.0.113.9"


def test_fewer_addresses_than_hops_uses_the_connection_ip() -> None:
    assert client_ip(request_with("198.51.100.7"), trusted_hops=2) == PEER
    assert client_ip(request_with(), trusted_hops=1) == PEER


def test_an_entry_that_is_not_an_ip_uses_the_connection_ip() -> None:
    assert client_ip(request_with("203.0.113.9, unknown"), trusted_hops=1) == PEER


def test_ipv6() -> None:
    assert client_ip(request_with("2001:db8::1"), trusted_hops=1) == "2001:db8::1"
