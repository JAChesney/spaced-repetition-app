import flet as ft
from datetime import datetime
from core.database import AbstractRepository
from core.models import MCQ
from core import theme as T
from core.taxonomy import subjects, topics, subtopics

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_cur = datetime.now().year
_YEARS = [str(y) for y in range(_cur - 1, _cur + 4)]


def _field(label, value="", multiline=False, min_lines=1, max_lines=1):
    return ft.TextField(
        label=label, value=value,
        multiline=multiline, min_lines=min_lines, max_lines=max_lines,
        bgcolor=T.CARD, border_color=T.BORDER, focused_border_color=T.ACCENT,
        color=T.TEXT, label_style=ft.TextStyle(color=T.TEXT2),
        border_radius=10, expand=True,
    )


def _dd(label, opts, value=None, on_change=None, width=None, expand=False):
    return ft.Dropdown(
        label=label,
        options=[ft.DropdownOption(key=o, text=o) for o in opts],
        value=value if value in opts else None,
        on_select=on_change,
        width=width,
        expand=expand,
        filled=True,
        fill_color=T.CARD,
        border_color=T.BORDER,
        focused_border_color=T.ACCENT,
        label_style=ft.TextStyle(color=T.TEXT2),
        border_radius=10,
        color=T.TEXT,
    )


