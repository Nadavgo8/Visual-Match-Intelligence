# D2-00 — הכרעת מודל, דרך הפעלה וגישה לשופטים

עודכן: 23.10.2026. **מצב: פתוח. לא נבחר מודל ולא ספק.** ההכרעה דורשת את שני המפתחים (תוכנית §7, נוהל §5). מסמך זה מרכז את הבירור, את כלי הבדיקה ואת מה שחסר כדי להכריע.

## מה נבנה ב־PR הזה

- `vmi/agents/providers.py` — שכבת חיבור ניטרלית לספק: בקשה עם snapshot קפוא, פרופיל ומגבלת זמן (עד 20 שניות כולל); ניסיון יחיד; timeout, מיצוי מכסה או שגיאה מחזירים תבנית שמסומנת `template`, בלי retry ובלי ספק חלופי. ספק שלא הצהיר `may_charge = False` נדחה לפני קריאה. **לא מחוברת לאפליקציה** עד ההכרעה.
- `vmi/evaluation/question_set.py` — סט 30 השאלות המשותף על seed 12: 10 עובדות, 5 פרשנות, 5 חוקים, 5 תקצירים, 5 מלכודות (עתיד, מניע קהל, הנחה שגויה). כל שאלה נשאלת בנקודת זמן; חבילת העובדות נבנית מ־replay של מה שנמסר עד אותה נקודה בלבד.

עדכון תאימות 25.10: הקלט המתויג ל־30 השאלות מוקפא מעתה ב־
`vmi/evaluation/fixtures/demo-v2.2.json.gz`, עם מקור וחתימה ב־README הסמוך.
זהו seed 12 בגרסת מחולל 2.2, שעליו נכתבו השאלות. הדמו הרגיל משתמש במחולל
העדכני; שינוי גרסתו אינו משנה בשקט את התשובות הצפויות בהערכת המודל.
אין בכך בחירת ספק או אישור תוצאה של מודל. החלפת סט ההערכה דורשת תיוג מחדש.
- `vmi/evaluation/model_eval.py` — הרצת הסט על מועמד, מדידת זמן ראשון/חם, דגלים אוטומטיים (מספר או שם שאינם ב־snapshot, תוצאה או שחקן עתידיים, מניע קהל) וגיליון ביקורת `review.csv` עם עמודות ריקות לשני המפתחים. הכלי **אינו** מכריז PASS.
- `prompts/model_eval.md` — הנחיית המועמד: רק עובדות מה־snapshot, בלי חיזוי, בלי מניע קהל, תיקון הנחה שגויה, תווית Interpretation, תשובת JSON עם ראיות.

```powershell
$env:VMI_OFFLINE = '1'; $env:VMI_WARM_DEMO = '0'
python -m vmi.evaluation.model_eval --provider template --runs 2              # baseline, אינו נספר כתשובות מודל
python -m vmi.evaluation.model_eval --provider local --model phi4-mini --runs 2  # Ollama מקומי, אחרי התקנה
```

הפלט נכתב תחת `out/model-eval/<model>/` (מחוץ ל־Git).

## החומרה שנבדקה (מחשב מפתח 2)

| פריט | ערך |
|---|---|
| מעבד | Intel Core i7-10510U, ‏4 ליבות / 8 threads (מחשב נייד, U-series) |
| זיכרון | 11.8GB; בזמן הבדיקה כ־0.8GB פנויים |
| GPU | Intel UHD בלבד; אין GPU ייעודי |
| דיסק | כ־0.3GB פנויים ב־C: אחרי התקנת סביבת Python |
| מערכת | Windows 11 Home 10.0.26200 |
| Ollama | לא מותקן |

**הערכה שלי, לא מדידה:** מודל 3.8B ב־4-bit על CPU כזה צפוי להיות איטי, וייתכן שלא יעמוד ב־95% תשובות תוך 20 שניות כשחבילת עובדות ארוכה. רק הרצת הסט תכריע.

## האפשרויות — מה אומת (23.10.2026)

