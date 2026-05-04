import flet as ft
from core.database import SQLiteRepository
from core import theme as T


def main(page: ft.Page):
    page.title = "StudyFlow"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = T.BG
    page.padding = ft.Padding(left=12, right=12, top=44, bottom=0)
    page.window.min_width = 360
    page.window.min_height = 640

    repo = SQLiteRepository("mcqs.db")
    content = ft.Column(expand=True, spacing=0)

    nav_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.GRID_VIEW_OUTLINED,
                selected_icon=ft.Icons.GRID_VIEW_ROUNDED,
                label="Dashboard",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.LIBRARY_BOOKS_OUTLINED,
                selected_icon=ft.Icons.LIBRARY_BOOKS,
                label="Library",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.UPLOAD_FILE_OUTLINED,
                selected_icon=ft.Icons.UPLOAD_FILE,
                label="Import",
            ),
            ft.NavigationBarDestination(
                icon=ft.Icons.PSYCHOLOGY_OUTLINED,
                selected_icon=ft.Icons.PSYCHOLOGY,
                label="Study",
            ),
        ],
        selected_index=0,
        bgcolor="#0F1729",
        indicator_color=ft.Colors.with_opacity(0.2, T.ACCENT),
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        on_change=lambda e: _tab_navigate(e.control.selected_index),
    )

    def navigate(route: str, data=None):
        content.controls.clear()

        if route == "dashboard":
            nav_bar.selected_index = 0
            import views.dashboard as v
            content.controls.append(v.build(page, repo, navigate))

        elif route == "library":
            nav_bar.selected_index = 1
            import views.library as v
            content.controls.append(v.build(page, repo, navigate))

        elif route == "import":
            nav_bar.selected_index = 2
            import views.import_view as v
            content.controls.append(v.build(page, repo, navigate))

        elif route == "study":
            nav_bar.selected_index = 3
            subject = data.get("subject", "") if isinstance(data, dict) else ""
            topic = data.get("topic", "") if isinstance(data, dict) else ""
            import views.study as v
            content.controls.append(v.build(page, repo, navigate, subject=subject, topic=topic))

        elif route == "complete":
            nav_bar.selected_index = 3
            import views.study as v
            content.controls.append(v.build_complete(repo, navigate))

        elif route == "create":
            import views.create_mcq as v
            content.controls.append(v.build(page, repo, navigate))

        elif route == "edit":
            import views.create_mcq as v
            content.controls.append(v.build(page, repo, navigate, edit_mcq=data))

        elif route == "manage":
            import views.manage as v
            content.controls.append(
                v.build(page, repo, navigate, on_edit=lambda m: navigate("edit", data=m))
            )

        page.update()

    def _tab_navigate(index: int):
        navigate(["dashboard", "library", "import", "study"][index])

    navigate("dashboard")
    page.add(ft.Column([content, nav_bar], spacing=0, expand=True))


if __name__ == "__main__":
    ft.run(main=main)
