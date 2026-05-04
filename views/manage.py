import flet as ft
from core.database import AbstractRepository
from core.models import MCQ


def build(page: ft.Page, repo: AbstractRepository, navigate, on_edit) -> ft.Control:
    search_field = ft.TextField(
        label="Search questions...",
        prefix_icon=ft.Icons.SEARCH,
        on_change=lambda _: refresh(),
        expand=True,
    )

    subjects = ["All"] + repo.list_subjects()
    subject_filter = ft.Dropdown(
        label="Subject",
        options=[ft.dropdown.Option(s, s) for s in subjects],
        value="All",
        width=180,
        on_text_change=lambda _: refresh(),
    )

    mcq_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    count_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)

    def confirm_delete(mcq: MCQ):
        def do_delete(_):
            repo.delete_mcq(mcq.id)
            page.close(dlg)
            refresh()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete MCQ?"),
            content=ft.Text("This cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: page.close(dlg)),
                ft.TextButton("Delete", on_click=do_delete,
                              style=ft.ButtonStyle(color=ft.Colors.ERROR)),
            ],
        )
        page.open(dlg)

    def build_card(mcq: MCQ) -> ft.Container:
        options_text = (
            f"A. {mcq.option_a}   B. {mcq.option_b}   "
            f"C. {mcq.option_c}   D. {mcq.option_d}"
        )
        return ft.Container(
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(mcq.question, size=14, weight=ft.FontWeight.W_500,
                                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(options_text, size=11, color=ft.Colors.ON_SURFACE_VARIANT,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Row(
                                [
                                    ft.Chip(label=ft.Text(f"Ans: {mcq.correct_answer}"),
                                            padding=ft.Padding.all(0)),
                                    *(
                                        [ft.Chip(label=ft.Text(mcq.subject), padding=ft.Padding.all(0))]
                                        if mcq.subject else []
                                    ),
                                    *(
                                        [ft.Chip(label=ft.Text(mcq.topic), padding=ft.Padding.all(0))]
                                        if mcq.topic else []
                                    ),
                                ],
                                spacing=4,
                                wrap=True,
                            ),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                    ft.Column(
                        [
                            ft.IconButton(
                                ft.Icons.EDIT_OUTLINED,
                                tooltip="Edit",
                                on_click=lambda _, m=mcq: on_edit(m),
                            ),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                tooltip="Delete",
                                icon_color=ft.Colors.ERROR,
                                on_click=lambda _, m=mcq: confirm_delete(m),
                            ),
                        ],
                        spacing=0,
                        horizontal_alignment=ft.CrossAxisAlignment.END,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.START,
                spacing=8,
            ),
            padding=ft.Padding.all(14),
            border_radius=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )

    def refresh():
        subject = "" if subject_filter.value == "All" else subject_filter.value
        mcqs = repo.list_mcqs(subject=subject)
        query = search_field.value.strip().lower()
        if query:
            mcqs = [m for m in mcqs if query in m.question.lower()
                    or query in m.option_a.lower() or query in m.option_b.lower()
                    or query in m.option_c.lower() or query in m.option_d.lower()
                    or query in m.subject.lower() or query in m.topic.lower()]
        count_text.value = f"{len(mcqs)} card{'s' if len(mcqs) != 1 else ''}"
        mcq_list.controls = [build_card(m) for m in mcqs]
        page.update()

    refresh()

    return ft.Column(
        [
            ft.Row(
                [
                    ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: navigate("dashboard")),
                    ft.Text("Manage MCQs", size=22, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Button(
                        "Add MCQ",
                        icon=ft.Icons.ADD,
                        on_click=lambda _: navigate("create"),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row([search_field, subject_filter], spacing=10),
            count_text,
            ft.Divider(height=8, color=ft.Colors.TRANSPARENT),
            mcq_list,
        ],
        spacing=10,
        expand=True,
    )
