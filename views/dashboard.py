from datetime import datetime
import flet as ft
from core.database import AbstractRepository
from core import theme as T
from core import settings


def _greeting() -> str:
    h = datetime.now().hour
    if 5 <= h < 12:
        return "GOOD MORNING"
    if 12 <= h < 17:
        return "GOOD AFTERNOON"
    if 17 <= h < 21:
        return "GOOD EVENING"
    return "GOOD NIGHT"


def _section(title: str, action_label: str = "", on_action=None) -> ft.Row:
    children = [ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=T.TEXT)]
    if action_label:
        children += [
            ft.Container(expand=True),
            ft.TextButton(
                action_label,
                on_click=on_action,
                style=ft.ButtonStyle(color=T.ACCENT),
            ),
        ]
    return ft.Row(children)


def _card(content: ft.Control, padding=16) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=T.CARD,
        border_radius=16,
        padding=padding,
        border=ft.Border.all(1, T.BORDER),
    )


def build(page: ft.Page, repo: AbstractRepository, navigate) -> ft.Control:
    s = settings.load()
    stats = repo.get_stats()
    recent = repo.get_recent_subject_activity(limit=3)
    total_due = stats["due"] + stats["new"]
    reviewed = stats["reviewed_today"]
    daily_goal = s["daily_goal"]
    goal_pct = min(reviewed / daily_goal, 1.0)

    # --- Due Today card ---
    due_card = _card(
        ft.Column(
            [
                ft.Row([
                    ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, color=T.ACCENT, size=20),
                    ft.Text("Due Today", color=T.TEXT2, size=13),
                ], spacing=8),
                ft.Row(
                    [
                        ft.Text(str(total_due), size=48, weight=ft.FontWeight.BOLD, color=T.TEXT),
                        ft.Text("cards", size=16, color=T.TEXT2),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    spacing=8,
                ),
                ft.Container(height=4),
                ft.Container(
                    content=ft.Text(
                        "Start Session",
                        color="white",
                        weight=ft.FontWeight.BOLD,
                        size=15,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    bgcolor=T.ACCENT if total_due > 0 else T.BORDER,
                    border_radius=12,
                    padding=ft.Padding.symmetric(vertical=14),
                    alignment=ft.Alignment.CENTER,
                    on_click=(lambda _: navigate("study")) if total_due > 0 else None,
                ),
            ],
            spacing=8,
        ),
        padding=20,
    )

    # --- Daily Progress card ---
    goal_label = f"{reviewed}/{daily_goal} cards reviewed"
    progress_card = _card(
        ft.Column(
            [
                ft.Stack(
                    [
                        ft.Container(
                            content=ft.ProgressRing(
                                value=goal_pct,
                                width=120,
                                height=120,
                                stroke_width=10,
                                color=T.ACCENT,
                                bgcolor=T.BORDER,
                            ),
                            alignment=ft.Alignment.CENTER,
                            width=120,
                            height=120,
                        ),
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Text(
                                        f"{round(goal_pct * 100)}%",
                                        size=26,
                                        weight=ft.FontWeight.BOLD,
                                        color=T.TEXT,
                                    ),
                                    ft.Text("GOAL", size=11, color=T.TEXT2),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=0,
                            ),
                            left=0,
                            top=0,
                            width=120,
                            height=120,
                        ),
                    ],
                    width=120,
                    height=120,
                ),
                ft.Text(
                    "Daily Progress",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=T.TEXT,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(goal_label, size=13, color=T.TEXT2, text_align=ft.TextAlign.CENTER),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
        padding=24,
    )

    # --- Recent Subjects ---
    def subject_row(info: dict) -> ft.Container:
        color = T.subject_color(info["subject"])
        initial = info["subject"][0].upper()
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Text(initial, color="white", weight=ft.FontWeight.BOLD, size=16),
                        width=44,
                        height=44,
                        bgcolor=color,
                        border_radius=10,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        [
                            ft.Text(info["subject"], color=T.TEXT, size=14, weight=ft.FontWeight.W_500),
                            ft.Text(
                                f"{info['due']} cards due  •  {info['mastery_pct']}% mastery",
                                color=T.TEXT2,
                                size=12,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_RIGHT, color=T.TEXT2, size=20),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            padding=ft.Padding.symmetric(vertical=12, horizontal=16),
            bgcolor=T.CARD,
            border_radius=14,
            border=ft.Border.all(1, T.BORDER),
            on_click=lambda _, s=info["subject"]: navigate("study", data={"subject": s}),
        )

    subject_rows = [subject_row(s) for s in recent] if recent else [
        ft.Container(
            content=ft.Text("No subjects yet. Add some MCQs to get started.", color=T.TEXT2, size=13),
            padding=16,
        )
    ]

    # --- Tip card ---
    if stats["due"] > 0 and recent:
        tip_subject = recent[0]["subject"]
        tip_text = f'"{tip_subject}" has cards due. Review now to maximize retention.'
    elif stats["total"] == 0:
        tip_text = "Add your first MCQ using the + button in the Library tab."
    else:
        tip_text = "You're all caught up! Great work keeping up with your reviews."

    tip_card = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, color=T.ACCENT, size=22),
                ft.Column(
                    [
                        ft.Text("Optimization Tip", color=T.TEXT, weight=ft.FontWeight.BOLD, size=14),
                        ft.Text(tip_text, color=T.TEXT2, size=12),
                    ],
                    spacing=4,
                    expand=True,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.START,
        ),
        bgcolor=ft.Colors.with_opacity(0.12, T.ACCENT),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, T.ACCENT)),
        border_radius=14,
        padding=16,
    )

    # --- Settings dialog ---
    def _num_field(label: str, value: int) -> ft.TextField:
        return ft.TextField(
            label=label,
            value=str(value),
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor=T.CARD2,
            border_color=T.BORDER,
            focused_border_color=T.ACCENT,
            color=T.TEXT,
            label_style=ft.TextStyle(color=T.TEXT2),
            text_size=14,
            border_radius=10,
        )

    def open_settings(_):
        cur = settings.load()
        goal_field = _num_field("Daily Goal (cards/day)", cur["daily_goal"])
        due_field  = _num_field("Due Cards per Session",  cur["due_cards_limit"])
        new_field  = _num_field("New Cards per Session",  cur["new_cards_limit"])

        def _save(_):
            settings.save({
                "daily_goal":       max(1, int(goal_field.value or 20)),
                "due_cards_limit":  max(1, int(due_field.value  or 50)),
                "new_cards_limit":  max(0, int(new_field.value  or 20)),
            })
            dlg.open = False
            page.update()

        def _cancel(_):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Session Settings", weight=ft.FontWeight.BOLD, color=T.TEXT),
            bgcolor=T.CARD,
            content=ft.Column([goal_field, due_field, new_field], spacing=14, tight=True),
            actions=[
                ft.TextButton("Cancel", on_click=_cancel,
                              style=ft.ButtonStyle(color=T.TEXT2)),
                ft.TextButton("Save",   on_click=_save,
                              style=ft.ButtonStyle(color=T.ACCENT)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=16),
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # --- Top bar ---
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
                ft.Container(expand=True),
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT,
                    icon_color=T.TEXT,
                    items=[
                        ft.PopupMenuItem(
                            content="Session Settings",
                            icon=ft.Icons.TUNE_ROUNDED,
                            on_click=open_settings,
                        ),
                        ft.PopupMenuItem(),  # divider
                        ft.PopupMenuItem(
                            content="Manage & Edit MCQs",
                            icon=ft.Icons.EDIT_NOTE_ROUNDED,
                            on_click=lambda _: navigate("manage"),
                        ),
                    ],
                ),
            ],
        ),
        padding=ft.Padding.symmetric(horizontal=20, vertical=14),
    )

    return ft.Column(
        [
            top_bar,
            ft.Column(
                [
                    ft.Text(_greeting(), size=12, color=T.TEXT2, weight=ft.FontWeight.W_600),
                    ft.Text("Ready to flow?", size=26, weight=ft.FontWeight.BOLD, color=T.TEXT),
                    ft.Container(height=4),
                    due_card,
                    progress_card,
                    ft.Container(height=4),
                    _section("Recent Subjects", "View Library", on_action=lambda _: navigate("library")),
                    ft.Column(subject_rows, spacing=8),
                    ft.Container(height=4),
                    tip_card,
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
