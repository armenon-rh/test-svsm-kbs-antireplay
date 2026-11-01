# CocoonFS anti-replay setup helper

Automates the stable, hardware-independent setup side of SVSM/Trustee KBS
attestation testing: clone/checkout the repos from scratch into a dedicated
workspace, build everything, stand up the KBS container, provision a real
CocoonFS vTPM image (via `tpm_provisioner` + `vtpm-to-svsm-blk`), register it,
verify the result on disk, and print the exact commands to continue manually
into the guest-boot leg.

Trustee's `feature/anti-replay-vtpm` and `kbs-softhsm` branches are no longer
merged on the fly -- they're merged once, with the anti-replay
Dockerfile/`config_resource.toml` patches committed directly on top, into a
single branch: `feature/anti-replay-container`, pushed to the
`armenon-rh/trustee` fork. The harness just checks that branch out like any
other (`config.TRUSTEE_BRANCH`). Override `TRUSTEE_REPO_URL` with a local path
if you want to build from uncommitted local changes instead:

```bash
export TRUSTEE_REPO_URL=/home/armenon/workdir/git/codebase/projects/trustee
```

## What this deliberately does NOT automate

Booting SVSM against the provisioned image stays a manual step, run by hand
following [`KBS-SVSM.md`](https://github.com/armenon-rh/svsm/blob/feature/anti-replay/Documentation/docs/developer/KBS-SVSM.md)'s
aproxy/`launch_guest.sh` steps (`manual_boot_setup.py` prints the exact
commands for you, filled in with the actual values from that run -- note that
doc currently has a stale `--protocol kbs`; use `trustee-kbs`, see the
printed output). That leg was cut after repeated attempts kept surfacing new
fragile assumptions baked into any script trying to assert pass/fail from it:

- it only runs on real AMD SEV-SNP (or TDX) hardware -- SVSM hardcodes
  `Tee::Snp` and its evidence path requires a genuine `SNP_GUEST_REQUEST`
  hypercall, with no software/sample fallback;
- SVSM's own kernel log is silently dropped unless built with the
  `enable-console-log` feature, and even then shares a serial port with the
  guest OS's own console output;
- "did it work" ends up depending on exact strings from a guest image we
  don't control here (a login prompt vs. a LUKS passphrase prompt if the
  vTPM-sealed `systemd-cryptenroll` auto-unlock fails -- see
  `svsm/Documentation/docs/developer/RELEASE-TESTPLAN.md`).

## Setup

```bash
cd anti-replay-e2e
```

Cloning uses plain HTTPS URLs (see `config.py`) against the public
`armenon-rh` forks (trustee, vtpm-to-svsm-blk, tpm_provisioner) and
`coconut-svsm/cocoon-tpm` -- no SSH keys needed. `podman` and `cargo` must be
installed; no SEV-SNP/TDX hardware is needed for anything this script runs.
No Python dependencies beyond the standard library.

## Running

```bash
python3 manual_boot_setup.py
```

First run clones+builds everything into `./workspace/` (a dedicated directory,
separate from any manually-managed checkouts elsewhere) -- expect it to take a
while. Subsequent runs reuse `./workspace/` and only re-fetch/re-reset to the
configured branches' latest tips (`git reset --hard`, destructive to any local
edits inside `./workspace/` -- by design, for reproducibility).

It leaves the KBS container **running** afterward (unlike a normal test
suite, which would tear it down) so you can continue straight into the
printed aproxy/`launch_guest.sh` commands. Tear it down yourself when done:

```bash
podman rm -f kbs-resource-service-e2e
```

Each run provisions a fresh image under a new random resource ID, prints the
on-disk KV store contents it just wrote (the resource secret's length and the
full `AntiReplayRecord`) so you can confirm it looks right without hunting
through the container's storage directory by hand, and warns if anything's
missing or malformed.

## Config

All of `config.py`'s defaults are overridable via env vars (repo URLs,
branches, KBS port/paths) -- see that file.
