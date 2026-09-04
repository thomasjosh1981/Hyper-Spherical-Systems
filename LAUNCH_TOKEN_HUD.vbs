Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
py313 = "C:\Users\twist\AppData\Local\Programs\Python\Python313\pythonw.exe"
If fso.FileExists(py313) Then
    cmd = """" & py313 & """ ""C:\hyper_spherical\LAUNCH_TOKEN_HUD.pyw"""
Else
    cmd = "pythonw.exe ""C:\hyper_spherical\LAUNCH_TOKEN_HUD.pyw"""
End If
WshShell.CurrentDirectory = "C:\hyper_spherical"
WshShell.Run cmd, 0, False
