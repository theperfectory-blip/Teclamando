' Arranca el mando-raton sin ventana. Con el argumento "espera" queda dormido hasta Back + Start.
Set fso = CreateObject("Scripting.FileSystemObject")
carpeta = fso.GetParentFolderName(WScript.ScriptFullName)
extra = ""
If WScript.Arguments.Count > 0 Then extra = " " & WScript.Arguments(0)
CreateObject("WScript.Shell").Run "pythonw """ & carpeta & "\mando_raton.py""" & extra, 0, False
