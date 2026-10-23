# VMI — נקודת המשך עדכנית

עודכן: 23.10.2026. המשתמש אישר ביצוע מסלול D1-01 עד D1-05, בדיקות מחמירות, סקירה, commits מפורטים, push, PR ומיזוג אוטומטי בסשן. אין אישור אנושי שגרתי. אין לעקוף כללי שרת או להמציא סוקר עצמאי. חוזה v2 ומעבר כל המפיקים והצרכנים יחד כבר אושרו בשיחה. אפס תשלום נוסף; D2 אינו מסלול העבודה שלנו.

## הושלם

- PR #1: נוהל. PR #3: ייצוב שוער ושחזור. PR #2 נסגר כמוחלף ב־#3.
- [PR #4](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/4): D1-01 הושלם. main המאומת הוא 3baa62d0e8f4c1fe55cb83d30bd32c9733d04d0f. 85 בדיקות עברו לאחר squash ב־17.10 שניות; smoke משחק מלא, תוצאה, קישורים ו־xG מאוחר עברו. ראיות HEAD, סקירה ו־B4 ברשומת PR #4.

## עבודה נוכחית

ענף codex/d1-generator-scenarios נפתח ישירות מה־main הזה. D1-02 ממומש וממתין לסקירה ולהרצת final HEAD לפני PR. אין עדיין מיזוג של D1-02 ואין לסמן DONE. נוספו scenarios.py, fixtures.py, בדיקות והוראות ב־[D1-02-SCENARIOS.md](D1-02-SCENARIOS.md). 20 תרחישים קצרים; דגימה לפי דרישה ב־20Hz; CLI ודוחות; ביטול שער ובישול, תנאי מסירה ו־metadata ללא זליגת סוג התרחיש.

[לוח העבודה](10-WORK-BOARD.md) מתעד את הרצות הביניים, התיקונים ושני ניסויי mutation. לאחר תיקון ביצועים עברו 130 בדיקות ב־17.79 שניות; מאז נוספו בדיקות/שדות קטנים ולכן תוצאה זו אינה הוכחת final SHA. נדרש commit מפורט, הרצה מלאה, סקירת כל diff, push ו־PR עצמאי ל־main, בדיקת HEAD/base/checks/דיונים, squash רגיל ללא bypass ואימות main.

## סביבת בדיקה

Python 3.12.13 בסביבה הזמנית הקיימת; אין צורך להתקין שוב או לבחור ספק. PowerShell משורש הריפו:

```powershell
$testTmpRoot = Join-Path (Get-Location) 'out/pytest-d1-02'
New-Item -ItemType Directory -Path $testTmpRoot -Force | Out-Null
$env:PYTEST_DEBUG_TEMPROOT = $testTmpRoot
$env:VMI_OFFLINE = '1'
$env:VMI_WARM_DEMO = '0'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
Remove-Item Env:APPLICATIONINSIGHTS_CONNECTION_STRING -ErrorAction SilentlyContinue
& "$env:TEMP/vmi-quality-baseline-20261022/Scripts/python.exe" -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error
& "$env:TEMP/vmi-quality-baseline-20261022/Scripts/python.exe" -m vmi.generator.fixtures --output out/v2-fixtures
```

תיקיית Temp הכללית הייתה חסומה לסריקה; השימוש בתיקיית out ייעודית פתר את סביבת הבדיקה בלי לשנות מוצר או להחליש בדיקה. קובצי fixtures ודוחות תחת out מוחרגים מ־Git.

## המשך אוטומטי

לאחר B4 של D1-02: לפתוח codex/d1-atmosphere-engine מה־main המעודכן, ואז D1-04 ו־D1-05 לאחר תלויותיהם. נדרשים 80/20, החזקה יציבה 300ms, טריות 500ms, זיהוי התקפה ושבע דקות מומנטום; לאחר מכן ליטוש 2D ומחזור חיי הסמלים לפי התוכנית. הרשאות חדרים, run_id, CI, כיסוי וספק מודל נשארים D2; אין טענה שהם הוקמו. שער שלב משותף אינו מוכרז רק משום שמשימת D1 הושלמה.

עדכון סקירה D1-02: 101 seeds מלאים ו־60 שילובי תרחיש/seed עברו. 50 הבדיקות החדשות עברו ב־1.17 שניות. בדיקת ביטול שגוי תוקנה כדי למסור תחילה את כל המקורות שלה: אירוע שחסר לו מקור צריך להמתין, ולא להיכשל מיד. הבדיקה המתוקנת עדיין דורשת דחיית זהות/זמן שגויים ללא שינוי תוצאה. קפיצת מגן בעצירה תוקנה באמצעות שימור נקודות המשתתפים. סוקר ומחבר: אותו Codex. final SHA עדיין נדרש להרצה מלאה.
