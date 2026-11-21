' Hidden launcher for fetch_daily.ps1
' 计划任务用 wscript.exe 起（GUI 子系统，无控制台），内层再以 window style 0
' 拉起 pwsh，这样凌晨跑的时候不会闪一个黑窗口。
Set sh = CreateObject("WScript.Shell")
sh.Run "C:\Users\iq112\AppData\Local\Microsoft\WindowsApps\pwsh.exe -NoProfile -ExecutionPolicy Bypass -File ""C:\Users\iq112\codes\cninfo-disclosure\bulk\fetch_daily.ps1""", 0, False
