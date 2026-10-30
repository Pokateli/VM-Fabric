# VM-Fabric

**Multi-VM orchestration for ChatGPT sandboxes and GitHub Actions.** Each operating system lives in its own profile; only approved, tested profiles can be executed. The repository is self-sufficient for building and publishing Debian 13 and does not need access to the legacy private Debian repository.

## VM catalog

| Profile | OS | Status | Runtime | Image |
| --- | --- | --- | --- | --- |
| \`debian13\` | Debian GNU/Linux 13 (amd64) | **Ready** | ChatGPT, GitHub Actions | QEMU/TCG; internally zlib-compressed QCOW2 |
| `tiny11` | Windows 11 Enterprise Evaluation / Tiny11 | **Ready for testing** | ChatGPT TCG GUI, GitHub KVM | ZSTD-QCOW2; first and second boots verified; evaluation license expired |

The Windows profile was tested in both GitHub KVM and a ChatGPT TCG sandbox, including a real graphical Windows desktop. New OSes are added through `profiles/<id>/profile.json` and their own scripts.

## Architecture

- \`vmfabric.py\` — stable CLI: \`list\`, \`info\`, \`build\`, \`deploy\`, \`verify\`, \`run\`.
- \`profiles/debian13/profile.json\` — Debian metadata, own release tag and supported runtimes.
- \`profiles/debian13/scripts/\` — migrated Debian image builder, offline preseed, unpacker, QEMU startup, console executor and smoke tests.
- \`.github/workflows/build-debian13.yml\` — builds **its own** Debian image on GitHub, tests the guest root console, publishes \`debian13-v1.2.0-fabric\` as a release in **this** repository.
- \`.github/workflows/run-vm.yml\` — downloads the **VM-Fabric release from this same repository**, verifies it, boots the selected ready profile and returns command output and logs.
- `profiles/tiny11/` — ready offline Windows 11 profile with SHA256-checked shard restore, immutable ZSTD base, per-session writable QCOW2 overlay, and local QEMU console commands.

The runtime always uses QEMU TCG, requires no \`/dev/kvm\` or root in the ChatGPT sandbox, and runs with the guest network disabled. Only the **build on GitHub Actions** requires Docker, sudo and network access to fetch official upstream Debian images. The QEMU guest does **not** have network access.

## Tiny11 / Windows 11 — dual-mode VM profile

The verified Tiny11 disk was built from a modified official Windows 11 Enterprise
Evaluation image. The base was confirmed under **GitHub Ubuntu KVM**, and its
**actual graphical desktop** was booted inside a ChatGPT sandbox using QEMU TCG,
with guest networking turned off. The evaluation watermark indicates an expired
license; use a properly licensed Windows image for production use.

**Provenance:** [Pokateli/Temp Actions run 40928819947](https://github.com/Pokateli/Temp/actions/runs/40928819947)
contains 20 ready-image shards and the integrity index. Its base QCOW2 has SHA256
`9d6b897b3ba5326b6de380b8ef48898c5c9f561b65e4b44507eb713e4300d402`.
The VGA-enabled portable QEMU runtime was built in Temp run 41013832628.

The VM-Fabric private release `tiny11-v1.0.0-fabric` is the intended durable
backup for those files. Check that the [import workflow](https://github.com/Pokateli/VM-Fabric/actions/workflows/import-tiny11-release.yml)
succeeded and the release contains `ready-parts.json` and all 20 shards before
relying on it. The image is not stored in Git history.

If a local unpacked base already exists, **no 8GB copy is required**. The deploy
command creates symbolic links to that immutable cache, then makes its own session
overlay only when booting:

```bash
python3 vmfabric.py deploy tiny11 \
  --archive /mnt/data/tiny11-ready \
  --target /mnt/data/vm-fabric/tiny11
python3 vmfabric.py verify tiny11 \
  --target /mnt/data/vm-fabric/tiny11
python3 vmfabric.py run tiny11 --mode chat \
  --target /mnt/data/vm-fabric/tiny11
python3 vmfabric.py console tiny11 status \
  --target /mnt/data/vm-fabric/tiny11
python3 vmfabric.py console tiny11 screenshot \
  --target /mnt/data/vm-fabric/tiny11 \
  --output /mnt/data/tiny11-desktop.png
```

If there is no unpacked base, first download the 20 shards and index from a
permitted private VM-Fabric release into a directory; then pass that directory
to `deploy`. The importer also accepts the original GitHub Actions ZIP files
named `tiny11-ready-shard-NNN.zip` plus `tiny11-ready-index.zip` **without
extracting each ZIP to disk**. It verifies SHA256 for each shard and each
reconstructed file.

Chat mode starts the guest in a detached **local** process, uses the portable
QEMU runtime under `QEMU_HOME` (or the usual /mnt/data path), and keeps the
desktop in a QEMU framebuffer. ChatGPT's 4GiB memory-limited containers default to 1792MiB guest RAM to reduce OOM kills; override with `TINY11_RAM_MIB` if headroom permits. Capture screenshots with `console screenshot`;
`console wake` handles an ACPI suspend, and `console powerdown` requests a
graceful shutdown. It does **not** expose the VM to the public Internet.

On GitHub, use the separate
[Run Tiny11 Windows desktop under GitHub KVM](https://github.com/Pokateli/VM-Fabric/actions/workflows/run-tiny11.yml)
workflow. It imports the private Release, verifies it, and runs a bounded
Windows second-boot probe with a disposable overlay. It does not execute Linux
shell commands inside Windows; `--command` and `--script` are intentionally
rejected for this profile.

**Persistence limits:** changes made by Windows are in the local
`tiny11-session.qcow2` overlay and `OVMF_VARS-session.fd`. Do not copy those
files while the guest is running. After Windows has shut down cleanly, save
both together using the offline VM-Fabric session tool:

```bash
python3 vmfabric.py session tiny11 save \
  --target /mnt/data/vm-fabric/tiny11 \
  --snapshot-dir /mnt/data/tiny11-session-backup
# After deploying the SAME immutable base in another sandbox:
python3 vmfabric.py session tiny11 restore \
  --target /mnt/data/vm-fabric/tiny11 \
  --snapshot-dir /mnt/data/tiny11-session-backup
```

The snapshot includes Windows user data and should be kept private. The
restore tool verifies checksums and rebases the overlay's absolute backing
path only when the original base image identity matches. The image cache and session files last only
as long as the particular ChatGPT sandbox filesystem lasts; a new conversation
does not automatically inherit them. The private GitHub Release preserves the
base image, but a new isolated sandbox must still receive those image bytes
at least once. To preserve **guest changes**, back up the stopped overlay and
its UEFI variables together with the base SHA256 reference.

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
