# Security policy

## Reporting a vulnerability

Report it privately on GitHub: open the repository's **Security** tab and choose **Report a vulnerability**. Please don't open a public issue.

We acknowledge reports within 2 business days and aim to ship a fix for confirmed high-severity issues within 14 days. We credit reporters in the release notes unless you ask us not to.

## What Lathe does and doesn't do

- It makes no network connections. The ffmpeg and ffprobe calls are restricted to local files with `-protocol_whitelist file,pipe`, so a crafted media file cannot make Lathe fetch a URL.
- It reads and writes only inside the working folder (`LATHE_WORKING_DIR`). Symlinks that point outside it are refused, and an output never replaces its input.
- It has no keys, accounts or telemetry, and nothing is sent anywhere.
- Every writing tool creates new files and never overwrites an existing one unless the call passes `overwrite=true`. Only `batch_process` asks for approval, and only for a run of two or more files. The person answers through the MCP client; the model's own arguments never count as approval. `LATHE_BATCH_PREAPPROVED=true` skips the prompt, and then the setting decides.
- Every batch request, approval and refusal is logged locally in `~/.local/state/lathe/approvals.jsonl`. File contents and file names are never logged.
- `tool-manifest.lock.json` records a hash of every tool description, prompt and the server instructions. CI fails if they change without the lock changing too.
- Playlist, concat and manifest files are refused as media inputs, so ffmpeg cannot be pointed at other files through them.

## Supported versions

The latest minor release receives security fixes.
