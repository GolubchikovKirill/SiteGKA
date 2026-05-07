from __future__ import annotations

from app.domains.inventory import reachability


def test_resolve_hostname_tries_dns_search_suffix(monkeypatch) -> None:
    calls: list[str] = []

    def fake_gethostbyname(hostname: str) -> str:
        calls.append(hostname)
        if hostname == "workstation.example.local":
            return "10.10.1.15"
        raise OSError

    monkeypatch.setattr(reachability.socket, "gethostbyname", fake_gethostbyname)

    result = reachability.resolve_hostname("workstation", dns_search_suffixes="example.local")

    assert result == "10.10.1.15"
    assert calls == ["workstation", "workstation.example.local"]


def test_probe_host_ports_returns_online_on_first_open_port(monkeypatch) -> None:
    monkeypatch.setattr(reachability.socket, "gethostbyname", lambda _hostname: "10.10.1.20")
    checked: list[int] = []

    def fake_checker(_address: str, port: int, _timeout: float) -> bool:
        checked.append(port)
        return port == 3389

    result = reachability.probe_host_ports(
        "cash-01",
        ports=(445, 3389),
        timeout=1.5,
        port_checker=fake_checker,
    )

    assert result.is_online is True
    assert result.reason is None
    assert result.resolved_address == "10.10.1.20"
    assert checked == [445, 3389]


def test_probe_host_ports_reports_dns_failure(monkeypatch) -> None:
    def fake_gethostbyname(_hostname: str) -> str:
        raise OSError

    monkeypatch.setattr(reachability.socket, "gethostbyname", fake_gethostbyname)

    result = reachability.probe_host_ports("missing-host", ports=(445,), timeout=1.0)

    assert result.is_online is False
    assert result.reason == "dns_unresolved"


def test_probe_host_ports_reports_closed_ports(monkeypatch) -> None:
    monkeypatch.setattr(reachability.socket, "gethostbyname", lambda _hostname: "10.10.1.30")

    result = reachability.probe_host_ports(
        "closed-host",
        ports=(445, 3389),
        timeout=1.0,
        port_checker=lambda _address, _port, _timeout: False,
    )

    assert result.is_online is False
    assert result.reason == "port_closed"
    assert result.resolved_address == "10.10.1.30"
