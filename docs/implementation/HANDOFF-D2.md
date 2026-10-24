# VMI — העברה: מסלול מפתח 2

המשתמש הוא מפתח 2 ואישר את משימות D2 לפי התוכנית והנוהל: מימוש, בדיקות, סקירה, תיקונים, commits מפורטים, push, PR ומיזוג אוטומטי בסשן אחרי השערים. אין אישור אנושי פיקטיבי, אין עקיפת שרת ואין תשלום. הכרעת D2-00 דורשת את שני המפתחים. כלי: Claude Code (Claude Opus 5.5), שהוא גם הכותב וגם הסוקר; אין זו ביקורת עצמאית.

## סביבה וחסמים

- Python 3.12.9 ב־`app/.venv`; Node 24.3.0. D2-02 ב־worktree `../app-d2-02`.
- `gh` מותקן ומחובר (Nadavgo8). מקום בדיסק עדיין מעט (כ־4GB) — מספיק לעבודה, לא ל־Ollama + מודל בנוחות.

## D2-01 — `codex/d2-platform-contracts`

- נבנו: `requirements-lock.txt` (pip freeze של סביבה שנבדקה, `pywin32` עם marker), `pyproject.toml` (markers, coverage branch, ruff ברמת שגיאות), שיוך כל קובץ בדיקה לשכבה ב־`tests/conftest.py` (קובץ לא משויך מכשיל איסוף), `tools/coverage_gate.py` + `coverage-baseline.json`, `contracts/v2/*.schema.json` + `examples.json`, `.github/workflows/ci.yml` (ארבעה jobs, SHA נעולים, הרשאות קריאה), `.env.example`, [02-SETUP-AND-GIT](02-SETUP-AND-GIT.md), יישור `docs/spec.md` §7 לחוזה שמוזג (tracking כולל `possession.holder_id`).
- בדיקות: 4 קבצים חדשים (שער כיסוי, CI, שכבות, סכמות). חבילה מלאה עם כיסוי: ‏249 עברו, exit 0 (משך 2:46 שעות כולל שינה של המחשב; ללא כיסוי החבילה נמשכת כ־2–4 דקות). ‏12 Node עברו; ruff נקי; `diff --check` נקי.
- mutations: גבול `<`→`<=` בשער — 2 נכשלו; התעלמות מקובץ שהשתנה בלי נתונים — 1 נכשל.
- השפעה על מפתח 1: כל קובץ בדיקה חדש צריך שורה ב־`LAYERS` שב־`tests/conftest.py`.
- לא אומת: התקנה נקייה מהקובץ הנעול (אין מקום בדיסק לסביבה שנייה; ה־CI יבדוק על Linux), ריצת CI, required checks והגנת `main`.

- **מוזג:** PR #13 ל־9918ede. CI ראשון ירוק (התקנה נקייה מהקובץ הנעול על Linux אומתה), כיסוי ב־CI ‏90.32%/83.71%. הגנת `main` הופעלה (ארבעה required checks, strict, enforce_admins, בלי force push/מחיקה). PR #14 עם assertion כושל: python-tests נכשל, GitHub סימן BLOCKED, לא נעשה ניסיון מיזוג; נסגר והענף נמחק.

## D2-02 — `codex/d2-realtime-session`

- נבנו: run_id/seq, snapshot, מארח עם טוקן, outbox ו־writer לכל לקוח, ביטול עבודה ישנה, `answer_discarded`, ניקוי חדרים (120s) ותקרה (64), אימות פקודות מארח פגומות, `web/session.mjs` (gate, backoff, טוקן), חיבור `tv.js`/`app.js`, הודעת ניתוק באפליקציה. [החוזה](D2-02-SESSION.md).
- בדיקות: `tests/test_realtime_session.py` ‏(17), עדכון `tests/test_api.py` (הטלפון כבר לא מבצע seek — דרישת התוכנית "בקרת ניגון למארח בלבד"), `tests/web/session.test.mjs` ‏(6).
- ממצא בדרך: TestClient בלי `with` מריץ כל חיבור בלולאת אירועים נפרדת, ולכן בדיקת seek נתקעה; תוקן בבדיקות ע״י portal משותף. ממצא P2 בסקירה: פקודת seek/new_match פגומה הפילה את חיבור המארח; נוספו אימות ובדיקת רגרסיה שנכשלה לפני ועוברת אחרי.
- mutations: הסרת בדיקת המארח — 1 נכשלה; הסרת בדיקת run בתשובות — 1 נכשלה.
- smoke מול uvicorn אמיתי (פורט 17781): מסך מארח עם טוקן, טלפון לא מארח, `play` מהטלפון נדחה, seq עולה ב־1, seek יוצר snapshot ‏r2 עם פיד.
- לא נבדק: דפדפן אמיתי לשני המסכים (אין כלי דפדפן בסשן); reconnect אמיתי של רשת.

## D2-00 — `codex/d2-model-feasibility`

