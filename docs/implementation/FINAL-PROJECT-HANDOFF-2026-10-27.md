# נקודת המשך — Inside the Game, 27.10.2026

זהו דוח מצב אמיתי לקראת עצירה לפי מכסת המשתמש. אין כאן טענה שהמוצר
כולו הושלם. אין לשנות מודל, לקנות שימוש או לצרוך איפוס. המשתמש ביקש
לעצור ב־5% הנותרים בחלון חמש השעות ולשמור מיקום מדויק של כל פער.

## ההכרעות המחייבות

- לשמר בדיוק 2–1: Dumont 37:58, Ferreira 43:34, Marsh 65:08;
  VAR פנדל 37:16 overturned ו־VAR שער 66:38 stands. אין דרישה לשער מבוטל.
- להשתמש במחולל ובתלת־ממד הקיימים. רצפים קצרים וקפיצות מציג מותרים;
  אין מנוע חדש או סימולציה מסחרית של 90 דקות.
- C מניע שלוש תנוחות קהל; A=0.8C+0.2T; שני פסים זהים, מומנטום נפרד,
  סמל יחיד, בלי xG ב־TV או חשיפת עתיד. מידע חסר אינו שקט.
- ASTRA gpt-6-astra Medium לחזות; Sol gpt-6.1-sol High להיגיון/סקירה.
  שלושת הסוכנים הקיימים סיימו/ממתינים. אין שני עורכים באותם קבצים.
- ענף/PR ממוקד → כל הבדיקות והכיסוי → סקירה ותיקון → squash מוגן → B4.
  אישור ידני שגרתי אינו נדרש; אין עקיפת הגנות או PASS מומצא.

## מה הושלם ומיקומו

| רכיב | מצב וראיה | מיקום |
| --- | --- | --- |
| תיקוני תזמון AI, PR #37 | DONE: מוזג ל־main ffd8cd055fce845951aa855e30b8461f217ec0a7; ארבעת שערי B4 עברו בריצה 40533145069: 522 Python ב־816.23s, כיסוי 94.91% שורות/90.74% ענפים; smoke של 3 בדיקות ב־3.51s | Visual-Match-Intelligence, ענף main; DEMO-AI-TIMING.md |
| מקור פיזיקלי ותרחיש מקורי, PR #32 | commit 9c15bb7; HEAD שנדחף f565949b04d901eee8ad4549be0b69b0e6151554, מסונכרן ל־main. 202 בדיקות מושפעות אחרי הסנכרון עברו ב־247.41s; 51 Node ו־Ruff/diff עברו. CI מלא 40534937315 עדיין בביצוע | vmi-d1-motion-source; codex/fix-d1-physical-motion; D1-PHYSICAL-MOTION.md |
| טעינה שאינה חוסמת חדרים, PR #38 | commit ו־push b11bd09f8da4389291e11ee8dd088e079d0551be. 42 בדיקות loader/session/API עברו ב־66.98s; 17 בדיקות loader סופיות ב־1.94s; 51 Node ו־Ruff/diff עברו. CI מלא 40537802507 עדיין בביצוע | vmi-session-review; codex/fix-demo-cold-loading; DEMO-COLD-LOADING.md |
| תלת־ממד, PR #12 | HEAD קודם 20d1cd5, גרסה 3.25; CI קודם עבר 522 Python/176 Node, כיסוי 94.94%/90.85%. אין קבלה של מקור 2.5 או תנועה חדשה | vmi-d1-trace; codex/d1-match-3d |

כל הנתיבים יחסיים ל־C:/Microsoft - PL/Visual Match Intelligence.
PRs: https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/12,
https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/32,
https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/37,
https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/38.

## מה נשאר — לפי סדר ביצוע

1. **לסגור PR #32.** לקרוא CI 40534937315, לתקן כל כשל/כיסוי בלי להחליש
   בדיקה; לבדוק HEAD/base/דיונים, למזג squash בהתאמה ל־SHA ולהריץ B4 מלא
   על main. לא למזג PR #38 קודם באופן שמבטל את תקפות בסיס המקור.
2. **לחבר את צרכן התלת־ממד ב־PR #12 רק אחרי מקור main+B4.** להשתמש
   ב־motion.facing/gait_cycles וב־contact foot/hands/head; גובה היעד הוא
   clearance+.16 במרכז הכדור. לבדוק מגע במשטח הריג האמיתי אחרי skinning,
   בלי להזיז שורש/כדור או להשתמש בהגדלה החזותית כדי להעביר בדיקה.
   קבצים: match-motion.mjs, scene-state.mjs, athlete.mjs,
   football-gait.mjs, match-3d.mjs תחת web. לא לנחש contact חסר במקור החדש.
3. **לסגור PR #38.** לסנכרן מול המקור הממוזג, לשמר get_match של Seed 2
   המפורש וברירת 1x, ולבדוק מחדש על HEAD המשולב. worker יחיד, 4 עבודות,
   cache של 8; ביטול waiter אינו מבטל עבודה משותפת. guards מונעים טעינה
   ישנה מלדרוס seek/new_match/expiry. שערים ומיזוג/B4 כמו בכל PR.
