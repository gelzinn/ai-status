# Windows development and builds

Use x64 Python 3.12, Inno Setup 6, and Visual Studio Build Tools with the x64
C++ compiler and Windows SDK on a Windows build machine. Git for Windows
supplies the OpenSSL test tool used to generate a temporary, self-signed localhost
certificate. Tests prefer that bundled tool over other PATH installations and
use EC P-256 with an isolated configuration to avoid slow RSA key generation.
The certificate and key are generated once per test process, loaded into memory,
and immediately deleted. Tests never change the OS certificate store; the
download test pins its certificate only inside its own PowerShell subprocess.
OpenSSL is not shipped with the app. From the repo:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r packages/lib/windows/requirements.txt
python packages/lib/src/windows.py tray
$env:QT_QPA_PLATFORM = "offscreen"
python -m unittest discover -s packages/lib/tests -v
Remove-Item Env:QT_QPA_PLATFORM
.\packages\lib\windows\build.ps1
```

The build produces a small native windowed launcher and a console helper sharing
one Python/Qt runtime in `dist/ai-status`, an installer and a portable ZIP. The
launcher carries the app icon, preserves arguments/exit status, and starts the
helper without a console window. The helper runs bundled collectors in isolated
subprocesses with explicit timeouts; running `.py` files through Windows file
associations is never required. Qt/Python remain external dynamic libraries in
the folder. Dependency license texts accompany the package.

The **Windows package** workflow runs tests, builds both distributions and
smoke-tests the packaged collectors, GUI dependencies, silent install and
uninstall on a Windows runner. Release automation attaches those artifacts to
the existing versioned GitHub release. Hosted Windows runners do not replace
interactive testing on Windows 10/11: validate tray interaction, scaling,
Explorer restart, suspend/resume, upgrade and authenticated usage on both OSes
before announcing full provider compatibility.

Check one and several selected tray items, including two limits from one
account and two accounts for one provider. Each item needs a tooltip with its
account, limit and value; clicking any icon must position the same usage panel
beside that icon. Verify icon addition/removal after Save, Cancel, empty-selection
validation and migration from single-item preferences. Click/Up/Down selection
changes must retain the extra items without duplicates. Restart Explorer and
the app with icons both beside the clock and in the hidden-icons menu. Check
temporary provider failures: saved selections must survive and return when
data does. Windows manages notification-area visibility and order.

Windows supports multiple notification-area icons per application window,
identified separately; see Microsoft's
[NOTIFYICONDATAW reference](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/ns-shellapi-notifyicondataw).
The Qt adapter manages these as separate `QSystemTrayIcon` instances.

The package ships only raster widgets and the required Windows/offscreen Qt
platform plugins. OpenGL software emulation, QML/Quick, QtNetwork/QtSvg, unused
image/TLS plugins, translations, legacy Bash collectors and bytecode caches are
excluded. Windows HTTPS uses WinHTTP and the system certificate store, including
normal certificate/hostname checks, timeouts, proxy settings and decompression.
Authentication headers are retained on same-origin redirects and removed when
the origin changes. HTTPS redirects to HTTP are rejected.

Python/OpenSSL and Qt TLS libraries are omitted from the Windows bundle. The
Universal CRT comes from Windows 10/11; duplicate MSVC 14 DLLs are consolidated
to the newest backwards-compatible version. Qt remains dynamically linked and
replaceable. The installer uses solid LZMA2 with a 64 MiB dictionary; the portable
ZIP retains Deflate for Windows Explorer compatibility. Frozen Python bytecode
uses optimization level 2 and maximum zlib compression, omitting development
docstrings/assertions; runtime input validation uses explicit exceptions.

CI renders the packaged widgets/logos, runs real ConPTY input/output checks,
tests native HTTP against localhost (including invalid TLS certificates), and
verifies public HTTPS from the frozen executable.

The public HTTPS probe records HTTP error statuses, including anonymous API
rate limits, as successful TLS round trips in `doctor --http-smoke` output.
Certificate, hostname and transport failures still fail the packaged smoke.
CI also tests the native launcher, silent install/upgrade/uninstall in a Unicode path (including removal
of obsolete runtime DLLs and preservation of user data), and enforces size budgets
of 56 MiB installed, 23 MiB for the portable ZIP, and 18 MiB for the installer.
These budgets include the required SQLite runtime for Cursor/Kiro credential
readers and live Google Cloud authentication fingerprints. Optional Qt/OpenSSL
libraries remain excluded. The build summary lists the largest remaining
runtime files.
