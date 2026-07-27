import random
import flet as ft
from datetime import datetime
from core.database import AbstractRepository
from core.models import CardProgress, ReviewLog
from core.spaced_repetition import review as sm2_review
from core import theme as T
from core import settings

LETTERS = ["A", "B", "C", "D"]


def _top_bar(deck_label: str, navigate) -> ft.Container:
    return ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Image(src="icon-android.svg", width=28, height=28, fit="contain"),
                        ft.Column(
                            [
                                ft.Text("StudyFlow", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT),
                                ft.Text(deck_label, size=10, color=T.TEXT2),
                            ],
                            spacing=0,
                        ),
                    ],
                    spacing=8,
                    expand=True,
                ),
                ft.IconButton(
                    ft.Icons.CLOSE_ROUNDED,
                    icon_color=T.TEXT2,
                    on_click=lambda _: navigate("dashboard"),
                    tooltip="Exit",
                ),
            ],
        ),
        padding=ft.Padding(left=0, right=0, top=8, bottom=8),
    )


def _option_card(letter: str, text: str, state: str, on_click=None) -> ft.Container:
    badge_bg = {
        "default":  T.CARD2,
        "correct":  T.SUCCESS,
        "wrong":    T.ERROR,
        "other":    T.BORDER,
    }.get(state, T.CARD2)

    badge_text_color = "white" if state != "default" else T.TEXT2

    border_color = {
        "default": T.BORDER,
        "correct": T.SUCCESS,
        "wrong":   T.ERROR,
        "other":   T.BORDER,
    }.get(state, T.BORDER)

    card_bg = {
        "default": T.CARD,
        "correct": ft.Colors.with_opacity(0.12, T.SUCCESS),
        "wrong":   ft.Colors.with_opacity(0.12, T.ERROR),
        "other":   T.CARD,
    }.get(state, T.CARD)

    trailing = []
    if state == "correct":
        trailing.append(ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=T.SUCCESS, size=20))

    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Text(letter, color=badge_text_color,
                                    weight=ft.FontWeight.BOLD, size=13),
                    width=32, height=32,
                    bgcolor=badge_bg,
                    border_radius=16,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Text(text, color=T.TEXT if state != "other" else T.TEXT2,
                        expand=True, size=14),
                *trailing,
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        border=ft.Border.all(1.5, border_color),
        border_radius=14,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
        bgcolor=card_bg,
        on_click=on_click,
        data=letter,
    )


def _rating_btn(label: str, color: str, on_click) -> ft.Container:
    return ft.Container(
        content=ft.Text(label, color=color, weight=ft.FontWeight.BOLD, size=13,
                        text_align=ft.TextAlign.CENTER),
        border=ft.Border.all(1.5, color),
        bgcolor=ft.Colors.with_opacity(0.1, color),
        border_radius=12,
        padding=ft.Padding.symmetric(vertical=14),
        expand=True,
        alignment=ft.Alignment.CENTER,
        on_click=on_click,
    )


