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
- בדיקות: `tests/test_realtime_session.py` ‏(12), עדכון `tests/test_api.py` (הטלפון כבר לא מבצע seek — דרישת התוכנית "בקרת ניגון למארח בלבד"), `tests/web/session.test.mjs` ‏(6).
- ממצא בדרך: TestClient בלי `with` מריץ כל חיבור בלולאת אירועים נפרדת, ולכן בדיקת seek נתקעה; תוקן בבדיקות ע״י portal משותף. ממצא P2 בסקירה: פקודת seek/new_match פגומה הפילה את חיבור המארח; נוספו אימות ובדיקת רגרסיה שנכשלה לפני ועוברת אחרי.
- mutations: הסרת בדיקת המארח — 1 נכשלה; הסרת בדיקת run בתשובות — 1 נכשלה.
- smoke מול uvicorn אמיתי (פורט 17781): מסך מארח עם טוקן, טלפון לא מארח, `play` מהטלפון נדחה, seq עולה ב־1, seek יוצר snapshot ‏r2 עם פיד.
- לא נבדק: דפדפן אמיתי לשני המסכים (אין כלי דפדפן בסשן); reconnect אמיתי של רשת.
