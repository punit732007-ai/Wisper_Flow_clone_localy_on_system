"""
LocalWhisper Pro — Universal Command Installer
Registers the `localwhisper` command in user PATH locations (~/.local/bin and ~/.localwhisper/bin),
creates zero-terminal VBS background runners, and repairs missing pythonw.exe in uv environments.
"""

import os
import sys
import struct
import subprocess
from pathlib import Path


def ensure_pythonw(workspace: Path) -> Path:
    """Ensure pythonw.exe exists and functions properly on Windows (especially for uv)."""
    venv_dir = workspace / ".venv"
    scripts_dir = venv_dir / "Scripts"
    python_exe = scripts_dir / "python.exe"
    pythonw_exe = scripts_dir / "pythonw.exe"

    if sys.platform != "win32":
        return python_exe

    cfg_file = venv_dir / "pyvenv.cfg"
    home_dir = None
    if cfg_file.exists():
        try:
            for line in cfg_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("home"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        home_dir = Path(parts[1].strip())
                        break
        except Exception:
            pass

    def patch_pe_to_gui(src_path: Path, dst_path: Path):
        try:
            with open(src_path, "rb") as f:
                data = bytearray(f.read())
            pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
            # Subsystem byte at pe_offset + 0x5C (2 = IMAGE_SUBSYSTEM_WINDOWS_GUI)
            struct.pack_into("<H", data, pe_offset + 0x5C, 2)
            with open(dst_path, "wb") as f:
                f.write(data)
        except Exception:
            pass

    # 1. If base home directory lacks pythonw.exe (typical for uv standalone cpython)
    if home_dir and (home_dir / "python.exe").exists() and not (home_dir / "pythonw.exe").exists():
        patch_pe_to_gui(home_dir / "python.exe", home_dir / "pythonw.exe")

    # 2. Check if .venv\Scripts\pythonw.exe actually runs
    test_ok = False
    if pythonw_exe.exists():
        try:
            res = subprocess.run([str(pythonw_exe), "-c", "import sys; sys.exit(0)"], capture_output=True, timeout=3)
            test_ok = (res.returncode == 0)
        except Exception:
            test_ok = False

    if not test_ok:
        if python_exe.exists():
            patch_pe_to_gui(python_exe, pythonw_exe)
            try:
                res = subprocess.run([str(pythonw_exe), "-c", "import sys; sys.exit(0)"], capture_output=True, timeout=3)
                test_ok = (res.returncode == 0)
            except Exception:
                test_ok = False

    return pythonw_exe if test_ok else python_exe


def register_command():
    user_home = Path.home()
    workspace = Path(__file__).resolve().parent

    py_runner = ensure_pythonw(workspace)

    # Candidate global bin folders
    target_dirs = [
        user_home / ".local" / "bin",
        user_home / ".localwhisper" / "bin",
    ]

    # Create root workspace run_silent.vbs
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{workspace}"
WshShell.Run Chr(34) & "{workspace / '.venv' / 'Scripts' / 'python.exe'}" & Chr(34) & " main.py", 0, False
Set WshShell = Nothing
'''
    try:
        with open(workspace / "run_silent.vbs", "w", encoding="utf-8") as f:
            f.write(vbs_content)
    except Exception:
        pass

    bat_content = f"""@echo off
cd /d "{workspace}"
if exist "{workspace / 'run_silent.vbs'}" (
    wscript.exe //nologo "{workspace / 'run_silent.vbs'}" %*
) else (
    start "" "{py_runner}" main.py %*
)
"""

    ps1_content = f"""Start-Process -FilePath "{py_runner}" -ArgumentList "main.py $args" -WorkingDirectory "{workspace}" -WindowStyle Hidden
"""

    for target_dir in target_dirs:
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. localwhisper.bat
        bat_file = target_dir / "localwhisper.bat"
        with open(bat_file, "w", encoding="utf-8") as f:
            f.write(bat_content)

        # 2. localwhisper.cmd
        cmd_file = target_dir / "localwhisper.cmd"
        with open(cmd_file, "w", encoding="utf-8") as f:
            f.write(bat_content)

        # 3. localwhisper.ps1
        ps1_file = target_dir / "localwhisper.ps1"
        with open(ps1_file, "w", encoding="utf-8") as f:
            f.write(ps1_content)

        print(f"[OK] Registered command in: {target_dir}")

    # Ensure ~/.localwhisper/bin is added to User PATH in Windows Registry
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0, winreg.KEY_ALL_ACCESS)
            current_path, _ = winreg.QueryValueEx(key, "Path")
            localwhisper_bin = str(user_home / ".localwhisper" / "bin")
            local_bin = str(user_home / ".local" / "bin")

            updated = False
            new_path_parts = [p for p in current_path.split(";") if p]

            if local_bin not in new_path_parts:
                new_path_parts.append(local_bin)
                updated = True

            if localwhisper_bin not in new_path_parts:
                new_path_parts.append(localwhisper_bin)
                updated = True

            if updated:
                new_path = ";".join(new_path_parts)
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path)
                print("[OK] Added bin directories to Windows User Environment PATH.")
            else:
                print("[OK] User Environment PATH already contains target bin directories.")
            winreg.CloseKey(key)
        except Exception as e:
            print(f"[Note] Could not update Registry PATH automatically: {e}")


if __name__ == "__main__":
    register_command()
