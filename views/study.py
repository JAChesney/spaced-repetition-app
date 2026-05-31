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
        "correct":  T.ACCENT,
        "wrong":    T.ERROR,
        "other":    T.BORDER,
    }.get(state, T.CARD2)

    badge_text_color = "white" if state != "default" else T.TEXT2

    border_color = {
        "default": T.BORDER,
        "correct": T.ACCENT,
        "wrong":   T.ERROR,
        "other":   T.BORDER,
    }.get(state, T.BORDER)

    card_bg = {
        "default": T.CARD,
        "correct": ft.Colors.with_opacity(0.12, T.ACCENT),
        "wrong":   ft.Colors.with_opacity(0.12, T.ERROR),
        "other":   T.CARD,
    }.get(state, T.CARD)

    trailing = []
    if state == "correct":
        trailing.append(ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=T.ACCENT, size=20))

    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=ft.Text(letter, color=badge_text_color,
                                    weight=ft.FontWeight.BOLD, size=13),
                    width=32,
                    height=32,
                    bgcolor=badge_bg,
                    border_radius=16,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Text(
                    text,
                    color=T.TEXT if state != "other" else T.TEXT2,
                    expand=True,
                    size=14,
                ),
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
          subject: str = "", topic: str = "") -> ft.Control:

    s = settings.load()
    due_cards = repo.get_due_mcqs(limit=s["due_cards_limit"], subject=subject, topic=topic)
    new_cards = repo.get_new_mcqs(limit=s["new_cards_limit"], subject=subject, topic=topic)
    queue = due_cards + new_cards

    if not queue:
        return _empty_state(navigate, subject, topic)

    deck_label = " • ".join(filter(None, [subject.upper(), topic.upper()])) or "ALL CARDS"

    state = {
        "index": 0,
        "answered": False,
        "advancing": False,
        "selected": None,
        "shuffled_correct": None,
        "pairs": [],
    }

    # --- Mutable controls ---
    progress_bar = ft.ProgressBar(value=0, bgcolor=T.BORDER, color=T.ACCENT, height=3)
    question_label = ft.Text("", size=11, color=T.ACCENT, weight=ft.FontWeight.W_600)
    question_text = ft.Text("", size=19, weight=ft.FontWeight.W_500, color=T.TEXT)

    options_col = ft.Column(spacing=8)

    answer_reveal = ft.Container(visible=False)
    explanation_box = ft.Container(visible=False)

    rating_section = ft.Container(visible=False)
    explanation_toggle = ft.Container(visible=False)
    show_exp_state = {"visible": False}

    def current_mcq():
        return queue[state["index"]]

    def rebuild_options(option_states: dict | None = None):
        pairs = state["pairs"]
        option_states = option_states or {}

        def make_click(ltr):
            return (lambda _: handle_answer(ltr)) if option_states.get(ltr, "default") == "default" else None

        options_col.controls = [
            _option_card(
                LETTERS[i],
                pairs[i][1],
                option_states.get(LETTERS[i], "default"),
                on_click=make_click(LETTERS[i]),
            )
            for i in range(4)
        ]

    def load_card():
        mcq = current_mcq()
        state["answered"] = False
        # Do NOT reset "advancing" here — it must stay True until the user
        # selects an answer on the new card, so any queued rating-button taps
        # from a rapid double-click are still blocked.
        state["selected"] = None
        show_exp_state["visible"] = False

        n = state["index"]
        total = len(queue)
        progress_bar.value = n / total
        question_label.value = f"QUESTION {n + 1} OF {total}"
        question_text.value = mcq.question

        pairs = list(zip(LETTERS, [mcq.option_a, mcq.option_b, mcq.option_c, mcq.option_d]))
        random.shuffle(pairs)
        state["pairs"] = pairs
        state["shuffled_correct"] = next(
            LETTERS[i] for i, (orig, _) in enumerate(pairs) if orig == mcq.correct_answer
        )

        rebuild_options()

        answer_reveal.visible = False
        explanation_box.visible = False
        rating_section.visible = False
        explanation_toggle.visible = False
        page.update()

    def handle_answer(selected_letter: str):
        if state["answered"]:
            return
        state["answered"] = True
        state["advancing"] = False  # new card is being answered — re-open the gate
        state["selected"] = selected_letter
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
            weight=ft.FontWeight.BOLD,
            size=15,
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
        explanation_box.visible = show_exp_state["visible"]
        page.update()

    def record_and_advance(quality: int):
        if state["advancing"]:
            return
        state["advancing"] = True

        mcq = current_mcq()
        was_correct = state["selected"] == state["shuffled_correct"]

        progress = repo.get_progress(mcq.id) or CardProgress(mcq_id=mcq.id)

        if quality == 0:
            updated = sm2_review(progress, quality)  # increments progress.again_count internally
            if updated.again_count % 3 == 1:
                queue.append(mcq)  # reappear instantly in session (cycle: instant→10min→6h→repeat)
        else:
            updated = sm2_review(progress, quality)

        updated.last_reviewed_at = datetime.now()
        repo.save_progress(updated)
        repo.add_review_log(ReviewLog(mcq_id=mcq.id, quality=quality, was_correct=was_correct))

        if state["index"] + 1 >= len(queue):
            navigate("complete")
        else:
            state["index"] += 1
            load_card()

    # Wire up explanation toggle
    explanation_toggle.content = ft.Row(
        [
            ft.Icon(ft.Icons.LIGHTBULB_OUTLINE_ROUNDED, color=T.ACCENT, size=16),
            ft.Text("Show Explanation", color=T.ACCENT, size=13),
        ],
        spacing=6,
    )
    explanation_toggle.on_click = toggle_explanation
    explanation_box.content = ft.Text("", color=T.TEXT2, size=13, italic=True)
    explanation_box.bgcolor = ft.Colors.with_opacity(0.06, T.ACCENT)
    explanation_box.border = ft.Border.all(1, ft.Colors.with_opacity(0.2, T.ACCENT))
    explanation_box.border_radius = 10
    explanation_box.padding = 12

    # Rating buttons
    rating_section.content = ft.Column(
        [
            ft.Row(
                [
                    ft.Text("Rate your recall difficulty", color=T.TEXT2, size=12, expand=True),
                    explanation_toggle,
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                [
                    _rating_btn("Again", T.ERROR,   lambda _: record_and_advance(0)),
                    _rating_btn("Hard",  T.WARN,    lambda _: record_and_advance(1)),
                    _rating_btn("Good",  T.SUCCESS, lambda _: record_and_advance(2)),
                    _rating_btn("Easy",  T.TEAL,    lambda _: record_and_advance(3)),
                ],
                spacing=8,
            ),
        ],
        spacing=10,
    )

    load_card()

    return ft.Column(
        [
            _top_bar(deck_label, navigate),
            progress_bar,
            ft.Column(
                [
                    question_label,
                    ft.Container(
                        content=question_text,
                        bgcolor=T.CARD,
                        border_radius=16,
                        padding=ft.Padding.symmetric(horizontal=20, vertical=18),
                        border=ft.Border.all(1, T.BORDER),
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


def _empty_state(navigate, subject: str, topic: str) -> ft.Control:
    label = " › ".join(filter(None, [subject, topic])) or "all cards"
    return ft.Column(
        [
            ft.Container(expand=True),
            ft.Column(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=64, color=T.SUCCESS),
                    ft.Text("All caught up!", size=22, weight=ft.FontWeight.BOLD, color=T.TEXT),
                    ft.Text(f"No cards due for {label}.", color=T.TEXT2, size=14),
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
    stats = repo.get_stats()
    return ft.Column(
        [
            ft.Container(expand=True),
            ft.Column(
                [
                    ft.Icon(ft.Icons.CELEBRATION_ROUNDED, size=64, color=T.ACCENT),
                    ft.Text("Session Complete!", size=24, weight=ft.FontWeight.BOLD, color=T.TEXT),
                    ft.Text(
                        f"You reviewed {stats['reviewed_today']} card(s) today.",
                        color=T.TEXT2,
                        size=15,
                    ),
                    ft.Container(height=8),
                    ft.Row(
                        [
                            ft.Container(
                                content=ft.Text("Dashboard", color="white",
                                                weight=ft.FontWeight.BOLD, size=14),
                                bgcolor=T.ACCENT,
                                border_radius=12,
                                padding=ft.Padding.symmetric(vertical=14, horizontal=24),
                                on_click=lambda _: navigate("dashboard"),
                                expand=True,
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Container(
                                content=ft.Text("Keep Studying", color=T.ACCENT,
                                                weight=ft.FontWeight.BOLD, size=14),
                                border=ft.Border.all(1.5, T.ACCENT),
                                border_radius=12,
                                padding=ft.Padding.symmetric(vertical=14, horizontal=24),
                                on_click=lambda _: navigate("study"),
                                expand=True,
                                alignment=ft.Alignment.CENTER,
                            ),
                        ],
                        spacing=10,
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
