@echo off
echo === تركيب خدمة البوت النهائية ===

echo 1. إيقاف أي عمليات سابقة...
taskkill /f /im python.exe >nul 2>&1

echo 2. إنشاء مهمة ويندوز مجدولة...
schtasks /delete /tn "QuizBotService" /f >nul 2>&1

schtasks /create /tn "QuizBotService" ^
/tr "C:\Users\Elite\myBot\start_bot.bat" ^
/sc onstart ^
/ru "SYSTEM" ^
/f

echo 3. بدء الخدمة...
schtasks /run /tn "QuizBotService"

echo 4. التحقق من التركيب...
timeout /t 3 >nul
schtasks /query /tn "QuizBotService"

echo.
echo ✅ تم التركيب بنجاح!
echo 📋 البوت سيعمل تلقائياً مع نظام التشغيل
echo 🔍 للتحقق: tasklist ^| findstr python
pause