"""Ephemeral loopback TLS credentials, shared within one test process."""

from functools import lru_cache
import hashlib
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import sys
import tempfile


_CONFIG = """[req]
distinguished_name = subject
x509_extensions = extensions
prompt = no

[subject]
CN = localhost

[extensions]
subjectAltName = DNS:localhost,IP:127.0.0.1
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature
extendedKeyUsage = serverAuth
"""


def _openssl():
    if sys.platform == "win32":
        # Git's bundled OpenSSL avoids a runner's unrelated PATH installation.
        git = shutil.which("git.exe") or shutil.which("git")
        roots = [Path(git).resolve().parent.parent] if git else []
        roots += [Path(os.environ.get(name, "C:/Program Files")) / "Git"
                  for name in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)")]
        for root in roots:
            candidate = root / "usr" / "bin" / "openssl.exe"
            if candidate.is_file():
                return str(candidate)
    executable = shutil.which("openssl")
    if executable:
        return executable
    raise RuntimeError("OpenSSL is required for TLS integration tests; install Git for Windows or OpenSSL.")


@lru_cache(maxsize=1)
def _localhost_tls_fixture():
    executable = _openssl()
    with tempfile.TemporaryDirectory(prefix="ai-status-test-tls-") as temporary:
        folder = Path(temporary)
        configuration = folder / "openssl.cnf"
        key, certificate = folder / "key.pem", folder / "cert.pem"
        configuration.write_text(_CONFIG, encoding="ascii")
        external = {"OPENSSL_CONF", "OPENSSL_CONF_INCLUDE", "OPENSSL_MODULES", "OPENSSL_ENGINES", "RANDFILE"}
        environment = {name: value for name, value in os.environ.items() if name.upper() not in external}
        environment["OPENSSL_CONF"] = str(configuration)
        try:
            subprocess.run(
                [executable, "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                 "-sha256", "-nodes", "-batch", "-days", "1", "-config", str(configuration),
                 "-keyout", str(key), "-out", str(certificate)],
                stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=15, env=environment)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(f"TLS fixture generation timed out using {executable}.") from error
        except subprocess.CalledProcessError as error:
            detail = error.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(f"TLS fixture generation failed using {executable}: {detail}") from error
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certificate, key)
        public_certificate = certificate.read_text(encoding="ascii")
    # SSLContext owns the loaded key; no credential files survive generation.
    return context, public_certificate


def localhost_tls_context():
    return _localhost_tls_fixture()[0]


def localhost_tls_fingerprint():
    certificate = ssl.PEM_cert_to_DER_cert(_localhost_tls_fixture()[1])
    return hashlib.sha1(certificate).hexdigest().upper()
