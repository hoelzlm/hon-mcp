"""MCP server for Haier hOn appliances (washing machine etc.) via pyhon."""
import asyncio
import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from pyhon import Hon
from pyhon.appliance import HonAppliance

def _load_env() -> None:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env()

mcp = FastMCP("hon", host=os.environ.get("MCP_HOST", "127.0.0.1"), port=int(os.environ.get("MCP_PORT", "8765")))

_hon: Hon | None = None
_lock = asyncio.Lock()


async def _client() -> Hon:
    global _hon
    async with _lock:
        if _hon is None:
            email = os.environ.get("HON_EMAIL")
            password = os.environ.get("HON_PASSWORD")
            if not email or not password:
                raise RuntimeError("Set HON_EMAIL and HON_PASSWORD in .env")
            _hon = await Hon(email=email, password=password).create()
        return _hon


async def _appliance(name: str | None) -> HonAppliance:
    hon = await _client()
    appliances = hon.appliances
    if not appliances:
        raise RuntimeError("No appliances on this hOn account")
    if name is None:
        if len(appliances) == 1:
            return appliances[0]
        raise RuntimeError(
            "Several appliances, pass `appliance`: "
            + ", ".join(a.nick_name or a.unique_id for a in appliances)
        )
    for a in appliances:
        if name in (a.nick_name, a.unique_id, a.mac_address):
            return a
    raise RuntimeError(f"No appliance named {name!r}")


def _val(v: Any) -> Any:
    return getattr(v, "value", v)


@mcp.tool()
async def list_appliances() -> str:
    """List appliances on the hOn account (name, type, model, online state)."""
    hon = await _client()
    return json.dumps(
        [
            {
                "name": a.nick_name,
                "id": a.unique_id,
                "type": a.appliance_type,
                "model": a.model_name,
                "brand": a.brand,
                "online": a.connection,
            }
            for a in hon.appliances
        ],
        indent=2,
    )


@mcp.tool()
async def get_status(appliance: str | None = None) -> str:
    """Current state of an appliance: all live attributes (machMode, remainingTimeMM, program, etc.)."""
    a = await _appliance(appliance)
    await a.update()
    params = {k: _val(v) for k, v in a.attributes.get("parameters", {}).items()}
    return json.dumps(
        {"name": a.nick_name, "online": a.connection, "parameters": params},
        indent=2,
        default=str,
    )


@mcp.tool()
async def list_programs(appliance: str | None = None) -> str:
    """List programs that can be started, with the settings (and allowed values) each accepts."""
    a = await _appliance(appliance)
    cmd = a.commands.get("startProgram")
    if cmd is None:
        raise RuntimeError("Appliance has no startProgram command")
    out: dict[str, Any] = {}
    for prog_name, prog_cmd in cmd.categories.items():
        settings = {}
        for key, p in prog_cmd.settings.items():
            info: dict[str, Any] = {"default": _val(p), "type": p.typology}
            if p.typology == "enum":
                info["values"] = p.values
            elif p.typology == "range":
                info.update(min=p.min, max=p.max, step=p.step)
            settings[key] = info
        out[prog_name] = settings
    return json.dumps(out, indent=2, default=str)


@mcp.tool()
async def start_program(
    program: str,
    settings: dict[str, str | float] | None = None,
    appliance: str | None = None,
) -> str:
    """Start a wash program. PHYSICAL ACTION: confirm program and settings with the user first.

    The machine must be loaded, door closed, and remote control enabled on the
    machine itself. `settings` overrides defaults, e.g. {"temp": "40", "spinSpeed": "1200"}.
    Use list_programs for valid names and values.
    """
    a = await _appliance(appliance)
    cmd = a.commands["startProgram"]
    if program not in cmd.categories:
        raise RuntimeError(f"Unknown program {program!r}, see list_programs")
    cmd.category = program
    prog_cmd = a.commands["startProgram"]
    for key, value in (settings or {}).items():
        if key not in prog_cmd.settings:
            raise RuntimeError(f"Unknown setting {key!r} for {program}")
        prog_cmd.settings[key].value = value
    await prog_cmd.send()
    return f"Started {program} on {a.nick_name}"


@mcp.tool()
async def stop_program(appliance: str | None = None) -> str:
    """Stop the running program."""
    a = await _appliance(appliance)
    await a.commands["stopProgram"].send()
    return f"Stop sent to {a.nick_name}"


@mcp.tool()
async def pause_program(appliance: str | None = None) -> str:
    """Pause the running program."""
    a = await _appliance(appliance)
    await a.commands["pauseProgram"].send()
    return f"Pause sent to {a.nick_name}"


@mcp.tool()
async def resume_program(appliance: str | None = None) -> str:
    """Resume a paused program."""
    a = await _appliance(appliance)
    await a.commands["resumeProgram"].send()
    return f"Resume sent to {a.nick_name}"


if __name__ == "__main__":
    # stdio locally; MCP_TRANSPORT=streamable-http (+ MCP_HOST/MCP_PORT) for LAN serving
    mcp.run(os.environ.get("MCP_TRANSPORT", "stdio"))
