import csv
import io
import asyncio
import pathlib
from datetime import date
import flet as ft
from core.database import AbstractRepository
from core.models import MCQ
from core import theme as T

TEMPLATE = (
    "question,A,B,C,D,answer,subject,topic,subtopic,question_type,date,explanation\n"
    "What is the powerhouse of the cell?,Nucleus,Mitochondria,Ribosome,Golgi apparatus,"
    "B,Science,Biology,Cell Biology,STATIC,,The mitochondria produces ATP.\n"
    "Who became the 47th President of USA?,Joe Biden,Donald Trump,Barack Obama,George Bush,"
    "B,Current Affairs,January 2025,,CURRENT_AFFAIRS,,Donald Trump was inaugurated on Jan 20 2025.\n"
)


def build(page: ft.Page, repo: AbstractRepository, navigate) -> ft.Control:

    # ── Mutable state ──────────────────────────────────────────────────────
    selected_file = [None]   # FilePickerFile returned by pick_files()
    importing     = [False]

    # ── UI elements ────────────────────────────────────────────────────────
    file_name_text = ft.Text(
        "No file selected", color=T.TEXT2, size=13, expand=True,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    parse_label = ft.Text("", color=T.TEXT2, size=12, visible=False)
    parse_bar   = ft.ProgressBar(
        value=None, color=T.ACCENT,
        bgcolor=ft.Colors.with_opacity(0.2, T.ACCENT),
        border_radius=4, height=6, visible=False,
    )

    upload_label = ft.Text("", color=T.TEXT2, size=12, visible=False)
    upload_bar   = ft.ProgressBar(
        value=0, color=T.ACCENT,
        bgcolor=ft.Colors.with_opacity(0.2, T.ACCENT),
        border_radius=4, height=6, visible=False,
    )

    result_container = ft.Container(visible=False)

    import_label = ft.Text("Import", color="white", size=13,
                           weight=ft.FontWeight.BOLD)
    import_btn = ft.Container(
        content=import_label,
        border_radius=10,
        padding=ft.Padding.symmetric(vertical=12, horizontal=24),
        expand=True,
        alignment=ft.Alignment.CENTER,
    )

    def _refresh_btn():
        active = bool(selected_file[0]) and not importing[0]
        import_btn.on_click = (lambda _: page.run_task(_run_import)) if active else None
        import_btn.bgcolor  = T.ACCENT if active else ft.Colors.with_opacity(0.35, T.ACCENT)
        import_label.color  = "white" if active else ft.Colors.with_opacity(0.5, "white")

    _refresh_btn()

    # ── Result helper ──────────────────────────────────────────────────────
    def _show_result(ok: int, errors: list):
        parts = [ft.Text(
            f"Imported {ok} MCQ{'s' if ok != 1 else ''} successfully.",
            color=T.SUCCESS, weight=ft.FontWeight.BOLD,
        )]
        if errors:
            parts.append(ft.Text(f"{len(errors)} row(s) failed:", color=T.ERROR, size=12))
            for e in errors[:5]:
                parts.append(ft.Text(f"  • {e}", color=T.ERROR, size=11))
            if len(errors) > 5:
                parts.append(ft.Text(f"  … and {len(errors) - 5} more",
                                     color=T.ERROR, size=11))
        result_container.content       = ft.Column(parts, spacing=4)
        result_container.bgcolor       = ft.Colors.with_opacity(
            0.08, T.SUCCESS if ok > 0 else T.ERROR)
        result_container.border        = ft.Border.all(
            1, T.SUCCESS if ok > 0 else T.ERROR)
        result_container.border_radius = 10
        result_container.padding       = 12
        result_container.visible       = True

    # ── File picker ────────────────────────────────────────────────────────
    # Use the shared FilePicker pre-created at app startup (_start_app).
    # If somehow not ready yet, create one here — Service.init() handles
    # registration automatically when context.page is available.
    file_picker = getattr(page, "_shared_file_picker", None)
    if file_picker is None:
        file_picker = ft.FilePicker()
        page._shared_file_picker = file_picker

    async def _pick_file():
        try:
            files = await file_picker.pick_files(
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["csv"],
                allow_multiple=False,
                with_data=True,
            )
        except Exception:
            return  # dialog cancelled or picker not ready — do nothing
        if not files:
            return
        selected_file[0]         = files[0]
        file_name_text.value     = files[0].name
        file_name_text.color     = T.TEXT
        result_container.visible = False
        _refresh_btn()
        page.update()

    # ── Import coroutine ───────────────────────────────────────────────────
    async def _run_import():
        loop = asyncio.get_event_loop()
        importing[0] = True
        _refresh_btn()
        result_container.visible = False

        # Stage 1 — read + parse ───────────────────────────────────────────
        parse_label.value    = "Reading file…"
        parse_label.visible  = True
        parse_bar.visible    = True
        upload_bar.visible   = False
        upload_label.visible = False
        page.update()

        f = selected_file[0]
        try:
            if f.bytes:
                raw = f.bytes.decode("utf-8-sig")
            elif f.path:
                raw = await loop.run_in_executor(
                    None, lambda: open(f.path, encoding="utf-8-sig").read()
                )
            else:
                raise RuntimeError("No file contents available")
        except Exception as exc:
            parse_bar.visible    = False
            parse_label.visible  = False
            importing[0] = False
            _refresh_btn()
            _show_result(0, [f"Could not read file: {exc}"])
            page.update()
            return

        reader   = csv.DictReader(io.StringIO(raw))
        required = {"question", "A", "B", "C", "D", "answer"}
        if not required.issubset(set(reader.fieldnames or [])):
            missing = required - set(reader.fieldnames or [])
            parse_bar.visible    = False
            parse_label.visible  = False
            importing[0] = False
            _refresh_btn()
            _show_result(0, [f"Missing columns: {', '.join(sorted(missing))}"])
            page.update()
            return

        parsed: list = []
        parse_errors: list = []
        for i, row in enumerate(reader, start=1):
            try:
                ans = str(row.get("answer", "")).strip().upper()
                if ans not in ("A", "B", "C", "D"):
                    raise ValueError(f"'answer' must be A/B/C/D, got '{ans}'")

                q_type = str(row.get("question_type", "STATIC")).strip().upper()
                if q_type not in ("STATIC", "CURRENT_AFFAIRS", "BIHAR_GK"):
                    q_type = "STATIC"

                raw_date    = str(row.get("date", "")).strip()
                parsed_date = None
                if raw_date:
                    try:
                        parsed_date = date.fromisoformat(raw_date)
                    except ValueError:
                        raise ValueError(f"'date' must be YYYY-MM-DD, got '{raw_date}'")

                subject  = str(row.get("subject",  "")).strip()
                topic    = str(row.get("topic",    "")).strip()
                subtopic = str(row.get("subtopic", "")).strip()

                if q_type == "CURRENT_AFFAIRS":
                    subject = "Current Affairs"
                    if parsed_date:
                        topic    = parsed_date.strftime("%B %Y")
                        subtopic = raw_date
                    parsed_date = None

                parsed.append(MCQ(
                    question=str(row["question"]).strip(),
                    option_a=str(row["A"]).strip(),
                    option_b=str(row["B"]).strip(),
                    option_c=str(row["C"]).strip(),
                    option_d=str(row["D"]).strip(),
                    correct_answer=ans,
                    subject=subject, topic=topic, subtopic=subtopic,
                    explanation=str(row.get("explanation", "")).strip(),
                    question_type=q_type,
                    event_date=parsed_date,
                ))
            except Exception as exc:
                parse_errors.append(f"Row {i}: {exc}")

        parse_bar.visible   = False
        parse_label.visible = False

        if not parsed:
            importing[0] = False
            _refresh_btn()
            _show_result(0, parse_errors)
            page.update()
            return

        # Stage 2 — upload to Supabase ─────────────────────────────────────
        upload_bar.value     = 0
        upload_bar.visible   = True
        upload_label.value   = f"Uploading 0 / {len(parsed)} cards…"
        upload_label.visible = True
        page.update()

        ok         = 0
        all_errors = list(parse_errors)
        for i, mcq in enumerate(parsed):
            try:
                await loop.run_in_executor(None, repo.add_mcq, mcq)
                ok += 1
            except Exception as exc:
                all_errors.append(f"Card {i + 1}: {exc}")
            upload_bar.value   = (i + 1) / len(parsed)
            upload_label.value = f"Uploading {i + 1} / {len(parsed)} cards…"
            page.update()

        upload_bar.visible   = False
        upload_label.visible = False
        importing[0] = False

        if ok > 0:
            selected_file[0]     = None
            file_name_text.value = "No file selected"
            file_name_text.color = T.TEXT2

        _refresh_btn()
        _show_result(ok, all_errors)
        page.update()

    async def _download_template():
        loop = asyncio.get_event_loop()
        try:
            dest = pathlib.Path.home() / "Downloads" / "studyflow_template.csv"
            dest.parent.mkdir(parents=True, exist_ok=True)
            await loop.run_in_executor(None, lambda: dest.write_text(TEMPLATE, encoding="utf-8"))
            page.show_dialog(ft.SnackBar(ft.Text(f"Saved to {dest}")))
        except Exception as exc:
            page.show_dialog(ft.SnackBar(ft.Text(f"Could not save: {exc}")))

    # ── Layout ─────────────────────────────────────────────────────────────
    top_bar = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Image(src="icon-android.svg", width=28, height=28, fit="contain"),
                ft.Text("StudyFlow", size=20, weight=ft.FontWeight.BOLD, color=T.TEXT),
            ], spacing=8),
        ]),
        padding=ft.Padding(left=0, right=0, top=8, bottom=8),
    )

    format_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.Icons.TABLE_ROWS_ROUNDED, color=T.ACCENT, size=18),
                ft.Text("CSV Format", color=T.TEXT, weight=ft.FontWeight.BOLD, size=14),
            ], spacing=8),
            ft.Text(
                'Required: question, A, B, C, D, answer (A/B/C/D).\n'
                'Optional: subject, topic, subtopic, explanation.\n'
                'Optional: question_type — STATIC (default), CURRENT_AFFAIRS, or BIHAR_GK.\n'
                'For CURRENT_AFFAIRS: provide date (YYYY-MM-DD). Subject is auto-set to\n'
                '"Current Affairs", topic → "Month Year", subtopic → the date string.',
                color=T.TEXT2, size=12,
            ),
        ], spacing=6),
        bgcolor=ft.Colors.with_opacity(0.1, T.ACCENT),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, T.ACCENT)),
        border_radius=12, padding=14,
    )

    file_pick_zone = ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.UPLOAD_FILE_OUTLINED, color=T.ACCENT, size=20),
                    ft.Text("Choose CSV", color=T.ACCENT, size=13,
                            weight=ft.FontWeight.W_600),
                ], spacing=8, tight=True),
                border=ft.Border.all(1, T.ACCENT),
                border_radius=10,
                padding=ft.Padding.symmetric(vertical=10, horizontal=14),
                on_click=lambda _: page.run_task(_pick_file),
            ),
            file_name_text,
        ], spacing=12),
        bgcolor=ft.Colors.with_opacity(0.05, T.ACCENT),
        border=ft.Border.all(1, T.BORDER),
        border_radius=12, padding=14,
    )

    return ft.Column([
        top_bar,
        ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("BULK IMPORT", size=11, color=T.TEXT2,
                            weight=ft.FontWeight.W_600),
                    ft.Text("Import MCQs", size=28, weight=ft.FontWeight.BOLD,
                            color=T.TEXT),
                ], spacing=0, expand=True),
            ]),
            format_card,
            file_pick_zone,
            ft.Column([
                ft.Column([parse_label, parse_bar],   spacing=6),
                ft.Column([upload_label, upload_bar], spacing=6),
            ], spacing=4),
            result_container,
            ft.Row([
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, color=T.TEXT2, size=16),
                        ft.Text("Download Template", color=T.TEXT2, size=13,
                                weight=ft.FontWeight.W_500),
                    ], spacing=6, tight=True),
                    border=ft.Border.all(1, T.BORDER),
                    border_radius=10,
                    padding=ft.Padding.symmetric(vertical=12, horizontal=14),
                    on_click=lambda _: page.run_task(_download_template),
                ),
                import_btn,
            ], spacing=10),
            ft.Container(height=16),
        ], spacing=14, scroll=ft.ScrollMode.AUTO, expand=True),
    ], spacing=0, expand=True)
