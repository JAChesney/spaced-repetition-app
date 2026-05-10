import threading
import flet as ft
from core.database import AbstractRepository
from core.models import MCQ

PAGE_SIZE = 50


def build(page: ft.Page, repo: AbstractRepository, navigate, on_edit) -> ft.Control:
    # --- mutable state via lists (closure-safe) ---
    state = {"page": 0, "timer": None}

    search_field = ft.TextField(
        label="Search questions...",
        prefix_icon=ft.Icons.SEARCH,
        on_change=lambda _: _debounce_search(),
        expand=True,
    )

    subjects = ["All"] + repo.list_subjects()
    subject_filter = ft.Dropdown(
        label="Subject",
        options=[ft.dropdown.Option(s, s) for s in subjects],
        value="All",
        width=180,
        on_text_change=lambda _: _reset_and_refresh(),
    )

    mcq_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    count_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)

    prev_btn = ft.IconButton(ft.Icons.CHEVRON_LEFT, tooltip="Previous page", disabled=True,
                             icon_size=18, padding=ft.Padding.all(4),
                             on_click=lambda _: _go_page(state["page"] - 1))
    next_btn = ft.IconButton(ft.Icons.CHEVRON_RIGHT, tooltip="Next page", disabled=True,
                             icon_size=18, padding=ft.Padding.all(4),
                             on_click=lambda _: _go_page(state["page"] + 1))
    page_label = ft.Text("", size=12, width=90, text_align=ft.TextAlign.CENTER)

    def _debounce_search():
        if state["timer"]:
            state["timer"].cancel()
        state["timer"] = threading.Timer(0.35, _reset_and_refresh)
        state["timer"].start()

    def _reset_and_refresh():
        state["page"] = 0
        refresh()

    def _go_page(n: int):
        state["page"] = n
        refresh()

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
        query = search_field.value.strip()
        offset = state["page"] * PAGE_SIZE

        total = repo.count_mcqs(subject=subject, search=query)
        mcqs = repo.list_mcqs(subject=subject, search=query, limit=PAGE_SIZE, offset=offset)

        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        showing_start = offset + 1 if total else 0
        showing_end = min(offset + PAGE_SIZE, total)
        count_text.value = (
            f"{total} card{'s' if total != 1 else ''}"
            + (f" — showing {showing_start}–{showing_end}" if total > PAGE_SIZE else "")
        )

        mcq_list.controls = [build_card(m) for m in mcqs]

        page_label.value = f"Page {state['page'] + 1} of {total_pages}"
        prev_btn.disabled = state["page"] == 0
        next_btn.disabled = state["page"] >= total_pages - 1

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
            ft.Row(
                [
                    ft.Container(content=count_text, expand=True),
                    ft.Row(
                        [prev_btn, page_label, next_btn],
                        spacing=0,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Divider(height=4, color=ft.Colors.TRANSPARENT),
            mcq_list,
        ],
        spacing=10,
        expand=True,
    )
