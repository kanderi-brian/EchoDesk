# EchoDesk 3.2 Windows Installation

For end users, run `EchoDesk-Setup-3.2.0.exe`. The installer creates a Start
Menu shortcut and can optionally create a Desktop shortcut and start EchoDesk
when you sign in. Upgrades replace only installed application files; personal
settings, logs, memory, cache, voice configuration, and temporary files stay
under `%LOCALAPPDATA%\EchoDesk`.

The application opens the floating assistant. Use `EchoDesk.exe --console` for
the console fallback. If Ollama is unavailable, EchoDesk remains open and logs
the status; start Ollama locally or install it from https://ollama.com.

## Building the release

From a development checkout with Inno Setup 6 installed:

```powershell
.\.venv\Scripts\python.exe -m pip install .[build]
.\release\build.ps1 -Format all
```

The PyInstaller application is written to `dist\EchoDesk\EchoDesk.exe` and the
installer to `dist\EchoDesk-Setup-3.2.0.exe`. The build first runs the complete
test suite unless `-SkipTests` is supplied.
# Windows desktop installation and startup

The Windows installer installs `EchoDesk.exe`, creates a Start Menu shortcut, and can create a Desktop shortcut. During setup, keep **Launch EchoDesk when I sign in** selected to register it for the current Windows user. The installer also removes that registration when EchoDesk is uninstalled.

After sign-in EchoDesk runs quietly in the notification area; it does not open a window. Use the tray menu, click the tray icon, say **Hey Echo**, or press **Ctrl+Shift+Space** to open the existing chat workspace. Its last UI session is restored from your local EchoDesk data folder.

You can change the sign-in preference later from **Settings → Launch EchoDesk when I sign in**. The setting writes only to your own Windows startup registration, never a machine-wide entry.

Build a signed-ready installer from a developer checkout with:

```powershell
.\release\build.ps1 -Format installer
```

This produces a windowed `EchoDesk.exe` and an Inno Setup installer in `dist`. Inno Setup 6 is required only for the installer stage. Use `-Format portable` for the portable archive.
