"""Run real Next/FastAPI/Postgres E2E with isolated auth/catalog boundaries.

Invoke using backend's Poetry Python: cd backend; poetry run python ../e2e/run.py
Never reads .env files or connects to production. Leaves logs/screenshots under
.codex/e2e for inspection. No production source file is rewritten for testing.
"""

# All subprocess arguments below are fixed commands and local test paths.
# No user input or provider data becomes executable text.
# ruff: noqa: S603

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwk, jwt
from testcontainers.postgres import PostgresContainer

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "frontend"
sys.path.insert(0, str(ROOT / "backend"))
NODE = shutil.which("node")
if not NODE:
    raise RuntimeError("Node.js must be installed to run browser tests.")


def port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_http(url: str, process: subprocess.Popen, seconds: int = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited: {process.returncode}")
        try:
            if httpx.get(url, timeout=2).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise TimeoutError(f"Server did not become ready: {url}")


def check_network_guards(api: str, accounts: dict) -> None:
    recipient = accounts["e2e_mobile_recipient"]
    headers = {"Authorization": "Bearer " + recipient["token"]}
    with httpx.Client(base_url=api, headers=headers) as client:
        inbox = client.get("/api/v1/melodies/inbox").raise_for_status().json()
        path = "/api/v1/melodies/" + inbox["items"][0]["id"] + "/react"
        for _ in range(31):
            response = client.post(path, json={"reaction": "loved"})
            if response.status_code == 429:
                break
            response.raise_for_status()
        else:
            raise AssertionError("Reaction rate limit did not reject real HTTP traffic")
        if client.get("/api/v1/health").status_code != 200:
            raise AssertionError("Rate limiting broke the health route")
    print("Real HTTP reaction rate limiting: passed (429).", flush=True)


async def seed(url: str, accounts: dict, track_mbid: str) -> None:
    # Imports occur only after disposable settings have been assigned.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.models.catalog import Artist, Track
    from app.models.user import User

    engine = create_async_engine(url)
    async with async_sessionmaker(engine)() as session:
        artist = Artist(
            mbid=str(uuid.uuid4()), name="E2E Artist", last_fetched_at=datetime.now(UTC)
        )
        session.add(artist)
        await session.flush()
        session.add(
            Track(
                mbid=track_mbid,
                title="E2E 青い空 / & Song",
                artist_id=artist.id,
                last_fetched_at=datetime.now(UTC),
            )
        )
        for account in accounts.values():
            session.add(
                User(
                    clerk_id=account["id"],
                    username=account["username"],
                    display_name=account["username"],
                )
            )
        await session.commit()
    await engine.dispose()


def main() -> int:
    artifact_parent = ROOT / ".codex" / "e2e"
    artifact_parent.mkdir(parents=True, exist_ok=True)
    artifacts = Path(tempfile.mkdtemp(prefix="v1-", dir=artifact_parent))
    api_port, frontend_port = port(), port()
    base = f"http://localhost:{frontend_port}"
    api = f"http://127.0.0.1:{api_port}"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = jwk.construct(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ),
        "RS256",
    ).to_dict()
    public["kid"] = "harmoniq-disposable-e2e"
    track_mbid = str(uuid.uuid4())
    accounts = {}
    for viewport in ("desktop", "mobile"):
        for role in ("sender", "recipient"):
            name = f"e2e_{viewport}_{role}"
            claims = {
                "sub": name,
                "username": name,
                "exp": int(time.time()) + 7200,
                "iat": int(time.time()),
            }
            accounts[name] = {
                "id": name,
                "username": name,
                "token": jwt.encode(
                    claims, pem, algorithm="RS256", headers={"kid": public["kid"]}
                ),
            }
    fixture_file = artifacts / "fixtures.json"
    fixture_file.write_text(
        json.dumps({"accounts": accounts, "track": track_mbid}), encoding="utf-8"
    )

    class Provider(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/jwks":
                payload = {"keys": [public]}
            elif self.path.startswith("/mb/recording/"):
                payload = {
                    "relations": [
                        {
                            "target-type": "url",
                            "type": "streaming",
                            "url": {
                                "resource": "https://open.spotify.com/track/0123456789abcdefghijkl"
                            },
                        }
                    ]
                }
            else:
                payload = {}
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    provider = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=provider.serve_forever, daemon=True).start()
    provider_url = f"http://127.0.0.1:{provider.server_port}"
    children = []
    logs = []
    try:
        with PostgresContainer("postgres:16-alpine") as pg:
            database_url = (
                "postgresql+asyncpg://" + pg.get_connection_url().split("://", 1)[1]
            )
            env = {
                key: value
                for key, value in os.environ.items()
                if not any(
                    word in key.upper()
                    for word in (
                        "CLERK",
                        "SPOTIFY",
                        "R2_",
                        "DATABASE_URL",
                        "TOKEN_ENCRYPTION",
                    )
                )
            }
            env.update(
                {
                    "DATABASE_URL": database_url,
                    "CLERK_JWKS_URL": provider_url + "/jwks",
                    "MUSICBRAINZ_USER_AGENT": "Harmoniq/e2e (ci@harmoniq.test)",
                    "APP_ENV": "test",
                    "CORS_ALLOWED_ORIGINS": base,
                    "E2E_PROVIDER_URL": provider_url + "/mb",
                    "NEXT_PUBLIC_API_URL": api,
                    "NEXT_TELEMETRY_DISABLED": "1",
                    "E2E_BASE_URL": base,
                    "E2E_API_URL": api,
                    "E2E_FIXTURES": str(fixture_file),
                    "E2E_ARTIFACTS": str(artifacts),
                    "PYTHONPATH": os.pathsep.join([str(ROOT / "backend"), str(ROOT)]),
                }
            )
            # Backend Settings reads only this new process environment and the
            # worktree (which has no copied .env). No secret source is consulted.
            os.environ.clear()
            os.environ.update(env)
            print(f"E2E artifacts: {artifacts}", flush=True)
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=ROOT / "backend",
                env=env,
                check=True,
            )
            asyncio.run(seed(database_url, accounts, track_mbid))
            runtime = artifacts / "frontend"
            runtime.mkdir()
            for name in ("src", "public"):
                if (FRONT / name).exists():
                    shutil.copytree(
                        FRONT / name,
                        runtime / name,
                        ignore=shutil.ignore_patterns("__tests__"),
                    )
            for name in (
                "package.json",
                "package-lock.json",
                "tsconfig.json",
                "next.config.ts",
                "postcss.config.mjs",
                "eslint.config.mjs",
            ):
                shutil.copy2(FRONT / name, runtime / name)
            modules = runtime / "node_modules"
            if os.name == "nt":
                powershell = shutil.which("pwsh") or shutil.which("powershell")
                if not powershell:
                    raise RuntimeError("PowerShell is needed to create a test junction")
                subprocess.run(
                    [
                        powershell,
                        "-NoProfile",
                        "-NonInteractive",
                        "-Command",
                        "New-Item -ItemType Junction -Path $env:E2E_NODE_LINK "
                        "-Target $env:E2E_NODE_SOURCE | Out-Null",
                    ],
                    env={
                        **env,
                        "E2E_NODE_LINK": str(modules),
                        "E2E_NODE_SOURCE": str(FRONT / "node_modules"),
                    },
                    check=True,
                    stdout=subprocess.DEVNULL,
                )
            else:
                modules.symlink_to(FRONT / "node_modules", target_is_directory=True)
            for source in (runtime / "src").rglob("*"):
                if source.suffix not in (".ts", ".tsx"):
                    continue
                content = (
                    source.read_text(encoding="utf-8")
                    .replace('"@clerk/nextjs/server"', '"@/e2e-auth/server"')
                    .replace('"@clerk/nextjs"', '"@/e2e-auth/client"')
                )
                source.write_text(content, encoding="utf-8")
            auth_dir = runtime / "src" / "e2e-auth"
            auth_dir.mkdir()
            shutil.copy2(ROOT / "e2e" / "auth-client.tsx", auth_dir / "client.tsx")
            shutil.copy2(ROOT / "e2e" / "auth-server.ts", auth_dir / "server.ts")
            layout = runtime / "src" / "app" / "layout.tsx"
            content = layout.read_text(encoding="utf-8")
            content = 'import { fixtureSession } from "@/e2e-auth/server";\n' + content
            content = content.replace(
                "<ClerkProvider appearance={clerkAppearance}>",
                "<ClerkProvider appearance={clerkAppearance} "
                "fixture={await fixtureSession()}>",
            )
            layout.write_text(content, encoding="utf-8")
            config = runtime / "next.config.ts"
            content = config.read_text(encoding="utf-8").replace(
                "const nextConfig: NextConfig = {",
                "const nextConfig: NextConfig = {\n  turbopack: { root: "
                + json.dumps(str(ROOT))
                + " },",
            )
            config.write_text(content, encoding="utf-8")

            api_log = (artifacts / "api.log").open("w", encoding="utf-8")
            logs.append(api_log)
            backend = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "e2e.api:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                ],
                cwd=ROOT / "backend",
                env=env,
                stdout=api_log,
                stderr=subprocess.STDOUT,
            )
            children.append(backend)
            wait_http(api + "/api/v1/health", backend)
            print(
                "Building disposable Next.js app with auth provider fixture.",
                flush=True,
            )
            build_log = (artifacts / "build.log").open("w", encoding="utf-8")
            logs.append(build_log)
            subprocess.run(
                [NODE, str(FRONT / "node_modules/next/dist/bin/next"), "build"],
                cwd=runtime,
                env=env,
                stdout=build_log,
                stderr=subprocess.STDOUT,
                check=True,
            )
            frontend_log = (artifacts / "frontend.log").open("w", encoding="utf-8")
            logs.append(frontend_log)
            frontend = subprocess.Popen(
                [
                    NODE,
                    str(FRONT / "node_modules/next/dist/bin/next"),
                    "start",
                    "--port",
                    str(frontend_port),
                    "--hostname",
                    "127.0.0.1",
                ],
                cwd=runtime,
                env=env,
                stdout=frontend_log,
                stderr=subprocess.STDOUT,
            )
            children.append(frontend)
            wait_http(base + "/sign-in", frontend)
            print(
                "Running browser scenarios against Next.js, FastAPI and PostgreSQL.",
                flush=True,
            )
            result = subprocess.run(
                [NODE, str(FRONT / "node_modules/@playwright/test/cli.js"), "test"],
                cwd=FRONT,
                env=env,
            )
            if result.returncode == 0:
                check_network_guards(api, accounts)
            return result.returncode
    finally:
        for child in reversed(children):
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for log in logs:
            log.close()
        provider.shutdown()
        provider.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
