"""Exercise ephemeral TLS credentials without network access or OS trust changes."""

import hashlib
import os
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch

import tls_fixture


def handshake(client_context, hostname):
    server_input, server_output = ssl.MemoryBIO(), ssl.MemoryBIO()
    client_input, client_output = ssl.MemoryBIO(), ssl.MemoryBIO()
    server = tls_fixture.localhost_tls_context().wrap_bio(server_input, server_output, server_side=True)
    client = client_context.wrap_bio(client_input, client_output, server_hostname=hostname)
    completed = set()
    for _ in range(20):
        for peer in (server, client):
            if peer not in completed:
                try:
                    peer.do_handshake()
                    completed.add(peer)
                except ssl.SSLWantReadError:
                    pass
        for outgoing, incoming in ((server_output, client_input), (client_output, server_input)):
            if outgoing.pending:
                incoming.write(outgoing.read())
        if len(completed) == 2:
            client.write(b"fixture payload")
            server_input.write(client_output.read())
            if server.read(100) != b"fixture payload":
                raise AssertionError("TLS handshake did not establish a working connection")
            return client
    raise AssertionError("TLS handshake did not complete")


class TLSFixtureTests(unittest.TestCase):
    def setUp(self):
        tls_fixture._localhost_tls_fixture.cache_clear()
        self.addCleanup(tls_fixture._localhost_tls_fixture.cache_clear)

    def test_generation_ignores_external_configuration_and_deletes_files_before_returning(self):
        external = {name: "invalid-external-tls-configuration" for name in (
            "OPENSSL_CONF", "OPENSSL_CONF_INCLUDE", "OPENSSL_MODULES", "OPENSSL_ENGINES", "RANDFILE")}
        with patch.dict(os.environ, external), \
                patch.object(tls_fixture.subprocess, "run", wraps=tls_fixture.subprocess.run) as generate:
            context = tls_fixture.localhost_tls_context()
            fingerprint = tls_fixture.localhost_tls_fingerprint()
            self.assertIs(tls_fixture.localhost_tls_context(), context)
            self.assertEqual(tls_fixture.localhost_tls_fingerprint(), fingerprint)
        generate.assert_called_once()
        arguments = generate.call_args.args[0]
        for flag in ("-keyout", "-out", "-config"):
            self.assertFalse(Path(arguments[arguments.index(flag) + 1]).exists(), flag)
        self.assertFalse(Path(arguments[arguments.index("-out") + 1]).parent.exists())

    def test_generated_certificate_supports_loopback_only_with_explicit_trust(self):
        _, certificate = tls_fixture._localhost_tls_fixture()
        trusted = ssl.create_default_context(cadata=certificate)
        # Match the TLS version used by the PowerShell installer downloader.
        trusted.maximum_version = ssl.TLSVersion.TLSv1_2
        for hostname in ("localhost", "127.0.0.1"):
            with self.subTest(hostname=hostname):
                client = handshake(trusted, hostname)
                fingerprint = hashlib.sha1(client.getpeercert(binary_form=True)).hexdigest().upper()
                self.assertEqual(tls_fixture.localhost_tls_fingerprint(), fingerprint)
        with self.assertRaises(ssl.SSLCertVerificationError):
            handshake(ssl.create_default_context(), "localhost")
        with self.assertRaises(ssl.SSLCertVerificationError):
            handshake(trusted, "other.invalid")

    def test_windows_prefers_openssl_from_git_over_an_unrelated_path_installation(self):
        with tempfile.TemporaryDirectory(prefix="ai-status-test-git-") as temporary:
            directory = Path(temporary) / "directory"
            directory.mkdir()
            # Exercise canonicalization on every host; Windows also expands
            # short temp paths such as RUNNER~1 to their long spelling.
            root = directory / ".."
            git = root / "Git" / "cmd" / "git.exe"
            bundled = root / "Git" / "usr" / "bin" / "openssl.exe"
            for executable in (git, bundled):
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.touch()
            unrelated = root / "other" / "openssl.exe"
            with patch.object(tls_fixture.sys, "platform", "win32"), \
                    patch.object(tls_fixture.shutil, "which", side_effect=lambda name:
                                 str(git) if name == "git.exe" else str(unrelated)):
                self.assertTrue(Path(tls_fixture._openssl()).samefile(bundled))


if __name__ == "__main__":
    unittest.main()
