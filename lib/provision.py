"""Builds a CocoonFS vTPM image via vtpm-to-svsm-blk and parses its printed
nonce/counter (see vtpm-to-svsm-blk/src/main.rs, the final SUCCESS banner).

The vTPM state fed into that image comes from the tpm_provisioner container
(git@github.com:armenon-rh/tpm_provisioner.git), which produces a real NVChip
state file at /app/tpm_provisioner/NVChip.
"""
import re
from pathlib import Path

from . import shell

_NONCE_RE = re.compile(r"Initial Nonce:\s+([0-9a-f]{32})")
_COUNTER_RE = re.compile(r"Initial Counter:\s+(\d+)")

NVCHIP_CONTAINER_PATH = "/app/tpm_provisioner/NVChip"


def generate_key(path: Path):
    shell.run(["openssl", "rand", "-out", str(path), "32"])


def generate_nvchip_state(image_tag: str, out_file: Path, container_name: str = "tpm-lab"):
    """Run tpm_provisioner's `provision && verify` once in a disposable container
    and copy the resulting NVChip state file out to `out_file`."""
    shell.run(["podman", "rm", "-f", container_name], check=False)
    try:
        shell.run([
            "podman", "run", "--name", container_name, image_tag,
            "sh", "-c", "tpm_provisioner provision && verify",
        ])
        shell.run(["podman", "cp", f"{container_name}:{NVCHIP_CONTAINER_PATH}", str(out_file)])
    finally:
        shell.run(["podman", "rm", "-f", container_name], check=False)


def provision_image(vtpm_blk_dir: Path, key_file: Path, state_file: Path,
                     resource_id: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = shell.run(
        ["cargo", "run", "--", "-c", "-k", str(key_file), "-s", str(state_file),
         "-r", resource_id, "-o", str(out_dir)],
        cwd=vtpm_blk_dir,
    )
    nonce_match = _NONCE_RE.search(proc.stdout)
    counter_match = _COUNTER_RE.search(proc.stdout)
    if not nonce_match or not counter_match:
        raise RuntimeError(
            "could not parse nonce/boot_counter from vtpm-to-svsm-blk output; "
            "its banner format may have changed:\n" + proc.stdout
        )
    return {
        "image": out_dir / "vtpm_state.img",
        "resource_id": resource_id,
        "nonce": nonce_match.group(1),
        "boot_counter": int(counter_match.group(1)),
    }
