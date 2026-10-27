"""Lathe server: one process, one tool per operation, plus health and discovery calls."""

import argparse

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import __version__
from . import skills as skills_mod
from .config import Config, config_path
from .modules import Module, Requirement, all_modules

PUBLISHER = "Seaynic Labs"
HOMEPAGE = "https://github.com/seayniclabs/lathe"

INSTRUCTIONS = (
    "Lathe processes files and media on this machine: images, PDFs, audio and video, and OCR. "
    "Call lathe_modules first: it lists the modules, which are on, which pieces are missing and the command to install each. "
    "Skills (MCP prompts) explain how to do the job well; start with the getting-started prompt. "
    "Paths are relative to the working directory (LATHE_WORKING_DIR) and must stay inside it. "
    "No output replaces an existing file unless overwrite=true. "
    "Tools that write files ask the person to approve first. "
    "Errors read 'lathe.<module>.<code>: <message> Fix: <hint>'."
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)


class DependencyInfo(BaseModel):
    kind: str = Field(description="python or binary")
    name: str
    available: bool
    install: str


class HealthResult(BaseModel):
    status: str
    version: str
    working_dir: str
    dependencies: list[DependencyInfo]


class MissingDependency(BaseModel):
    kind: str
    name: str
    install: str


class ToolInfo(BaseModel):
    name: str
    description: str
    available: bool
    missing: list[MissingDependency]


class SettingInfo(BaseModel):
    env_var: str
    help: str
    default: str | None
    set: bool


class ModuleInfo(BaseModel):
    name: str
    summary: str
    enabled: bool
    available: bool
    missing: list[MissingDependency]
    tools: list[ToolInfo]
    settings: list[SettingInfo] | None = None


class SkillInfo(BaseModel):
    name: str
    description: str
    license: str


class ModulesResult(BaseModel):
    version: str
    working_dir: str
    config_file: str
    config_error: str | None
    modules: list[ModuleInfo]
    skills: list[SkillInfo]
    publisher: str = PUBLISHER
    homepage: str = HOMEPAGE


def _missing(reqs: list[Requirement]) -> list[MissingDependency]:
    return [MissingDependency(kind=r.kind, name=r.name, install=r.install) for r in reqs if not r.available()]


def build_server(config: Config | None = None, modules: list[Module] | None = None, **settings) -> FastMCP:
    config = config or Config()
    modules = modules if modules is not None else all_modules()
    mcp = FastMCP("lathe", instructions=INSTRUCTIONS, **settings)
    # FastMCP 1.x reports the SDK's version unless the low-level server is told otherwise.
    mcp._mcp_server.version = __version__

    for module in modules:
        if config.enabled(module.name, module.default_enabled):
            module.register(mcp, config)

    loaded_skills = skills_mod.register(mcp, "lathe")

    @mcp.tool(annotations=READ_ONLY)
    def health() -> HealthResult:
        """Server status, version, working directory, and whether each external piece is installed."""
        reqs = {f"{r.kind}:{r.name}": r for m in modules for r in m.requirements}
        deps = [DependencyInfo(kind=r.kind, name=r.name, available=r.available(), install=r.install)
                for r in reqs.values()]
        return HealthResult(status="ok", version=__version__, working_dir=str(config.working_dir()), dependencies=deps)

    @mcp.tool(annotations=READ_ONLY)
    def lathe_modules(module: str | None = None) -> ModulesResult:
        """Which modules are on, which pieces are missing (with the install command), and what each tool does.
        Pass a module name for its settings too."""
        infos = []
        for m in modules:
            if module and m.name != module:
                continue
            tools = []
            for spec in m.tools:
                missing = _missing(list(spec.requires))
                tools.append(ToolInfo(name=spec.name, description=spec.description,
                                      available=not missing, missing=missing))
            missing_all = _missing(m.requirements)
            info = ModuleInfo(
                name=m.name, summary=m.summary,
                enabled=config.enabled(m.name, m.default_enabled),
                available=not missing_all, missing=missing_all, tools=tools,
            )
            if module:
                info.settings = [
                    SettingInfo(env_var=s.env_var(m.name), help=s.help, default=s.default,
                                set=bool(config.get(m.name, s.key)))
                    for s in m.settings
                ]
            infos.append(info)
        return ModulesResult(
            version=__version__, working_dir=str(config.working_dir()),
            config_file=str(config_path(config.env)), config_error=config.file_error, modules=infos,
            skills=[SkillInfo(name=s["name"], description=s["description"], license=s["license"]) for s in loaded_skills],
        )

    return mcp


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="lathe", description=INSTRUCTIONS)
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP only. Keep 127.0.0.1 unless you add auth in front.")
    parser.add_argument("--port", type=int, default=8765, help="HTTP only.")
    parser.add_argument("--version", action="version", version=f"lathe {__version__}")
    parser.add_argument("--doctor", action="store_true", help="Check settings and installed programs, print fixes, and exit.")
    args = parser.parse_args(argv)

    if args.doctor:
        from .doctor import run
        raise SystemExit(run())

    if args.transport == "http":
        build_server(host=args.host, port=args.port).run(transport="streamable-http")
    else:
        build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
