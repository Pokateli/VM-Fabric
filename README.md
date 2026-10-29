# VM-Fabric

**Multi-VM orchestration for ChatGPT sandboxes and GitHub Actions.** Each operating system lives in its own profile; only approved, tested profiles can be executed. The repository is self-sufficient for building and publishing Debian 13 and does not need access to the legacy private Debian repository.

## VM catalog

| Profile | OS | Status | Runtime | Image |
| --- | --- | --- | --- | --- |
| \`debian13\` | Debian GNU/Linux 13 (amd64) | **Ready** | ChatGPT, GitHub Actions | QEMU/TCG; internally zlib-compressed QCOW2 |
| \`tiny11\` | Tiny11 / Windows 11 | **Experimental** | Not enabled yet | Image and provisioning under development |

The Windows entry is a placeholder, **not** a claim that Tiny11 already runs successfully. New OSes are added through \`profiles/<id>/profile.json\` and their own scripts.

## Architecture

- \`vmfabric.py\` — stable CLI: \`list\`, \`info\`, \`build\`, \`deploy\`, \`verify\`, \`run\`.
- \`profiles/debian13/profile.json\` — Debian metadata, own release tag and supported runtimes.
- \`profiles/debian13/scripts/\` — migrated Debian image builder, offline preseed, unpacker, QEMU startup, console executor and smoke tests.
- \`.github/workflows/build-debian13.yml\` — builds **its own** Debian image on GitHub, tests the guest root console, publishes \`debian13-v1.2.0-fabric\` as a release in **this** repository.
- \`.github/workflows/run-vm.yml\` — downloads the **VM-Fabric release from this same repository**, verifies it, boots the selected ready profile and returns command output and logs.
- \`profiles/tiny11/\` — future Windows configuration, disabled until validated.

The runtime always uses QEMU TCG, requires no \`/dev/kvm\` or root in the ChatGPT sandbox, and runs with the guest network disabled. Only the **build on GitHub Actions** requires Docker, sudo and network access to fetch official upstream Debian images. The QEMU guest does **not** have network access.

## 1. Building Debian on GitHub

Open **Actions → Build Debian 13 image (VM-Fabric)** or push changes to the Debian profile. The build verifies the official Debian upstream SHA-512, preconfigures UTC and root serial autologin, generates an internally **zlib-compressed QCOW2**, verifies guest filesystem contents and uploads the ready-to-use archive.

On a successful build, both are available:
- Actions artifact \`vm-fabric-debian13-image\` (temporary, 90-day retention).
- Release tag \`debian13-v1.2.0-fabric\` (durable, in VM-Fabric).

The release contains \`debian13-qemu-bundle.tar.gz\`, its detached SHA-256 and a boot test log. The archive contains a portable QEMU runtime and an immutable base \`debian13.qcow2\`.

## 2. Running Debian on GitHub Actions

Open **Actions → Run VM (VM-Fabric) → Run workflow**. Use profile ID \`debian13\` and optionally provide Bash commands (empty means \`id -u\`, \`uname -r\`, \`cat /etc/os-release\`).

The workflow:
1. Verifies the manifest status and resolves the release tag from the profile.
2. Downloads its own private release with \`GITHUB_TOKEN\`.
3. Runs \`vmfabric.py deploy\` and \`verify\` (SHA-256 / SHA-512 and QCOW2 check).
4. Boots QEMU in software emulation, waits for a real root prompt, executes the command via read-only VirtIO FAT and the serial console.
5. Shuts down the guest, verifies \`work.qcow2\` and uploads \`guest-console.log\`, \`guest-output.txt\` and \`overlay-check.txt\`.

A successful build may automatically trigger this execution workflow as a smoke test. GitHub-hosted runners are **ephemeral**; they are not persistent or remotely accessible VMs.

## 3. Running Debian in a ChatGPT sandbox

In a new ChatGPT conversation, connect GitHub and ask for the most recent successful \`vm-fabric-debian13-image\` artifact from **Pokateli/VM-Fabric**, or download the private release. The ZIP from Actions contains the TAR.GZ bundle plus SHA-256. Retrieve this repository's source files from GitHub, or check out the repository if available in your environment.

After the archive is available at its **actual** filesystem path, for example \`/mnt/data/vm-fabric-debian13-image.zip\`:

```bash
python3 vmfabric.py list
python3 vmfabric.py deploy debian13 \
  --archive /mnt/data/vm-fabric-debian13-image.zip \
  --target /mnt/data/vm-fabric/debian13
