# Demo flow (2:30) — see deck/SCRIPT.md for the full script

- Open https://0xtkey256.github.io/everett/?replay=tokyo (EN/日本語 in the header). The opening screen: "the pipeline thinks Tokyo Tower is here" (polar ice) vs ground truth (Tokyo).
- 32 worlds appear across 8 Daytona sandboxes; each tile turns into the satellite image its code fetches. 4 turn green on Tokyo.
- Collapse: the winning diff with the real Tokyo tile; 31 worlds thrown away.
- Optional live: open `/?api=<tunnel>` and trigger `POST /runs` with the admin header; phones on the QR follow along. Live success varies — use the replay as the main story.