| חלופה | מה אומת במקור רשמי | מה לא ידוע / חוסם | מצב |
|---|---|---|---|
| **Phi-4-mini דרך Ollama + Agent Framework** | רישיון MIT; ‏3.8B פרמטרים; הקשר 128K; תמיכה ב־function calling ([כרטיס המודל](https://huggingface.co/microsoft/Phi-4-mini-instruct)). ב־Ollama ‏`phi4-mini` שוקל 2.5GB ומסומן tools ([Ollama](https://ollama.com/library/phi4-mini)). Agent Framework תומך ב־Ollama דרך `agent-framework-ollama` (prerelease) או `OpenAIChatClient` מול `http://localhost:11434/v1/` ([Microsoft Learn, 15.10.2026](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/model-providers/ollama)) | **אין מקום בדיסק** (נדרשים כ־2.5GB למודל + Ollama). ביצועים על המחשב לא נמדדו. גישה לשופטים: קישור ציבורי ממחשב ביתי לא מעשי; test build מחייב את השופט להתקין Ollama ומודל | מועמד ראשון לבדיקה; חסום בדיסק |
| **Copilot SDK עם Copilot Free** | ה־SDK זמין לכל מנויי Copilot, "including Copilot Free for personal use" ([GitHub changelog](https://github.blog/changelog/2026-06-02-copilot-sdk-is-now-generally-available/)). ב־Free "Limited chat and agent usage" ואין Flex/חריגה בתשלום ([מסלולים](https://github.com/features/copilot/plans)). בשירות מרובה משתמשים ההנחיה היא אסימון לכל משתמש: "Avoid sharing one service token across users" ([multi-tenancy](https://github.com/github/copilot-sdk/blob/main/docs/setup/multi-tenancy.md)) | Free מוגדר לשימוש אישי; הפעלת שירות לשופטים עם אסימון אישי אחד סותרת את ההנחיה. מכסה מדויקת לא פורסמה | מתאים לניסוי אישי בלבד; לא לדמו משותף בלי אישור תנאים |
| **Foundry / Azure** | Azure for Students: "No credit card required", ‏$100 ל־12 חודשים; בסוף מוצעת העברה ל־pay-as-you-go, ובלי בחירה המנוי מושבת ([Azure for Students](https://azure.microsoft.com/en-us/free/students)) | זכאות: סטודנטים במשרה מלאה עם מייל מוסדי — לא ידוע אם מי מכם זכאי. מכסת מודלים ב־Foundry במנוי כזה לא נבדקה. משאבים נלווים (registry, ניטור) צריכים בדיקת עלות נפרדת | הדרך היחידה שנמצאה ל־Azure ללא כרטיס; תלוי בזכאות |
| **ספק חינמי אחר** | לא נבדק | — | רק אם הראשונים נכשלים |
| **תבניות** | baseline רץ: 30/30 תשובות `template`, 0 תשובות מודל | אינן צ׳אט גנרטיבי | גיבוי בלבד |

GitHub Models: "As of July 30, 2026, GitHub Models has been fully retired" ([GitHub Docs](https://docs.github.com/en/github-models), נבדק 23.10.2026). אינו מועמד.

**תקנון (נבדק 23.10.2026):** §4.8 מקבל "a link to a website, functioning demo, or a test build", זמין עד סוף השיפוט (10.11.2026, 23:59 PT) ו־"free of charge and without any restriction". המונח "required technologies" אינו מוגדר; §6.2 מונה hero technologies (Foundry, Agent Framework, Azure MCP, Copilot Agent Mode) בלי לחייב אותן ([תקנון](https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md)).

## תוצאות עד עכשיו

| בדיקה | מצב |
|---|---|
| baseline תבניות, 30 שאלות × 1 | רץ: 30 fallback, ‏0 תשובות מודל; פסק `BASELINE_ONLY` |
| Phi-4-mini מקומי, 30 × 2 | NOT_RUN — אין מקום בדיסק ו־Ollama לא מותקן |
| Copilot SDK | NOT_RUN — שימוש אישי בלבד; לא הוגדר חשבון |
| Foundry | NOT_RUN — זכאות ל־Azure for Students לא ידועה |
| ביקורת שני המפתחים על `review.csv` | PENDING |
| בדיקת עומס: AI במקביל למשחק | NOT_RUN — תלויה במועמד |

## מה נדרש כדי להכריע

1. **מקום בדיסק** במחשב מפתח 2 (לפחות 4GB פנויים) או מחשב אחר להרצת Ollama.
2. **זכאות Azure for Students** — האם אחד מכם סטודנט במשרה מלאה עם מייל מוסדי.
3. הרצת הסט פעמיים על מועמד אחד לפחות, וביקורת `review.csv` של שני המפתחים.
4. הכרעה משותפת שנרשמת כאן: מודל מדויק, דרך הפעלה, גישה לשופטים, מגבלות, מדיניות גיבוי וחלופה שנפסלה.

## ההכרעה

| שדה | ערך |
|---|---|
| מודל וגרסה | PENDING |
| דרך הפעלה | PENDING |
| גישה לשופטים | PENDING |
| חלופה שנפסלה ולמה | PENDING |
| אישור מפתח 1 / מפתח 2 | PENDING / PENDING |
