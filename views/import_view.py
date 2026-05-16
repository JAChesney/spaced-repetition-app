import csv
import io
from datetime import date
import flet as ft
from core.database import AbstractRepository
from core.models import MCQ
from core import theme as T

TEMPLATE = """\
question,A,B,C,D,answer,subject,topic,subtopic,question_type,date,explanation
What is the powerhouse of the cell?,Nucleus,Mitochondria,Ribosome,Golgi apparatus,B,Science,Biology,Cell Biology,STATIC,,The mitochondria produces ATP through cellular respiration.
Who became the 47th President of USA?,Joe Biden,Donald Trump,Barack Obama,George Bush,B,Current Affairs,,,CURRENT_AFFAIRS,2025-01-20,Donald Trump was inaugurated as the 47th US President on Jan 20 2025."""


def build(page: ft.Page, repo: AbstractRepository, navigate) -> ft.Control:
    text_input = ft.TextField(
        multiline=True,
        min_lines=12,
        max_lines=20,
        hint_text="Paste your CSV here...",
        bgcolor=T.CARD,
        border_color=T.BORDER,
        focused_border_color=T.ACCENT,
        color=T.TEXT,
        hint_style=ft.TextStyle(color=T.TEXT2),
        text_size=13,
        border_radius=12,
    )

    result_container = ft.Container(visible=False)

    def show_result(ok: int, errors: list[str]):
        parts = [ft.Text(f"Imported {ok} MCQ{'s' if ok != 1 else ''} successfully.",
                         color=T.SUCCESS, weight=ft.FontWeight.BOLD)]
        if errors:
            parts.append(ft.Text(f"{len(errors)} row(s) failed:", color=T.ERROR, size=12))
            for e in errors[:5]:
                parts.append(ft.Text(f"  • {e}", color=T.ERROR, size=11))
        result_container.content = ft.Column(parts, spacing=4)
        result_container.bgcolor = ft.Colors.with_opacity(0.08, T.SUCCESS if ok > 0 else T.ERROR)
        result_container.border = ft.Border.all(1, T.SUCCESS if ok > 0 else T.ERROR)
        result_container.border_radius = 10
        result_container.padding = 12
        result_container.visible = True
        page.update()

    def do_import(_):
        raw = text_input.value.strip()
        if not raw:
            show_result(0, ["Input is empty."])
            return

        reader = csv.DictReader(io.StringIO(raw))
        required = {"question", "A", "B", "C", "D", "answer"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = required - set(reader.fieldnames or [])
            show_result(0, [f"Missing columns: {', '.join(sorted(missing))}"])
            return

        ok, errors = 0, []
        for i, row in enumerate(reader, start=1):
            try:
                ans = str(row.get("answer", "")).strip().upper()
                if ans not in ("A", "B", "C", "D"):
                    raise ValueError(f"'answer' must be A/B/C/D, got '{ans}'")

                q_type = str(row.get("question_type", "STATIC")).strip().upper()
                if q_type not in ("STATIC", "CURRENT_AFFAIRS"):
                    q_type = "STATIC"

                raw_date = str(row.get("date", "")).strip()
                parsed_date = None
                if raw_date:
                    try:
                        parsed_date = date.fromisoformat(raw_date)
                    except ValueError:
                        raise ValueError(f"'date' must be YYYY-MM-DD, got '{raw_date}'")

                topic = str(row.get("topic", "")).strip()
                if q_type == "CURRENT_AFFAIRS" and raw_date:
                    topic = raw_date

                mcq = MCQ(
                    question=str(row["question"]).strip(),
                    option_a=str(row["A"]).strip(),
                    option_b=str(row["B"]).strip(),
                    option_c=str(row["C"]).strip(),
                    option_d=str(row["D"]).strip(),
                    correct_answer=ans,
                    subject=str(row.get("subject", "")).strip(),
                    topic=topic,
                    subtopic=str(row.get("subtopic", "")).strip(),
                    explanation=str(row.get("explanation", "")).strip(),
                    question_type=q_type,
                    event_date=parsed_date,
                )
                repo.add_mcq(mcq)
                ok += 1
            except (KeyError, ValueError) as exc:
                errors.append(f"Row {i}: {exc}")

        show_result(ok, errors)
        if ok > 0:
            text_input.value = ""

    def load_template(_):
        text_input.value = TEMPLATE
        result_container.visible = False
        page.update()

    top_bar = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, color=T.ACCENT, size=24),
                        ft.Text("StudyFlow", size=20, weight=ft.FontWeight.BOLD, color=T.TEXT),
                    ],
                    spacing=8,
                ),
            ],
        ),
        padding=ft.Padding.symmetric(horizontal=20, vertical=14),
    )

    format_card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.TABLE_ROWS_ROUNDED, color=T.ACCENT, size=18),
                        ft.Text("CSV Format", color=T.TEXT, weight=ft.FontWeight.BOLD, size=14),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    'Required: question, A, B, C, D, answer (must be A/B/C/D).\n'
                    'Optional: subject, topic, subtopic, explanation.\n'
                    'Optional: question_type (STATIC or CURRENT_AFFAIRS, default STATIC).\n'
                    'Optional: date (YYYY-MM-DD). For CURRENT_AFFAIRS, date is required and becomes the topic.',
                    color=T.TEXT2,
                    size=12,
                ),
            ],
            spacing=6,
        ),
        bgcolor=ft.Colors.with_opacity(0.1, T.ACCENT),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, T.ACCENT)),
        border_radius=12,
        padding=14,
    )

    return ft.Column(
        [
            top_bar,
            ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("BULK IMPORT", size=11, color=T.TEXT2, weight=ft.FontWeight.W_600),
                                    ft.Text("Import MCQs", size=28, weight=ft.FontWeight.BOLD, color=T.TEXT),
                                ],
                                spacing=0,
                                expand=True,
                            ),
                        ],
                    ),
                    format_card,
                    text_input,
                    result_container,
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text("Load Example", color=T.TEXT2, size=13,
                                                weight=ft.FontWeight.W_500),
                                border=ft.Border.all(1, T.BORDER),
                                border_radius=10,
                                padding=ft.Padding.symmetric(vertical=12, horizontal=18),
                                on_click=load_template,
                            ),
                            ft.Container(
                                content=ft.Text("Import", color="white", size=13,
                                                weight=ft.FontWeight.BOLD),
                                bgcolor=T.ACCENT,
                                border_radius=10,
                                padding=ft.Padding.symmetric(vertical=12, horizontal=24),
                                on_click=do_import,
                                expand=True,
                                alignment=ft.Alignment.CENTER,
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Container(height=16),
                ],
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        ],
        spacing=0,
        expand=True,
    )
