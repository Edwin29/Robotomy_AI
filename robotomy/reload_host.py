"""Stable player MCP host. Reload immutable implementation generations only between calls.

Storage, process ownership and this host stay resident. A bad edit blocks dispatch,
never silently runs stale input code. No file watcher thread or game input is used.
"""
import asyncio
import hashlib
import importlib
import json
from pathlib import Path
import sys
import types
import uuid
from mcp import types as mt
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

HOT = ('live', 'live_control', 'virtual_input', 'history', 'mcp_server')
PINNED = ('experience', 'store', 'mock', 'game_power', 'observer_window', '__init__', 'reload_host', 'input_sequence')


def fingerprint(sources):
    return hashlib.sha256(b''.join(name.encode()+b'\0'+sources[name] for name in sorted(sources))).hexdigest()


class ReloadHost:
    def __init__(self, root, source=None):
        self.root = Path(root).resolve()
        self.source = Path(source or Path(__file__).parent)
        self.condition = asyncio.Condition()
        self.active = 0
        self.reloading = False
        self.backend = None
        self.prefix = None
        self.revision = None
        self.error = None
        self.catalog = None
        self.pinned = self.read(PINNED)
        from .game_power import GamePower
        from .experience import journal
        self.power = GamePower(self.root)
        self.experience = journal(self.root)

    def read(self, names):
        return {name:(self.source/(name+'.py')).read_bytes() for name in names}

    @staticmethod
    def discard(prefix):
        if prefix:
            for name in list(sys.modules):
                if name == prefix or name.startswith(prefix+'.'):
                    del sys.modules[name]

    def build(self, sources):
        # Compile every file before executing any of the candidate modules.
        code = {name:compile(data, str(self.source/(name+'.py')), 'exec') for name,data in sources.items()}
        prefix = '_robotomy_generation_'+uuid.uuid4().hex
        package = types.ModuleType(prefix)
        package.__path__ = []
        sys.modules[prefix] = package
        try:
            # Shared storage owns its single queue/worker for the entire host lifetime.
            for name in ('experience','store','game_power'):
                sys.modules[prefix+'.'+name] = importlib.import_module('robotomy.'+name)
            for name in HOT:
                module = types.ModuleType(prefix+'.'+name)
                module.__package__ = prefix
                module.__file__ = str(self.source/(name+'.py'))
                sys.modules[module.__name__] = module
                exec(code[name], module.__dict__)
            backend = sys.modules[prefix+'.mcp_server'].create_server(self.root, player_only=True, power=self.power)
            return prefix, backend
        except BaseException:
            self.discard(prefix)
            raise

    @staticmethod
    def contract(tools):
        return {t.name:(t.inputSchema,t.outputSchema) for t in tools}

    async def refresh_locked(self):
        """Caller holds condition; callbacks already in flight must finish before swap."""
        try:
            if self.read(PINNED) != self.pinned:
                raise RuntimeError('Resident component changed; MCP reconnection required.')
            sources = self.read(HOT)
            revision = fingerprint(sources)
            if revision == self.revision:
                self.error = None
                return
            sequences = getattr(self.backend, '_input_sequences', None)
            if sequences is not None and sequences.has_active():
                raise RuntimeError('Input sequence active; cancel or finish before code reload.')
            self.reloading = True
            await self.condition.wait_for(lambda: self.active == 0)
            # Freeze the newest complete bytes after waiting for existing calls.
            sources = self.read(HOT)
            revision = fingerprint(sources)
            if any((self.root/'.robotomy/live/control'/n).exists() for n in ('request.json','virtual-command.txt')):
                raise RuntimeError('Pending game input; resolve receipt before reload.')
            await asyncio.to_thread(self.experience.flush)
            prefix, candidate = self.build(sources)
            try:
                catalog = await candidate.list_tools()
                if self.catalog is not None and self.contract(catalog) != self.contract(self.catalog):
                    raise RuntimeError('Tool schema changed; MCP reconnection required.')
            except BaseException:
                self.discard(prefix)
                raise
            old = self.prefix
            self.prefix, self.backend, self.catalog = prefix, candidate, catalog
            self.revision, self.error = revision, None
            self.discard(old)
        except Exception as exc:
            # Do not return source, internal paths or game implementation details to player.
            self.error = str(exc) if isinstance(exc, RuntimeError) else 'Code reload failed: '+type(exc).__name__+'. Ask operator to repair.'
        finally:
            self.reloading = False
            self.condition.notify_all()

    async def initialize(self):
        async with self.condition:
            await self.refresh_locked()
            if self.error: raise RuntimeError(self.error)

    def status(self):
        return {'status':'blocked' if self.error else 'ready', 'code_revision':self.revision,
                'active_calls':self.active, 'reload_error':self.error,
                'scope':'Observation/input/tool implementations auto-reload at idle boundaries; storage, host, power and tool schema require MCP reconnect. Game DLL requires separate maintenance.'}

    async def call(self, name, arguments):
        async with self.condition:
            await self.condition.wait_for(lambda: not self.reloading)
            await self.refresh_locked()
            if name in ('player_runtime_status','reload_player_code'):
                return self.status()
            # A pending command must remain inspectable even while reload is blocked.
            if self.error and name not in ('live_action_receipt','input_sequence_status','cancel_input_sequence'):
                raise RuntimeError(self.error)
            backend = self.backend
            self.active += 1
        try:
            return await backend.call_tool(name, arguments)
        finally:
            async with self.condition:
                self.active -= 1
                self.condition.notify_all()

    async def tools(self):
        # Keep catalog stable for existing clients; implementation changes need no rediscovery.
        return list(self.catalog or []) + [mt.Tool(name=name,description=description,
            inputSchema={'type':'object','properties':{},'additionalProperties':False})
            for name,description in (
                ('player_runtime_status','Check loaded code revision and reload errors. Does not play, resume or restart game.'),
                ('reload_player_code','Apply local code edits when calls are idle. No source/path arguments. Preserves game, operator stop and experience. Also automatic before every tool call.'))]


async def serve(root):
    host = ReloadHost(root)
    await host.initialize()
    server = Server('Robotomy Player', version='1.0.0', instructions=host.backend.instructions)
    @server.list_tools()
    async def list_tools():
        return await host.tools()
    @server.call_tool()
    async def call_tool(name, arguments):
        return await host.call(name, arguments)
    try:
        async with stdio_server() as (incoming,outgoing):
            await server.run(incoming,outgoing,server.create_initialization_options())
    finally:
        await asyncio.to_thread(host.experience.flush)
        host.discard(host.prefix)
