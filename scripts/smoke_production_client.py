#!/usr/bin/env python3
"""Exercise the public API flow from a disposable container on the ingress network."""

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path
from uuid import uuid4


def request(opener, base_url, path, *, method="GET", payload=None, headers=None):
    data = None if payload is None else json.dumps(payload).encode()
    request_headers = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{base_url}{path}", data=data, method=method, headers=request_headers
    )
    try:
        with opener.open(request, timeout=15) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        body = error.read().decode(errors="replace")
        raise RuntimeError(f"{method} {path} returned {error.code}: {body}") from error


def upload_bot(opener, base_url, *, name, executable_path):
    boundary = f"----AhinArenaSmoke{uuid4().hex}"
    executable = executable_path.read_bytes()
    fields = [
        ("game_id", "tictactoe"),
        ("name", name),
    ]
    body = bytearray()
    for field_name, value in fields:
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        b'Content-Disposition: form-data; name="executable"; filename="smoke-player"\r\n'
    )
    body.extend(
        f"Content-Type: {mimetypes.guess_type(executable_path.name)[0] or 'application/octet-stream'}\r\n\r\n".encode()
    )
    body.extend(executable)
    body.extend(f"\r\n--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        f"{base_url}/bots",
        data=bytes(body),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    with opener.open(request, timeout=30) as response:
        if response.status != 201:
            raise RuntimeError(f"bot upload returned {response.status}")
        return json.loads(response.read())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--verification-token")
    parser.add_argument("--bot-dir", type=Path)
    parser.add_argument("--register-only", action="store_true")
    parser.add_argument("--already-registered", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    arguments = parser.parse_args()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    status, readiness = request(opener, arguments.base_url, "/health/ready")
    assert status == 200 and readiness == {"status": "ok"}, readiness

    if arguments.check_only:
        print(json.dumps({"smoke": "restart_check_passed", "readiness": readiness}))
        return

    if not arguments.already_registered:
        status, registration = request(
            opener,
            arguments.base_url,
            "/auth/register",
            method="POST",
            payload={"email": arguments.email, "username": arguments.username, "password": arguments.password},
        )
        assert status == 201, registration
        if arguments.register_only:
            print(json.dumps({"smoke": "registered", "user": registration["user"]}))
            return

    if not arguments.verification_token or arguments.bot_dir is None:
        raise ValueError("--verification-token and --bot-dir are required after registration")
    status, _ = request(
        opener,
        arguments.base_url,
        "/auth/verify-email",
        method="POST",
        payload={"token": arguments.verification_token},
    )
    assert status == 200
    status, login = request(
        opener,
        arguments.base_url,
        "/auth/login",
        method="POST",
        payload={"email": arguments.email, "password": arguments.password},
    )
    assert status == 200, login
    upload_bot(opener, arguments.base_url, name="smokebotone", executable_path=arguments.bot_dir / "one")
    upload_bot(opener, arguments.base_url, name="smokebottwo", executable_path=arguments.bot_dir / "two")
    status, queued = request(
        opener,
        arguments.base_url,
        "/matches",
        method="POST",
        payload={"game": "tictactoe", "players": [{"bot": "smokebotone"}, {"bot": "smokebottwo"}]},
    )
    assert status == 202, queued
    job_id = queued["job_id"]
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        status, job = request(opener, arguments.base_url, f"/match-jobs/{job_id}")
        assert status == 200
        if job["status"] == "completed":
            print(json.dumps({"smoke": "completed", "job_id": job_id, "match_id": job["match_id"]}))
            return
        if job["status"] == "failed":
            raise RuntimeError(f"match job failed: {job}")
        time.sleep(1)
    raise TimeoutError(f"match job {job_id} did not complete within 90 seconds")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"production smoke test failed: {error}", file=sys.stderr)
        raise
