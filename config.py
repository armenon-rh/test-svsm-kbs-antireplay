"""Central configuration for the anti-replay E2E harness, overridable via env vars.

Scope: build trustee + run the KBS container + provision a CocoonFS image +
register it, and verify via the on-host KV store and the KBS REST API.
Booting SVSM against the image is a deliberately separate, manual step (see
../anti_replay_test_plan.txt) -- see README.md for why.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Dedicated workspace, kept separate from any manually-managed checkouts of the
# same repos so this harness's `git reset --hard` never touches unrelated work.
WORKDIR = Path(os.environ.get("ANTI_REPLAY_WORKDIR", str(ROOT / "workspace")))

# feature/anti-replay-container (feature/anti-replay-vtpm + kbs-softhsm merged,
# plus the anti-replay Dockerfile/config.toml patches, all committed directly
# on the branch) is pushed to this fork. Override TRUSTEE_REPO_URL with a local
# path instead if you want the harness to build from uncommitted local changes.
TRUSTEE_REPO_URL = os.environ.get("TRUSTEE_REPO_URL", "https://github.com/armenon-rh/trustee.git")
TRUSTEE_BRANCH = os.environ.get("TRUSTEE_BRANCH", "feature/anti-replay-container")

VTPM_BLK_REPO_URL = os.environ.get("VTPM_BLK_REPO_URL", "https://github.com/armenon-rh/vtpm-to-svsm-blk.git")
VTPM_BLK_BRANCH = os.environ.get("VTPM_BLK_BRANCH", "feature/cocoonfs-integration")

COCOON_TPM_REPO_URL = os.environ.get("COCOON_TPM_REPO_URL", "https://github.com/coconut-svsm/cocoon-tpm.git")
COCOON_TPM_BRANCH = os.environ.get("COCOON_TPM_BRANCH", "main")

TPM_PROVISIONER_REPO_URL = os.environ.get(
    "TPM_PROVISIONER_REPO_URL", "https://github.com/armenon-rh/tpm_provisioner.git"
)
TPM_PROVISIONER_BRANCH = os.environ.get("TPM_PROVISIONER_BRANCH", "main")
TPM_PROVISIONER_IMAGE_TAG = os.environ.get("TPM_PROVISIONER_IMAGE_TAG", "tpm-provisioner:anti-replay-e2e")

KBS_IMAGE_TAG = os.environ.get("KBS_IMAGE_TAG", "kbs-service:anti-replay-e2e")
KBS_CONTAINER_NAME = os.environ.get("KBS_CONTAINER_NAME", "kbs-resource-service-e2e")
KBS_PORT = int(os.environ.get("KBS_PORT", "8080"))
KBS_STORAGE_DIR = Path(os.environ.get("KBS_STORAGE_DIR", str(WORKDIR / "kbs-storage")))
KBS_SOFTHSM_DIR = Path(os.environ.get("KBS_SOFTHSM_DIR", str(WORKDIR / "softhsm_tokens")))