- נבנו: `vmi/agents/providers.py`, `vmi/evaluation/` (סט 30 שאלות, runner, ציון, גיליון ביקורת), `prompts/model_eval.md`, `tests/test_model_layer.py`, `tests/test_model_eval.py`, [11-MODEL-DECISION](11-MODEL-DECISION.md).
- בדיקות: 25 חדשות; timeout בבדיקה הראשונה נכשל באמת (timeout 0 לא התחיל ניסיון) ותוקן ל־10ms. חבילה מלאה על HEAD: ‏208 Python עברו ב־101s, ‏12 Node עברו, `diff --check` נקי.
- mutations (עותק זמני, שוחזר): הסרת `check_zero_cost` — 2 בדיקות נכשלו; סימון fallback כ־`live` — 3 נכשלו.
- סקירה: אין P0–P2. P3 נדחו: ייבוא פונקציות פרטיות מ־explainer; ערך `atmosphere` במאגר החוקים עדיין מזכיר "mood label" (שייך ל־D2-05).
- הכרעה: PENDING. נדרש: מקום בדיסק או מחשב אחר ל־Ollama, בירור זכאות Azure for Students, הרצת הסט פעמיים וביקורת שני המפתחים.
- PR [#16](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/16) ממזג רק את הכלים; ההכרעה נשארת חסומה.

## D2-03 — `codex/d2-companion-app`

- נבנו: `web/companion.mjs` (`normaliseProfile` + `DEFAULT_PROFILE`, `FeedStore.upsert` שמחזיר update לפריט קיים, `AnswerLog` שמציג תשובה פעם אחת לכל שאלה, `itemLabel`), חיבור ב־`web/app.js`: פריט שהועשר (xG) מוחלף במקומו בלי הדגשה ובלי שינוי מיקום; תווית Fact לפריטי פיד ו־Analysis · interpretation לכרטיסים; מקורות (מזהי אירועים) נפתחים בלחיצה; כפתור "Skip, use defaults"; Ask בזמן ניתוק מודיע שלא נשלח; פרופיל ישן מאחסון מנורמל.
- בדיקות: `tests/web/companion.test.mjs` ‏(6), כולל בדיקה שאין Notification/vibrate/Audio/service worker ב־`app.js`.
- ממצא בדרך: `.mjs` הוגש כ־text/plain במחשב הזה, והדפדפן לא היה מריץ את המודולים. תוקן בנפרד ב־[PR #17](https://github.com/Nadavgo8/Visual-Match-Intelligence/pull/17) עם בדיקת רגרסיה.
- לא נבדק: דפדפן אמיתי בטלפון (אין כלי דפדפן בסשן); נבדקו תחביר המודולים, בדיקות Node והגשת הדפים.

## D2-04 — `codex/d2-catch-up`

- נבנו: `vmi/api/catchup.py` (חלון, בחירה דטרמיניסטית, שעון לגבולות, טקסט), `Replay` מסמן כל פלט ב־`at` (זמן מסירה; שינוי תוספתי בקובץ של מפתח 1, מוסבר ב־PR), `delivered` בפריטי פיד ובהודעות, פקודת `catch_up`, כפתור ופאנל באפליקציה, `CatchUpCheckpoints`.
- בדיקות: `tests/test_catch_up.py` ‏(13, unit), שתי בדיקות שרת ב־`test_realtime_session.py`, שתי בדיקות Node. חבילה מלאה: 326 Python, ‏29 Node.
- ממצא בבדיקות: פריטי בדיקה בלי `kind` הפילו את `visible_to`; תוקן בנתוני הבדיקה (בפיד אמיתי תמיד יש `kind`).
- mutations: גבול חלון כולל — 1 נכשלה; בחירה לפי `t` במקום מסירה — 1 נכשלה.

## D2-05 — `codex/d2-commentary-agents` (שלד, בלי מודל)

- נבנו: `Assistant.answer` עונה מול עותק של מודל המשחק שהוקפא ברגע השאלה (deepcopy, כ־31ms במשחק מלא); נתיב הסוכנים חסום ב־20 שניות כולל (`TOTAL_TIMEOUT_S`) עם גיבוי מקומי מסומן; כל תשובה מסומנת `answer_kind` (live / template) ו־`snapshot_clock`; תשובת "מי לוחץ" מתחילה ב־"Interpretation:" ומפרידה "Facts:"; הסבר אוטומטי שהושלם כשהכדור כבר במשחק מוחזק (`held`) ומפורסם בעצירה הבאה, רק לאותה הרצה; ערך `atmosphere` במאגר החוקים מתאר את פסי 80/20 במקום "mood".
- בדיקות: `tests/test_commentary_agents.py` ‏(10): snapshot מול משחק שממשיך, timeout, תוויות, שני ניסיונות prompt injection לחשיפת עתיד, תקציב שש קריאות כלים, ערך החוקים, החזקה עד עצירה, ומניעת פרסום מוחזק מהרצה ישנה.
- ממצא בדרך: `_text_cache` של השרת משותף לכל הבדיקות; בדיקה חדשה הכשילה בדיקת D2-02 שהשתמשה באותו רגע. נוסף fixture שמבודד את המטמון.
- mutations: מענה מהמודל החי במקום העותק — 1 נכשלה; פרסום בזמן משחק — 2 נכשלו.
- לא נעשה: אנליסט משמעות וכותב כסוכני מודל, ובדיקת groundedness מול מודל אמיתי — תלויים בהכרעת D2-00.
