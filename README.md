# StudyFlow — Spaced Repetition MCQ App

A desktop application for exam preparation using multiple-choice questions (MCQs) and the SM-2 spaced repetition algorithm. Built with Python and [Flet](https://flet.dev/) (Flutter for Python).

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Flet](https://img.shields.io/badge/flet-0.84.0-purple)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

- **Spaced repetition scheduling** — SM-2 algorithm adjusts review intervals based on how well you know each card
- **Difficulty ratings** — Rate each answer as Again / Hard / Good / Easy to influence future scheduling
- **Subject & topic organization** — Group MCQs by subject and topic for targeted study sessions
- **Daily progress tracking** — Set a daily review goal and track your streak
- **Bulk CSV import** — Add hundreds of questions at once from a CSV file
- **MCQ editor** — Create, edit, and delete questions individually
- **Search & filter** — Find questions by keyword or subject
- **Dark mode UI** — Clean, readable interface built for long study sessions

---

## Screenshots

> Add screenshots here after first run.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| UI Framework | [Flet](https://flet.dev/) 0.84.0 (Flutter for Python) |
| Database | SQLite (via `sqlite3` stdlib) |
| Algorithm | SM-2 Spaced Repetition |
| Language | Python 3.10+ |
| Config | JSON (`settings.json`) |

---

## Installation

### Prerequisites

- Python 3.10 or higher
- `pip` (comes with Python)

### Steps

**1. Clone the repository**

```bash
git clone https://github.com/your-username/SpacedRepetitionApp.git
cd SpacedRepetitionApp
```

**2. Create a virtual environment**

```bash
python -m venv sraenv
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

**5. Run the app**

```bash
python main.py
```

The app window will open automatically.

---

## Project Structure

```
SpacedRepetitionApp/
├── main.py                  # App entry point, routing
├── requirements.txt         # Python dependencies
├── settings.json            # User configuration (auto-created)
├── mcqs.db                  # SQLite database (auto-created at runtime)
├── core/
│   ├── database.py          # SQLite repository and data access layer
│   ├── models.py            # Data models: MCQ, CardProgress, ReviewLog
│   ├── spaced_repetition.py # SM-2 algorithm implementation
│   ├── settings.py          # Settings loader and saver
│   └── theme.py             # UI theme colors and styling
└── views/
    ├── dashboard.py         # Home screen with daily progress
    ├── library.py           # Browse subjects and topics
    ├── study.py             # Interactive study session
    ├── create_mcq.py        # Create / edit MCQ form
    ├── import_view.py       # Bulk CSV import
    └── manage.py            # Search and manage all MCQs
```

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
question,option_a,option_b,option_c,option_d,correct_answer,subject,topic,explanation
```

- `correct_answer` must be one of: `A`, `B`, `C`, or `D`
- `explanation` is optional but recommended
- Download the template from within the app (Import screen)

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

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## License

MIT — see [LICENSE](LICENSE) for details.