def build(page: ft.Page, repo: AbstractRepository, navigate, edit_mcq: MCQ = None):
    is_edit   = edit_mcq is not None
    init_type = edit_mcq.question_type if is_edit else "STATIC"
    init_subj = edit_mcq.subject       if is_edit else ""
    init_top  = edit_mcq.topic         if is_edit else ""
    init_sub  = edit_mcq.subtopic      if is_edit else ""

    state = {"subject": init_subj, "topic": init_top}

    # ── question fields ───────────────────────────────────────────────────
    q     = _field("Question *", edit_mcq.question if is_edit else "",
                   multiline=True, min_lines=2, max_lines=5)
    opt_a = _field("Option A *",  edit_mcq.option_a if is_edit else "")
    opt_b = _field("Option B *",  edit_mcq.option_b if is_edit else "")
    opt_c = _field("Option C *",  edit_mcq.option_c if is_edit else "")
    opt_d = _field("Option D *",  edit_mcq.option_d if is_edit else "")
    expl  = _field("Explanation (optional)", edit_mcq.explanation if is_edit else "",
                   multiline=True, min_lines=2, max_lines=4)

    correct_dd = _dd("Correct Answer *", ["A", "B", "C", "D"],
                     value=edit_mcq.correct_answer if is_edit else None, width=160)

    # ── Current Affairs: month + year dropdowns ───────────────────────────
    # Pre-populate from existing topic (e.g. "January 2026") when editing
    _ca_parts   = init_top.split() if (is_edit and init_type == "CURRENT_AFFAIRS") else []
    _init_month = _ca_parts[0] if len(_ca_parts) == 2 else ""
    _init_year  = _ca_parts[1] if len(_ca_parts) == 2 else str(_cur)

    month_dd = _dd("Month *",  _MONTHS, value=_init_month, expand=True)
    year_dd  = _dd("Year *",   _YEARS,  value=_init_year,  expand=True)

    # Optional free-text subtopic (date like 2026-01-31) for CA
    ca_subtopic = _field(
        "Date (optional, e.g. 2026-01-31)",
        value=init_sub if (is_edit and init_type == "CURRENT_AFFAIRS") else "",
    )

    # Slot that holds month+year row — only visible for CURRENT_AFFAIRS
    ca_slot = ft.Column(
        controls=[ft.Row([month_dd, year_dd], spacing=10)]
                 if init_type == "CURRENT_AFFAIRS" else [],
        spacing=0,
    )

    # ── type dropdown + change handler ────────────────────────────────────
    def on_type_change(e):
        is_ca = e.control.value == "CURRENT_AFFAIRS"
        if is_ca:
            ca_slot.controls = [ft.Row([month_dd, year_dd], spacing=10)]
            subject_dd.value = "Current Affairs"
            state["subject"] = "Current Affairs"
            state["topic"]   = ""
            subject_dd.update()
            topic_slot.visible    = False
            subtopic_slot.controls = [ca_subtopic]
        else:
            ca_slot.controls = []
            topic_slot.visible    = True
            subtopic_slot.controls = [_fresh_subtopic_dd(state["subject"], state["topic"])]
        ca_slot.update()
        topic_slot.update()
        subtopic_slot.update()

    _type_opts = [
        ft.DropdownOption(key="STATIC",         text="Static"),
        ft.DropdownOption(key="CURRENT_AFFAIRS", text="Current Affairs"),
        ft.DropdownOption(key="BIHAR_GK",        text="Bihar GK"),
    ]
    type_dd = ft.Dropdown(
        label="Question Type *",
        options=_type_opts,
        value=init_type if init_type in ("STATIC", "CURRENT_AFFAIRS", "BIHAR_GK") else "STATIC",
        on_select=on_type_change,
        width=220,
        filled=True,
        fill_color=T.CARD,
        border_color=T.BORDER,
        focused_border_color=T.ACCENT,
        label_style=ft.TextStyle(color=T.TEXT2),
        border_radius=10,
        color=T.TEXT,
    )

    # ── cascading taxonomy (used for non-CA types) ────────────────────────
    def on_topic_change(e):
        state["topic"] = e.control.value or ""
        subtopic_slot.controls = [_fresh_subtopic_dd(state["subject"], state["topic"])]
        subtopic_slot.update()

    def on_subject_change(e):
        state["subject"] = e.control.value or ""
        state["topic"]   = ""
        topic_slot.controls = [_fresh_topic_dd(state["subject"])]
        topic_slot.update()
        subtopic_slot.controls = [_fresh_subtopic_dd(state["subject"], "")]
        subtopic_slot.update()

    def _fresh_topic_dd(subj):
        return _dd("Topic *", topics(subj), on_change=on_topic_change)

    def _fresh_subtopic_dd(subj, top):
        return _dd("Subtopic (optional)", subtopics(subj, top))

    init_topic_dd    = _fresh_topic_dd(init_subj)
    init_subtopic_dd = _fresh_subtopic_dd(init_subj, init_top)

    if is_edit and init_type != "CURRENT_AFFAIRS":
        if init_top and init_top in [o.key for o in init_topic_dd.options]:
            init_topic_dd.value = init_top
        if init_sub and init_sub in [o.key for o in init_subtopic_dd.options]:
            init_subtopic_dd.value = init_sub

    # topic_slot lives inside ft.Row → expand=True = horizontal expansion
    topic_slot = ft.Column([init_topic_dd], spacing=0, expand=True,
                           visible=init_type != "CURRENT_AFFAIRS")

    # subtopic_slot: taxonomy dd for non-CA, free text field for CA
    _init_subtopic_ctrl = (
        ca_subtopic if init_type == "CURRENT_AFFAIRS" else init_subtopic_dd
    )
    subtopic_slot = ft.Column([_init_subtopic_ctrl], spacing=0)

    subject_dd = _dd("Subject *", subjects(),
                     value=init_subj or None,
                     on_change=on_subject_change, expand=True)

    # ── feedback ──────────────────────────────────────────────────────────
    error_text  = ft.Text("", color=T.ERROR, size=13)
    success_box = ft.Container(visible=False)

    def show_success(msg):
        success_box.content       = ft.Text(msg, color=T.SUCCESS)
        success_box.bgcolor       = ft.Colors.with_opacity(0.1, T.SUCCESS)
        success_box.border        = ft.Border.all(1, ft.Colors.with_opacity(0.4, T.SUCCESS))
        success_box.border_radius = 8
        success_box.padding       = 10
        success_box.visible       = True
        success_box.update()

    def _topic_value():
        if type_dd.value == "CURRENT_AFFAIRS":
            m = month_dd.value or ""
            y = year_dd.value  or ""
            return f"{m} {y}".strip() or None
        dd = topic_slot.controls[0] if topic_slot.controls else None
        return dd.value if dd else None

    def _subtopic_value():
        if type_dd.value == "CURRENT_AFFAIRS":
            return ca_subtopic.value.strip()
        dd = subtopic_slot.controls[0] if subtopic_slot.controls else None
        return dd.value if dd else None

    # ── validation ────────────────────────────────────────────────────────
    def validate():
        for f in [q, opt_a, opt_b, opt_c, opt_d]:
            if not f.value or not f.value.strip():
                error_text.value = "Question and all four options are required."
                error_text.update()
                return False
        if not correct_dd.value:
            error_text.value = "Please select the correct answer."
            error_text.update()
            return False
        if not subject_dd.value:
            error_text.value = "Please select a subject."
            error_text.update()
            return False
        if type_dd.value == "CURRENT_AFFAIRS":
            if not month_dd.value or not year_dd.value:
                error_text.value = "Please select month and year for Current Affairs."
                error_text.update()
                return False
        elif not _topic_value():
            error_text.value = "Please select a topic."
            error_text.update()
            return False
        error_text.value = ""
        error_text.update()
        return True

    # ── save ──────────────────────────────────────────────────────────────
    def save(_):
        if not validate():
            return
        mcq = MCQ(
            id=edit_mcq.id if is_edit else None,
            question=q.value.strip(),
            option_a=opt_a.value.strip(),
            option_b=opt_b.value.strip(),
            option_c=opt_c.value.strip(),
            option_d=opt_d.value.strip(),
            correct_answer=correct_dd.value,
            subject=subject_dd.value or "",
            topic=_topic_value() or "",
            subtopic=_subtopic_value() or "",
            explanation=expl.value.strip(),
            question_type=type_dd.value or "STATIC",
            event_date=None,
        )
        if is_edit:
            repo.update_mcq(mcq)
            navigate("manage")
        else:
            repo.add_mcq(mcq)
            show_success("MCQ saved! Fill in another or go back.")
            for f in [q, opt_a, opt_b, opt_c, opt_d, expl]:
                f.value = ""
                f.update()
            correct_dd.value = None
            correct_dd.update()
            type_dd.value = "STATIC"
            type_dd.update()
            month_dd.value = None
            year_dd.value  = None
            ca_subtopic.value = ""
            ca_slot.controls = []
            ca_slot.update()
            topic_slot.visible = True
            topic_slot.update()
            subject_dd.value = None
            subject_dd.update()
            state["subject"] = ""
            state["topic"]   = ""
            topic_slot.controls = [_fresh_topic_dd("")]
            topic_slot.update()
            subtopic_slot.controls = [_fresh_subtopic_dd("", "")]
            subtopic_slot.update()

    # ── layout ────────────────────────────────────────────────────────────
    top_bar = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, icon_color=T.TEXT2,
                              on_click=lambda _: navigate("manage" if is_edit else "library")),
                ft.Text("Edit MCQ" if is_edit else "New MCQ",
                        size=20, weight=ft.FontWeight.BOLD, color=T.TEXT),
                *([ft.Container(expand=True),
                   ft.Text(edit_mcq.public_id, size=13, color=T.TEXT2,
                           font_family="monospace")]
                  if is_edit and edit_mcq.public_id else []),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=14),
    )

    return ft.Column(
        [
            top_bar,
            ft.Column(
                [
                    success_box,
                    q,
                    ft.Row([opt_a, opt_b], spacing=10),
                    ft.Row([opt_c, opt_d], spacing=10),
                    ft.Row([correct_dd, type_dd], spacing=10),
                    ft.Row([subject_dd, topic_slot], spacing=10),
                    ca_slot,
                    subtopic_slot,
                    expl,
                    error_text,
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(
                                    "Save" if is_edit else "Save MCQ",
                                    color="white", weight=ft.FontWeight.BOLD, size=14,
                                ),
                                bgcolor=T.ACCENT, border_radius=10,
                                padding=ft.Padding.symmetric(vertical=13, horizontal=24),
                                on_click=save,
                            ),
                            ft.Container(
                                content=ft.Text("Cancel", color=T.TEXT2, size=14),
                                border=ft.Border.all(1, T.BORDER), border_radius=10,
                                padding=ft.Padding.symmetric(vertical=13, horizontal=20),
                                on_click=lambda _: navigate("manage" if is_edit else "library"),
                            ),
                        ],
                        spacing=10,
                    ),
                    ft.Container(height=16),
                ],
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        ],
        spacing=0,
        expand=True,
    )
