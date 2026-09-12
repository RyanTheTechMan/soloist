# Soloist macOS runtime constraints

- Initial target: Linux AArch64 on Apple Silicon macOS only.
- Do not modify Soloist executable instructions on disk or in memory. No trap
  insertion, address-specific replacements, binary hash allowlist as a substitute
  for compatibility, or fallback to the previous patched lab.
- ELF data relocations are distinct from instruction rewriting; reject text
  relocations. Future loaders must verify executable bytes remain unchanged.
- The user approved evaluating the hardware-assisted macOS path on 2026-09-12
  after discussion of elfuse and Windows WHP. Hypervisor.framework virtual CPUs
  are now in scope. Do not boot a guest Linux OS, install a VM image, or describe
  this as non-virtualized. Keep the Linux syscall layer in the host process.
- No private Apple entitlements, SIP changes, kernel patches, or DRM/auth bypasses.
- Keep all account keys, session state, media payloads, and official Soloist
  binaries out of source, diagnostic output, and distributable archives.
- Keep the old native-soloist-lab separate as a historical feasibility prototype.
- Clearly distinguish fixture execution, Soloist startup, authenticated playback,
  and verified lossless playback. Success at one is not success at the others.
