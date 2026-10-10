# Windows distribution dependencies

The portable folder keeps Python and Qt libraries outside the executable. Keep
the entire folder when distributing or upgrading the application.

| Component | License | Source |
| --- | --- | --- |
| Python | PSF License | https://www.python.org/downloads/source/ |
| PySide6 / Qt | LGPLv3 (open-source distribution) | https://code.qt.io/cgit/pyside/pyside-setup.git/ and https://code.qt.io/cgit/qt/ |
| Shiboken6 | LGPLv3 | https://code.qt.io/cgit/pyside/pyside-setup.git/ |
| pywinpty | MIT | https://github.com/andfoy/pywinpty |
| PyInstaller bootloader | GPL with distribution exception | https://github.com/pyinstaller/pyinstaller |

Full dependency license texts are shipped in `THIRD_PARTY_LICENSES.txt`. Qt
remains dynamically linked so users can replace its libraries. This project is
MIT-licensed; see `LICENSE`.
