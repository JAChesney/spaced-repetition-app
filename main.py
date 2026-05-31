import flet as ft
import os
import asyncio
from pathlib import Path
from core.database import CachedRepository
from core import theme as T


def _load_env(path: Path) -> None:
    """Minimal .env loader — no external dependency, works on Android."""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    except FileNotFoundError:
        pass


_load_env(Path(__file__).parent / ".env")

_NAV_ITEMS = [
    ("Dashboard", ft.Icons.GRID_VIEW_OUTLINED,      ft.Icons.GRID_VIEW_ROUNDED),
    ("Library",   ft.Icons.LIBRARY_BOOKS_OUTLINED,  ft.Icons.LIBRARY_BOOKS),
    ("Import",    ft.Icons.UPLOAD_FILE_OUTLINED,     ft.Icons.UPLOAD_FILE),
    ("Study",     ft.Icons.PSYCHOLOGY_OUTLINED,      ft.Icons.PSYCHOLOGY),
]
_TAB_ROUTES = ["dashboard", "library", "import", "study"]


def main(page: ft.Page):
    page.title = "StudyFlow"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = T.BG
    page.padding = 0
    page.window.min_width = 360
    page.window.min_height = 640

    # Set custom app icon (Flet on Windows requires .ico format)
    _icon_path = os.path.join(os.path.dirname(__file__), "assets", "icon.ico")
    if os.path.exists(_icon_path):
        page.window.icon = _icon_path

    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_KEY", "")

    async def _launch():
        loop = asyncio.get_event_loop()

        # Start repo init (Supabase sync) in a thread so it races the 2s splash.
        if supabase_url and supabase_key:
            repo_future = loop.run_in_executor(
                None,
                lambda: CachedRepository(supabase_url=supabase_url, supabase_key=supabase_key),
            )
        else:
            repo_future = None

        # On desktop show a branded splash for 2s. On Android the native splash
        # already handles this — adding a Python splash there causes a squished
        # flicker followed by a blank frame, so we skip it.
        is_android = str(page.platform).lower() == "android"
        if not is_android:
            page.add(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Image(src="assets/icon.png", width=160, height=160, fit="contain"),
                            ft.Text("StudyFlow", size=32, weight=ft.FontWeight.BOLD, color=T.TEXT),
                            ft.Text("Spaced Repetition Learning", size=18, color=T.TEXT2),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=16,
                    ),
                    expand=True,
                    bgcolor="#1B2444",
                    alignment=ft.Alignment.CENTER,
                )
            )
            page.update()
            await asyncio.sleep(2)

        # Switch to skeleton while waiting for Supabase sync to finish.
        page.controls.clear()
        from views.dashboard import build_skeleton
        skeleton, stop_pulse = build_skeleton(page)
        page.add(
            ft.Container(
                content=skeleton,
                expand=True,
                bgcolor=T.BG,
                padding=ft.Padding(left=20, right=20, top=46, bottom=0),
            )
        )
        page.update()

        if not supabase_url or not supabase_key:
            stop_pulse[0] = False
            page.controls.clear()
            page.add(ft.Text(
                f"Missing credentials.\n.env path: {Path(__file__).parent / '.env'}\n"
                f"Exists: {(Path(__file__).parent / '.env').exists()}",
                color=ft.Colors.ERROR, selectable=True,
            ))
            page.update()
            return

        try:
            repo = await repo_future
        except Exception:
            stop_pulse[0] = False
            import traceback
            page.controls.clear()
            page.add(ft.Text(
                f"Repo init error:\n{traceback.format_exc()}",
                color=ft.Colors.ERROR, selectable=True,
            ))
            page.update()
            return

        stop_pulse[0] = False
        page.controls.clear()
        page.update()
        _start_app(page, repo)

    page.run_task(_launch)


