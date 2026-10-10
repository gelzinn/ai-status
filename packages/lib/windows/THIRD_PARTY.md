# Windows distribution dependencies

The portable folder keeps Python and Qt libraries outside the executable. Keep
the entire folder when distributing or upgrading the application.

The GUI launcher shares the console helper's single Python/Qt runtime. HTTPS
uses Windows WinHTTP/SChannel and Windows' Universal CRT is supplied by the OS;
OpenSSL is not distributed. One copy of the newest compatible MSVC 14 runtime
DLLs is retained in the shared runtime directory.

| Component | License | Source |
| --- | --- | --- |
| Python | PSF License | https://www.python.org/downloads/source/ |
| PySide6 / Qt | LGPLv3 (open-source distribution) | https://code.qt.io/cgit/pyside/pyside-setup.git/ and https://code.qt.io/cgit/qt/ |
| Shiboken6 | LGPLv3 | https://code.qt.io/cgit/pyside/pyside-setup.git/ |
| PyInstaller bootloader | GPL with distribution exception | https://github.com/pyinstaller/pyinstaller |
| Geist Mono | SIL Open Font License 1.1 | https://github.com/vercel/geist-font |

Full dependency license texts are shipped in `THIRD_PARTY_LICENSES.txt`. Qt
remains dynamically linked so users can replace its libraries. This project is
MIT-licensed; see `LICENSE`.