python3 vmfabric.py verify debian13 \
  --target /mnt/data/vm-fabric/debian13
python3 vmfabric.py run debian13 --mode chat \
  --target /mnt/data/vm-fabric/debian13
```


For a **noninteractive** command with captured output:

```bash
python3 vmfabric.py run debian13 --mode chat \
  --target /mnt/data/vm-fabric/debian13 \
  --command 'id -u; uname -r' \
  --log /mnt/data/debian-console.log \
  --output /mnt/data/debian-output.txt
```


The CLI also supports `--mode auto` (GitHub Actions when `GITHUB_ACTIONS=true`, interactive chat/local otherwise), `--script file.sh`, and `--timeout SECONDS`.

## Working disk and safe resets

`debian13.qcow2` is an immutable, compressed base. `start.sh` automatically creates a writable `work.qcow2` overlay on first boot. Writes are not compressed in real time; the base uses zlib QCOW2 clusters. Preserve both files if moving a modified VM elsewhere. To reset, stop QEMU and delete **only** the `work.qcow2` overlay. Never modify an image while QEMU is running.

`sharefiles/` is exposed inside Debian as a read-only VirtIO FAT disk (usually `/dev/vdb` or `/dev/vdb1`). The guest kernel is different from the sandbox host kernel.

## Migration provenance

Debian source was migrated from private `Pokateli/Debian13-ChatGPT-VM` (known-good release `vm-v1.2.0`). The original repository remains intact as an archive / rollback source, but **the VM-Fabric build and run workflows do not depend on it**. We intentionally do not put a 400+ MB image into Git history; VM images are created by GitHub Actions and distributed as release assets.

## Security limitations

The Debian guest has passwordless root on a serial console. Its network is disabled (`-nic none`). Do not turn on its network or expose the root console to untrusted users without redesigning authentication. **Never supply secrets in workflow command inputs**: commands, guest console output, and GitHub artifacts may be visible to authorized repository users. All GitHub Actions runners are temporary, and no continuous cloud VM session is promised.


## Debian 13 ARM64 (AArch64 guest on x86-64 host)

The new independent profile `debian13-arm64` provides a Debian 13 **ARM64** guest using portable **x86-64 QEMU aarch64 TCG**, an ARM virtual machine (`-machine virt`), an official Debian nocloud ARM64 image, and bundled `QEMU_EFI.fd` firmware. No ARM host processor, KVM or guest networking is required. CPU emulation is slower than native x86-64 Debian.

Build on GitHub Actions: **Build Debian 13 ARM64 image (VM-Fabric)**. The image is downloaded from official Debian, SHA512 checked, prepared for unattended root login on ARM serial `ttyAMA0`, internally recompressed with zlib QCOW2 clusters, boot tested and published as Release `debian13-arm64-v1.0.0-fabric` with asset `debian13-arm64-qemu-bundle.tar.gz`. The compressed base remains immutable; the first boot creates a writable `work.qcow2` overlay.

Run via **Run VM (VM-Fabric)** with VM profile `debian13-arm64` and optional command `uname -m; id -u; uname -r`. The build smoke test insists that the guest reports `aarch64` and root UID 0; the unified runner uploads command output, full serial console, and overlay-check.txt.

In a new ChatGPT sandbox, retrieve the **ARM64** release or workflow artifact (not the x86 Debian archive), then:

```bash
python3 vmfabric.py deploy debian13-arm64 \
  --archive /mnt/data/vm-fabric-debian13-arm64-image.zip \
  --target /mnt/data/vm-fabric/debian13-arm64
python3 vmfabric.py verify debian13-arm64 \
  --target /mnt/data/vm-fabric/debian13-arm64
python3 vmfabric.py run debian13-arm64 --mode chat \
  --target /mnt/data/vm-fabric/debian13-arm64
```


Use the *real* downloaded ZIP path; an interactive session begins automatically with root. To run one command and collect output, add `--command 'uname -m; id -u'`. The Linux host still reports x86-64; `uname -m` **inside the guest** must be `aarch64`.
