# ABCI status (ChuangMa side)

Updated 2026-10-21 01:13:06 JST by the ABCI monitor (abci/monitor, local to ABCI).

Stage of the ABCI pipeline: **done**

| model | condition | runs | completed | success | interrupted | errors |
|---|---|---|---|---|---|---|
| holo4-35b-a3b | C0 | 22 | 18 | 2 | 4 | 0 |
| holo4-35b-a3b | C2 | 21 | 18 | 7 | 3 | 0 |
| holo4-35b-a3b | C3 | 21 | 18 | 6 | 3 | 0 |

Run-level details: [analysis/runs_manifest.csv](analysis/runs_manifest.csv) (one row per attempt; interrupted
attempts are kept, as the protocol asks).  Raw traces, screenshots and the viewer stay on ABCI under the
`abci_path` of each row (git-ignored); see README.md for the layout and how to open the viewer.

Environment: CUA-World GIMP tasks run in a rootless Singularity desktop (Ubuntu 24.04, GIMP 2.10, Xvfb, fluxbox)
because ABCI jobs have no root, Docker or usable KVM; the benchmark's own setup hooks and verifiers are used
unchanged (ves/envs/sif_desktop.py).  C3/C4 use the DRAFT oracle notes in oracles/ (not yet reviewed).
