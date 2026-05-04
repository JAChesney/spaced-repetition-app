import flet as ft
from core.database import AbstractRepository
from core.models import MCQ
from core import theme as T


def _field(label: str, value: str = "", multiline: bool = False,
           min_lines: int = 1, max_lines: int = 1) -> ft.TextField:
    return ft.TextField(
        label=label,
        value=value,
        multiline=multiline,
        min_lines=min_lines,
        max_lines=max_lines,
        bgcolor=T.CARD,
        border_color=T.BORDER,
        focused_border_color=T.ACCENT,
        color=T.TEXT,
        label_style=ft.TextStyle(color=T.TEXT2),
        border_radius=10,
        expand=True,
    )


def build(page: ft.Page, repo: AbstractRepository, navigate, edit_mcq: MCQ = None) -> ft.Control:
    is_edit = edit_mcq is not None

    q        = _field("Question", edit_mcq.question if is_edit else "", multiline=True, min_lines=2, max_lines=5)
    opt_a    = _field("Option A", edit_mcq.option_a if is_edit else "")
    opt_b    = _field("Option B", edit_mcq.option_b if is_edit else "")
    opt_c    = _field("Option C", edit_mcq.option_c if is_edit else "")
    opt_d    = _field("Option D", edit_mcq.option_d if is_edit else "")
    expl     = _field("Explanation (optional)", edit_mcq.explanation if is_edit else "", multiline=True, min_lines=2, max_lines=4)
    subj     = _field("Subject", edit_mcq.subject if is_edit else "")
    topic_f  = _field("Topic", edit_mcq.topic if is_edit else "")

    correct_dd = ft.Dropdown(
        label="Correct Answer",
        options=[ft.dropdown.Option(l, l) for l in ("A", "B", "C", "D")],
        value=edit_mcq.correct_answer if is_edit else None,
        width=160,
        bgcolor=T.CARD,
        border_color=T.BORDER,
        focused_border_color=T.ACCENT,
        color=T.TEXT,
        label_style=ft.TextStyle(color=T.TEXT2),
        border_radius=10,
    )

    error_text   = ft.Text("", color=T.ERROR, size=13)
    success_box  = ft.Container(visible=False)

    def show_success(msg: str):
        success_box.content = ft.Text(msg, color=T.SUCCESS)
        success_box.bgcolor = ft.Colors.with_opacity(0.1, T.SUCCESS)
        success_box.border  = ft.Border.all(1, ft.Colors.with_opacity(0.4, T.SUCCESS))
        success_box.border_radius = 8
        success_box.padding = 10
        success_box.visible = True
        page.update()

    def validate() -> bool:
        for f in [q, opt_a, opt_b, opt_c, opt_d]:
            if not f.value or not f.value.strip():
                error_text.value = "Question and all four options are required."
                return False
        if not correct_dd.value:
            error_text.value = "Please select the correct answer."
            return False
        error_text.value = ""
        return True

    def save(_):
        if not validate():
            page.update()
            return
        mcq = MCQ(
            id=edit_mcq.id if is_edit else None,
            question=q.value.strip(),
            option_a=opt_a.value.strip(),
            option_b=opt_b.value.strip(),
            option_c=opt_c.value.strip(),
            option_d=opt_d.value.strip(),
            correct_answer=correct_dd.value,
            subject=subj.value.strip(),
            topic=topic_f.value.strip(),
            explanation=expl.value.strip(),
        )
        if is_edit:
            repo.update_mcq(mcq)
            show_success("MCQ updated.")
        else:
            repo.add_mcq(mcq)
            show_success("MCQ saved! Fill in another or go back.")
            for f in [q, opt_a, opt_b, opt_c, opt_d, expl]:
                f.value = ""
            correct_dd.value = None
        page.update()

    back_route = "library" if is_edit else "library"

    top_bar = ft.Container(
        content=ft.Row(
            [
                ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, icon_color=T.TEXT2,
                              on_click=lambda _: navigate(back_route)),
                ft.Text("Edit MCQ" if is_edit else "New MCQ",
                        size=20, weight=ft.FontWeight.BOLD, color=T.TEXT),
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
                    correct_dd,
                    expl,
                    ft.Row([subj, topic_f], spacing=10),
                    error_text,
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text("Save" if is_edit else "Save MCQ",
                                                color="white", weight=ft.FontWeight.BOLD, size=14),
                                bgcolor=T.ACCENT,
                                border_radius=10,
                                padding=ft.Padding.symmetric(vertical=13, horizontal=24),
                                on_click=save,
                            ),
                            ft.Container(
                                content=ft.Text("Cancel", color=T.TEXT2, size=14),
                                border=ft.Border.all(1, T.BORDER),
                                border_radius=10,
                                padding=ft.Padding.symmetric(vertical=13, horizontal=20),
                                on_click=lambda _: navigate(back_route),
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
