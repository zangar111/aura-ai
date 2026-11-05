# Видеоға арналған шикі материал

Барлық клип **демо-деректермен** (`demo_data.py`) жасалған: жеке бағалар, құпиясөздер
және нақты Telegram аккаунты кадрға түспейді. Бот хабарламаларының мәтіндері ботыңның
өз функцияларымен генерацияланады (`format_grade_changes`, `render_grade_summary`,
`format_day`, `STATUSES` және т.б.), ал Mini App — нақты `webapp/` коды.

## Файлдар (`out/`)

| Файл | Өлшемі | Ұзақтығы | Сценарийдегі орны |
|---|---|---|---|
| `01_journal.mp4` | 1920×1080 | 18 с | 0:00–0:20 · Мәселе: көп бағанды журнал |
| `02_notify.mp4` | 1080×1920 | 26 с | 0:20–0:50 · Пуш + «🔔 Жаңа бағалар» + ЖИ-шолу |
| `03_ai_chat.mp4` | 1080×1920 | 31 с | 0:50–1:30 · «Ең нашар сабағым қайсы?» → статус → жауап → график |
| `04_schedule.mp4` | 1080×1920 | 40 с | 1:30–2:00 · Таңғы дайджест, `/schedule`, 14 минуттық еске салу, «ертең қандай сабақ бар?» |
| `05a_open_miniapp.mp4` | 1080×1920 | 3 с | 2:00 · «Aura» батырмасын басу |
| `05_miniapp.mp4` | 1080×1920 | 31 с | 2:00–2:30 · Mini App, қараңғы тақырып |
| `05b_miniapp_light.mp4` | 1080×1920 | 31 с | Сол, жарық тақырып (ауысу үшін) |
| `06_pytest.mp4` | 1920×1080 | 10 с | 2:30–2:50 · `86 passed` (нақты нәтиже) |
| `logo.png`, `logo_icon.png` | мөлдір PNG | — | 2:50–3:00 · Финал |

## Қайта жасау

```bash
pip install -r requirements-dev.txt
python video/raw/build_messages.py            # мәтіндер мен график → build/
python video/raw/serve_miniapp.py &           # Mini App демо-сервері :8090
node video/raw/record.js telegram notify   video/raw/out/02_notify.mp4
node video/raw/record.js telegram chat     video/raw/out/03_ai_chat.mp4
node video/raw/record.js telegram schedule video/raw/out/04_schedule.mp4
node video/raw/record.js telegram miniapp  video/raw/out/05a_open_miniapp.mp4
node video/raw/miniapp.js dark  video/raw/out/05_miniapp.mp4
node video/raw/miniapp.js light video/raw/out/05b_miniapp_light.mp4
node video/raw/record.js journal  x video/raw/out/01_journal.mp4
node video/raw/record.js terminal x video/raw/out/06_pytest.mp4
node video/raw/record.js logo full video/raw/out/logo.png
```

Бір кадрды тексеру: `node video/raw/record.js still chat kadr.png 21000` (21-секунд).
Кадрлар виртуалды уақытпен түсіріледі, сондықтан қозғалыс тегіс, 30 fps.
