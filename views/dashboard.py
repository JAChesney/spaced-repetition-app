from datetime import datetime
import flet as ft
from core.database import AbstractRepository, CachedRepository
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

    # --- Next-due countdown (shown only when nothing is due right now) ---
    next_due_text = ft.Container(visible=False)
    if total_due == 0:
        next_info = repo.get_next_due_info()
        if next_info:
            d = next_info["days_until"]
            n = next_info["count"]
            when = "tomorrow" if d == 1 else f"in {d} days"
            label = f"Next: {n} card{'s' if n != 1 else ''} due {when}"
            next_due_text = ft.Row(
                [
                    ft.Icon(ft.Icons.SCHEDULE_ROUNDED, color=T.ACCENT, size=14),
                    ft.Text(label, size=12, color=T.TEXT2),
                ],
                spacing=6,
            )

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
                next_due_text,
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

    # --- Settings dialog helpers (defined first so cards below can reference them) ---
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

        def _confirm_reset(_):
            dlg.open = False
            page.update()

            confirm_dlg = ft.AlertDialog(
                title=ft.Text("Reset Schedule?", weight=ft.FontWeight.BOLD, color=T.TEXT),
                bgcolor=T.CARD,
                content=ft.Text(
                    "Every card will become due immediately.\n"
                    "Your progress (ease factor, repetitions) will be kept.",
                    color=T.TEXT2, size=13,
                ),
                actions=[
                    ft.TextButton("Cancel",
                                  on_click=lambda _: _close_confirm(),
                                  style=ft.ButtonStyle(color=T.TEXT2)),
                    ft.TextButton("Reset",
                                  on_click=lambda _: _do_reset(),
                                  style=ft.ButtonStyle(color=ft.Colors.ERROR)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                shape=ft.RoundedRectangleBorder(radius=16),
            )

            def _close_confirm():
                confirm_dlg.open = False
                page.update()

            def _do_reset():
                repo.reset_schedule()
                confirm_dlg.open = False
                page.update()
                navigate("dashboard")

            page.overlay.append(confirm_dlg)
            confirm_dlg.open = True
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Session Settings", weight=ft.FontWeight.BOLD, color=T.TEXT),
            bgcolor=T.CARD,
            content=ft.Column(
                [
                    goal_field, due_field, new_field,
                    ft.Divider(height=1, color=T.BORDER),
                    ft.TextButton(
                        "Reset Schedule",
                        icon=ft.Icons.RESTART_ALT_ROUNDED,
                        icon_color=ft.Colors.ERROR,
                        on_click=_confirm_reset,
                        style=ft.ButtonStyle(color=ft.Colors.ERROR),
                    ),
                ],
                spacing=14,
                tight=True,
            ),
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

    def force_sync(_):
        """Wipe the local SQLite cache and re-pull everything from Supabase."""
        if not isinstance(repo, CachedRepository):
            return  # offline / local-only mode — nothing to sync

        sync_status = ft.Text("Syncing…", color=T.TEXT2, size=13)
        dlg = ft.AlertDialog(
            title=ft.Text("Force Sync", weight=ft.FontWeight.BOLD, color=T.TEXT),
            bgcolor=T.CARD,
            content=ft.Column([
                ft.Text(
                    "This will delete the local cache and download all cards\n"
                    "fresh from Supabase. Your review progress stored in\n"
                    "Supabase will NOT be lost.",
                    color=T.TEXT2, size=13,
                ),
                sync_status,
            ], spacing=10, tight=True),
            actions=[
                ft.TextButton("Cancel",
                              on_click=lambda _: _close_dlg(),
                              style=ft.ButtonStyle(color=T.TEXT2)),
                ft.TextButton("Sync Now",
                              on_click=lambda _: _do_sync(),
                              style=ft.ButtonStyle(color=T.ACCENT)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=16),
        )

        def _close_dlg():
            dlg.open = False
            page.update()

        def _do_sync():
            sync_status.value = "Syncing…"
            sync_status.color = T.TEXT2
            page.update()
            try:
                repo.clear_local_cache_and_sync()
                sync_status.value = f"✓ Done — {repo.count_mcqs()} cards loaded from Supabase."
                sync_status.color = T.ACCENT
            except Exception as e:
                sync_status.value = f"✗ Sync failed: {e}"
                sync_status.color = ft.Colors.ERROR
            page.update()

        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # --- First-run sync card (shown only when DB is empty) ---
    first_run_card = ft.Container(visible=False)
    if stats["total"] == 0 and isinstance(repo, CachedRepository):
        first_run_card = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CLOUD_DOWNLOAD_OUTLINED, color=T.ACCENT, size=26),
                            ft.Column(
                                [
                                    ft.Text("No cards yet", color=T.TEXT,
                                            weight=ft.FontWeight.BOLD, size=15),
                                    ft.Text(
                                        "Tap below to download your questions from Supabase.",
                                        color=T.TEXT2, size=12,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.Container(height=10),
                    ft.Container(
                        content=ft.Text(
                            "Sync from Supabase",
                            color="white",
                            weight=ft.FontWeight.BOLD,
                            size=14,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        bgcolor=T.ACCENT,
                        border_radius=12,
                        padding=ft.Padding.symmetric(vertical=12),
                        alignment=ft.Alignment.CENTER,
                        on_click=force_sync,
                    ),
                ],
                spacing=0,
            ),
            bgcolor=ft.Colors.with_opacity(0.12, T.ACCENT),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.35, T.ACCENT)),
            border_radius=14,
            padding=16,
        )

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

    # Surface any sync error from startup as a dismissible banner
    if isinstance(repo, CachedRepository) and repo.last_sync_error:
        def _dismiss_banner(_):
            sync_banner.visible = False
            page.update()

        sync_banner = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, color=ft.Colors.AMBER, size=16),
                ft.Text(
                    f"Offline — showing cached data.  ({repo.last_sync_error})",
                    color=ft.Colors.AMBER, size=12, expand=True,
                ),
                ft.IconButton(ft.Icons.CLOSE, icon_size=14,
                              icon_color=ft.Colors.AMBER, on_click=_dismiss_banner),
            ], spacing=8),
            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.4, ft.Colors.AMBER)),
            border_radius=10,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            margin=ft.margin.only(bottom=8),
        )
    else:
        sync_banner = ft.Container(visible=False)

    # --- Top bar ---
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
                        ft.PopupMenuItem(),  # divider
                        ft.PopupMenuItem(
                            content="Force Sync from Supabase",
                            icon=ft.Icons.SYNC_ROUNDED,
                            on_click=force_sync,
                        ),
                    ],
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
                    sync_banner,
                    ft.Text(_greeting(), size=12, color=T.TEXT2, weight=ft.FontWeight.W_600),
                    ft.Text("Ready to flow?", size=26, weight=ft.FontWeight.BOLD, color=T.TEXT),
                    ft.Container(height=4),
                    due_card,
                    progress_card,
                    ft.Container(height=4),
                    first_run_card,
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
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
    )
