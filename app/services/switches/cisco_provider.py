from __future__ import annotations

import re
import time

from app.models import NetworkSwitch
from app.services.cisco_ssh import CiscoSSH, get_switch_info
from app.services.switches.base import SwitchPollInfo, SwitchPortState
from app.services.switches.snmp_provider import SnmpSwitchProvider


class CiscoSwitchProvider:
    def __init__(self) -> None:
        self.snmp_provider = SnmpSwitchProvider()

    def poll_switch(self, switch: NetworkSwitch) -> SwitchPollInfo:
        info = get_switch_info(
            switch.ip_address,
            switch.ssh_username,
            switch.ssh_password,
            switch.enable_password,
            switch.ssh_port,
        )
        if info.is_online:
            return SwitchPollInfo(
                is_online=True,
                hostname=info.hostname,
                model_info=info.model_info,
                ios_version=info.ios_version,
                uptime=info.uptime,
            )
        return self.snmp_provider.poll_switch(switch)

    def get_ports(self, switch: NetworkSwitch) -> list[SwitchPortState]:
        ports = self.snmp_provider.get_ports(switch)
        switchport_map = self._get_switchport_details(switch)
        if ports:
            self._enrich_ports_with_switchport(ports, switchport_map)
            return ports
        ssh_ports = self._get_ports_via_ssh(switch)
        self._enrich_ports_with_switchport(ssh_ports, switchport_map)
        return ssh_ports

    def _get_ports_via_ssh(self, switch: NetworkSwitch) -> list[SwitchPortState]:
        ssh = CiscoSSH(
            switch.ip_address,
            switch.ssh_username,
            switch.ssh_password,
            switch.enable_password,
            switch.ssh_port,
        )
        if not ssh.connect():
            return []
        try:
            output = ssh.execute("show interfaces status")
        finally:
            ssh.close()
        return self._parse_interfaces_status(output)

    def _parse_interfaces_status(self, output: str) -> list[SwitchPortState]:
        ports: list[SwitchPortState] = []
        for line in output.splitlines():
            line = line.rstrip()
            if not line or line.lower().startswith("port ") or line.startswith("---"):
                continue
            match = re.match(r"^(\S+)\s+(.+?)\s+(connected|notconnect|disabled|err-disabled)\s+", line)
            if not match:
                continue
            port_name = match.group(1)
            descr = match.group(2).strip()
            oper_state = "up" if match.group(3) == "connected" else "down"
            ports.append(
                SwitchPortState(
                    port=port_name,
                    if_index=0,
                    description=descr if descr != "--" else None,
                    admin_status=None,
                    oper_status=oper_state,
                )
            )
        return ports

    def _get_switchport_details(self, switch: NetworkSwitch) -> dict[str, dict[str, str]]:
        ssh = CiscoSSH(
            switch.ip_address,
            switch.ssh_username,
            switch.ssh_password,
            switch.enable_password,
            switch.ssh_port,
        )
        if not ssh.connect():
            return {}
        try:
            output = ssh.execute("show interfaces switchport")
        finally:
            ssh.close()
        return self._parse_switchport_output(output)

    def _parse_switchport_output(self, output: str) -> dict[str, dict[str, str]]:
        sections = re.split(r"\n(?=Name:\s)", output)
        details: dict[str, dict[str, str]] = {}
        for section in sections:
            name_match = re.search(r"Name:\s*(\S+)", section)
            if not name_match:
                continue
            port = name_match.group(1).strip()
            norm = self._normalize_port(port)
            mode_match = re.search(r"Administrative Mode:\s*(.+)", section)
            access_match = re.search(r"Access Mode VLAN:\s*(\d+)", section)
            native_match = re.search(r"Trunking Native Mode VLAN:\s*(\d+)", section)
            allowed_match = re.search(r"Trunking VLANs Enabled:\s*(.+)", section)
            details[norm] = {
                "mode": (mode_match.group(1).strip().lower() if mode_match else ""),
                "access_vlan": access_match.group(1) if access_match else "",
                "native_vlan": native_match.group(1) if native_match else "",
                "allowed_vlans": (allowed_match.group(1).strip() if allowed_match else ""),
            }
        return details

    def _enrich_ports_with_switchport(self, ports: list[SwitchPortState], details: dict[str, dict[str, str]]) -> None:
        for port in ports:
            norm = self._normalize_port(port.port)
            cfg = details.get(norm)
            if not cfg:
                continue
            mode_raw = cfg.get("mode", "")
            port.port_mode = self._normalize_mode(mode_raw)
            if cfg.get("access_vlan"):
                try:
                    port.access_vlan = int(cfg["access_vlan"])
                except ValueError:
                    port.access_vlan = None
            if cfg.get("native_vlan"):
                try:
                    port.trunk_native_vlan = int(cfg["native_vlan"])
                except ValueError:
                    port.trunk_native_vlan = None
            if cfg.get("allowed_vlans"):
                port.trunk_allowed_vlans = cfg["allowed_vlans"]

    def _normalize_mode(self, mode_raw: str) -> str | None:
        if not mode_raw:
            return None
        if "trunk" in mode_raw:
            return "trunk"
        if "access" in mode_raw or "static access" in mode_raw:
            return "access"
        if "dynamic" in mode_raw:
            return "dynamic"
        return "unknown"

    def _normalize_port(self, port: str) -> str:
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

    def set_admin_state(self, switch: NetworkSwitch, port: str, admin_state: str) -> None:
        cmd = "no shutdown" if admin_state == "up" else "shutdown"
        self._exec_config(switch, [f"interface {port}", cmd])

    def set_description(self, switch: NetworkSwitch, port: str, description: str) -> None:
        self._exec_config(switch, [f"interface {port}", f"description {description}"])

    def set_vlan(self, switch: NetworkSwitch, port: str, vlan: int) -> None:
        self._exec_config(
            switch,
            [f"interface {port}", "switchport mode access", f"switchport access vlan {vlan}"],
        )

    def set_mode(
        self,
        switch: NetworkSwitch,
        port: str,
        mode: str,
        access_vlan: int | None = None,
        native_vlan: int | None = None,
        allowed_vlans: str | None = None,
    ) -> None:
        normalized = mode.strip().lower()
        if normalized == "access":
            commands = [f"interface {port}", "switchport mode access"]
            if access_vlan is not None:
                commands.append(f"switchport access vlan {access_vlan}")
            self._exec_config(switch, commands)
            return
        if normalized == "trunk":
            commands = [f"interface {port}", "switchport mode trunk"]
            if native_vlan is not None:
                commands.append(f"switchport trunk native vlan {native_vlan}")
            if allowed_vlans:
                commands.append(f"switchport trunk allowed vlan {allowed_vlans}")
            self._exec_config(switch, commands)
            return
        raise RuntimeError("Unsupported mode. Use 'access' or 'trunk'")

    def set_poe(self, switch: NetworkSwitch, port: str, action: str) -> None:
        if action == "on":
            self._exec_config(switch, [f"interface {port}", "power inline auto"])
            return
        if action == "off":
            self._exec_config(switch, [f"interface {port}", "power inline never"])
            return
        self._exec_config(switch, [f"interface {port}", "power inline never"])
        time.sleep(3)
        self._exec_config(switch, [f"interface {port}", "power inline auto"])

    def _exec_config(self, switch: NetworkSwitch, commands: list[str]) -> None:
        ssh = CiscoSSH(
            switch.ip_address,
            switch.ssh_username,
            switch.ssh_password,
            switch.enable_password,
            switch.ssh_port,
        )
        if not ssh.connect():
            raise RuntimeError("SSH connection failed")
        try:
            ssh.execute("configure terminal")
            for cmd in commands:
                ssh.execute(cmd)
            ssh.execute("end")
        finally:
            ssh.close()
