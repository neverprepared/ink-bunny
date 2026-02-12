"""CLI entrypoint: python -m container_lifecycle <command> [options]."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .log import setup_logging


def main() -> None:
    setup_logging()

    parser = argparse.ArgumentParser(prog="container-lifecycle")
    sub = parser.add_subparsers(dest="command")

    # Common opts
    def add_session_opts(p: argparse.ArgumentParser) -> None:
        p.add_argument("--session", default="default")
        p.add_argument("--port", type=int, default=None)
        p.add_argument("--hardened", action="store_true", default=False)
        p.add_argument("--ttl", type=int, default=None)
        p.add_argument("--volume", action="append", default=[])

    # provision
    p_prov = sub.add_parser("provision")
    add_session_opts(p_prov)

    # run (full pipeline)
    p_run = sub.add_parser("run")
    add_session_opts(p_run)

    # recycle
    p_recycle = sub.add_parser("recycle")
    p_recycle.add_argument("--session", default="default")
    p_recycle.add_argument("--reason", default="cli")

    # api
    p_api = sub.add_parser("api")
    p_api.add_argument("--host", default="127.0.0.1")
    p_api.add_argument("--port", type=int, default=8000)
    p_api.add_argument("--reload", action="store_true", default=False)

    # mcp
    p_mcp = sub.add_parser("mcp")
    p_mcp.add_argument("--url", default=None, help="API URL (default: $CONTAINER_LIFECYCLE_URL or http://127.0.0.1:8000)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        if args.command == "provision":
            asyncio.run(_provision(args))
        elif args.command == "run":
            asyncio.run(_run_pipeline(args))
        elif args.command == "recycle":
            asyncio.run(_recycle(args))
        elif args.command == "api":
            _start_api(args)
        elif args.command == "mcp":
            _start_mcp(args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        sys.exit(1)


async def _provision(args: argparse.Namespace) -> None:
    from .lifecycle import provision

    ctx = await provision(
        session_name=args.session,
        port=args.port,
        hardened=args.hardened,
        ttl=args.ttl,
        volume_mounts=args.volume,
    )
    print(json.dumps({"ok": True, "session": ctx.session_name, "port": ctx.port}))


async def _run_pipeline(args: argparse.Namespace) -> None:
    from .lifecycle import run_pipeline

    ctx = await run_pipeline(
        session_name=args.session,
        port=args.port,
        hardened=args.hardened,
        ttl=args.ttl,
        volume_mounts=args.volume,
    )
    print(json.dumps({
        "ok": True,
        "session": ctx.session_name,
        "port": ctx.port,
        "url": f"http://localhost:{ctx.port}",
    }))


async def _recycle(args: argparse.Namespace) -> None:
    from .lifecycle import recycle

    await recycle(args.session, reason=args.reason)


def _start_mcp(args: argparse.Namespace) -> None:
    import os

    if args.url:
        os.environ["CONTAINER_LIFECYCLE_URL"] = args.url

    from .mcp_server import run
    run()


def _start_api(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run(
        "container_lifecycle.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