def build(page: ft.Page, repo: AbstractRepository, navigate,
          subject: str = "", topic: str = "",
          is_review_session: bool = False) -> ft.Control:

    s = settings.load()
    session_size = s.get("session_size", 100)

    # ── Build queue ───────────────────────────────────────────────────────
    if is_review_session:
        queue = repo.get_review_pool_mcqs(limit=session_size, subject=subject, topic=topic)
    else:
        due   = repo.get_due_mcqs(limit=session_size, subject=subject, topic=topic)
        slots = max(0, session_size - len(due))
        new   = repo.get_new_mcqs(limit=slots, subject=subject, topic=topic) if slots > 0 else []
        queue = due + new
        random.shuffle(queue)

    if not queue:
        return _empty_state(navigate, subject, topic, is_review_session)

    # initial_size is fixed; re-queued Again cards extend the list but are bonus
    initial_size  = len(queue)
    requeued_ids: set[int] = set()   # each card re-queued at most once per session

    deck_label = (
        "REVIEW SESSION"
        if is_review_session
        else (" • ".join(filter(None, [subject.upper(), topic.upper()])) or "ALL CARDS")
    )

    # ── UI state ──────────────────────────────────────────────────────────
    state = {
        "index":    0,
        "answered": False,
        "advancing": False,
        "selected": None,
        "shuffled_correct": None,
        "pairs": [],
    }

    progress_bar     = ft.ProgressBar(value=0, bgcolor=T.BORDER, color=T.ACCENT if not is_review_session else T.WARN, height=3)
    question_label   = ft.Text("", size=11, color=T.ACCENT if not is_review_session else T.WARN, weight=ft.FontWeight.W_600)
    question_text    = ft.Text("", size=19, weight=ft.FontWeight.W_500, color=T.TEXT)
    options_col      = ft.Column(spacing=8)
    answer_reveal    = ft.Container(visible=False)
    explanation_box  = ft.Container(visible=False)
    rating_section   = ft.Container(visible=False)
    explanation_toggle = ft.Container(visible=False)
    show_exp_state   = {"visible": False}

    def current_mcq():
        return queue[state["index"]]

    def rebuild_options(option_states: dict | None = None):
        pairs = state["pairs"]
        option_states = option_states or {}

        def make_click(ltr):
            return (lambda _: handle_answer(ltr)) if option_states.get(ltr, "default") == "default" else None

        options_col.controls = [
            _option_card(
                LETTERS[i], pairs[i][1],
                option_states.get(LETTERS[i], "default"),
                on_click=make_click(LETTERS[i]),
            )
            for i in range(4)
        ]

    def load_card():
        mcq = current_mcq()
        state["answered"]  = False
        state["selected"]  = None
        show_exp_state["visible"] = False

        card_progress = repo.get_progress(mcq.id)
        is_drill = is_review_session and bool(card_progress) and card_progress.review_tag == "drill"
        _build_rating_section(is_drill)

        n     = state["index"]
        total = len(queue)
        progress_bar.value   = n / total
        question_label.value = (
            f"{'REVIEW ' if is_review_session else ''}QUESTION {n + 1} OF {total}"
            f"  •  ID: {mcq.public_id or '—'}"
        )
        question_text.value  = mcq.question

        pairs = list(zip(LETTERS, [mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d]))
        random.shuffle(pairs)
        state["pairs"] = pairs
        state["shuffled_correct"] = next(
            LETTERS[i] for i, (orig, _) in enumerate(pairs) if orig == mcq.correct_answer
        )

        rebuild_options()
        answer_reveal.visible    = False
        explanation_box.visible  = False
        rating_section.visible   = False
        explanation_toggle.visible = False
        page.update()

    def handle_answer(selected_letter: str):
        if state["answered"]:
            return
        state["answered"]  = True
        state["advancing"] = False
        state["selected"]  = selected_letter
        correct = state["shuffled_correct"]

        states = {}
        for ltr in LETTERS:
            if ltr == correct:
                states[ltr] = "correct"
            elif ltr == selected_letter:
                states[ltr] = "wrong"
            else:
                states[ltr] = "other"

        rebuild_options(states)

        was_correct = selected_letter == correct
        answer_reveal.content = ft.Text(
            "Correct!" if was_correct else f"Incorrect — correct answer: {correct}",
            color=T.SUCCESS if was_correct else T.ERROR,
            weight=ft.FontWeight.BOLD, size=15,
        )
        answer_reveal.visible = True

        mcq = current_mcq()
        if mcq.explanation:
            explanation_box.content = ft.Text(mcq.explanation, color=T.TEXT2, size=13, italic=True)
            explanation_toggle.visible = True

        rating_section.visible = True
        page.update()

    def toggle_explanation(_):
        show_exp_state["visible"] = not show_exp_state["visible"]
        explanation_box.visible   = show_exp_state["visible"]
        page.update()

    def record_and_advance(quality: int):
        if state["advancing"]:
            return
        state["advancing"] = True

        mcq         = current_mcq()
        was_correct = state["selected"] == state["shuffled_correct"]
        is_retry    = mcq.id in requeued_ids

        progress  = repo.get_progress(mcq.id) or CardProgress(mcq_id=mcq.id)
        was_drill = is_review_session and progress.review_tag == "drill"

        # Drill cards always use the single forced button (Hard/1-day); everything
        # else — normal cards, retries, and resurfaced echo cards — uses the real rating.
        effective_quality = 1 if was_drill else quality

        updated = sm2_review(progress, effective_quality)
        updated.last_reviewed_at = datetime.now()

        if was_drill:
            updated.review_tag = ""   # one pass through the review session clears drill
        elif is_retry:
            # Retry resolved: corrected → echo (real rating sticks); wrong again → drill
            updated.review_tag = "echo" if effective_quality != 0 else "drill"
        # else: leave review_tag as loaded — untagged cards stay untagged until a
        # retry resolves; resurfaced echo cards keep their tag while cycling

        repo.save_progress(updated)
        repo.add_review_log(ReviewLog(mcq_id=mcq.id, quality=quality, was_correct=was_correct))

        # A fresh wrong rating gets one immediate re-attempt, in any session
        if effective_quality == 0 and not is_retry:
            requeued_ids.add(mcq.id)
            queue.append(mcq)

        if state["index"] + 1 >= len(queue):
            navigate("complete")
        else:
            state["index"] += 1
            load_card()

    # ── Wire up explanation toggle ────────────────────────────────────────
    explanation_toggle.content = ft.Row(
        [
            ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, color=T.ACCENT, size=16),
            ft.Text("Show Explanation", color=T.ACCENT, size=13),
        ],
        spacing=6,
    )
    explanation_toggle.on_click = toggle_explanation
    explanation_box.content     = ft.Text("", color=T.TEXT2, size=13, italic=True)
    explanation_box.bgcolor     = ft.Colors.with_opacity(0.06, T.ACCENT)
    explanation_box.border      = ft.Border.all(1, ft.Colors.with_opacity(0.2, T.ACCENT))
    explanation_box.border_radius = 10
    explanation_box.padding     = 12

    # ── Rating buttons ────────────────────────────────────────────────────
    def _build_rating_section(is_drill: bool):
        if is_drill:
            # Drill cards (wrong twice, never corrected) get one forced button —
            # answering it, right or wrong, always clears the tag.
            rating_section.content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Drill card — comes back tomorrow, then rejoins normal review",
                                    color=T.TEXT2, size=12, expand=True),
                            explanation_toggle,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text("Next  •  Back Tomorrow", color="white",
                                                weight=ft.FontWeight.BOLD, size=14,
                                                text_align=ft.TextAlign.CENTER),
                                bgcolor=T.WARN, border_radius=12,
                                padding=ft.Padding.symmetric(vertical=14),
                                expand=True, alignment=ft.Alignment.CENTER,
                                on_click=lambda _: record_and_advance(1),
                            )
                        ],
                        spacing=8,
                    ),
                ],
                spacing=10,
            )
        else:
            # Normal cards, in-session retries, and resurfaced echo cards all get
            # the real rating buttons.
            rating_section.content = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Rate your recall difficulty",
                                    color=T.TEXT2, size=12, expand=True),
                            explanation_toggle,
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            _rating_btn("Again",          T.ERROR,   lambda _: record_and_advance(0)),
                            _rating_btn("Hard\n(1 day)",  T.WARN,    lambda _: record_and_advance(1)),
                            _rating_btn("Good\n(2 days)", T.SUCCESS, lambda _: record_and_advance(2)),
                            _rating_btn("Easy\n(3 days)", T.TEAL,    lambda _: record_and_advance(3)),
                        ],
                        spacing=8,
                    ),
                ],
                spacing=10,
            )

    load_card()

    # Amber banner shown only in review sessions
    review_banner = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.REPLAY_ROUNDED, color=T.WARN, size=16),
                ft.Text("REVIEW SESSION — drill cards reset tomorrow, others follow your rating",
                        color=T.WARN, size=12, weight=ft.FontWeight.W_600,
                        expand=True),
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.with_opacity(0.12, T.WARN),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.35, T.WARN)),
        border_radius=10,
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        visible=is_review_session,
    )

    return ft.Column(
        [
            _top_bar(deck_label, navigate),
            progress_bar,
            ft.Column(
                [
                    review_banner,
                    question_label,
                    ft.Container(
                        content=question_text,
                        bgcolor=T.CARD,
                        border_radius=16,
                        padding=ft.Padding.symmetric(horizontal=20, vertical=18),
                        border=ft.Border.all(
                            1.5 if is_review_session else 1,
                            T.WARN if is_review_session else T.BORDER,
                        ),
                    ),
                    options_col,
                    answer_reveal,
                    explanation_box,
                    rating_section,
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


def _empty_state(navigate, subject: str, topic: str,
                 is_review_session: bool = False) -> ft.Control:
    if is_review_session:
        icon  = ft.Icons.REVIEWS_OUTLINED
        title = "No review cards yet"
        body  = "Cards you got wrong once (echo) or twice in a row (drill) show up here once due."
    else:
        label = " › ".join(filter(None, [subject, topic])) or "all cards"
        icon  = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
        title = "All caught up!"
        body  = f"No cards due for {label}."

    return ft.Column(
        [
            ft.Container(expand=True),
            ft.Column(
                [
                    ft.Icon(icon, size=64, color=T.SUCCESS),
                    ft.Text(title, size=22, weight=ft.FontWeight.BOLD, color=T.TEXT),
                    ft.Text(body, color=T.TEXT2, size=14),
                    ft.Container(height=8),
                    ft.Container(
                        content=ft.Text("Back to Dashboard", color="white",
                                        weight=ft.FontWeight.BOLD, size=14),
                        bgcolor=T.ACCENT,
                        border_radius=12,
                        padding=ft.Padding.symmetric(vertical=14, horizontal=24),
                        on_click=lambda _: navigate("dashboard"),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            ft.Container(expand=True),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )


def build_complete(repo: AbstractRepository, navigate) -> ft.Control:
    stats       = repo.get_stats()
    review_pool = repo.get_review_pool_mcqs(limit=500)
    more_normal = bool(repo.get_due_mcqs(limit=1) or repo.get_new_mcqs(limit=1))

    buttons: list[ft.Control] = []

    if review_pool:
        buttons.append(ft.Container(
            content=ft.Text(f"Start Review  •  {len(review_pool)} cards",
                            color="white", weight=ft.FontWeight.BOLD, size=14,
                            text_align=ft.TextAlign.CENTER),
            bgcolor=T.WARN, border_radius=12,
            padding=ft.Padding.symmetric(vertical=14, horizontal=24),
            on_click=lambda _: navigate("study", data={"review": True}),
            expand=True, alignment=ft.Alignment.CENTER,
        ))

    if more_normal:
        buttons.append(ft.Container(
            content=ft.Text("Keep Studying", color="white",
                            weight=ft.FontWeight.BOLD, size=14),
            bgcolor=T.ACCENT, border_radius=12,
            padding=ft.Padding.symmetric(vertical=14, horizontal=24),
            on_click=lambda _: navigate("study"),
            expand=True, alignment=ft.Alignment.CENTER,
        ))

    buttons.append(ft.Container(
        content=ft.Text("Dashboard", color=T.ACCENT,
                        weight=ft.FontWeight.BOLD, size=14),
        border=ft.Border.all(1.5, T.ACCENT), border_radius=12,
        padding=ft.Padding.symmetric(vertical=14, horizontal=24),
        on_click=lambda _: navigate("dashboard"),
        expand=True, alignment=ft.Alignment.CENTER,
    ))

    if review_pool:
        sub_note = ft.Text(
            f"{len(review_pool)} wrong card(s) pooled for review.",
            color=T.WARN, size=13, text_align=ft.TextAlign.CENTER,
        )
    else:
        sub_note = ft.Text(
            "No wrong cards to review — great session!",
            color=T.TEXT2, size=12, italic=True, text_align=ft.TextAlign.CENTER,
        )

    # Pair buttons into rows of 2
    btn_rows: list[ft.Control] = []
    for i in range(0, len(buttons), 2):
        btn_rows.append(ft.Row(buttons[i:i+2], spacing=10))

    return ft.Column(
        [
            ft.Container(expand=True),
            ft.Column(
                [
                    ft.Icon(ft.Icons.CELEBRATION_ROUNDED, size=64, color=T.ACCENT),
                    ft.Text("Session Complete!", size=24, weight=ft.FontWeight.BOLD, color=T.TEXT),
                    ft.Text(f"You reviewed {stats['reviewed_today']} card(s) today.",
                            color=T.TEXT2, size=15),
                    sub_note,
                    ft.Container(height=8),
                    *btn_rows,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            ft.Container(expand=True),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
    )
