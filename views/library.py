import flet as ft
from core.database import AbstractRepository
from core import theme as T


def build(page: ft.Page, repo: AbstractRepository, navigate) -> ft.Control:
    expanded: set[str] = set()
    subject_list = ft.Column(spacing=10)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _icon_btn(icon, color, tooltip, on_click):
        return ft.Container(
            content=ft.Icon(icon, color=color, size=18),
            width=34,
            height=34,
            border_radius=8,
            alignment=ft.Alignment.CENTER,
            tooltip=tooltip,
            on_click=on_click,
        )

    def _confirm_delete(title: str, body: str, on_confirm):
        def _close(_):
            dlg.open = False
            page.update()

        def _do(_):
            dlg.open = False
            page.update()
            on_confirm()

        dlg = ft.AlertDialog(
            title=ft.Text(title, weight=ft.FontWeight.BOLD, color=T.TEXT),
            bgcolor=T.CARD,
            content=ft.Text(body, color=T.TEXT2, size=13),
            actions=[
                ft.TextButton("Cancel", on_click=_close,
                              style=ft.ButtonStyle(color=T.TEXT2)),
                ft.TextButton("Delete", on_click=_do,
                              style=ft.ButtonStyle(color=ft.Colors.ERROR)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=16),
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ── main refresh ─────────────────────────────────────────────────────────

    def refresh():
        subject_stats  = repo.get_subject_stats()
        hidden_subjs   = repo.get_hidden_subjects()
        hidden_tops    = repo.get_hidden_topics()
        subject_list.controls.clear()

        for info in subject_stats:
            subj     = info["subject"]
            color    = T.subject_color(subj)
            initial  = subj[0].upper()
            is_open  = subj in expanded
            is_hidden_subj = subj in hidden_subjs

            # ── topic rows (shown when expanded) ─────────────────────────────
            topic_rows = []
            if is_open:
                for t in repo.get_topic_stats(subj):
                    tp = t["topic"]
                    is_hidden_top = (subj, tp) in hidden_tops

                    def _make_topic_row(s, tp, iht):
                        def _toggle_top_vis(e):
                            e.control.data  # stop bubbling
                            repo.set_topic_hidden(s, tp, not iht)
                            refresh()

                        def _delete_top(e):
                            e.control.data
                            _confirm_delete(
                                f'Delete "{tp}"?',
                                f'All cards in "{tp}" under "{s}" will be permanently deleted.',
                                lambda: _do_delete_topic(s, tp),
                            )

                        eye_icon  = ft.Icons.VISIBILITY_OFF if iht else ft.Icons.VISIBILITY
                        eye_color = ft.Colors.ERROR if iht else T.TEXT2

                        return ft.Container(
                            content=ft.Row(
                                [
                                    ft.Container(width=8),
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.TOPIC_OUTLINED,
                                                        color=T.TEXT2 if not iht else T.BORDER,
                                                        size=16),
                                        width=36, height=36,
                                        bgcolor=T.CARD2,
                                        border_radius=10,
                                        alignment=ft.Alignment.CENTER,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(tp,
                                                    color=T.TEXT2 if iht else T.TEXT,
                                                    size=13,
                                                    weight=ft.FontWeight.W_500),
                                            ft.Text(
                                                f"{t['total']} Cards • {t['due']} Due\nMastered: {t['mastery_pct']}%",
                                                color=T.BORDER if iht
                                                      else (T.WARN if t['due'] > 0 else T.TEXT2),
                                                size=11,
                                            ),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                    _icon_btn(eye_icon, eye_color,
                                              "Hide from sessions" if not iht else "Show in sessions",
                                              _toggle_top_vis),
                                    _icon_btn(ft.Icons.DELETE_OUTLINE_ROUNDED,
                                              ft.Colors.ERROR, "Delete topic",
                                              _delete_top),
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.CHEVRON_RIGHT,
                                                        color=T.TEXT2 if not iht else T.BORDER,
                                                        size=18),
                                        tooltip="Study this topic" if not iht else None,
                                        on_click=(lambda _, s=s, tp=tp:
                                                  navigate("study", data={"subject": s, "topic": tp}))
                                        if not iht else None,
                                    ),
                                ],
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=6,
                            ),
                            padding=ft.Padding.symmetric(vertical=10, horizontal=12),
                            border=ft.Border.only(top=ft.BorderSide(1, T.BORDER)),
                            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ERROR)
                            if iht else ft.Colors.TRANSPARENT,
                        )

                    topic_rows.append(_make_topic_row(subj, tp, is_hidden_top))

            # ── subject header ────────────────────────────────────────────────
            def _make_header(s, ihs, is_op):
                eye_icon  = ft.Icons.VISIBILITY_OFF if ihs else ft.Icons.VISIBILITY
                eye_color = ft.Colors.ERROR if ihs else T.TEXT2

                def _toggle_subj_vis(e):
                    repo.set_subject_hidden(s, not ihs)
                    refresh()

                def _delete_subj(e):
                    _confirm_delete(
                        f'Delete "{s}"?',
                        f'All topics and cards in "{s}" will be permanently deleted. This cannot be undone.',
                        lambda: _do_delete_subject(s),
                    )

                avatar = ft.Container(
                    content=ft.Text(s[0].upper(), color="white",
                                    weight=ft.FontWeight.BOLD, size=20),
                    width=52, height=52,
                    bgcolor=T.subject_color(s) if not ihs
                            else ft.Colors.with_opacity(0.4, T.subject_color(s)),
                    border_radius=12,
                    alignment=ft.Alignment.CENTER,
                )

                # Left tappable area (avatar + name + chevron) triggers expand
                tap_area = ft.GestureDetector(
                    content=ft.Row(
                        [
                            avatar,
                            ft.Column(
                                [
                                    ft.Text(s, color=T.TEXT2 if ihs else T.TEXT,
                                            size=16, weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        f"{info['topics']} Topics • {info['total']} Cards\n"
                                        f"{info['due']} Due",
                                        color=T.BORDER if ihs
                                              else (T.WARN if info['due'] > 0 else T.TEXT2),
                                        size=12,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Icon(
                                ft.Icons.KEYBOARD_ARROW_DOWN if is_op
                                else ft.Icons.KEYBOARD_ARROW_RIGHT,
                                color=T.TEXT2, size=22,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=14,
                        expand=True,
                    ),
                    on_tap=lambda _, sv=s: _toggle(sv),
                    expand=True,
                )

                return ft.Container(
                    content=ft.Row(
                        [
                            tap_area,
                            _icon_btn(eye_icon, eye_color,
                                      "Hide from sessions" if not ihs else "Show in sessions",
                                      _toggle_subj_vis),
                            _icon_btn(ft.Icons.DELETE_OUTLINE_ROUNDED,
                                      ft.Colors.ERROR, "Delete subject",
                                      _delete_subj),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    padding=ft.Padding.symmetric(vertical=14, horizontal=14),
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ERROR)
                    if ihs else ft.Colors.TRANSPARENT,
                )

            header = _make_header(subj, is_hidden_subj, is_open)
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
                            ft.Text("No subjects yet.", color=T.TEXT, size=16,
                                    weight=ft.FontWeight.BOLD),
                            ft.Text("Create MCQs with a subject to see them here.",
                                    color=T.TEXT2, size=13),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                )
            )

        page.update()

    # ── actions ──────────────────────────────────────────────────────────────

    def _toggle(subject: str):
        if subject in expanded:
            expanded.discard(subject)
        else:
            expanded.add(subject)
        refresh()

    def _do_delete_subject(subject: str):
        expanded.discard(subject)
        repo.delete_subject(subject)
        refresh()

    def _do_delete_topic(subject: str, topic: str):
        repo.delete_topic(subject, topic)
        refresh()

    refresh()

    # ── import promo card ─────────────────────────────────────────────────────
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
                    content=ft.Text("Get Started", color="white",
                                    weight=ft.FontWeight.BOLD, size=13),
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
                    width=38, height=38,
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
                                    ft.Text("COLLECTION", size=11, color=T.TEXT2,
                                            weight=ft.FontWeight.W_600),
                                    ft.Text("Library", size=28, weight=ft.FontWeight.BOLD,
                                            color=T.TEXT),
                                ],
                                spacing=0,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Icon(ft.Icons.ADD, color="white", size=16),
                                        ft.Text("New Subject", color="white", size=13,
                                                weight=ft.FontWeight.BOLD),
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
