"""SSH client for Cisco IOS switches.

Supports:
  - Fetching switch info (hostname, model, IOS version, uptime)
  - Discovering access points on a VLAN via MAC address table + CDP + PoE
  - Rebooting access points via PoE power cycling
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

import paramiko

logger = logging.getLogger(__name__)

SSH_TIMEOUT = 15
CMD_TIMEOUT = 30
RECV_CHUNK = 65535
RECV_WAIT = 0.5


@dataclass
class SwitchInfo:
    hostname: str | None = None
    model_info: str | None = None
    ios_version: str | None = None
    uptime: str | None = None
    is_online: bool = False


@dataclass
class APInfo:
    mac_address: str
    port: str
    vlan: int
    ip_address: str | None = None
    cdp_name: str | None = None
    cdp_platform: str | None = None
    poe_power: str | None = None
    poe_status: str | None = None


class CiscoSSH:
    """Manages an SSH session to a Cisco IOS device."""

    def __init__(self, ip: str, username: str, password: str,
                 enable_password: str = "", port: int = 22):
        self.ip = ip
        self.username = username
        self.password = password
        self.enable_password = enable_password or password
        self.port = port
        self.client: paramiko.SSHClient | None = None
        self.shell: paramiko.Channel | None = None

    def connect(self) -> bool:
        allowed = self._query_auth_methods()
        logger.info("SSH to %s: server allows auth methods: %s", self.ip, allowed)

        strategies: list[tuple[str, callable]] = []
        if "password" in allowed:
            strategies.append(("password", self._connect_password))
        if "keyboard-interactive" in allowed:
            strategies.append(("keyboard-interactive", self._connect_keyboard_interactive))
        if not strategies:
            strategies = [
                ("password", self._connect_password),
                ("keyboard-interactive", self._connect_keyboard_interactive),
            ]

        for name, method in strategies:
            logger.info("SSH to %s: trying %s auth", self.ip, name)
            if method():
                logger.info("SSH to %s: %s auth succeeded", self.ip, name)
                return True
            logger.warning("SSH to %s: %s auth failed", self.ip, name)
        return False

    def _query_auth_methods(self) -> list[str]:
        """Ask the server which auth methods it supports."""
        try:
            transport = paramiko.Transport((self.ip, self.port))
            transport.connect()
            try:
                transport.auth_none(self.username)
            except paramiko.BadAuthenticationType as e:
                return list(e.allowed_types)
            except paramiko.AuthenticationException:
                return ["password", "keyboard-interactive"]
            finally:
                transport.close()
        except Exception as e:
            logger.debug("SSH auth query to %s failed: %s", self.ip, e)
        return ["password", "keyboard-interactive"]

    def _connect_password(self) -> bool:
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                self.ip,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=SSH_TIMEOUT,
                look_for_keys=False,
                allow_agent=False,
                disabled_algorithms={"pubkeys": ["rsa-sha2-512", "rsa-sha2-256"]},
            )
            return self._post_connect()
        except Exception as e:
            logger.debug("SSH password connect to %s: %s", self.ip, e)
            self.close()
            return False

    def _connect_keyboard_interactive(self) -> bool:
        """Cisco often uses keyboard-interactive instead of standard password auth."""
        try:
            transport = paramiko.Transport((self.ip, self.port))
            transport.connect()
            transport.set_keepalive(30)

            password = self.password

            def _ki_handler(_title, _instructions, prompt_list):
                logger.debug("KI prompts from %s: %s", self.ip, prompt_list)
                return [password] * len(prompt_list)

            transport.auth_interactive(self.username, _ki_handler)

            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client._transport = transport
            self.shell = transport.open_session()
            self.shell.get_pty()
            self.shell.invoke_shell()
            self.shell.settimeout(CMD_TIMEOUT)
            self._recv_until_prompt()

            self._enter_enable()
            self._send("terminal length 0")
            self._recv_until_prompt()
            return True
        except Exception as e:
            logger.debug("SSH keyboard-interactive to %s: %s", self.ip, e)
            self.close()
            return False

    def _post_connect(self) -> bool:
        """Open shell and enter privileged mode after successful transport auth."""
        self.shell = self.client.invoke_shell()  # type: ignore[union-attr]
        self.shell.settimeout(CMD_TIMEOUT)
        self._recv_until_prompt()
        self._enter_enable()
        self._send("terminal length 0")
        self._recv_until_prompt()
        return True

    def _enter_enable(self) -> None:
        self._send("enable")
        output = self._recv_until_prompt()
        if "assword" in output:
            self._send(self.enable_password)
            self._recv_until_prompt()

    def close(self) -> None:
        try:
            if self.shell:
                self.shell.close()
            if self.client:
                self.client.close()
        except Exception:
            pass
        self.shell = None
        self.client = None

    def _send(self, cmd: str) -> None:
        if self.shell:
            self.shell.send(cmd + "\n")

    def _recv_until_prompt(self, timeout: float = CMD_TIMEOUT) -> str:
        if not self.shell:
            return ""
        output = ""
        end_time = time.monotonic() + timeout
        while time.monotonic() < end_time:
            time.sleep(RECV_WAIT)
            if self.shell.recv_ready():
                chunk = self.shell.recv(RECV_CHUNK).decode("utf-8", errors="replace")
                output += chunk
                if re.search(r"[#>]\s*$", output):
                    break
            elif output and re.search(r"[#>]\s*$", output):
                break
        return output

    def execute(self, cmd: str) -> str:
        self._send(cmd)
        return self._recv_until_prompt()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()


def get_switch_info(ip: str, username: str, password: str,
                    enable_password: str = "", port: int = 22) -> SwitchInfo:
    info = SwitchInfo()
    ssh = CiscoSSH(ip, username, password, enable_password, port)
    if not ssh.connect():
        return info

    try:
        info.is_online = True
        output = ssh.execute("show version")

        m = re.search(r"^(\S+)\s+uptime", output, re.MULTILINE)
        if m:
            info.hostname = m.group(1)

        m = re.search(r"uptime is (.+)", output)
        if m:
            info.uptime = m.group(1).strip()

        m = re.search(r"Cisco IOS Software.*?Version\s+(\S+)", output, re.IGNORECASE)
        if not m:
            m = re.search(r"Version\s+(\S+)", output)
        if m:
            info.ios_version = m.group(1).rstrip(",")

        m = re.search(r"[Mm]odel\s+[Nn]umber\s*:\s*(\S+)", output)
        if not m:
            m = re.search(r"cisco\s+(WS-\S+|C\d+\S*)", output, re.IGNORECASE)
        if not m:
            m = re.search(r"^[Cc]isco\s+(\S+)\s+\(", output, re.MULTILINE)
        if m:
            info.model_info = m.group(1)
    except Exception as e:
        logger.warning("Failed to get switch info from %s: %s", ip, e)
    finally:
        ssh.close()

    return info


def get_access_points(ip: str, username: str, password: str,
                      enable_password: str = "", port: int = 22,
                      vlan: int = 20) -> list[APInfo]:
    """Discover access points on the given VLAN."""
    ssh = CiscoSSH(ip, username, password, enable_password, port)
    if not ssh.connect():
        return []

    try:
        mac_output = ssh.execute(f"show mac address-table vlan {vlan}")
        aps = _parse_mac_table(mac_output, vlan)

        if not aps:
            return []

        cdp_output = ssh.execute("show cdp neighbors detail")
        _enrich_cdp(aps, cdp_output)

        poe_output = ssh.execute("show power inline")
        _enrich_poe(aps, poe_output)

        arp_output = ssh.execute(f"show ip arp vlan {vlan}")
        _enrich_arp(aps, arp_output)

        return aps
    except Exception as e:
        logger.warning("Failed to get APs from %s: %s", ip, e)
        return []
    finally:
        ssh.close()


def reboot_ap(ip: str, username: str, password: str,
              enable_password: str, port: int,
              interface: str) -> bool:
    """Reboot an AP by PoE cycling the switch port."""
    ssh = CiscoSSH(ip, username, password, enable_password, port)
    if not ssh.connect():
        return False

    try:
        ssh.execute("configure terminal")
        ssh.execute(f"interface {interface}")
        ssh.execute("shutdown")
        time.sleep(3)
        ssh.execute("no shutdown")
        ssh.execute("end")
        logger.info("PoE cycle completed on %s port %s", ip, interface)
        return True
    except Exception as e:
        logger.warning("Failed to reboot AP on %s port %s: %s", ip, interface, e)
        return False
    finally:
        ssh.close()


def poe_cycle_ap(ip: str, username: str, password: str,
                 enable_password: str, port: int,
                 interface: str) -> bool:
    """Reboot AP via PoE power cycle (cleaner than shutdown)."""
    ssh = CiscoSSH(ip, username, password, enable_password, port)
    if not ssh.connect():
        return False

    try:
        ssh.execute("configure terminal")
        ssh.execute(f"interface {interface}")
        ssh.execute("power inline never")
        ssh.execute("end")
        time.sleep(5)
        ssh.execute("configure terminal")
        ssh.execute(f"interface {interface}")
        ssh.execute("power inline auto")
        ssh.execute("end")
        logger.info("PoE power cycle completed on %s port %s", ip, interface)
        return True
    except Exception as e:
        logger.warning("PoE cycle failed on %s port %s: %s", ip, interface, e)
        return False
    finally:
        ssh.close()


def _parse_mac_table(output: str, vlan: int) -> list[APInfo]:
    """Parse 'show mac address-table vlan X' output."""
    aps: list[APInfo] = []
    seen_macs: set[str] = set()

    for line in output.split("\n"):
        m = re.match(
            r"\s*(\d+)\s+"
            r"([0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4})\s+"
            r"\S+\s+"
            r"(\S+)",
            line,
        )
        if m and int(m.group(1)) == vlan:
            mac = m.group(2).lower()
            port_name = m.group(3)
            if mac not in seen_macs and not port_name.startswith(("Po", "Vl", "CPU")):
                seen_macs.add(mac)
                aps.append(APInfo(
                    mac_address=_format_mac(mac),
                    port=port_name,
                    vlan=vlan,
                ))
    return aps


def _format_mac(cisco_mac: str) -> str:
    """Convert Cisco MAC format (0011.2233.4455) to standard (00:11:22:33:44:55)."""
    raw = cisco_mac.replace(".", "").lower()
    if len(raw) == 12:
        return ":".join(raw[i:i + 2] for i in range(0, 12, 2))
    return cisco_mac


def _enrich_cdp(aps: list[APInfo], cdp_output: str) -> None:
    """Enrich AP list with CDP neighbor info."""
    entries = re.split(r"-{5,}", cdp_output)
    cdp_by_port: dict[str, dict] = {}

    for entry in entries:
        port_m = re.search(r"Interface:\s*(\S+),", entry)
        name_m = re.search(r"Device ID:\s*(.+)", entry)
        plat_m = re.search(r"Platform:\s*(.+?)(?:,|$)", entry)
        if port_m:
            port_key = _normalize_port(port_m.group(1))
            cdp_by_port[port_key] = {
                "name": name_m.group(1).strip() if name_m else None,
                "platform": plat_m.group(1).strip() if plat_m else None,
            }

    for ap in aps:
        port_key = _normalize_port(ap.port)
        if port_key in cdp_by_port:
            ap.cdp_name = cdp_by_port[port_key].get("name")
            ap.cdp_platform = cdp_by_port[port_key].get("platform")


def _enrich_poe(aps: list[APInfo], poe_output: str) -> None:
    """Enrich AP list with PoE info."""
    poe_by_port: dict[str, dict] = {}
    for line in poe_output.split("\n"):
        m = re.match(r"\s*(\S+)\s+\S+\s+(\S+)\s+([\d.]+)\s+", line)
        if m:
            port_key = _normalize_port(m.group(1))
            poe_by_port[port_key] = {
                "status": m.group(2),
                "power": m.group(3) + "W",
            }

    for ap in aps:
        port_key = _normalize_port(ap.port)
        if port_key in poe_by_port:
            ap.poe_status = poe_by_port[port_key].get("status")
            ap.poe_power = poe_by_port[port_key].get("power")


def _enrich_arp(aps: list[APInfo], arp_output: str) -> None:
    """Enrich AP list with IP from ARP table."""
    mac_to_ip: dict[str, str] = {}
    for line in arp_output.split("\n"):
        m = re.search(
            r"(\d+\.\d+\.\d+\.\d+)\s+\S+\s+"
            r"([0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4})",
            line,
        )
        if m:
            formatted = _format_mac(m.group(2).lower())
            mac_to_ip[formatted] = m.group(1)

    for ap in aps:
        if ap.mac_address in mac_to_ip:
            ap.ip_address = mac_to_ip[ap.mac_address]


def _normalize_port(port: str) -> str:
    """Normalize port names for comparison (Gi0/1 == GigabitEthernet0/1)."""
    port = port.strip()
    replacements = [
        (r"^GigabitEthernet", "Gi"),
        (r"^FastEthernet", "Fa"),
        (r"^TenGigabitEthernet", "Te"),
        (r"^TwentyFiveGigE", "Twe"),
    ]
    for pattern, repl in replacements:
        port = re.sub(pattern, repl, port)
    return port
