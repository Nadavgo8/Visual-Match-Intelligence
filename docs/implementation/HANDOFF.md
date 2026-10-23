# VMI — העברה עדכנית: D1-04 ממתין לאימות FPS

עודכן: 23.10.2026. המשתמש אישר מסלול מפתח 1, D1-01 עד D1-05, כולל בדיקות, סקירה, תיקונים, commits מפורטים, push, PR ומיזוג squash אוטומטי בסשן. אין אישור אנושי שגרתי, עקיפת שרת או תשלום. חוזה v2 ומעבר כל הצרכנים אושרו. הבקשה האחרונה מחייבת התאמה מדויקת לתוכנית ולמסמך ששת העמודים; כל העמודים והאיורים נקראו והעותק המצורף זהה לעותק בריפו.

## הושלם ואומת על main

| משימה | PR / main | אימות אחרי מיזוג |
|---|---|---|
| נוהל | #1 / b5fe932 | 33 בדיקות |
| ייצוב מחולל | #3 / 2bc616a | 42 בדיקות; Draft #2 נסגר כמוחלף ולא מוזג |
| D1-01 | [#4](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/4) / 3baa62d | 85 בדיקות ב־17.10s ו־smoke משחק מלא |
| D1-02 | [#5](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/5) / 12adc05 | 135 בדיקות ב־17.90s ו־20 exports תקינים |
| D1-03 | [#6](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/6) / 52ad4a5 | 174 Python ב־64.47s, ‏3 Node ו־smoke עצירה/תוצאה |
| D1-05 | [#8](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/8) / 56732ff7bf36b76f773900289bfdd1825249da0d | 183 Python ב־65.67s, ‏12 Node ו־smoke סמל שתייה, תוצאה וחידוש מפורש |

D1-05 נפתח מ־main מאומת בתיקיית vmi-d1-overlay הנפרדת ולא מעל PR #7. הוא הושלם כמשימה עצמאית על מסך 2D הקיים. [מפת ההתאמה לעיצוב](D1-05-ACCESSIBILITY.md) מתעדת את שני פסי הקצה, הסמל העגול היחיד, ה־HUD הקטן, מומנטום והפרדת המציג. תיקיית vmi-d1-overlay נמצאת כעת על main המאומת והיא נקייה.

## D1-04 — מומש ושולב, טרם מוזג

[Draft PR #7](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/7), ענף codex/d1-match-2d, בתיקיית Visual-Match-Intelligence המקורית. אחרי B4 של D1-05 מוזג main ‏56732ff לענף באמצעות merge רגיל; commit השילוב הוא 7f3fa9d2586ebb3cf389579f853451bfee5d9472. לא בוצע rebase, force push או פתרון גורף לפי צד אחד.

השילוב משמר את עיצוב D1-05 ואת renderer הדו־ממד של D1-04: מגרש 105×68 ביחס מטרי תקין, תלבושות מקוריות ומובחנות, גובה/צל, אינטרפולציה לפי זמן מקור ובאפר מוגבל. MatchScreen מרכז איפוס של שני המשטחים ב־seek, שינוי זהות והרצה, ושינויי זמן גדולים. תוצאת משחק אינה נקבעת בגרפיקה. [פירוט](D1-04-MATCH-2D.md).

ראיות לפני commit השילוב: 184 Python עברו ב־64.39s ו־28 Node עברו. נוספו שש בדיקות שילוב; סקירה מצאה וחסמה מצב שבו קפיצה קדימה מאפסת פריימים אך משאירה סמל ישן. בדפדפן הוצג העיצוב המשולב ללא שגיאות JS. תוצאות על HEAD הסופי נשמרות בגוף PR #7; אין להשתמש בראיות של 51df5a8 כראיות לשילוב החדש. סקירה היא של Codex המחבר, ללא אישור אנושי או ביקורת עצמאית מומצאת.

## החסם שנותר והצעד הבא

יעד 30FPS עדיין NOT_VERIFIED. ה־rAF בדפדפן דיווח 1FPS, אף שעלות הציור הייתה כ־0.4–1.3ms. נבדקו טאב נבחר, viewport, ניגון בסיסי ורענון; ניסיון לפתוח טאב עם visibility מפורש אינו נתמך בכלי הדפדפן. זמן ציור נמוך אינו הוכחת 30FPS ולא נקבעה סיבת האטת ה־rAF בוודאות. נשלחה בקשה חד־פעמית להציג את Chrome בחזית לצורך מדידה חוזרת.

אין למזג #7 או לסמן D1-04 DONE לפני מדידת FPS תקינה, הרצה/סקירה עדכניות על אותו HEAD ואימות בסיס/דיונים/כללי שרת. אם המדידה תעבור: לעדכן ראיות, להסיר Draft, לבצע squash רגיל עם match-head-commit ולבדוק את main ב־B4. אין משימת D1 עצמאית נוספת שנותרה לפני סגירת החסם.

## סביבת בדיקה

Python ‏3.12.13 בסביבה הזמנית TEMP/vmi-quality-baseline-20261022/Scripts/python.exe; Node ‏24.15.0. אין תלות חדשה בפרויקט. PyMuPDF הותקן רק בסביבה הזמנית לקריאת המסמך.

```powershell
$env:VMI_OFFLINE = '1'
$env:VMI_WARM_DEMO = '0'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:PYTEST_DEBUG_TEMPROOT = Join-Path (Get-Location) 'out/pytest-d1-02'
Remove-Item Env:APPLICATIONINSIGHTS_CONNECTION_STRING -ErrorAction SilentlyContinue
python -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error
node --test tests/web/*.test.mjs
```

יש להשתמש ב־python הזמני המפורש במחשב זה. שרת QA המשולב היחיד שנותר: PID ‏13136, session ‏43313, ‏127.0.0.1:17761, offline וללא warm demo/telemetry; אינו מופעל מחדש אוטומטית. טאב Chrome זמני: /tv?room=quality-d1-03. שרתי D1-05 ותרחישים 7424/24340 נעצרו לאחר אימות זהותם. ה־viewport הוחזר לברירת המחדל. אין לעצור Python של השותף או למחוק worktree/branch שאינם שלנו.

CI, כיסוי, הגנות ענף, run_id/הרשאת טלפון, מודל, catch-up והפצה נשארים D2. אין טענת השלמה של האפליקציה בעמוד 4 למסמך או של שערי עומס/soak/הגשה. הראיות ההיסטוריות נשמרות ב־PRs, בלוח ובהיסטוריית Git.
