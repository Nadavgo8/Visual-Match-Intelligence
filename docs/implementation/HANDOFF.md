# VMI — העברה עדכנית: סקירת D1 ו־D1-04

עודכן: 24.10.2026. המשתמש אישר D1-01 עד D1-05, בדיקות מחמירות, סקירת קוד, תיקון ממצאים, commits מפורטים, push, PR ומיזוג squash אוטומטי בסשן אחרי השערים. אין צורך באישור אנושי שגרתי; אין להמציא אישור או סוקר עצמאי. חוזה v2 ומעבר כל המפיקים והצרכנים אושרו. אין תשלום או השתלטות על משימות D2.

## מצב מאומת

| היקף | PR / main | ראיות |
|---|---|---|
| D1-01 | [#4](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/4), ‏3baa62d | 85 בדיקות ו־smoke משחק מלא אחרי מיזוג |
| D1-02 | [#5](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/5), ‏12adc05 | 135 בדיקות ו־20 exports תקינים אחרי מיזוג |
| D1-03 | [#6](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/6), ‏52ad4a5 | 174 Python, ‏3 Node ו־smoke אחרי מיזוג |
| D1-05 | [#8](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/8), ‏56732ff | 183 Python, ‏12 Node ו־smoke אחרי מיזוג; התאמה למסמך ששת העמודים |
| תיקון סדר מסירה ושעון | [#9](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/9), ‏37fe99e36aec37c83ca6879ced543316cf977303 | B4: ‏199 Python ב־130.54s, ‏12 Node וחמישה תרחישי smoke עברו |
| תיקון חלון מומנטום | [#10](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/10), ‏e8eb619ed2c937f2e86a2a41a0d9b5581d98e8a2 | B4: ‏202 Python ב־132.30s, ‏12 Node; אותו ערך ב־meters ובכלי הפרשן |
| טקסט בטוח באזור המציג | [#11](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/11), ‏cbbc511db02b1d0211d3a05a70693aca22b6973d | B4: ‏202 Python ב־126.03s ו־15 Node עברו; ה־DOM מציג טקסט מילולי עם מגבלה של 40 פריטים |

ה־PRs החדשים נפתחו בנפרד מ־main משולב, עם רגרסיות וסקירה מתועדת, ונמזגו ללא עקיפה. [דוח הסקירה החוזרת](D1-AUDIT-2026-10-24.md) מתעד שמונה ממצאים, שחזורים לפני תיקון, תוצאות ולמידה. סקירה היא של אותו Codex שכתב את הקוד, בשלב נפרד; אין אישור אנושי או ביקורת בלתי תלויה מומצאת.

PR #2 הישן היה Draft של בדיקות שחזור. הפיצול לא הועיל כמשימה עצמאית; הוא נסגר כמוחלף והתיקון המלא מוזג ב־#3. אין למזג בדיקה כושלת בנפרד מתיקון המשימה. היסטוריה מפורטת נשמרת ב־PRs וב־Git.

## D1-04 — קוד משולב, שער ביצועים פתוח

[Draft PR #7](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/7), ענף `codex/d1-match-2d`, בתיקיית `Visual-Match-Intelligence`. הוא משלב כעת את main ‏cbbc511 ב־merge רגיל. קונפליקט ה־imports נפתר במפורש כך שנשמרים MatchScreen, ‏MatchRenderer ו־prependTrace הבטוח; מסמך ההעברה משמר את ראיות שני הצדדים ומחליף רישומי ביניים מבלבלים. אין rebase, force push או פתרון גורף לפי צד אחד.

הקוד כולל מגרש מטרי 105×68, תלבושות ומספרים מקוריים, גובה וצל, אינטרפולציה לפי זמן מקור ובאפר מוגבל; MatchScreen מאפס את שכבת המשחק ואת הסמל יחד ב־seek, שינוי משחק/הרצה וקפיצות זמן. הגרפיקה אינה קובעת תוצאה. שני פסי הקצה, הסמל העגול היחיד, ה־HUD והמומנטום נשמרים לפי [מפת העיצוב](D1-05-ACCESSIBILITY.md) וה־PDF. [פירוט D1-04](D1-04-MATCH-2D.md).

לפני commit השילוב הנוכחי עברו 31 בדיקות Node. סקירה מחודשת של D1-04 תפסה בניסויים בזיכרון הסרת הגנת pause והסרת איפוס seek; קובצי המוצר לא שונו בניסויים. הרצה מלאה על HEAD השילוב הסופי נדרשת, ותוצאתה המדויקת תופיע בגוף PR #7. אין להשתמש בתוצאות 184/28 של c478d2e כהוכחה לשילוב החדש.

**החסם:** יעד לפחות 30FPS עדיין NOT_VERIFIED. מסך המשחק מדווח 1FPS, עם כ־0.4–2.2ms ציור; דף מקומי מבודד עם requestAnimationFrame בלבד, בלי קוד VMI, מדד גם הוא 1.0FPS בחלון 5.1 שניות. המשתמש אישר ש־Chrome גלוי בחזית; גם לאחר בחירת טאב המשחק, סגירת דף הבקרה, מיקוד וניגון במהירות 1 המדידה בכלי נשארה 1FPS. הדבר מבודד שעון אנימציה איטי גם בלי המשחק, אך הסיבה המדויקת לא הוכחה ואין מכך PASS לביצועי VMI.

ציוד הבדיקה: Lenovo 81X3, ‏Intel i7-1065G7, ארבע ליבות/שמונה תהליכונים, כ־16GB זיכרון, Chrome מקומי. קריאת viewport: ‏2048×926, canvas ‏1378×775. בדיקות הפריסה הקודמות ב־1920×1080 וב־391×844 עברו. זמן ציור, סימולציה או בדיקות יחידה אינם FPS. לא הוחלף rAF בטיימר ולא הונמך סף.

נשאלה שאלה ממוקדת לקריאת ערך FPS כשהמשחק גלוי ומנגן; אין לשלוח תזכורות שגרתיות. נדרשת מדידה אמיתית, רצוי ללא עומס הבדיקות ברקע. לאחר ראיה תקינה: לתעד ערך, ציוד, viewport, מהירות ו־SHA; לרענן בסיס/HEAD/דיונים/בדיקות, להסיר Draft, לבצע squash רגיל עם match-head-commit ולבדוק main ב־B4. עד אז D1-04 נשאר BLOCKED ואין לסמן את כל מסלול D1 DONE.

## סביבת בדיקה ותיקיות

Python ‏3.12.13 בסביבה הזמנית `C:/Users/Avish/AppData/Local/Temp/vmi-quality-baseline-20261022/Scripts/python.exe`, ‏Node ‏24.15.0. לא נוספו תלויות לפרויקט. דוחות QA ו־fixtures נשארים ב־out המתעלם מ־Git. בעיית הרשאות Temp ישנה נפתרה באמצעות basetemp מפורש חדש בתוך out; לא מדלגים על בדיקות.

```powershell
$env:VMI_OFFLINE = '1'
$env:VMI_WARM_DEMO = '0'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
Remove-Item Env:APPLICATIONINSIGHTS_CONNECTION_STRING -ErrorAction SilentlyContinue
python -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error --tb=short --basetemp=out/pytest-next-unique-run
node --test tests/web/*.test.mjs
```

יש להשתמש ב־Python הזמני המפורש במחשב זה, ולבחור basetemp חדש לכל הרצה. מיפוי תיקיות: `Visual-Match-Intelligence` — D1-04; ‏`vmi-d1-overlay` — main לאימותי B4; ‏`vmi-d1-trace` — ענף תיקון המציג שנדחף. אין לערוך באותה תיקייה במקביל עם כלי נוסף או למחוק ענפים/תיקיות של השותף. הענף המרוחק של D2-01 הופיע במהלך הסשן; הוא לא נערך או מוזג על ידינו.

שרת QA של המסך: `127.0.0.1:17761`, חדר `quality-d1-audit`, offline, ללא חימום/telemetry. אחרי שינויי קוד שרת יש להפעיל מחדש את שרת הבדיקה שלנו. מזהי תהליך יש לאמת מול command line בהווה; אין לעצור תהליך לפי PID היסטורי. שרת הבקרה המבודד נסגר. טאב המשחק נשמר רק לצורך בדיקת הביצועים.

CI, ספי כיסוי אוטומטיים והגנות שרת אינם PASS מאומת; רשימת checks ריקה אינה ירוק. run_id והרשאת טלפון, חיבור מודל, catch-up והפצה נשארים D2. אין טענת השלמת האפליקציה, מחקר משתמשים, שער עומס/soak או הגשה. אין שירות רקע אוטומטי שממשיך לאחר סיום הסשן.
