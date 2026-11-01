#!/usr/bin/env python3
"""One-off driver for the setup side of SVSM/Trustee KBS attestation testing.
Builds everything, provisions a CocoonFS vTPM image, registers it with KBS,
and leaves the container running -- it does NOT tear anything down -- then
prints the exact follow-on commands (aproxy, launch_guest.sh) with this run's
real values filled in, for you to run by hand to continue into the guest-boot
leg (see KBS-SVSM.md, referenced in the printed output below).

Usage: python3 manual_boot_setup.py
"""
import uuid

import config as cfg
from lib import build, kbs as kbslib, provision, repos


def main():
    cfg.WORKDIR.mkdir(parents=True, exist_ok=True)

    print("=== cocoon-tpm (cocoonfs-cli) ===")
    cocoon_tpm_dir = cfg.WORKDIR / "cocoon-tpm"
    repos.clone_or_fetch(cocoon_tpm_dir, cfg.COCOON_TPM_REPO_URL)
    repos.checkout_clean(cocoon_tpm_dir, cfg.COCOON_TPM_BRANCH)
    repos.submodules_update(cocoon_tpm_dir)
    build.build_cocoonfs_cli(cocoon_tpm_dir)

    print("=== vtpm-to-svsm-blk ===")
    vtpm_blk_dir = cfg.WORKDIR / "vtpm-to-svsm-blk"
    repos.clone_or_fetch(vtpm_blk_dir, cfg.VTPM_BLK_REPO_URL)
    repos.checkout_clean(vtpm_blk_dir, cfg.VTPM_BLK_BRANCH)
    build.build_vtpm_to_svsm_blk(vtpm_blk_dir)

    print("=== tpm_provisioner image ===")
    tpm_provisioner_dir = cfg.WORKDIR / "tpm_provisioner"
    repos.clone_or_fetch(tpm_provisioner_dir, cfg.TPM_PROVISIONER_REPO_URL)
    repos.checkout_clean(tpm_provisioner_dir, cfg.TPM_PROVISIONER_BRANCH)
    build.build_tpm_provisioner_image(tpm_provisioner_dir, cfg.TPM_PROVISIONER_IMAGE_TAG)

    print("=== trustee KBS image + kbs-client ===")
    trustee_dir = cfg.WORKDIR / "trustee"
    repos.clone_or_fetch(trustee_dir, cfg.TRUSTEE_REPO_URL)
    repos.checkout_clean(trustee_dir, cfg.TRUSTEE_BRANCH)
    build.build_trustee_image(trustee_dir, cfg.KBS_IMAGE_TAG)
    kbs_client = build.build_kbs_client(trustee_dir)

    print("=== generating a real NVChip state via tpm_provisioner ===")
    nvchip = cfg.WORKDIR / "nvchip_state.bin"
    provision.generate_nvchip_state(cfg.TPM_PROVISIONER_IMAGE_TAG, nvchip)

    print("=== starting KBS container (left running on purpose) ===")
    container = kbslib.KbsContainer(
        name=cfg.KBS_CONTAINER_NAME, image=cfg.KBS_IMAGE_TAG, port=cfg.KBS_PORT,
        storage_dir=cfg.KBS_STORAGE_DIR, softhsm_dir=cfg.KBS_SOFTHSM_DIR,
    )
    container.start()

    print("=== provisioning a CocoonFS image + registering it in KBS ===")
    manual_dir = cfg.WORKDIR / "manual-run"
    manual_dir.mkdir(parents=True, exist_ok=True)
    key_file = manual_dir / "key.bin"
    provision.generate_key(key_file)

    resource_id = f"default/vtpm/{uuid.uuid4()}"
    info = provision.provision_image(
        vtpm_blk_dir, key_file, nvchip, resource_id, manual_dir / "artefact"
    )
    container.set_resource(kbs_client, resource_id, key_file)
    container.register_nonce(resource_id, info["boot_counter"], info["nonce"])

    print("=== verifying KBS state on disk (equivalent of `ls`/`cat`) ===")
    repo_dir = container.storage_dir / "repository"
    anti_replay_dir = container.storage_dir / "svsm-anti-replay"
    print(f"  ls {repo_dir}:")
    for p in sorted(repo_dir.iterdir()):
        print(f"    {p.name}")
    print(f"  ls {anti_replay_dir}:")
    for p in sorted(anti_replay_dir.iterdir()):
        print(f"    {p.name}")

    secret = container.read_resource_secret(resource_id)
    record = container.read_anti_replay_record(resource_id)
    print(f"  secret: {len(secret) if secret else 'MISSING'} bytes")
    print(f"  anti-replay record: {record}")
    if secret is None or len(secret) != 32 or record is None:
        print("  WARNING: KBS state does not look right -- check `podman logs "
              f"{cfg.KBS_CONTAINER_NAME}` before continuing")

    escaped = resource_id.replace("/", "\\x2F")
    print(f"""
{"=" * 78}
Setup complete -- KBS is running and will stay running after this exits.
{"=" * 78}
  KBS URL:          {container.url}
  Resource ID:      {resource_id}
  CocoonFS image:   {info["image"]}
  Registered:       boot_counter={info["boot_counter"]}, nonce={info["nonce"]}

Next steps (manual -- see KBS-SVSM.md in the svsm repo, steps 9-10:
https://github.com/armenon-rh/svsm/blob/feature/anti-replay/Documentation/docs/developer/KBS-SVSM.md
-- note that doc currently says `--protocol kbs`, which is stale; use
`trustee-kbs` as below). These need a separately built svsm repo (this
harness does not build it) plus a pre-built QEMU binary, OVMF firmware, and
guest qcow2 image -- none of that is covered here.

1. Build + run aproxy on the host: (make sure to add the OVMF file, and include
persistence)

     cd <svsm-repo>
     FW_FILE=/path/to/OVMF.fd make FEATURES=svsm:vtpm,svsm:attest,svsm:virtio-drivers,svsm:block,svsm:persistence igvm
     make aproxy
     ./bin/aproxy --protocol trustee-kbs --url {container.url} --vsock > aproxy.log 2>&1 &

2. Launch the guest with the provisioned CocoonFS image attached:

     ./scripts/launch_guest.sh --vsock 3 \\
          --state {info["image"]} \\
          --snapshot off \\
          --qemu /path/to/qemu/build/qemu-system-x86_64 \\
          --image /path/to/snp-svsm-vtpm/images/guest-luks.qcow2

3. Watch aproxy.log and the guest console, then confirm the roll:

     tail -f <svsm-repo>/aproxy.log
     cat {cfg.KBS_STORAGE_DIR}/svsm-anti-replay/{escaped}
     # boot_counter should now read {info["boot_counter"] + 1}, nonce should have changed

   To exercise the replay-rejection path: copy {info["image"]} aside *before*
   step 2, let that boot complete and roll the counter, then try booting the
   pre-boot copy -- KBS should reject it with HTTP 403 NonceMismatch.

When you're done testing, tear down the container:

     podman rm -f {cfg.KBS_CONTAINER_NAME}
{"=" * 78}
""")


if __name__ == "__main__":
    main()
