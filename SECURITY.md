# Security

## Reporting a problem

If you find a security problem in Mixie, please **don't** open a public issue. Use
[Report a vulnerability](../../security/advisories/new) on GitHub (private), and describe what you found
and how to reproduce it. You'll get an answer as soon as possible.

## What Mixie does – and doesn't – do

- **No accounts, no tracking.** Mixie never sends anything about you anywhere.
- **One network call:** once a day it asks GitHub's public API which version is the newest. You can turn this
  off in **⋯ → Tell me about new versions**. Mixie never downloads or runs anything by itself – it only opens
  Mixie's own release page, and only if you click the button.
- **Song names** are read from window titles to show *Now playing*. They stay on your PC and are never written
  to the logs.
- **Runs as you, not as administrator.** Settings are stored in `mixie_config.json` (or
  `%LOCALAPPDATA%\Mixie` for Mixie.exe), and *Start with Windows* only uses your own user's startup list.
- **A damaged settings file can't break it.** Every setting is checked when it's loaded, and settings are saved
  in a way that can't leave half-written files.
- **Moving one app to another sound device** uses an undocumented part of Windows. It runs in a separate small
  process that only accepts a process number and a real device id, so if Windows changes, only that process fails.

## Checking that a download is genuine

- **Mixie.exe** is built from this repository by the [Build Mixie.exe](.github/workflows/build-exe.yml) workflow
  – nobody builds it by hand. Each release has a `SHA256SUMS.txt`, and the exe carries a signed GitHub
  *build provenance attestation*. To check it with the GitHub CLI:

  ```
  gh attestation verify Mixie.exe --repo Modda-ctrl/Mixie
  ```

- **Install Mixie.bat** is plain text: open it in Notepad to read it. It carries a SHA-256 checksum of the Mixie
  program inside it and refuses to install if the two don't match.
- Mixie.exe isn't code-signed (a certificate costs money every year), so Windows SmartScreen may warn about it
  the first time.
