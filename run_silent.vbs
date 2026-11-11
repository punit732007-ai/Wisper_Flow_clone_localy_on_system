Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)
pythonExe = currentDir & "\.venv\Scripts\python.exe"

If fso.FileExists(pythonExe) Then
    WshShell.CurrentDirectory = currentDir
    WshShell.Run Chr(34) & pythonExe & Chr(34) & " main.py", 0, False
Else
    WshShell.CurrentDirectory = currentDir
    WshShell.Run Chr(34) & currentDir & "\run.bat" & Chr(34), 1, False
End If
Set WshShell = Nothing
Set fso = Nothing
