# VMI — נקודת המשך D1-03

המשתמש אישר מסלול מפתח 1 עד D1-05, כולל בדיקות, סקירה, commits מפורטים ו־PR/מיזוג אוטומטיים בסשן ללא אישור אנושי שגרתי. אין לעקוף כללי שרת, להמציא סוקר עצמאי או להוסיף עלות. חוזה v2 ומעבר כל הצרכנים כבר אושרו.

D1-01 הסתיים ב־PR #4. D1-02 הסתיים ב־PR #5, main המאומת 12adc0528d30853c772515b5cf77c1e413e3e423; לאחר המיזוג 135 בדיקות עברו ב־17.90 שניות ו־20 fixtures נוצרו מחדש עם אפס כשלי איכות.

כרגע codex/d1-atmosphere-engine, נפתח מ־main זה. D1-03 ממומש בחלקו וטרם commit/PR: Atmosphere חדש, מעקב עצל ל־Replay, שמירת snapshot מעקב, טריות/יציבות, קהל חסר וזמינות החזקה, palette/אחוזים משותפים ל־TV ולאפליקציה ו־tests/test_atmosphere.py + tests/web/atmosphere.test.mjs. קריאת התוכנית והנוהל בוצעה; אין להתחיל D1-04 לפני מיזוג ואימות D1-03.

158 בדיקות Python עברו ב־54.75 שניות לפני תוספות קטנות אחרונות; 3 בדיקות Node עברו. בדיקת Chrome הראתה 35% זהים ב־TV ובאפליקציה, ללא שגיאות JS. יש להריץ מחדש על final SHA לאחר השלמת הסקירה.

שרת בדיקה מקומי בלבד: PID 4688, פורט 17761, exec session 15408; אין reload אוטומטי. נוצרו שני טאבים זמניים ב־Chrome, TV ואפליקציה, חדר quality-d1-03; הניגון מושהה. יש לעצור רק את השרת שלנו בסוף או לפני הפעלת קוד backend מעודכן, ולטעון מחדש את הטאבים לפני אימות נוסף.

פקודת Python: אותה סביבה זמנית, offline/warm_demo=0/plugin_autoload=0 ו־PYTEST_DEBUG_TEMPROOT ל־out/pytest-d1-02. pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error. בדיקות JS: node --test tests/web/atmosphere.test.mjs (Node 24.15.0). אין package.json/תלות חדשה; CI נשאר D2-01.

הצעד הבא: לסיים סקירת D1-03, בדיקות קצה/משולבות, מסמך חוזה/למידה, commit מפורט, full suite על SHA סופי, PR ל־main, אימות HEAD/base/דיונים וכללי שרת, squash ואימות main. לאחר מכן D1-04 ו־D1-05 בענפים המיועדים. עדכון זה קודם לרקע ההיסטורי להלן.

## רקע D1-02 לפני המיזוג (היסטורי)

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

עדכון סופי לפני commit D1-03: 38 בדיקות רכיב + 3 Node עברו; יש להריץ את כל 173 בדיקות Python על ה־HEAD הסופי. היו red/green אמיתיים לתקציר fractional deadline ולאיפוס באותה קריאת ingest. מעקב פג תוקף מקבל deadline עצמאי, וקהל/החזקה חסרים אינם מתוארים כ־0 או 50% מדודים. שני mutation נתפסו. שרת ה־QA הנוכחי הוא PID 4688; בדיקת UI הראתה 28% ו־RGB זהים. שינויים אחרונים ב־backend דורשים restart נוסף לפני אימות UI סופי. אין CI פעיל או כיסוי אחוזי שנמדד.
