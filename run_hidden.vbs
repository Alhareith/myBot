Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd C:\Users\Elite\myBot && python bot.py", 0, False
MsgBox "✅ تم تشغيل البوت في الخلفية", vbInformation, "Quiz Bot"