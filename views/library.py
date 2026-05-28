import flet as ft
from core.database import AbstractRepository
from core import theme as T


def build(page: ft.Page, repo: AbstractRepository, navigate) -> ft.Control:
    expanded: set[str] = set()
    subject_list = ft.Column(spacing=10)

    def refresh():
        subject_stats = repo.get_subject_stats()
        subject_list.controls.clear()

        for info in subject_stats:
            subj = info["subject"]
            color = T.subject_color(subj)
            initial = subj[0].upper()
            is_open = subj in expanded

            topic_stats = repo.get_topic_stats(subj) if is_open else []

            topic_rows = []
            for t in topic_stats:
                topic_rows.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Container(width=8),
                                ft.Container(
                                    content=ft.Icon(ft.Icons.TOPIC_OUTLINED, color=T.TEXT2, size=16),
                                    width=36,
                                    height=36,
                                    bgcolor=T.CARD2,
                                    border_radius=10,
                                    alignment=ft.Alignment.CENTER,
                                ),
                                ft.Column(
                                    [
                                        ft.Text(t["topic"], color=T.TEXT, size=13, weight=ft.FontWeight.W_500),
                                        ft.Text(
                                            f"{t['total']} Cards  •  Mastered: {t['mastery_pct']}%",
                                            color=T.TEXT2,
                                            size=11,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Icon(ft.Icons.CHEVRON_RIGHT, color=T.TEXT2, size=18),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                        padding=ft.Padding.symmetric(vertical=10, horizontal=12),
                        border=ft.Border.only(top=ft.BorderSide(1, T.BORDER)),
                        on_click=lambda _, s=subj, tp=t["topic"]: navigate(
                            "study", data={"subject": s, "topic": tp}
                        ),
                    )
                )

            header = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Text(initial, color="white", weight=ft.FontWeight.BOLD, size=20),
                            width=52,
                            height=52,
                            bgcolor=color,
                            border_radius=12,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text(subj, color=T.TEXT, size=16, weight=ft.FontWeight.BOLD),
                                ft.Text(
                                    f"{info['topics']} Topics  •  {info['total']} Cards",
                                    color=T.TEXT2,
                                    size=12,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        ft.Icon(
                            ft.Icons.KEYBOARD_ARROW_DOWN if is_open else ft.Icons.KEYBOARD_ARROW_RIGHT,
                            color=T.TEXT2,
                            size=22,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                ),
                padding=ft.Padding.symmetric(vertical=14, horizontal=14),
                on_click=lambda _, s=subj: _toggle(s),
            )

            card_controls = [header] + topic_rows

            subject_list.controls.append(
                ft.Container(
                    content=ft.Column(card_controls, spacing=0),
                    bgcolor=T.CARD,
                    border_radius=16,
                    border=ft.Border.all(1, T.BORDER),
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                )
            )

        if not subject_stats:
            subject_list.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.LIBRARY_BOOKS_OUTLINED, color=T.TEXT2, size=48),
                            ft.Text("No subjects yet.", color=T.TEXT, size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("Create MCQs with a subject to see them here.", color=T.TEXT2, size=13),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                )
            )

        page.update()

    def _toggle(subject: str):
        if subject in expanded:
            expanded.discard(subject)
        else:
            expanded.add(subject)
        refresh()

    refresh()

    # --- Import promo card ---
    promo = ft.Container(
        content=ft.Column(
            [
                ft.Text("Import in Bulk", color="white", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Paste JSON to add many MCQs at once into the database.",
                    color=ft.Colors.with_opacity(0.8, "white"),
                    size=13,
                ),
                ft.Container(height=4),
                ft.Container(
                    content=ft.Text("Get Started", color="white", weight=ft.FontWeight.BOLD, size=13),
                    bgcolor=ft.Colors.with_opacity(0.75, T.BG),
                    border_radius=10,
                    padding=ft.Padding.symmetric(vertical=10, horizontal=16),
                    on_click=lambda _: navigate("import"),
                ),
            ],
            spacing=8,
        ),
        bgcolor=T.ACCENT,
        border_radius=16,
        padding=20,
    )

    top_bar = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Image(src="icon-android.svg", width=28, height=28, fit="contain"),
                        ft.Text("StudyFlow", size=20, weight=ft.FontWeight.BOLD, color=T.TEXT),
                    ],
                    spacing=8,
                ),
                ft.Container(expand=True),
                ft.Container(
                    content=ft.Icon(ft.Icons.PERSON_ROUNDED, color=T.TEXT, size=20),
                    width=38,
                    height=38,
                    bgcolor=T.CARD2,
                    border_radius=19,
                    alignment=ft.Alignment.CENTER,
                ),
            ],
        ),
        padding=ft.Padding(left=0, right=0, top=8, bottom=8),
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
                                    ft.Text("COLLECTION", size=11, color=T.TEXT2, weight=ft.FontWeight.W_600),
                                    ft.Text("Library", size=28, weight=ft.FontWeight.BOLD, color=T.TEXT),
                                ],
                                spacing=0,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.ADD, color="white", size=16),
                                        ft.Text("New Subject", color="white", size=13, weight=ft.FontWeight.BOLD),
                                    ],
                                    spacing=4,
                                ),
                                bgcolor=T.ACCENT,
                                border_radius=10,
                                padding=ft.Padding.symmetric(vertical=10, horizontal=14),
                                on_click=lambda _: navigate("create"),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    subject_list,
                    promo,
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