def _start_app(page: ft.Page, repo: CachedRepository):
    content = ft.Column(expand=True, spacing=0)
    selected_index = [0]

    def _build_nav():
        def _item(i, label, icon, sel_icon):
            active = i == selected_index[0]
            return ft.GestureDetector(
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Icon(
                                sel_icon if active else icon,
                                color=T.ACCENT if active else T.TEXT2,
                                size=24,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.15, T.ACCENT) if active else ft.Colors.TRANSPARENT,
                            border_radius=14,
                            padding=ft.Padding.symmetric(vertical=3, horizontal=14),
                        ),
                        ft.Text(label, size=10,
                                color=T.ACCENT if active else T.TEXT2,
                                weight=ft.FontWeight.W_600 if active else ft.FontWeight.NORMAL),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                ),
                on_tap=lambda _, idx=i: navigate(_TAB_ROUTES[idx]),
                expand=True,
            )

        return ft.Container(
            content=ft.Row(
                [_item(i, lbl, ico, sel) for i, (lbl, ico, sel) in enumerate(_NAV_ITEMS)],
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                expand=True,
            ),
            bgcolor="#0F1729",
            padding=ft.Padding(left=4, right=4, top=6, bottom=10),
        )

    nav_container = ft.Container(content=_build_nav(), bgcolor="#0F1729")

    def navigate(route: str, data=None):
        content.controls.clear()

        if route == "dashboard":
            selected_index[0] = 0
            import views.dashboard as vdash

            # Show dashboard immediately from local data — no skeleton flash.
            content.controls.append(vdash.build(page, repo, navigate))

            async def _refresh_dashboard():
                loop = asyncio.get_event_loop()
                # First refresh: pull from Supabase then silently update.
                await loop.run_in_executor(None, repo.soft_sync)
                if selected_index[0] != 0:
                    return
                content.controls.clear()
                content.controls.append(vdash.build(page, repo, navigate))
                page.update()

                # Keep refreshing while the dashboard is open.
                while selected_index[0] == 0:
                    next_info = repo.get_next_due_info()
                    secs = next_info["seconds_until"] if next_info else 30
                    await asyncio.sleep(min(secs, 30))
                    if selected_index[0] != 0:
                        break
                    await loop.run_in_executor(None, repo.soft_sync)
                    if selected_index[0] != 0:
                        break
                    content.controls.clear()
                    content.controls.append(vdash.build(page, repo, navigate))
                    page.update()

            page.run_task(_refresh_dashboard)

        elif route == "library":
            selected_index[0] = 1
            import views.library as v
            content.controls.append(v.build(page, repo, navigate))

        elif route == "import":
            selected_index[0] = 2
            import views.import_view as v
            content.controls.append(v.build(page, repo, navigate))

        elif route == "study":
            selected_index[0] = 3
            subject = data.get("subject", "") if isinstance(data, dict) else ""
            topic = data.get("topic", "") if isinstance(data, dict) else ""
            import views.study as v
            content.controls.append(v.build(page, repo, navigate, subject=subject, topic=topic))

        elif route == "complete":
            selected_index[0] = 3
            import views.study as v
            content.controls.append(v.build_complete(repo, navigate))

        elif route == "create":
            selected_index[0] = -1  # stops the dashboard refresh loop
            import views.create_mcq as v
            content.controls.append(v.build(page, repo, navigate))

        elif route == "edit":
            selected_index[0] = -1
            import views.create_mcq as v
            content.controls.append(v.build(page, repo, navigate, edit_mcq=data))

        elif route == "manage":
            selected_index[0] = -1
            import views.manage as v
            content.controls.append(
                v.build(page, repo, navigate, on_edit=lambda m: navigate("edit", data=m))
            )

        nav_container.content = _build_nav()
        page.update()

    navigate("dashboard")
    page.add(
        ft.Container(
            content=ft.Column(
                [
                    ft.Container(content=content, padding=ft.Padding(left=20, right=20, top=0, bottom=0), expand=True),
                    nav_container,
                ],
                spacing=0,
                expand=True,
            ),
            padding=ft.Padding(left=0, right=0, top=46, bottom=0),
            expand=True,
        )
    )


if __name__ == "__main__":
    ft.run(main=main)
