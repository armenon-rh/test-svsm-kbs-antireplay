"""Lifecycle + REST/storage helpers for the merged anti-replay KBS container.

File-naming scheme for the on-disk KV store mirrors
deps/key-value-storage/src/local_fs/mod.rs (`/` escaped as `\\x2F`) and the
namespaces `repository` / `svsm-anti-replay` defined in
kbs/src/plugins/implementations/resource/backend.rs and kbs/src/anti_replay/mod.rs.
"""
import json
import time
from pathlib import Path

from . import http, shell


class KbsContainer:
    def __init__(self, name, image, port, storage_dir, softhsm_dir,
                 config_file="/etc/kbs/kbs-config-resource.toml"):
        self.name = name
        self.image = image
        self.port = port
        self.storage_dir = Path(storage_dir)
        self.softhsm_dir = Path(softhsm_dir)
        self.config_file = config_file

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        self.stop()
        (self.storage_dir / "kbs").mkdir(parents=True, exist_ok=True)
        self.softhsm_dir.mkdir(parents=True, exist_ok=True)
        (self.storage_dir / "kbs" / "resource-policy.rego").write_text(
            "package policy\n\ndefault allow = false\n\nallow if {\n    true\n}\n"
        )
        shell.run([
            "podman", "run", "-d", "--name", self.name,
            "-p", f"{self.port}:8080",
            "-v", f"{self.storage_dir}/:/etc/kbs/repository:Z",
            "-v", f"{self.softhsm_dir}/:/var/lib/softhsm/tokens:Z",
            self.image,
            "/usr/local/bin/kbs", "--config-file", self.config_file,
        ])
        self._wait_ready()

    def stop(self):
        shell.run(["podman", "rm", "-f", self.name], check=False)

    def _wait_ready(self, timeout=30):
        deadline = time.monotonic() + timeout
        last_err = None
        while time.monotonic() < deadline:
            try:
                http.curl_json("POST", f"{self.url}/kbs/v0/auth",
                                json_body={"version": "0.1.0", "tee": "sample"}, timeout=2)
                return
            except RuntimeError as e:
                last_err = e
                time.sleep(1)
        raise TimeoutError(f"KBS container did not become ready: {last_err}")

    def set_resource(self, kbs_client_bin: Path, resource_path: str, resource_file: Path):
        shell.run([
            str(kbs_client_bin), "--url", self.url, "config", "set-resource",
            "--path", resource_path, "--resource-file", str(resource_file),
        ])

    def register_nonce(self, resource_id: str, boot_counter: int, nonce_hex: str, version: int = 1):
        code, body = http.curl_json("POST", f"{self.url}/kbs/v0/svsm/register-nonce", json_body={
            "version": version,
            "resource_id": resource_id,
            "boot_counter": boot_counter,
            "nonce": nonce_hex,
        })
        if code != 200:
            raise RuntimeError(f"register-nonce failed: HTTP {code}: {body}")
        return body

    def get_resource_unauthenticated(self, resource_path: str):
        """Returns (status_code, body) for an unauthenticated GET — expected to be
        401 TokenNotFound, see api_server.rs resource GET branch."""
        return http.curl_json("GET", f"{self.url}/kbs/v0/resource/{resource_path}")

    def _kv_path(self, namespace: str, key: str) -> Path:
        return self.storage_dir / namespace / key.replace("/", "\\x2F")

    def read_anti_replay_record(self, resource_id: str):
        path = self._kv_path("svsm-anti-replay", resource_id)
        return json.loads(path.read_text()) if path.exists() else None

    def read_resource_secret(self, resource_id: str):
        path = self._kv_path("repository", resource_id)
        return path.read_bytes() if path.exists() else None
