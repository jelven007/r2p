"""Ordered crate uploads with durable progress and independent download checks."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from tools.candidate import index_path
from tools.candidate_artifacts import SDK


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Registry:
    def __init__(self, local: str | None = None, token: str | None = None):
        if local:
            parsed = urllib.parse.urlsplit(local)
            if (
                parsed.scheme != "http"
                or parsed.hostname != "127.0.0.1"
                or parsed.username
                or parsed.password
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("fixture registry must be http://127.0.0.1:<port>")
            base = local.rstrip("/")
            self.api = base + "/api/v1/crates/new"
            self.index = base + "/index/"
            self.download = base + "/crates/{crate}/{version}/download"
        else:
            self.api = "https://crates.io/api/v1/crates/new"
            self.index = "https://index.crates.io/"
            self.download = (
                "https://static.crates.io/crates/{crate}/{crate}-{version}.crate"
            )
        self.token = token

    def find(self, row: dict) -> dict | None:
        try:
            with urllib.request.urlopen(
                self.index + index_path(row["name"]), timeout=10
            ) as response:
                versions = [json.loads(line) for line in response if line.strip()]
        except urllib.error.HTTPError as error:
            error.close()
            if error.code == 404:
                return None
            raise
        matches = [entry for entry in versions if entry.get("vers") == row["version"]]
        if not matches:
            return None
        if len(matches) != 1 or (
            matches[0].get("name") != row["name"]
            or matches[0].get("cksum") != row["sha256"]
            or matches[0].get("yanked") is not False
        ):
            raise ValueError(
                f"remote index identity/checksum/yank differs: {row['name']}"
            )
        return matches[0]

    def wait(self, row: dict, timeout: float, poll: float) -> dict:
        deadline = time.monotonic() + timeout
        while True:
            try:
                if self.find(row):
                    url = self.download.format(
                        crate=row["name"], version=row["version"]
                    )
                    with urllib.request.urlopen(url, timeout=10) as response:
                        checksum = hashlib.file_digest(response, "sha256").hexdigest()
                    if checksum != row["sha256"]:
                        raise ValueError(
                            f"remote download checksum differs: {row['name']}"
                        )
                    return {
                        "index_checksum": row["sha256"],
                        "download_sha256": checksum,
                    }
            except urllib.error.HTTPError as error:
                error.close()
                if error.code != 404 and error.code < 500:
                    raise
            except urllib.error.URLError:
                pass
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"index/download not verified before deadline: {row['name']}"
                )
            time.sleep(min(poll, remaining))

    def put(self, body: bytes) -> dict:
        headers = {
            "Content-Type": "application/octet-stream",
            "User-Agent": "r2p-candidate-release/2",
        }
        if self.token:
            headers["Authorization"] = self.token
        request = urllib.request.Request(
            self.api, data=body, method="PUT", headers=headers
        )
        # Never forward the release credential to a redirect target.
        try:
            with urllib.request.build_opener(NoRedirect).open(
                request, timeout=30
            ) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            error.close()
            raise
        if result.get("errors"):
            raise RuntimeError("registry returned an upload error")
        return result


def publish(
    rows: list[dict],
    *,
    registry: Registry,
    journal_path: Path,
    binding: dict,
    body_for,
    timeout: float = 300,
    poll: float = 2,
    retry_unindexed: bool = False,
) -> dict:
    """Resume from remote truth; uncertain requests never automatically repeat."""
    if timeout <= 0 or poll <= 0:
        raise ValueError("wait timeout and poll interval must be positive")
    if len(rows) != len(SDK) or {row["name"] for row in rows} != set(SDK):
        raise ValueError("publish requires the exact six SDK crates")
    by_name = {row["name"]: row for row in rows}
    ordered = [by_name[name] for name in SDK]
    identity = binding | {
        "registry_api": registry.api,
        "registry_index": registry.index,
        "registry_download": registry.download,
        "artifacts": [
            {key: row[key] for key in ("name", "version", "sha256")} for row in ordered
        ],
    }
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    lock = journal_path.with_name(journal_path.name + ".lock")
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise ValueError(
            "another upload owns the journal lock; inspect before clearing a stale lock"
        ) from error
    try:
        if journal_path.exists():
            journal = json.loads(journal_path.read_text())
            if journal.get("schema_version") != 1 or journal.get("binding") != identity:
                raise ValueError("upload journal source/gate/registry/artifacts differ")
            if set(journal.get("packages", {})) != set(SDK) or any(
                entry.get("state")
                not in {"pending", "uploading", "accepted", "verified"}
                for entry in journal["packages"].values()
            ):
                raise ValueError("upload journal package/state differs")
        else:
            journal = {
                "schema_version": 1,
                "binding": identity,
                "packages": {name: {"state": "pending", "attempts": 0} for name in SDK},
                "result": "incomplete",
            }

        def save() -> None:
            journal["updated_at"] = datetime.now(timezone.utc).isoformat()
            temporary = journal_path.with_name(journal_path.name + ".tmp")
            temporary.write_text(json.dumps(journal, indent=2) + "\n")
            temporary.replace(journal_path)

        journal["result"] = "incomplete"
        save()
        for row in ordered:
            progress = journal["packages"][row["name"]]
            try:
                indexed = registry.find(row) is not None
                if indexed or progress["state"] in {"accepted", "verified"}:
                    verified = registry.wait(row, timeout, poll)
                else:
                    verified = None
                    if progress["state"] == "uploading":
                        try:
                            verified = registry.wait(row, timeout, poll)
                        except TimeoutError:
                            if not retry_unindexed:
                                raise
                    if verified is None:
                        progress.update(
                            state="uploading", attempts=progress["attempts"] + 1
                        )
                        save()
                        registry.put(body_for(row))
                        progress["state"] = "accepted"
                        save()
                        verified = registry.wait(row, timeout, poll)
                progress.update(state="verified", **verified)
                progress.pop("error", None)
                save()
                print(
                    f"Verified index and download: {row['name']} {row['version']}",
                    flush=True,
                )
            except Exception as error:
                # Do not persist response bodies or credential-bearing headers.
                progress["error"] = type(error).__name__
                journal["result"] = "incomplete"
                save()
                raise
        journal["result"] = "success"
        save()
        return journal
    finally:
        lock.rmdir()
