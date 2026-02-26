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
        if ports:
            return ports
        return self._get_ports_via_ssh(switch)

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
