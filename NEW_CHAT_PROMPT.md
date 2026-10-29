# VM-Fabric: переносимая VM для нового чата

Подключён GitHub. Работай с приватным репозиторием Pokateli/VM-Fabric.

1. Прочитай README.md и profiles/debian13/profile.json; найди последний успешный workflow "Build Debian 13 image (VM-Fabric)" и артефакт vm-fabric-debian13-image, либо релиз debian13-v1.2.0-fabric.
2. Скачай ZIP через GitHub connector и определи его действительный путь в /mnt/data. Не выдумывай пути к архивам. При отсутствии доступа сообщи об этом явно.
3. Возьми vmfabric.py и scripts из profiles/debian13/scripts (или checkout этого репозитория), разверни архив командой:
   python3 vmfabric.py deploy debian13 --archive /path/to/artifact.zip --target /mnt/data/vm-fabric/debian13
4. Выполни:
   python3 vmfabric.py verify debian13 --target /mnt/data/vm-fabric/debian13
   python3 vmfabric.py run debian13 --mode chat --target /mnt/data/vm-fabric/debian13
5. Гостевая ОС: Debian 13, root по ttyS0, QEMU TCG, zlib QCOW2 + work.qcow2. Сеть гостя отключена. При необходимости запускай команды --command и сохраняй console/output.
6. Не путай ядро гостя с ядром хост-контейнера; не обещай постоянную VM в GitHub Actions. Windows/Tiny11 ещё экспериментальный профиль без готового образа.

На GitHub отдельный workflow "Run VM (VM-Fabric)" исполняет команды на временном GitHub runner и выгружает результат в Actions artifacts. Все рабочие данные в work.qcow2 после завершения GitHub runner не сохраняются, если отдельно не экспортировать их.

Для ARM64: выбери профиль `debian13-arm64`, релиз `debian13-arm64-v1.0.0-fabric`, артефакт `vm-fabric-debian13-arm64-image`. Проверь `uname -m` внутри VM (должно быть `aarch64`). Хост остаётся x86-64, ARM запускается через QEMU TCG и ARM UEFI.
