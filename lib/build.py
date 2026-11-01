"""Build steps for each repo. Trustee's branch merge + anti-replay feature/config
patches are no longer done here -- they're committed directly on the
`feature/anti-replay-container` branch (merging `feature/anti-replay-vtpm` and
`kbs-softhsm`, plus the Dockerfile FEATURES and config_resource.toml changes),
so the harness just checks that branch out like any other."""
from pathlib import Path

from . import shell

DOCKERFILE_REL = "kbs/docker/kbs-softhsm-pkcs11/Dockerfile"


def build_cocoonfs_cli(cocoon_tpm_dir: Path) -> Path:
    shell.run(["cargo", "build", "-p", "cocoonfs-cli"], cwd=cocoon_tpm_dir)
    return cocoon_tpm_dir / "target" / "debug" / "cocoonfs"


def build_vtpm_to_svsm_blk(repo_dir: Path):
    shell.run(["cargo", "build"], cwd=repo_dir)


def build_trustee_image(repo_dir: Path, image_tag: str):
    shell.run(
        ["podman", "build", "-t", image_tag, "-f", DOCKERFILE_REL, "."],
        cwd=repo_dir,
    )


def build_kbs_client(repo_dir: Path) -> Path:
    shell.run(["cargo", "build", "-p", "kbs-client", "--locked", "--release"], cwd=repo_dir)
    return repo_dir / "target" / "release" / "kbs-client"


def build_tpm_provisioner_image(repo_dir: Path, image_tag: str):
    shell.run(["podman", "build", "-t", image_tag, "-f", "Dockerfile", "."], cwd=repo_dir)
