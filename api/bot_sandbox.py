import os
import secrets
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from api.errors import api_error
from api.models import Bot


DEFAULT_BOT_SANDBOX_IMAGE = "ahinarena-bot-runner:latest"
DEFAULT_BOT_SANDBOX_MEMORY_LIMIT = "128m"
DEFAULT_BOT_SANDBOX_CPU_LIMIT = "0.5"
DEFAULT_BOT_SANDBOX_PIDS_LIMIT = "64"
DEFAULT_BOT_SANDBOX_TMPFS_SIZE = "16m"
DEFAULT_DOCKER_BINARY = "docker"
BOT_SANDBOX_SOURCE_PATH = "/bot/source.py"


@dataclass(frozen=True)
class BotSandbox:
    command: list[str]
    container_name: str
    temp_dir: Path
    source_path: Path

    def cleanup(self) -> None:
        cleanup_bot_sandbox(self)


def _env_setting(name: str, default: str) -> str:
    return os.environ.get(name, default).strip() or default


def _remove_readonly(_func, path, _exc_info) -> None:
    os.chmod(path, 0o666)
    os.remove(path)


def build_bot_sandbox(bot: Bot) -> BotSandbox:
    if bot.active_submission_id is None or bot.active_submission is None:
        api_error(
            400,
            "bot_has_no_submission",
            f"Bot has no active submission: {bot.name}",
        )

    temp_dir = Path(
        tempfile.mkdtemp(prefix=f"ahinarena_bot_{bot.id}_", suffix="_sandbox")
    )
    source_path = temp_dir / "source.py"

    try:
        source_path.write_text(bot.active_submission.source_code, encoding="utf-8")
        source_path.chmod(0o444)

        container_name = f"ahinarena-bot-{bot.id}-{secrets.token_hex(8)}"
        docker_binary = _env_setting("DOCKER_BINARY", DEFAULT_DOCKER_BINARY)
        image = _env_setting("BOT_SANDBOX_IMAGE", DEFAULT_BOT_SANDBOX_IMAGE)
        memory_limit = _env_setting(
            "BOT_SANDBOX_MEMORY_LIMIT",
            DEFAULT_BOT_SANDBOX_MEMORY_LIMIT,
        )
        cpu_limit = _env_setting("BOT_SANDBOX_CPU_LIMIT", DEFAULT_BOT_SANDBOX_CPU_LIMIT)
        pids_limit = _env_setting(
            "BOT_SANDBOX_PIDS_LIMIT",
            DEFAULT_BOT_SANDBOX_PIDS_LIMIT,
        )
        tmpfs_size = _env_setting(
            "BOT_SANDBOX_TMPFS_SIZE",
            DEFAULT_BOT_SANDBOX_TMPFS_SIZE,
        )

        command = [
            docker_binary,
            "run",
            "--rm",
            "-i",
            "--init",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--read-only",
            "--tmpfs",
            f"/tmp:rw,noexec,nosuid,nodev,size={tmpfs_size}",
            "--memory",
            memory_limit,
            "--cpus",
            cpu_limit,
            "--pids-limit",
            pids_limit,
            "--name",
            container_name,
            "--mount",
            f"type=bind,src={source_path},dst={BOT_SANDBOX_SOURCE_PATH},readonly",
            image,
        ]
        return BotSandbox(
            command=command,
            container_name=container_name,
            temp_dir=temp_dir,
            source_path=source_path,
        )
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def cleanup_bot_sandbox(sandbox: BotSandbox | None) -> None:
    if sandbox is None:
        return

    docker_binary = sandbox.command[0] if sandbox.command else DEFAULT_DOCKER_BINARY
    try:
        subprocess.run(
            [docker_binary, "rm", "--force", sandbox.container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        pass

    shutil.rmtree(sandbox.temp_dir, onerror=_remove_readonly)
