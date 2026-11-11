Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\D_Drive\local_wisper"
WshShell.Run Chr(34) & "D:\D_Drive\local_wisper\.venv\Scripts\python.exe" & Chr(34) & " main.py", 0, False
Set WshShell = Nothing
