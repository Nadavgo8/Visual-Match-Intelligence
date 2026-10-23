# VMI — העברה: מסלול מפתח 2

המשתמש הוא מפתח 2 ואישר את משימות D2 לפי התוכנית והנוהל: מימוש, בדיקות, סקירה, תיקונים, commits מפורטים, push, PR ומיזוג אוטומטי בסשן אחרי השערים. אין אישור אנושי פיקטיבי, אין עקיפת שרת ואין תשלום. הכרעת D2-00 דורשת את שני המפתחים. כלי: Claude Code (Claude Opus 5.5), שהוא גם הכותב וגם הסוקר; אין זו ביקורת עצמאית.

## סביבה (מחשב מפתח 2)

- Python 3.12.9 ב־`.venv` (מחוץ ל־Git), מותקן מ־`requirements-dev.txt` ללא prerelease flag; Node 24.3.0.
- בדיקות: `VMI_OFFLINE=1`, `VMI_WARM_DEMO=0`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `PYTEST_DEBUG_TEMPROOT=out/pytest-d2`, ואז `python -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error` ו־`node --test tests/web/*.test.mjs`.
- baseline על main ‏56732ff: ‏183 Python עברו ב־244s, ‏12 Node עברו.
- **חסם:** כ־0.3GB פנויים ב־C:. מונע Ollama ומודל מקומי (D2-00) ומגביל התקנות נוספות.
- **חסם:** `gh` לא מותקן ואין הזדהות GitHub לכלי. אפשר push של ענפים; פתיחת PR ומיזוג דרך PR חסומים עד `gh auth login` של המשתמש. חילוץ אסימון ממנהל ההרשאות נחסם ולא נעקף.

## D2-00 — `codex/d2-model-feasibility`

- נבנו: `vmi/agents/providers.py`, `vmi/evaluation/` (סט 30 שאלות, runner, ציון, גיליון ביקורת), `prompts/model_eval.md`, `tests/test_model_layer.py`, `tests/test_model_eval.py`, [11-MODEL-DECISION](11-MODEL-DECISION.md).
- בדיקות: 25 חדשות; timeout בבדיקה הראשונה נכשל באמת (timeout 0 לא התחיל ניסיון) ותוקן ל־10ms. חבילה מלאה על HEAD: ‏208 Python עברו ב־101s, ‏12 Node עברו, `diff --check` נקי.
- mutations (עותק זמני, שוחזר): הסרת `check_zero_cost` — 2 בדיקות נכשלו; סימון fallback כ־`live` — 3 נכשלו.
- סקירה: אין P0–P2. P3 נדחו: ייבוא פונקציות פרטיות מ־explainer; ערך `atmosphere` במאגר החוקים עדיין מזכיר "mood label" (שייך ל־D2-05).
- הכרעה: PENDING. נדרש: מקום בדיסק או מחשב אחר ל־Ollama, בירור זכאות Azure for Students, הרצת הסט פעמיים וביקורת שני המפתחים.

## הצעד הבא

D2-01 מ־main מעודכן (הקמה, נעילת תלויות, markers, כיסוי, CI, בדיקות JS). D2-02 עד D2-04 ממתינות לחוזים של D2-01.