4. **קבלה בתנועה:** פתיחה/מסירה/נשיאה, פנדל, שני שערי נגיחה,
   עבירה־צהוב, נבדל ומומנטום. לבדוק גם הצלה/קרן מתרחיש מקור רגיל,
   pause/resume/seek/reset/reconnect, החלפת משחק וגיבוי WebGL.
   בקהל לבדוק שקט, עלייה/ירידה, שקט בזמן התקפה, עוצמה בזמן עצירה,
   מידע חסר ו־reduced motion. ASTRA מצא שהידיים מורגשות אך ההבחנה בין
   ישיבה מורמת לעמידה עוד דורשת רצף בזווית כמעט קבועה.
5. **אינטגרציה מלאה:** TV וטלפון באותו חדר, השיחה המאוחדת Kai/Ada,
   snapshots ו־run_id, גיבוי מסומן, הרשאות host ושמירת מצב לאחר reconnect.
   אישור מודל Foundry קיים היסטורית; לא בוצעה כאן קריאה חיה חדשה.
   health=foundry מוכיח תצורה, לא הצלחת קריאת מודל.
6. **ביצועים ועמידות:** מדידת מוצר חדש של לפחות 30FPS בחלון תקף,
   זמני פריימים, סנכרון, כמה חדרים ו־soak של 30 דקות. המשתמש מדד בעבר
   55.66FPS אך דחה את הגרפיקה; זו אינה קבלה לשינוי חדש. אוטומציית
   הדפדפן הוגבלה גם בבקרות ל־1FPS: לא להסיק מוצר 1FPS ולא להוריד איכות
   כדי לתקן את סביבת המדידה. אין לבקש שוב את אותה מדידה הישנה.
7. **פריסה והגשה:** המשתמש פתח Vercel וישלח כתובת. כתובת/פריסה/הרשאות
   טרם אומתו; אין לבצע חיוב או להדפיס סודות. לבדוק חדר משותף בין
   חיבורים, lifecycle/reconnect והרשאת Foundry בסביבת האירוח בפועל.
   קישור ציבורי, מחשב נוסף, חומרי ההגשה והווידאו הקצר עדיין אינם מאומתים.

## הראיות המקומיות החשובות

ב־vmi-d1-motion-source/out:
physical-demo-original-world.pkl, physical-demo-original-replay.pkl,
physical-demo-original-receipt.json, physical-demo-root-tracker-review.json,
merged-source-focused.xml. העולם נבנה ב־0.260s; 4,414 רשומות אומתו;
12,775 פלטי Replay עברו את בדיקת קישורי הצ׳אט המקורית. root בדק 3,566
דגימות ב־20Hz בשישה חלונות. אלה ראיות מקור, לא rig/FPS/קבלה חזותית.
אין להחליף אותן בעולם האבחון ההיסטורי 1–1.

ב־vmi-session-review/out: loading-focused.xml, loading-focused-coverage.json,
ci-pr37-7579a50.log. ב־Visual-Match-Intelligence/out: ci-main-ffd8cd0.log.
ב־vmi-d1-trace/out/visual-reference-review: תמונות מוצר 3.25/מקור 2.4,
דפי החזון ומדידת LIVE הישנה. הקבצים ב־out אינם מחויבים ל־Git.
חזון: docs/context/product-doc-2026-10-21.pdf; תוכנית:
docs/implementation/VMI-FINAL-PLAN-F.md.

## בדיקות והמשך בטוח

Python: C:/Users/Avish/AppData/Local/Temp/vmi-quality-baseline-20261022/Scripts/python.exe.
VMI_OFFLINE=1, VMI_WARM_DEMO=0, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1;
ללא APPLICATIONINSIGHTS_CONNECTION_STRING. pytest tests -q -ra
--strict-markers --strict-config -p no:cacheprovider -W error.
Node: node --test tests/web/*.test.mjs. כיסוי מלא: לפי workflow ci.yml
ו־tools.coverage_gate, לא לפי דוח server ממוקד.

שרת 17761 האחרון הידוע מפעיל מקור 2.4 מתוך trace, ולא את הדמו החדש.
לפני שינוי יש לאמת PID ושורת פקודה מדויקים; אין להרוג את כל תהליכי Python.
Chrome שנבחר לבקרה הוא browser 3; הטאב הזמני האחרון הוסר. טאב שנעלם
אינו הוכחה שחיבור התוסף נכשל. אין לולאת פתיחה/רענון/מדידת FPS כושלת.

העבודה שנותרה משמעותית: מקור וצרכן עדיין אינם משולבים ומאושרים
חזותית, והפריסה והקבלה המלאה פתוחות. אין לסמן D1-04 או הפרויקט DONE.
הערכת מאמץ מתעדכנת אחרי הקבלה בתנועה; CI מוסיף זמני המתנה ואינו
מחליף את העבודה החזותית. לא מובטחת השלמה ללא תיקונים נוספים.
