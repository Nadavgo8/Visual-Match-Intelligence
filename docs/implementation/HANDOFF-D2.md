# VMI — העברה: מסלול מפתח 2

המשתמש הוא מפתח 2 ואישר את משימות D2 לפי התוכנית והנוהל: מימוש, בדיקות, סקירה, תיקונים, commits מפורטים, push, PR ומיזוג אוטומטי בסשן אחרי השערים. אין אישור אנושי פיקטיבי, אין עקיפת שרת ואין תשלום. הכרעת D2-00 דורשת את שני המפתחים. כלי: Claude Code (Claude Opus 5.5), שהוא גם הכותב וגם הסוקר; אין זו ביקורת עצמאית.

## סביבה (מחשב מפתח 2)

- Python 3.12.9 ב־`.venv` (מחוץ ל־Git); Node 24.3.0. בדיקות לפי [02-SETUP-AND-GIT](02-SETUP-AND-GIT.md).
- baseline על main ‏56732ff: ‏183 Python עברו ב־244s, ‏12 Node עברו.
- **חסם:** כ־0.1–0.3GB פנויים ב־C:. מונע Ollama (D2-00) והתקנות נוספות.
- **חסם:** `gh` לא מותקן ואין הזדהות GitHub לכלי. אפשר push של ענפים; פתיחת PR, מיזוג, הרצת CI והגנת `main` חסומים עד `gh auth login` של המשתמש. חילוץ אסימון ממנהל ההרשאות נחסם ולא נעקף.

## D2-01 — `codex/d2-platform-contracts`

- נבנו: `requirements-lock.txt` (pip freeze של סביבה שנבדקה, `pywin32` עם marker), `pyproject.toml` (markers, coverage branch, ruff ברמת שגיאות), שיוך כל קובץ בדיקה לשכבה ב־`tests/conftest.py` (קובץ לא משויך מכשיל איסוף), `tools/coverage_gate.py` + `coverage-baseline.json`, `contracts/v2/*.schema.json` + `examples.json`, `.github/workflows/ci.yml` (ארבעה jobs, SHA נעולים, הרשאות קריאה), `.env.example`, [02-SETUP-AND-GIT](02-SETUP-AND-GIT.md), יישור `docs/spec.md` §7 לחוזה שמוזג (tracking כולל `possession.holder_id`).
- בדיקות: 4 קבצים חדשים (שער כיסוי, CI, שכבות, סכמות). חבילה מלאה עם כיסוי: ‏249 עברו, exit 0 (משך 2:46 שעות כולל שינה של המחשב; ללא כיסוי החבילה נמשכת כ־2–4 דקות). ‏12 Node עברו; ruff נקי; `diff --check` נקי.
- mutations: גבול `<`→`<=` בשער — 2 נכשלו; התעלמות מקובץ שהשתנה בלי נתונים — 1 נכשל.
- השפעה על מפתח 1: כל קובץ בדיקה חדש צריך שורה ב־`LAYERS` שב־`tests/conftest.py`.
- לא אומת: התקנה נקייה מהקובץ הנעול (אין מקום בדיסק לסביבה שנייה; ה־CI יבדוק על Linux), ריצת CI, required checks והגנת `main`.

## D2-00 — `codex/d2-model-feasibility`

ראו את ענף D2-00 ואת [11-MODEL-DECISION](11-MODEL-DECISION.md) לאחר המיזוג. הכרעה: PENDING.

## הצעד הבא

D2-02 (`codex/d2-realtime-session`) נבנה בתיקיית worktree נפרדת `../app-d2-02` מ־main ‏56732ff.
