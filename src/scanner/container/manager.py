from __future__ import annotations

import hashlib
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import docker

DEFAULT_BASE_IMAGE = "mcr.microsoft.com/playwright/python:v1.54.0-jammy"
CACHED_REPO_NAME = "a11y-scanner-cache"
CACHED_VENV_PATH = "/opt/a11y/venv"
IN_CONTAINER_ENV = "A11Y_SCANNER_IN_CONTAINER"
IN_CONTAINER_VALUE = "1"


def find_project_root(start: Optional[Path] = None) -> Path:
    """
    Locate the project root by searching upwards for pyproject.toml.
    Falls back to the current working directory if not found.
    """
    start = start or Path.cwd()
    current = start.resolve()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return current


@dataclass
class ContainerConfig:
    base_image: str = DEFAULT_BASE_IMAGE
    workdir: str = "/worksrc"
    data_subdir: str = "data"
    shm_size: str = "2g"
    env: dict[str, str] | None = None

    def __post_init__(self):
        if self.env is None:
            # Keep output unbuffered and quiet apt dialogs.
            self.env = {
                "PYTHONUNBUFFERED": "1",
                "DEBIAN_FRONTEND": "noninteractive",
            }


class ContainerManager:
    """
    Run the scanner in Docker with a fast path:
      - A cached derived image with python3-venv + your package in /opt/a11y/venv
      - Cache key = sha256(pyproject.toml + contents of src/)
    Fallback slow path (no cache):
      - apt-get python3-venv + pip install on each run

    Also supports running a long-lived API server (FastAPI+Uvicorn) in a container.
    """

    def __init__(
        self,
        project_root: Path | None = None,
        config: ContainerConfig | None = None,
    ):
        self.client = docker.from_env()
        self.project_root = (project_root or find_project_root()).resolve()
        self.config = config or ContainerConfig()

        # Detect Podman engine to avoid unsupported options (e.g., shm_size in host IPC)
        self._is_podman = False
        try:
            ver = self.client.version()
            comps = ver.get("Components") or []
            if any((c.get("Name") or "").lower().startswith("podman") for c in comps):
                self._is_podman = True
        except Exception:
            # Default to Docker-compatible behavior
            self._is_podman = False

        # Host paths
        self.repo_src = self.project_root
        self.data_dir = self.project_root / self.config.data_subdir

        # Container paths
        self.container_workdir = self.config.workdir
        self.container_repo_path = self.container_workdir  # bind repo here (ro)
        self.container_data_path = str(
            Path(self.container_workdir) / self.config.data_subdir
        )

    # ---------- generic helpers ----------

    def _host_uid_gid(self) -> tuple[int | None, int | None]:
        """Return (uid, gid) on Unix; (None, None) on Windows."""
        if platform.system().lower().startswith("win"):
            return (None, None)
        try:
            return (os.getuid(), os.getgid())
        except AttributeError:
            return (None, None)

    def _prepare_host_dirs(self) -> None:
        """Ensure host 'data' directory exists before binding it into the container."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def ensure_image(self) -> None:
        self.ensure_base_image()

    def _volumes(self) -> dict[str, dict[str, str]]:
        """
        Bind mount configuration.
        - repo: read-only at /worksrc (for data dir + visibility)
        - data: read-write at /worksrc/data for inputs/outputs
        """
        # On Podman (rootless + SELinux), require relabeling (":Z") for mounts
        repo_mode = "ro,Z" if self._is_podman else "ro"
        data_mode = "rw,Z" if self._is_podman else "rw"
        return {
            str(self.repo_src): {"bind": self.container_repo_path, "mode": repo_mode},
            str(self.data_dir): {"bind": self.container_data_path, "mode": data_mode},
        }

    def ensure_base_image(self) -> None:
        """Pull the base Playwright Python image if it is not present locally."""
        try:
            self.client.images.get(self.config.base_image)
        except docker.errors.ImageNotFound:
            print(f"[container] Pulling base image: {self.config.base_image}")
            self.client.images.pull(self.config.base_image)

    # ---------- cache key / image name ----------

    def _hash_file(self, path: Path, h: "hashlib._Hash") -> None:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)

    def _compute_cache_key(self) -> str:
        """
        Compute a stable key using pyproject.toml + src/ tree.
        If either changes, the cache invalidates.
        """
        h = hashlib.sha256()
        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            self._hash_file(pyproject, h)

        src_root = self.project_root / "src"
        if src_root.exists():
            for p in sorted(src_root.rglob("*")):
                if p.is_file():
                    # skip compiled junk
                    if p.suffix in {".pyc", ".pyo"}:
                        continue
                    self._hash_file(p, h)

        return h.hexdigest()

    def _cached_image_ref(self) -> tuple[str, str, str]:
        """
        Return (repository, tag, full_ref) for the cache image.
        Example:
          repo='a11y-scanner-cache', tag='9f1a0c3d2a10',
          full='a11y-scanner-cache:9f1a0c3d2a10'
        """
        key = self._compute_cache_key()[:12]
        repo = CACHED_REPO_NAME
        tag = key
        return repo, tag, f"{repo}:{tag}"

    def cached_image_exists(self) -> bool:
        _, _, full = self._cached_image_ref()
        try:
            self.client.images.get(full)
            return True
        except docker.errors.ImageNotFound:
            return False

    # ---------- prepare cached image ----------

    def prepare_cached_image(self) -> str:
        """
        Build a derived image with:
          - python3-venv installed
          - your project installed into /opt/a11y/venv
        Returns the full image ref (e.g. a11y-scanner-cache:<sha12>).
        """
        self.ensure_base_image()
        self._prepare_host_dirs()

        repo, tag, full = self._cached_image_ref()
        print(f"[cache] Building cached image {full} ...")

        volumes = self._volumes()

        # Command to install venv + your package into /opt/a11y/venv
        # We copy /worksrc (ro) -> /tmp/src so pip can write metadata.
        cmd = (
            "bash -lc '"
            "set -euo pipefail;"
            "apt-get update -y && "
            "apt-get install -y --no-install-recommends python3-venv && "
            "rm -rf /var/lib/apt/lists/* && "
            "rm -rf /tmp/src && mkdir -p /tmp/src && "
            "cp -a /worksrc/. /tmp/src && rm -rf /tmp/src/data && "
            f"python3 -m venv {CACHED_VENV_PATH} && "
            f"{CACHED_VENV_PATH}/bin/pip install --no-cache-dir /tmp/src && "
            "true'"
        )

        # Run as root, we need apt-get and /opt writes
        run_kwargs = dict(
            command=cmd,
            working_dir=self.container_workdir,
            environment=self.config.env,
            user="root",
            volumes=volumes,
            detach=True,
            auto_remove=False,  # we will commit it
        )
        if not self._is_podman and self.config.shm_size:
            run_kwargs["shm_size"] = self.config.shm_size
        container = self.client.containers.run(self.config.base_image, **run_kwargs)

        # Stream logs
        try:
            for line in container.logs(stream=True, follow=True):
                sys.stdout.buffer.write(line)
                sys.stdout.flush()
        except KeyboardInterrupt:
            print("\n[cache] Interrupted; stopping container...")
            container.stop(timeout=5)

        status = container.wait()
        code = int(status.get("StatusCode", 1))
        if code != 0:
            logs = container.logs().decode("utf-8", errors="ignore")
            container.remove(force=True)
            raise RuntimeError(f"[cache] Prepare failed with exit code {code}\n{logs}")

        # Commit the prepared container as a new image
        print(f"[cache] Committing image: {full}")
        container.commit(repository=repo, tag=tag)
        container.remove()

        print(f"[cache] Cached image ready: {full}")
        return full

    # ---------- run (cached / uncached) ----------

    def _command_uncached(self, chown_uid: int | None, chown_gid: int | None) -> str:
        chown_clause = ""
        if chown_uid is not None and chown_gid is not None:
            chown_clause = f" && chown -R {chown_uid}:{chown_gid} /worksrc/data"

        # Install on every run (slow path)
        return (
            "bash -lc '"
            "set -euo pipefail;"
            "apt-get update -y && "
            "apt-get install -y --no-install-recommends python3-venv && "
            "python3 -m venv /tmp/venv && "
            "rm -rf /tmp/src && mkdir -p /tmp/src && "
            "cp -a /worksrc/. /tmp/src && rm -rf /tmp/src/data && "
            "/tmp/venv/bin/pip install --no-cache-dir /tmp/src && "
            "cd /worksrc && /tmp/venv/bin/python -m scanner.main"
            f"{chown_clause}"
            "'"
        )

    def _command_cached(self) -> str:
        # Use the preinstalled venv from the cached image
        return (
            f"bash -lc 'set -e; cd /worksrc; "
            f"{CACHED_VENV_PATH}/bin/python -m scanner.main'"
        )

    def _command_api_uncached(self) -> str:
        # Slow path for API server
        return (
            "bash -lc '"
            "set -euo pipefail;"
            "apt-get update -y && "
            "apt-get install -y --no-install-recommends python3-venv && "
            "python3 -m venv /tmp/venv && "
            "rm -rf /tmp/src && mkdir -p /tmp/src && "
            "cp -a /worksrc/. /tmp/src && rm -rf /tmp/src/data && "
            "/tmp/venv/bin/pip install --no-cache-dir /tmp/src && "
            "cd /worksrc && /tmp/venv/bin/python -m scanner.web.server'"
        )

    def _command_api_cached(self) -> str:
        # Cached path for API server
        return (
            f"bash -lc 'set -e; cd /worksrc; "
            f"{CACHED_VENV_PATH}/bin/python -m scanner.web.server'"
        )

    def run_scanner(
        self,
        use_cache: bool = True,
        rebuild_cache: bool = False,
        stream_logs: bool = True,
    ) -> int:
        """
        Run the scanner and return its exit code.
        - use_cache: prefer cached image; auto-build if missing or rebuild requested
        - rebuild_cache: force rebuild of cached image
        """
        self._prepare_host_dirs()

        if use_cache:
            if rebuild_cache or not self.cached_image_exists():
                self.prepare_cached_image()
            _, _, cached_ref = self._cached_image_ref()
            return self._run_with_image(
                cached_ref, cached=True, stream_logs=stream_logs
            )
        else:
            # Slow path: base image + apt-get + pip each run
            self.ensure_base_image()
            return self._run_with_image(
                self.config.base_image, cached=False, stream_logs=stream_logs
            )

    def _run_with_image(self, image_ref: str, cached: bool, stream_logs: bool) -> int:
        volumes = self._volumes()

        # Merge env + mark container context for the app guards.
        env = dict(self.config.env or {})
        env[IN_CONTAINER_ENV] = IN_CONTAINER_VALUE

        if cached:
            # Run as host uid:gid so result files are owned by you.
            uid, gid = self._host_uid_gid()
            user = f"{uid}:{gid}" if uid is not None and gid is not None else None
            command = self._command_cached()
        else:
            # Need root for apt-get on the slow path
            user = "root"
            command = self._command_uncached(None, None)

        print(f"[container] Starting scanner container (image: {image_ref})...")
        run_kwargs = dict(
            command=command,
            working_dir=self.container_workdir,
            environment=env,
            user=user,
            volumes=volumes,
            detach=True,
            auto_remove=False,
        )
        if not self._is_podman and self.config.shm_size:
            run_kwargs["shm_size"] = self.config.shm_size
        container = self.client.containers.run(image_ref, **run_kwargs)

        if stream_logs:
            try:
                for line in container.logs(stream=True, follow=True):
                    sys.stdout.buffer.write(line)
                    sys.stdout.flush()
            except KeyboardInterrupt:
                print("\n[container] Interrupted by user, stopping container...")
                container.stop(timeout=5)

        try:
            status = container.wait()
            code = int(status.get("StatusCode", 1))
        except Exception:
            # Some engines (e.g., Podman) may remove container early; fall back to 0
            code = 0
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass
        print(f"[container] Exit code: {code}")
        return code

    # ---------- API server (long-running) ----------

    def run_api_server(
        self,
        host_port: int = 8008,
        use_cache: bool = True,
        rebuild_cache: bool = False,
        stream_logs: bool = True,
    ) -> int:
        """
        Launch the FastAPI server inside a container and port-forward to host_port.
        Blocks until Ctrl+C. Returns the container exit code.
        """
        self._prepare_host_dirs()
        if use_cache:
            if rebuild_cache or not self.cached_image_exists():
                self.prepare_cached_image()
            _, _, cached_ref = self._cached_image_ref()
            return self._run_api_with_image(
                cached_ref,
                cached=True,
                host_port=host_port,
                stream_logs=stream_logs,
            )
        else:
            self.ensure_base_image()
            return self._run_api_with_image(
                self.config.base_image,
                cached=False,
                host_port=host_port,
                stream_logs=stream_logs,
            )

    def _run_api_with_image(
        self, image_ref: str, cached: bool, host_port: int, stream_logs: bool
    ) -> int:
        volumes = self._volumes()

        env = dict(self.config.env or {})
        env[IN_CONTAINER_ENV] = IN_CONTAINER_VALUE

        if cached:
            uid, gid = self._host_uid_gid()
            user = f"{uid}:{gid}" if uid is not None and gid is not None else None
            command = self._command_api_cached()
        else:
            user = "root"
            command = self._command_api_uncached()

        print(
            f"[container] Starting API server (image: {image_ref}) at http://127.0.0.1:{host_port}"
        )
        run_kwargs = dict(
            command=command,
            working_dir=self.container_workdir,
            environment=env,
            user=user,
            volumes=volumes,
            ports={"8008/tcp": host_port},
            detach=True,
            auto_remove=False,
        )
        if not self._is_podman and self.config.shm_size:
            run_kwargs["shm_size"] = self.config.shm_size
        container = self.client.containers.run(image_ref, **run_kwargs)

        if stream_logs:
            try:
                for line in container.logs(stream=True, follow=True):
                    sys.stdout.buffer.write(line)
                    sys.stdout.flush()
            except KeyboardInterrupt:
                print("\n[container] Stopping API server container...")
                try:
                    container.stop(timeout=5)
                except Exception:
                    pass

        try:
            status = container.wait()
            code = int(status.get("StatusCode", 1))
        except Exception:
            code = 0
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass
        print(f"[container] API server exit code: {code}")
        return code
