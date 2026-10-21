#!/bin/bash
# Run inside the CPU allocation; Ctrl-C stops only this disposable VM.
set -euo pipefail
runtime=${VISUAL_EFFECT_RUNTIME:-/scratch/pioneer/jobs/wxy320/visual_effect_runtime}
port=${VISUAL_EFFECT_DESKTOP_PORT:-15000}
q="$runtime/qemu-root"
mkdir -p "$runtime/vm/tmp"
export TMPDIR="$runtime/vm/tmp"
export QEMU_MODULE_DIR="$q/usr/lib/x86_64-linux-gnu/qemu"
disk="$runtime/vm/Ubuntu.qcow2"
test -s "$disk"
# Direct loader avoids Singularity's user namespace, which denies KVM.
# Read-only base disk + temporary per-boot overlays reset A/B initial state.
exec "$q/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2" \
  --library-path "$q/lib/x86_64-linux-gnu:$q/usr/lib/x86_64-linux-gnu" \
  "$q/usr/bin/qemu-system-x86_64" -L "$q/usr/share/qemu" \
  -enable-kvm -cpu host -machine q35 -smp 2 -m 6144 \
  -drive "file=$disk,format=qcow2,if=virtio,snapshot=on" \
  -drive "if=pflash,format=raw,file=$q/usr/share/OVMF/edk2-x86_64-code.fd,snapshot=on" \
  -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:$port-:5000" \
  -device virtio-net-pci,netdev=net0,romfile= -device "virtio-vga,romfile=$q/usr/share/seabios/vgabios-virtio.bin" \
  -device qemu-xhci -device usb-tablet \
  -display none -serial "file:$runtime/vm/serial.log" \
  -monitor "unix:$runtime/vm/monitor.sock,server=on,wait=off"
