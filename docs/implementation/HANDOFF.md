# VMI — העברה נוכחית: D1-04 ושדרוג הייחוס החזותי

עודכן: 24.10.2026. דרישת המשתמש כוללת תלת־ממד ברמת תמונת הייחוס לפחות, והמחשת אווירת הקהל. זהו המשך D1-04 באותו ענף ו־PR. ביצוע שוטף, בדיקות, סקירה, commit/push ומיזוג אחרי שערים מורשים אוטומטית. אין אישור אנושי שגרתי, תשלום נוסף או מעבר למסלול D2.

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

## מצב D1-04

`codex/d1-match-3d` נפתח ישירות מה־main לעיל, בתיקיית worktree קיימת `vmi-d1-trace`. ‏[PR #12](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/12) נשאר Draft; ‏#7 נסגר כמוחלף ללא מחיקת ענפו. commit ‏e2920d2 כלל את התלת־ממד הראשוני ותיקון 32x. השדרוג הנוכחי מחליף את הדמויות הבסיסיות בגאומטריה אנושית עם שלד, דשא מפות CC0 וקהל מפורט יותר המקודד את `atmosphere.crowd` בלבד. הקוד, הבדיקות והתיקונים שייכים לאותה משימה ואינם PR בדיקות נפרד.

[מפרט, סקירה וראיות](D1-04-MATCH-3D.md) ו־[מקור הנכסים](../../web/assets/README.md). אין CDN או נכסים בתשלום. שמורים רישיונות, commit מקור ו־hashes. ‏80/20 נשאר ללא שינוי; המחשת הקהל אינה הוכחה עצמאית לתקפות המדד ואינה מסיקה רגשות.

## בדיקות וסקירה

- baseline בתחילת השדרוג: 203 Python ב־97.95s. חבילת JS אחרי השדרוג: 56 עברו ב־4.79s, ללא skipped. SHA סופי, פקודות ותוצאות חבילה מלאה לאחר commit נרשמים ב־PR; אין לייחס להרצה קוד מאוחר יותר.
- בדיקות חדשות: שלד שמזיז בפועל vertices ברגל; כיוון משטח שיער; חילופים וניקוי GPU משותף; מסלול ריצה זהה ב־20/60 דגימות; קהל שקט/רועש/חסר בנפרד מהתקפה; shader בפועל; רישיונות ו־hashes; כשל בניית renderer אחרי טעינת טקסטורות.
- שלושה ניסויי mutation נתפסו: גובה, זהות משחק וקהל שניזון מהמדד המשולב. לא נשמר mutation בקוד מוצר.
- בדפדפן: קהל שקט עם התקפה מלאה, קהל חזק ללא התקפה, קלט חסר ואובדן WebGL אמיתי נבדקו ב־fixture מבודד. Foul נשמר ב־DOM בגיבוי מסומן. בדיקות מצב חסכוני, pause והפחתת תנועה בוצעו במשחק החי.
- ממצאים שתוקנו: שחרור buffers משותפים בחילוף, כיוון שיער הפוך, חיבור shader של צבע עור/חולצה, שלב ריצה שאינו תלוי דגימה, LF מפורש בפלט הממיר. שתי בניות חוזרות הניבו אותו hash.
- Codex המחבר והסוקר בשלבים נפרדים באותו סשן. אין לייחס סקירה לאדם או לסוכן אחר.

## שערים פתוחים

ביצועים נמדדו כעת בדפדפן IAB גלוי, ב־1x ועם 22 שחקנים, במחשב i7-1065G7 / Iris Plus. ‏1280×850: ‏High ‏40–42FPS, ‏Low ‏48FPS. ‏1920×1080, canvas ‏1576×887: ‏High ‏31FPS, ‏Low ‏38FPS. אלו חלונות מדידה מוצגים של שתי שניות, לא soak ולא הבטחה לכל חומרה. חסם Chrome הישן של 1FPS אינו מתאר מדידה זו.

**קבלת רמת הייחוס עדיין פתוחה:** קיימים שיפור משמעותי באנטומיה, בדשא ובקהל, אך גם חזרתיות ביציעים, פרטי אצטדיון מוגבלים ואנימציית כדורגל בסיסית. אין לסמן את דרישת המשתמש ״לפחות כמו התמונה״ כ־PASS בגלל FPS ובדיקות ירוקים. סטטוס D1-04 נשאר IN_PROGRESS ו־PR נשאר Draft. המשך הליטוש באותו ענף; לא מתחילים D2 או משימה חדשה כדי לעקוף פער חזותי. B4 לא בוצע לשדרוג זה.

## פקודות והדגמה

```powershell
$env:VMI_OFFLINE = '1'
$env:VMI_WARM_DEMO = '0'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
Remove-Item Env:APPLICATIONINSIGHTS_CONNECTION_STRING -ErrorAction SilentlyContinue
& 'C:/Users/Avish/AppData/Local/Temp/vmi-quality-baseline-20261022/Scripts/python.exe' -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error --tb=short --basetemp=out/pytest-reference-final
node --test tests/web/*.test.mjs
```

יש להתאים את נתיב Python ולהשתמש ב־basetemp חדש. הרצות מוגבלות הרשאות נתקעו בעבר; ריצה מקומית רגילה עם אותן דרישות עברה. אין להציג הרצה שנעצרה כהצלחה.

הדגמה מקומית: `http://127.0.0.1:17761/tv?room=quality-d1-audit`, offline ללא חימום/telemetry. שרת uvicorn נוכחי: child PID ‏7196; יש לזהות מחדש שורת פקודה לפני עצירה. fixture תחת `out` אינו קוד מוצר. override זמני של viewport מוחזר בסיום הבדיקה.

שלוש תיקיות של אותו מאגר: primary בענף 2D הישן; `vmi-d1-overlay` ב־main; `vmi-d1-trace` בענף 3D. לא למחוק תיקייה/ענף או להחליף ענף בתיקיית כלי אחר ללא אימות בעלות ועבודה. CI, כיסוי אחוזי, הגנות שרת, הרשאות חדר/טלפון, מודל ופריסה נשארים D2 ולא דווחו כ־PASS.
