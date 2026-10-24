# VMI — הקמה, בדיקות ו־CI

עודכן: 23.10.2026 (D2-01). הנחיות משותפות לשני המפתחים ולכל כלי בינה. נוהל השערים המלא: [12-QUALITY-AND-GIT-GATES](12-QUALITY-AND-GIT-GATES.md). הנחיות ייעודיות לכלי נמצאות ב־`AGENTS.md` (Codex) וב־`CLAUDE.md` (Claude Code), ושתיהן מפנות לכאן.

## התקנה נקייה

Python 3.12 בסביבה מבודדת, מהקובץ הנעול. אין צורך ב־flag של prerelease: הגרסאות המדויקות בקובץ כוללות את חבילת ה־beta שנבדקה.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-lock.txt
copy .env.example .env   # אופציונלי; אין בו סודות
```

`requirements.txt` ו־`requirements-dev.txt` נשארים טווחי גרסאות לעדכון. אחרי שינוי בהם: מתקינים בסביבה נקייה, מריצים את כל הבדיקות, ומחליפים את `requirements-lock.txt` בפלט `pip freeze --exclude-editable`, עם ה־marker של `pywin32`. בדיקת `tests/test_ci_config.py` מוודאת שכל שורה נעולה ושכלי הבדיקה בקובץ.

## בדיקות מקומיות

```powershell
$env:VMI_OFFLINE = '1'; $env:VMI_WARM_DEMO = '0'; $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -m pytest tests -q -ra --strict-markers --strict-config -p no:cacheprovider -W error
python -m pytest tests -m unit -q -p no:cacheprovider        # או contract / integration
node --test tests/web/*.test.mjs
python -m ruff check vmi tests tools
```

שכבות: כל קובץ בדיקה משויך לשכבה אחת ב־`tests/conftest.py`. קובץ חדש בלי שכבה מכשיל את האיסוף, כך ש־`-m` לא ידלג עליו בשקט.

כיסוי ושער כיסוי (איטי: מדידת ענפים על משחק מלא):

```powershell
python -m pytest tests -q -p no:cacheprovider -p pytest_cov --cov --cov-branch --cov-report=json:out/coverage.json
python -m tools.coverage_gate --coverage out/coverage.json --base origin/main
```

השער בודק בנפרד: כלל `vmi/` לא יורד מ־`coverage-baseline.json`; שורות וענפים שהשתנו לפחות 90%/85%; בקבצים קריטיים 95%/90%. מידע חסר מכשיל. `--update-baseline` רק מעלה.

## חוזי נתונים

`contracts/v2/event.schema.json` ו־`stream.schema.json` מתעדים את חוזה v2 שמוזג ב־D1-01/02 (JSON Schema 2020-12), עם `examples.json`. `tests/test_schemas.py` בודק שכל רשומה של משחק הדמו ושל כל תרחיש תואמת, ושכל דוגמה פסולה נדחית בדיוק במקום המתועד: בסכמה, ב־`vmi/contracts.py` או בשניהם. כללים בין שדות (מסירה לפני התרחשות, קישור לעצמו, סדר הגעה) נאכפים רק בקוד. שינוי חוזה מעדכן סכמה, דוגמאות, מפיק וצרכן באותו PR ודורש את שני המפתחים.

## CI

`.github/workflows/ci.yml` רץ על כל PR ל־`main` ועל כל push ל־`main`, ללא סינון נתיבים. ארבע בדיקות: `python-tests` (חבילה מלאה, כיסוי, JUnit ו־artifact), `coverage-gate`, `web-tests`, `static-checks` (ruff וגם `diff --check`). ה־actions נעולים ל־SHA מלא; ההרשאות לקריאה בלבד.

**מצב אכיפה: לא מאומת.** הריפו פרטי, ולכן Actions צורך מהמכסה החינמית של החשבון. הוא נשאר חינמי רק אם תקציב Actions הוא $0 (ברירת המחדל). הגנת `main`, required checks ובדיקת "CI כושל חוסם מיזוג" דורשות הרשאת admin דרך `gh`, ועדיין לא הוגדרו.

## Git

לפי סעיף 7 בנוהל: ענף ו־PR לכל משימה מ־`main` מעודכן, ‏squash merge אחרי השערים, בלי push ישיר ל־`main` ובלי force push. כל כלי שעורך במקביל עובד בתיקייה או worktree משלו.
