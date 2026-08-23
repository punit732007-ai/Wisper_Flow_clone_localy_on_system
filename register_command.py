"""
LocalWhisper Pro — Universal Command Installer
Registers the `localwhisper` command in user PATH locations (~/.local/bin and ~/.localwhisper/bin).
"""

import os
import sys
from pathlib import Path

def register_command():
    user_home = Path.home()
    workspace = Path(__file__).resolve().parent

    # Candidate global bin folders
    target_dirs = [
        user_home / ".local" / "bin",
        user_home / ".localwhisper" / "bin",
    ]

    bat_content = f"""@echo off
cd /d "{workspace}"
start "" "{workspace / '.venv' / 'Scripts' / 'pythonw.exe'}" main.py %*
"""

    ps1_content = f"""Start-Process -FilePath "{workspace / '.venv' / 'Scripts' / 'pythonw.exe'}" -ArgumentList "main.py $args" -WorkingDirectory "{workspace}"
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
