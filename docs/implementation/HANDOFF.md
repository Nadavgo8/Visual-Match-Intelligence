# VMI — העברה נוכחית: D1-04 בתלת־ממד

עודכן: 24.10.2026. המשתמש אישר תלת־ממד אמיתי באיכות חזותית גבוהה, במקום החלטת הדו־ממד. נשמרים מסלול מפתח 1, ענף ו־PR לכל משימה, בדיקות מחמירות, סקירה טכנית, commits מפורטים ומיזוג אוטומטי רק לאחר מעבר השערים. אין אישור ידני שגרתי, עקיפת כללי שרת או תשלום נוסף.

## בסיס משותף מאומת

main: ‏`cbbc511db02b1d0211d3a05a70693aca22b6973d`. ‏B4 אחרון: 202 Python ב־126.03s ו־15 Node; smoke של טקסט מציג מילולי וגבול 40 רשומות עבר.

| תחום | PR / commit במיזוג | מצב |
|---|---|---|
| D1-01 חוזה v2 ומעבר מתואם | [#4](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/4) · 3baa62d | DONE |
| D1-02 תרחישים ומעקב עצל | [#5](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/5) · 12adc05 | DONE |
| D1-03 אווירה ומומנטום | [#6](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/6) · 52ad4a5 | DONE |
| D1-05 סמלים ופסים לפי PDF | [#8](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/8) · 56732ff | DONE |
| סקירת סדר מסירה ושעון | [#9](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/9) · 37fe99e | DONE |
| סקירת חלון מומנטום | [#10](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/10) · e8eb619 | DONE |
| סקירת טקסט המציג | [#11](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/11) · cbbc511 | DONE |

## עבודה נוכחית

`codex/d1-match-3d` נפתח ישירות מ־main לעיל, בתיקיית worktree קיימת `vmi-d1-trace`. אינו בנוי על PR שלא מוזג. מחליף את [Draft #7](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/7); דגימת זמן המקור, האיפוס המשותף ובדיקותיהם הועברו במפורש, וה־Canvas משמש רק גיבוי. הענף הקודם וההיסטוריה שלו נשמרים. אין להמשיך את שתי גרסאות D1-04 במקביל.

[מפרט, סקירה וראיות](D1-04-MATCH-3D.md): Three.js ‏0.186.1 מקומי ברישיון MIT ו־hash מאומת; דמויות מפרקיות, מגרש/אצטדיון פרוצדורליים, תאורה/צללים, שתי מצלמות, Low power ו־Reduce motion. עד 22 דמויות ואצוות מוגבלות. עובדות המשחק נשארות במחולל/מנוע. כל סימני הנגישות נשמרים.

ראיות לפני commit: ‏203 Python עברו ב־123.79s; ‏44 Node עברו. בדפדפן: 22 דמויות, 29 draw calls במצב High, ללא שגיאות JS; 391×844 ללא overflow ושני פסי קצה זהים. אובדן WebGL אמיתי והיעדר WebGL2 עברו ב־fixture מבודד: גיבוי מסומן וסמל Foul נשמר. סקירה: אותו Codex כתב וסקר; אין לייחס ביקורת לאדם/סוכן נוסף.

**החסם שנותר הוא ≥30FPS בפועל.** Chrome עדיין מדווח 1FPS וכ־2.4–2.9ms draw; גם דף rAF ללא VMI היה מוגבל ל־1FPS. הגורם המדויק לא אומת. אין להוריד את הסף, להחליף מדידת FPS ב־CPU draw או למזג על סמך המצב הנוכחי. ההרשאה האוטומטית למיזוג נשמרת, אך אינה עוקפת את השער. PR נשאר Draft.

נפתח [Draft PR #12](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/12); #7 נסגר כמוחלף ללא מחיקת ענפו. commit מפורט d339cc6 הועלה; על אותו SHA עברו 203 Python ב־154.01s ו־44 Node ב־1.70s. סקירה סופית הוסיפה תיקון לריצה ב־32x: מרווח 1.6 שניות מקור תקין אינו seek. הבדיקה נכשלה לפני התיקון ועברה אחריו. יש לבצע commit ממוקד וחבילה מלאה על ה־HEAD החדש; התוצאה הסופית מעודכנת ב־PR. לאחר ראיית ביצועים תקינה: אימות remote HEAD/base/דיונים, מיזוג רגיל עם match-head ואימות main. אין עבודה עצמאית נוספת של D1 שנותרה להשלמה לפני חסם זה; D2 מחוץ להיקף.

## סביבה ו־QA

Python זמני בפועל: `C:/Users/Avish/AppData/Local/Temp/vmi-quality-baseline-20261022/Scripts/python.exe` ‏3.12.13. Node ‏24.15.0. אין לשער ש־TEMP של sandbox מצביע לאותה תיקייה.

```powershell
$env:VMI_OFFLINE='1'
$env:VMI_WARM_DEMO='0'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
Remove-Item Env:APPLICATIONINSIGHTS_CONNECTION_STRING -ErrorAction SilentlyContinue
python -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error --tb=short --basetemp=out/pytest-3d-final
node --test tests/web/*.test.mjs
```

יש להתאים את נתיב Python המדויק, להשתמש בתיקיית basetemp חדשה ולשמור exit code. הרצות מוגבלות הרשאות נתקעו; ריצה רגילה עם אותן בדיקות עברה. אין skips, הנמכת assertions או ביטול warnings.

הכתובת שנשמרת למשתמש: `http://127.0.0.1:17761/tv?room=quality-d1-audit`, מוגשת כעת מענף התלת־ממד, offline ובלי חימום/telemetry. שרת uvicorn נוכחי: child PID ‏7196, session ‏24622; יש לזהות מחדש את שורת הפקודה לפני עצירה. שרת fixture זמני 17762 נסגר אחרי הבדיקה. `out/renderer-qa.html` הוא כלי QA מקומי ואינו נכנס ל־commit.

יש שלוש תיקיות של אותו מאגר, לא שלושה מוצרים: primary בענף הדו־ממד הישן; `vmi-d1-overlay` ב־main; `vmi-d1-trace` בענף התלת־ממד. לא למחוק תיקייה/ענף או להחליף branch בתיקיית כלי אחר ללא אימות עבודה ובעלות. קישור PR מכיל את ה־HEAD, ראיות ההרצה הסופית והשער הפתוח.

CI, כיסוי אחוזי, הגנות שרת, run_id/הרשאת טלפון, מודל ופריסה נשארים D2 ולא הוצגו כ־PASS.
