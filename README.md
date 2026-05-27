# StudyFlow — Spaced Repetition MCQ App

<p align="center">
  <img src="assets/icon.png" width="120" alt="StudyFlow icon" />
</p>

A cross-platform application for exam preparation using multiple-choice questions (MCQs) and the **SM-2 spaced repetition algorithm**. Built with Python and [Flet](https://flet.dev/) (Flutter for Python), with **Supabase** as the cloud backend and **SQLite** as a local cache.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Flet](https://img.shields.io/badge/flet-0.84.0-purple)
![Supabase](https://img.shields.io/badge/supabase-cloud-green)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **Spaced repetition scheduling** — SM-2 algorithm adjusts review intervals based on recall quality
- **Difficulty ratings** — Rate each answer as Again / Hard / Good / Easy
- **Structured taxonomy** — Subject → Topic → Subtopic cascading organisation across 13 subjects
- **Current Affairs mode** — Special subject where the event date is used as the topic for date-based recall
- **Static & Current Affairs question types** — Tag each MCQ as `STATIC` or `CURRENT_AFFAIRS`
- **Daily progress tracking** — Set a daily review goal and track your streak
- **Bulk CSV import** — Add hundreds of questions at once from a CSV file
- **MCQ editor** — Create, edit, and delete questions individually with full field support
- **Search & filter** — Find questions by keyword, subject, or topic
- **Paginated library** — Fast browsing even with thousands of questions
- **Cloud sync** — Supabase is the source of truth; SQLite caches data locally for offline speed
- **Dark mode UI** — Clean, readable interface built for long study sessions
- **Splash screen** — 2-second branded splash on every launch before the main UI loads
- **Smart navigation** — Editing an MCQ returns you to the MCQ list, not the dashboard
- **Custom app icon** — Branded adaptive icon shown in the Android launcher and window title bar

---

## Screenshots

> Add screenshots here after first run.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| UI Framework | [Flet](https://flet.dev/) 0.84.0 (Flutter for Python) |
| Cloud Database | [Supabase](https://supabase.com/) (PostgreSQL) |
| Local Cache | SQLite (via `sqlite3` stdlib) |
| Algorithm | SM-2 Spaced Repetition |
| Language | Python 3.10+ |
| HTTP Client | `httpx` via `supabase-py` |
| Config | `.env` (Supabase credentials) + `settings.json` |

---

## Installation

### Prerequisites

- Python 3.10 or higher
- A [Supabase](https://supabase.com/) account and project

### Steps

**1. Clone the repository**

```bash
git clone https://github.com/JAChesney/spaced-repetition-app.git
cd spaced-repetition-app
```

**2. Create a virtual environment**

```bash
py -3.12 -m venv sraenv
```

**3. Activate the virtual environment**

- Windows:
  ```bash
  sraenv\Scripts\activate
  ```
- macOS / Linux:
  ```bash
  source sraenv/bin/activate
  ```

**4. Install dependencies**

```bash
pip install -r requirements.txt
```

**5. Configure environment variables**

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-or-service-role-key
```

You can find these in your Supabase project under **Settings → API**.

**6. Run the app**

```bash
python main.py
```

The app window will open automatically. On first launch it pulls all data from Supabase into the local SQLite cache.

---

## Project Structure

```
SpacedRepetitionApp/
├── main.py                  # Entry point: 2s splash screen → _start_app() → routing
├── requirements.txt         # Python dependencies
├── pyproject.toml           # Flet build config (Android adaptive icon, product name)
├── settings.json            # User configuration (gitignored, auto-created)
├── .env                     # Supabase credentials (gitignored)
├── icon-android.svg         # Android adaptive icon foreground (no background layer)
├── assets/
│   ├── icon.png             # App icon raster source (1024×1024)
│   ├── icon.svg             # Full icon with background — fallback for web/desktop
│   ├── icon-android.svg     # Android adaptive icon foreground copy (inside assets)
│   └── icon.ico             # Windows desktop icon (multi-size 16–256px)
├── core/
│   ├── database.py          # Repository layer: AbstractRepository, SQLiteRepository, CachedRepository
│   ├── models.py            # Data models: MCQ, CardProgress, ReviewLog
│   ├── spaced_repetition.py # SM-2 algorithm implementation
│   ├── taxonomy.py          # Subject → Topic → Subtopic definitions (13 subjects)
│   ├── settings.py          # Settings loader and saver
│   └── theme.py             # UI theme colours and styling constants
└── views/
    ├── dashboard.py         # Home screen with daily progress and due-card summary
    ├── library.py           # Browse subjects and topics
    ├── study.py             # Interactive study session with SM-2 rating
    ├── create_mcq.py        # Create / edit MCQ form — save returns to MCQ list
    ├── import_view.py       # Bulk CSV import with template download
    └── manage.py            # Paginated search and manage all MCQs
```

---

## Data Architecture

```
Supabase (source of truth)
        ↕  sync on startup + every write
SQLite local cache  ←  all reads (fast, offline)
```

`CachedRepository` in `core/database.py` wraps both:
- **Writes** go to Supabase first, then mirror to SQLite
- **Reads** always hit SQLite for low-latency UI
- **On startup**, all Supabase data is pulled into the local cache

---

## Configuration

`settings.json` is created automatically on first run. You can edit it directly or use the in-app Settings dialog.

```json
{
  "daily_goal": 20,
  "due_cards_limit": 50,
  "new_cards_limit": 50
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `daily_goal` | 20 | Target cards to review per day |
| `due_cards_limit` | 50 | Max due (review) cards per session |
| `new_cards_limit` | 50 | Max new cards per session |

---

## CSV Import Format

To bulk-import questions, create a CSV with these columns:

```
question,option_a,option_b,option_c,option_d,correct_answer,subject,topic,subtopic,explanation,question_type,event_date
```

| Column | Required | Notes |
|--------|----------|-------|
| `question` | ✅ | The MCQ question text |
| `option_a` – `option_d` | ✅ | Answer choices |
| `correct_answer` | ✅ | One of: `A`, `B`, `C`, `D` |
| `subject` | ✅ | Must match a subject in the taxonomy |
| `topic` | ✅ | Must match a topic under the subject |
| `subtopic` | ❌ | Optional further classification |
| `explanation` | ❌ | Shown after answering |
| `question_type` | ❌ | `STATIC` (default) or `CURRENT_AFFAIRS` |
| `event_date` | ❌ | `YYYY-MM-DD` — required for `CURRENT_AFFAIRS` questions |

A template CSV can be downloaded from within the app on the **Import** screen.

---

## Question Types

| Type | Description |
|------|-------------|
| `STATIC` | Standard MCQ — subject/topic/subtopic classification |
| `CURRENT_AFFAIRS` | News-based MCQ — `event_date` is used as the topic for date-based recall |

For **Current Affairs** questions, the event date (e.g. `2026-05-23`) is automatically stored as the topic so you can filter and study by date.

---

## Taxonomy

The app includes a built-in taxonomy of **13 subjects** with topics and subtopics:

History, Geography, Polity, Economy, Science, International Relations, Defence, Art and Culture, Sports, Awards and Honours, Important Days, Current Affairs, Miscellaneous

Subjects, topics, and subtopics are defined in `core/taxonomy.py` and drive the cascading dropdowns in the MCQ editor.

---

## Spaced Repetition Algorithm

StudyFlow uses the **SM-2** algorithm. After each answer you rate your recall:

| Rating | Effect |
|--------|--------|
| **Again (0)** | Resets progress; card shown again tomorrow |
| **Hard (1)** | Ease −0.15; interval × 1.2 |
| **Good (2)** | Standard progression; interval × ease factor |
| **Easy (3)** | Ease +0.15; interval × ease factor × 1.3 |

Ease factor is bounded between **1.3** and **3.0**.

---

## Building for Android

Flet packages the app as an Android APK using Flutter under the hood.

### Prerequisites

- [Temurin JDK 17](https://adoptium.net/) or higher
- [Android Studio](https://developer.android.com/studio) (for Android SDK)
- `ANDROID_HOME` environment variable set to your SDK path

### Build

```bash
flet build apk --clear-cache
```

The generated APK will be at `build/apk/app-release.apk`.

### Install on device

```bash
adb install build/apk/app-release.apk
```

### App icon (Android Adaptive Icon)

The launcher icon uses Android's **Adaptive Icon** system so it renders crisp at every screen density and on every device icon shape (circle, squircle, rounded-square, etc.).

| File | Purpose |
|---|---|
| `icon-android.svg` | **Foreground layer** — card-and-waves artwork on a transparent canvas, placed at project root for Flet to pick up |
| `assets/icon-android.svg` | Copy of the foreground SVG kept inside assets for reference |
| `assets/icon.svg` | Full icon with background — fallback for web/desktop |
| `assets/icon.png` | Raster fallback (1024×1024) |
| `pyproject.toml` → `adaptive_icon_background` | Background layer colour (`#162040`, dark navy) |
| `pyproject.toml` → `adaptive_icon_foreground` | Points to `icon-android.svg` at project root |

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "feat: describe your change"`
4. Push the branch: `git push origin feature/your-feature`
5. Open a Pull Request against `main`
