"""Exercise upload recovery against a real loopback HTTP fixture, never crates.io."""

from __future__ import annotations

import hashlib
import http.server
import json
import struct
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path

from tools.candidate import index_path
from tools.candidate_artifacts import SDK
from tools.engineering.registry_upload import Registry, publish


class RegistryUploadTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.journal = Path(temporary.name) / "progress.json"
        self.uploads = []
        self.stored = {}
        self.index_reads = {}
        self.download_reads = {}
        self.fail_before = None
        self.fail_after = None
        self.bad_index = False
        self.bad_download = False
        self.bytes = {name: f"immutable crate: {name}".encode() for name in SDK}
        self.rows = [
            {
                "name": name,
                "version": "0.30.1",
                "sha256": hashlib.sha256(self.bytes[name]).hexdigest(),
            }
            for name in SDK
        ]
        state = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def respond(self, code, content=b""):
                self.send_response(code)
                self.end_headers()
                self.wfile.write(content)

            def do_PUT(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                (size,) = struct.unpack_from("<I", body)
                metadata = json.loads(body[4 : 4 + size])
                (crate_size,) = struct.unpack_from("<I", body, 4 + size)
                crate = body[8 + size :]
                name = metadata["name"]
                state.uploads.append(name)
                if (
                    self.path != "/api/v1/crates/new"
                    or crate != state.bytes[name]
                    or len(crate) != crate_size
                ):
                    self.respond(400, b'{"errors": ["bad body"]}')
                    return
                if state.fail_before == name:
                    state.fail_before = None
                    self.respond(503)
                    return
                state.stored[name] = crate
                if state.fail_after == name:
                    state.fail_after = None
                    self.respond(503)
                    return
                self.respond(200, b'{"ok": true}')

            def do_GET(self):
                for row in state.rows:
                    name = row["name"]
                    if self.path == "/index/" + index_path(name):
                        state.index_reads[name] = state.index_reads.get(name, 0) + 1
                        if name not in state.stored or state.index_reads[name] < 3:
                            self.respond(404)
                            return
                        entry = {
                            "name": name,
                            "vers": row["version"],
                            "cksum": "0" * 64 if state.bad_index else row["sha256"],
                            "yanked": False,
                        }
                        self.respond(200, json.dumps(entry).encode() + b"\n")
                        return
                    if self.path == f"/crates/{name}/{row['version']}/download":
                        state.download_reads[name] = (
                            state.download_reads.get(name, 0) + 1
                        )
                        if name not in state.stored or state.download_reads[name] < 2:
                            self.respond(404)
                            return
                        self.respond(
                            200,
                            b"tampered" if state.bad_download else state.stored[name],
                        )
                        return
                self.respond(404)

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.registry = Registry(f"http://127.0.0.1:{self.server.server_port}")

    def body(self, row):
        encoded = json.dumps({"name": row["name"], "vers": row["version"]}).encode()
        crate = self.bytes[row["name"]]
        return (
            struct.pack("<I", len(encoded))
            + encoded
            + struct.pack("<I", len(crate))
            + crate
        )

    def run_publish(self, **kwargs):
        return publish(
            list(reversed(self.rows)),
            registry=self.registry,
            journal_path=self.journal,
            binding={"source_sha": "1" * 40, "scope": "local-fixture"},
            body_for=self.body,
            timeout=0.15,
            poll=0.005,
            **kwargs,
        )

    def test_delay_download_checks_and_idempotent_resume(self):
        result = self.run_publish()
        self.assertEqual(self.uploads, list(SDK))
        self.assertEqual(result["result"], "success")
        for row in self.rows:
            self.assertEqual(
                result["packages"][row["name"]]["download_sha256"], row["sha256"]
            )
        self.run_publish()
        self.assertEqual(self.uploads, list(SDK))

    def test_partial_error_requires_explicit_retry_of_an_unindexed_request(self):
        self.fail_before = SDK[1]
        with self.assertRaises(urllib.error.HTTPError):
            self.run_publish()
        progress = json.loads(self.journal.read_text())
        self.assertEqual(progress["packages"][SDK[0]]["state"], "verified")
        self.assertEqual(progress["packages"][SDK[1]]["state"], "uploading")
        with self.assertRaises(TimeoutError):
            self.run_publish()
        self.assertEqual(self.uploads, list(SDK[:2]))
        result = self.run_publish(retry_unindexed=True)
        self.assertEqual(result["result"], "success")
        self.assertEqual(self.uploads, [SDK[0], SDK[1], *SDK[1:]])

    def test_request_accepted_before_http_error_is_not_uploaded_again(self):
        self.fail_after = SDK[1]
        with self.assertRaises(urllib.error.HTTPError):
            self.run_publish()
        self.assertEqual(self.run_publish()["result"], "success")
        self.assertEqual(self.uploads, list(SDK))

    def test_mismatched_index_and_download_stop_the_remaining_packages(self):
        for which in ("bad_index", "bad_download"):
            self.stored.clear()
            self.index_reads.clear()
            self.download_reads.clear()
            self.uploads.clear()
            self.journal.unlink(missing_ok=True)
            self.bad_index = which == "bad_index"
            self.bad_download = which == "bad_download"
            with (
                self.subTest(which=which),
                self.assertRaisesRegex(ValueError, "checksum"),
            ):
                self.run_publish()
            self.assertEqual(self.uploads, [SDK[0]])
            self.assertEqual(
                json.loads(self.journal.read_text())["result"], "incomplete"
            )

    def test_journal_and_endpoint_cannot_drift(self):
        self.run_publish()
        journal = json.loads(self.journal.read_text())
        journal["binding"]["source_sha"] = "2" * 40
        self.journal.write_text(json.dumps(journal))
        with self.assertRaisesRegex(ValueError, "journal source"):
            self.run_publish()
        for endpoint in (
            "https://crates.io",
            "http://localhost:1",
            "http://127.0.0.1:1/api",
            "http://token@127.0.0.1:1",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                Registry(endpoint)


if __name__ == "__main__":
    unittest.main()
