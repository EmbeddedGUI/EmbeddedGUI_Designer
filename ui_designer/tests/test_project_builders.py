"""Tests for shared test project builders."""

import ui_designer.tests.project_builders as project_builders_module

from ui_designer.tests.page_builders import build_test_pages
from ui_designer.tests.project_builders import (
    build_saved_test_project,
    build_saved_test_project_with_widgets,
    build_saved_test_project_with_page_widgets,
    build_test_project,
    build_test_project_and_root_with_widgets,
    build_test_project_from_root,
    build_test_project_only_from_root_with_widgets,
    build_test_project_from_root_with_widgets,
    build_test_project_and_page_with_widget,
    build_test_project_and_page_with_widgets,
    build_test_project_only_with_page_widgets,
    build_test_project_only_with_widget,
    build_test_project_only_with_widgets,
    build_test_project_with_page_widgets,
    build_test_project_with_widget,
    build_test_project_with_widgets,
    build_test_project_with_page_root,
    build_test_project_with_page_roots,
    build_test_project_with_root,
    build_test_project_from_pages,
)
from ui_designer.model.widget_model import WidgetModel
from ui_designer.utils.scaffold import add_widget_children, require_project_page_root


class TestProjectBuilders:
    def test_build_test_project_uses_shared_empty_project_model(self):
        project = build_test_project(
            "BuilderDemo",
            320,
            240,
            sdk_root="D:/sdk",
            project_dir="D:/workspace/BuilderDemo",
            pages=["home", "detail"],
        )
        page, root = require_project_page_root(project)

        assert project.app_name == "BuilderDemo"
        assert project.startup_page == "home"
        assert [page.name for page in project.pages] == ["home", "detail"]
        assert page.name == "home"
        assert root.width == 320
        assert root.height == 240

    def test_build_saved_test_project_writes_project_on_disk(self, tmp_path):
        project_dir = tmp_path / "SavedBuilderDemo"

        project = build_saved_test_project(project_dir, "SavedBuilderDemo", pages=["main_page", "settings"])

        assert project.project_dir == str(project_dir)
        assert (project_dir / "SavedBuilderDemo.egui").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "main_page.xml").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "settings.xml").is_file()

    def test_build_saved_test_project_can_include_designer_scaffold(self, tmp_path):
        project_dir = tmp_path / "ScaffoldedSavedBuilderDemo"

        project = build_saved_test_project(
            project_dir,
            "ScaffoldedSavedBuilderDemo",
            pages=["main_page", "settings"],
            with_designer_scaffold=True,
        )

        assert project.project_dir == str(project_dir)
        assert (project_dir / "ScaffoldedSavedBuilderDemo.egui").is_file()
        assert (project_dir / ".eguiproject" / "layout" / "main_page.xml").is_file()
        assert (project_dir / "build.mk").is_file()
        assert (project_dir / "app_egui_config.h").is_file()
        assert (project_dir / ".designer" / "build_designer.mk").is_file()
        assert (project_dir / ".designer" / "app_egui_config_designer.h").is_file()
        assert (project_dir / "resource" / "src" / "app_resource_config.json").is_file()
        assert (project_dir / "resource" / "src" / ".designer" / "app_resource_config_designer.json").is_file()

    def test_build_saved_test_project_reuses_empty_scaffold_save_helper(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "SharedScaffoldedSavedBuilderDemo"
        captured = {}

        def fake_save_empty_project_with_designer_scaffold(
            app_name,
            project_dir_arg,
            screen_width=240,
            screen_height=320,
            **kwargs,
        ):
            captured["app_name"] = app_name
            captured["project_dir"] = project_dir_arg
            captured["screen_width"] = screen_width
            captured["screen_height"] = screen_height
            captured["kwargs"] = kwargs
            return build_test_project(
                app_name,
                screen_width,
                screen_height,
                sdk_root=kwargs.get("sdk_root", ""),
                project_dir=project_dir_arg,
                pages=kwargs.get("pages"),
            )

        monkeypatch.setattr(
            project_builders_module,
            "save_empty_project_with_designer_scaffold",
            fake_save_empty_project_with_designer_scaffold,
        )

        project = build_saved_test_project(
            project_dir,
            "SharedScaffoldedSavedBuilderDemo",
            pages=["main_page", "settings"],
            sdk_root="D:/sdk",
            with_designer_scaffold=True,
            overwrite_scaffold=True,
        )

        assert project.app_name == "SharedScaffoldedSavedBuilderDemo"
        assert captured == {
            "app_name": "SharedScaffoldedSavedBuilderDemo",
            "project_dir": str(project_dir),
            "screen_width": 240,
            "screen_height": 320,
            "kwargs": {
                "sdk_root": "D:/sdk",
                "pages": ["main_page", "settings"],
                "overwrite_scaffold": True,
                "remove_legacy_designer_files": True,
            },
        }

    def test_build_saved_test_project_forwards_project_customizer_to_empty_scaffold_helper(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "CustomizedSharedScaffoldedSavedBuilderDemo"
        captured = {}

        def _customize_project(project):
            project.screen_width = 480
            project.screen_height = 272

        def fake_save_empty_project_with_designer_scaffold(
            app_name,
            project_dir_arg,
            screen_width=240,
            screen_height=320,
            **kwargs,
        ):
            project = build_test_project(
                app_name,
                screen_width,
                screen_height,
                sdk_root=kwargs.get("sdk_root", ""),
                project_dir=project_dir_arg,
                pages=kwargs.get("pages"),
            )
            kwargs["project_customizer"](project)
            captured["project_customizer"] = kwargs["project_customizer"]
            return project

        monkeypatch.setattr(
            project_builders_module,
            "save_empty_project_with_designer_scaffold",
            fake_save_empty_project_with_designer_scaffold,
        )

        project = build_saved_test_project(
            project_dir,
            "CustomizedSharedScaffoldedSavedBuilderDemo",
            with_designer_scaffold=True,
            project_customizer=_customize_project,
        )

        assert captured["project_customizer"] is _customize_project
        assert project.screen_width == 480
        assert project.screen_height == 272

    def test_build_saved_test_project_applies_project_customizer(self, tmp_path):
        project_dir = tmp_path / "SavedProjectCustomizerDemo"

        def _customize_project(project):
            project.screen_width = 480
            project.screen_height = 272

        project = build_saved_test_project(
            project_dir,
            "SavedProjectCustomizerDemo",
            project_customizer=_customize_project,
        )

        assert project.project_dir == str(project_dir)
        assert project.screen_width == 480
        assert project.screen_height == 272
        assert (project_dir / "SavedProjectCustomizerDemo.egui").is_file()

    def test_build_saved_test_project_reuses_shared_empty_build_save_helper(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "SharedSavedBuilderDemo"
        captured = {}

        def fake_build_empty_project_model_and_save(
            app_name,
            project_dir_arg,
            screen_width=240,
            screen_height=320,
            **kwargs,
        ):
            captured["app_name"] = app_name
            captured["project_dir"] = project_dir_arg
            captured["screen_width"] = screen_width
            captured["screen_height"] = screen_height
            captured["kwargs"] = kwargs
            return (
                build_test_project(
                    app_name,
                    screen_width,
                    screen_height,
                    sdk_root=kwargs.get("sdk_root", ""),
                    project_dir=project_dir_arg,
                    pages=kwargs.get("pages"),
                ),
                {},
            )

        monkeypatch.setattr(
            project_builders_module,
            "build_empty_project_model_and_save",
            fake_build_empty_project_model_and_save,
        )

        project = build_saved_test_project(
            project_dir,
            "SharedSavedBuilderDemo",
            sdk_root="D:/sdk",
            pages=["main_page", "settings"],
        )

        assert project.app_name == "SharedSavedBuilderDemo"
        assert captured == {
            "app_name": "SharedSavedBuilderDemo",
            "project_dir": str(project_dir),
            "screen_width": 240,
            "screen_height": 320,
            "kwargs": {
                "sdk_root": "D:/sdk",
                "pages": ["main_page", "settings"],
                "project_customizer": None,
                "remove_legacy_designer_files": True,
            },
        }

    def test_build_saved_test_project_with_page_widgets_writes_populated_pages(self, tmp_path):
        project_dir = tmp_path / "SavedWidgetBuilderDemo"
        home_label = WidgetModel("label", name="home_title", x=10, y=10, width=120, height=24)
        detail_button = WidgetModel("button", name="detail_cta", x=10, y=48, width=80, height=32)

        project, roots = build_saved_test_project_with_page_widgets(
            project_dir,
            "SavedWidgetBuilderDemo",
            page_widgets={
                "main_page": [home_label],
                "detail_page": [detail_button],
            },
        )

        assert project.project_dir == str(project_dir)
        assert (project_dir / "SavedWidgetBuilderDemo.egui").is_file()
        assert roots["main_page"].children == [home_label]
        assert roots["detail_page"].children == [detail_button]

    def test_build_saved_test_project_with_page_widgets_reuses_shared_build_save_helper(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "SharedSavedWidgetBuilderDemo"
        home_label = WidgetModel("label", name="home_title", x=10, y=10, width=120, height=24)
        detail_button = WidgetModel("button", name="detail_cta", x=10, y=48, width=80, height=32)
        captured = {}

        def fake_build_project_model_with_page_widgets_and_save(
            app_name,
            screen_width=240,
            screen_height=320,
            **kwargs,
        ):
            captured["app_name"] = app_name
            captured["screen_width"] = screen_width
            captured["screen_height"] = screen_height
            captured["kwargs"] = kwargs
            project, roots = build_test_project_with_page_widgets(
                app_name,
                screen_width,
                screen_height,
                sdk_root=kwargs.get("sdk_root", ""),
                project_dir=kwargs.get("project_dir", ""),
                page_widgets=kwargs.get("page_widgets"),
                page_customizers=kwargs.get("page_customizers"),
                pages=kwargs.get("pages"),
                project_customizer=kwargs.get("project_customizer"),
            )
            return project, roots, {}

        monkeypatch.setattr(
            project_builders_module,
            "build_project_model_with_page_widgets_and_save",
            fake_build_project_model_with_page_widgets_and_save,
        )

        project, roots = build_saved_test_project_with_page_widgets(
            project_dir,
            "SharedSavedWidgetBuilderDemo",
            page_widgets={
                "main_page": [home_label],
                "detail_page": [detail_button],
            },
            with_designer_scaffold=True,
            overwrite_scaffold=True,
        )

        assert project.app_name == "SharedSavedWidgetBuilderDemo"
        assert list(roots) == ["main_page", "detail_page"]
        assert captured == {
            "app_name": "SharedSavedWidgetBuilderDemo",
            "screen_width": 240,
            "screen_height": 320,
            "kwargs": {
                "sdk_root": "",
                "project_dir": str(project_dir),
                "page_widgets": {
                    "main_page": [home_label],
                    "detail_page": [detail_button],
                },
                "page_customizers": None,
                "pages": None,
                "project_customizer": None,
                "with_designer_scaffold": True,
                "overwrite_scaffold": True,
                "remove_legacy_designer_files": True,
            },
        }

    def test_build_saved_test_project_with_page_widgets_applies_project_customizer(self, tmp_path):
        project_dir = tmp_path / "SavedMultiPageProjectCustomizerDemo"
        home_label = WidgetModel("label", name="home_title", x=10, y=10, width=120, height=24)
        detail_button = WidgetModel("button", name="detail_cta", x=10, y=48, width=80, height=32)

        def _customize_project(project):
            project.resource_catalog.add_image("hero.png")

        project, roots = build_saved_test_project_with_page_widgets(
            project_dir,
            "SavedMultiPageProjectCustomizerDemo",
            page_widgets={
                "main_page": [home_label],
                "detail_page": [detail_button],
            },
            project_customizer=_customize_project,
        )

        assert project.project_dir == str(project_dir)
        assert roots["main_page"].children == [home_label]
        assert roots["detail_page"].children == [detail_button]
        assert project.resource_catalog.has_image("hero.png") is True

    def test_build_saved_test_project_with_widgets_writes_populated_startup_page(self, tmp_path):
        project_dir = tmp_path / "SavedSinglePageWidgetBuilderDemo"
        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)
        button = WidgetModel("button", name="confirm", x=10, y=48, width=80, height=32)

        project, page, root = build_saved_test_project_with_widgets(
            project_dir,
            "SavedSinglePageWidgetBuilderDemo",
            page_name="home",
            widgets=[label, button],
        )

        assert project.project_dir == str(project_dir)
        assert page.name == "home"
        assert (project_dir / "SavedSinglePageWidgetBuilderDemo.egui").is_file()
        assert root.children == [label, button]

    def test_build_saved_test_project_with_widgets_reuses_shared_build_save_helper(self, tmp_path, monkeypatch):
        project_dir = tmp_path / "SharedSavedSinglePageWidgetBuilderDemo"
        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)
        button = WidgetModel("button", name="confirm", x=10, y=48, width=80, height=32)
        captured = {}

        def fake_build_project_model_with_widgets_and_save(
            app_name,
            screen_width=240,
            screen_height=320,
            **kwargs,
        ):
            captured["app_name"] = app_name
            captured["screen_width"] = screen_width
            captured["screen_height"] = screen_height
            captured["kwargs"] = kwargs
            project, page, root = build_test_project_with_widgets(
                app_name,
                page_name=kwargs.get("page_name", "main_page"),
                screen_width=screen_width,
                screen_height=screen_height,
                sdk_root=kwargs.get("sdk_root", ""),
                project_dir=kwargs.get("project_dir", ""),
                widgets=kwargs.get("widgets"),
                page_customizer=kwargs.get("page_customizer"),
                project_customizer=kwargs.get("project_customizer"),
            )
            return project, page, root, {}

        monkeypatch.setattr(
            project_builders_module,
            "build_project_model_with_widgets_and_save",
            fake_build_project_model_with_widgets_and_save,
        )

        project, page, root = build_saved_test_project_with_widgets(
            project_dir,
            "SharedSavedSinglePageWidgetBuilderDemo",
            page_name="home",
            widgets=[label, button],
            with_designer_scaffold=True,
            overwrite_scaffold=True,
        )

        assert project.app_name == "SharedSavedSinglePageWidgetBuilderDemo"
        assert page.name == "home"
        assert root.children == [label, button]
        assert captured == {
            "app_name": "SharedSavedSinglePageWidgetBuilderDemo",
            "screen_width": 240,
            "screen_height": 320,
            "kwargs": {
                "sdk_root": "",
                "project_dir": str(project_dir),
                "page_name": "home",
                "widgets": [label, button],
                "page_customizer": None,
                "project_customizer": None,
                "with_designer_scaffold": True,
                "overwrite_scaffold": True,
                "remove_legacy_designer_files": True,
            },
        }

    def test_build_saved_test_project_with_widgets_applies_page_customizer(self, tmp_path):
        project_dir = tmp_path / "SavedSinglePageCustomizerDemo"
        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)
        badge = WidgetModel("label", name="badge", x=10, y=40, width=60, height=20)

        def _customize(page, root):
            page.user_fields = [{"name": "counter", "type": "int", "default": "0"}]
            page.timers = [{"name": "tick", "callback": "on_tick", "delay_ms": "250", "period_ms": "250", "auto_start": False}]
            add_widget_children(root, [badge])

        project, page, root = build_saved_test_project_with_widgets(
            project_dir,
            "SavedSinglePageCustomizerDemo",
            widgets=[label],
            page_customizer=_customize,
        )

        assert project.project_dir == str(project_dir)
        assert page.user_fields == [{"name": "counter", "type": "int", "default": "0"}]
        assert page.timers == [{"name": "tick", "callback": "on_tick", "delay_ms": "250", "period_ms": "250", "auto_start": False}]
        assert root.children == [label, badge]

    def test_build_saved_test_project_with_widgets_applies_project_customizer(self, tmp_path):
        project_dir = tmp_path / "SavedSinglePageProjectCustomizerDemo"

        def _customize_project(project):
            project.string_catalog.set("greeting", "Hello", "default")

        project, page, root = build_saved_test_project_with_widgets(
            project_dir,
            "SavedSinglePageProjectCustomizerDemo",
            widgets=[],
            project_customizer=_customize_project,
        )

        assert project.project_dir == str(project_dir)
        assert page.name == "main_page"
        assert root.children == []
        assert project.string_catalog.get("greeting", "default") == "Hello"

    def test_build_test_project_from_pages_preserves_page_mode_and_startup(self):
        home_page, detail_page = build_test_pages("home", "detail")

        project = build_test_project_from_pages(
            [home_page, detail_page],
            app_name="BuilderDemo",
            page_mode="activity",
            startup_page="detail",
        )

        assert project.app_name == "BuilderDemo"
        assert project.page_mode == "activity"
        assert project.startup_page == "detail"
        assert [page.name for page in project.pages] == ["home", "detail"]

    def test_build_test_project_from_pages_accepts_legacy_startup_alias(self):
        home_page, detail_page = build_test_pages("home", "detail")

        project = build_test_project_from_pages(
            [home_page, detail_page],
            startup="detail",
        )

        assert project.startup_page == "detail"

    def test_build_test_project_from_root_wraps_custom_root_as_single_page_project(self):
        root = WidgetModel("linearlayout", name="root_layout", x=0, y=0, width=200, height=120)
        project, page = build_test_project_from_root(
            root,
            page_name="main_page",
            app_name="LayoutGroupDemo",
            page_mode="activity",
        )

        assert project.app_name == "LayoutGroupDemo"
        assert project.page_mode == "activity"
        assert project.startup_page == "main_page"
        assert project.screen_width == 200
        assert project.screen_height == 120
        assert page.name == "main_page"
        assert page.root_widget is root

    def test_build_test_project_from_root_with_widgets_attaches_children_to_custom_root(self):
        root = WidgetModel("linearlayout", name="root_layout", x=0, y=0, width=200, height=120)
        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")

        project, page = build_test_project_from_root_with_widgets(
            root,
            page_name="main_page",
            app_name="LayoutGroupDemo",
            widgets=[first, second],
        )

        assert project.app_name == "LayoutGroupDemo"
        assert page.name == "main_page"
        assert page.root_widget is root
        assert root.children == [first, second]

    def test_build_test_project_only_from_root_with_widgets_returns_populated_project(self):
        root = WidgetModel("linearlayout", name="root_layout", x=0, y=0, width=200, height=120)
        first = WidgetModel("label", name="first")
        second = WidgetModel("label", name="second")

        project = build_test_project_only_from_root_with_widgets(
            root,
            page_name="main_page",
            app_name="LayoutGroupDemo",
            widgets=[first, second],
        )

        page, resolved_root = require_project_page_root(project, "main_page")

        assert project.app_name == "LayoutGroupDemo"
        assert page.name == "main_page"
        assert resolved_root is root
        assert root.children == [first, second]

    def test_build_test_project_with_root_returns_startup_root_widget(self):
        project, root = build_test_project_with_root(
            "RootBuilderDemo",
            page_name="home",
            screen_width=320,
            screen_height=240,
        )
        page, startup_root = require_project_page_root(project)

        assert project.app_name == "RootBuilderDemo"
        assert project.startup_page == "home"
        assert page.name == "home"
        assert root is startup_root
        assert root.width == 320
        assert root.height == 240

    def test_build_test_project_with_page_root_returns_project_page_and_root(self):
        project, page, root = build_test_project_with_page_root(
            "PageRootBuilderDemo",
            page_name="home",
            screen_width=320,
            screen_height=240,
        )

        assert project.app_name == "PageRootBuilderDemo"
        assert project.startup_page == "home"
        assert page.name == "home"
        assert root is page.root_widget
        assert root.width == 320
        assert root.height == 240

    def test_build_test_project_with_page_roots_returns_all_named_roots(self):
        project, roots = build_test_project_with_page_roots(
            "MultiRootBuilderDemo",
            pages=["home", "detail"],
            screen_width=320,
            screen_height=240,
        )

        assert project.app_name == "MultiRootBuilderDemo"
        assert project.startup_page == "home"
        assert list(roots) == ["home", "detail"]
        assert roots["home"].width == 320
        assert roots["detail"].height == 240

    def test_build_test_project_with_widgets_attaches_supplied_widgets(self):
        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)
        button = WidgetModel("button", name="confirm", x=10, y=48, width=80, height=32)

        project, page, root = build_test_project_with_widgets(
            "ProjectWidgetDemo",
            page_name="home",
            widgets=[label, button],
        )

        assert project.app_name == "ProjectWidgetDemo"
        assert page.name == "home"
        assert root.children == [label, button]

    def test_build_test_project_with_widgets_applies_project_customizer(self):
        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)

        def _customize_project(project):
            project.string_catalog.set("greeting", "Hello", "default")

        project, page, root = build_test_project_with_widgets(
            "ProjectWidgetDemo",
            widgets=[label],
            project_customizer=_customize_project,
        )

        assert project.app_name == "ProjectWidgetDemo"
        assert page.name == "main_page"
        assert root.children == [label]
        assert project.string_catalog.get("greeting", "default") == "Hello"

    def test_build_test_project_and_page_with_widgets_returns_project_and_page(self):
        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)

        project, page = build_test_project_and_page_with_widgets(
            "ProjectWidgetDemo",
            page_name="home",
            widgets=[label],
        )

        assert project.app_name == "ProjectWidgetDemo"
        assert page.name == "home"
        assert page.root_widget.children == [label]

    def test_build_test_project_and_root_with_widgets_returns_project_and_root(self):
        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)

        project, root = build_test_project_and_root_with_widgets(
            "ProjectWidgetDemo",
            page_name="home",
            widgets=[label],
        )

        assert project.app_name == "ProjectWidgetDemo"
        assert [child.name for child in root.children] == ["title"]

    def test_build_test_project_only_with_widgets_returns_populated_project(self):
        label = WidgetModel("label", name="title", x=10, y=10, width=120, height=24)

        project = build_test_project_only_with_widgets(
            "ProjectWidgetDemo",
            page_name="home",
            widgets=[label],
        )
        page, root = require_project_page_root(project, "home")

        assert project.app_name == "ProjectWidgetDemo"
        assert page.name == "home"
        assert root.children == [label]

    def test_build_test_project_with_page_widgets_attaches_widgets_per_named_page(self):
        home_label = WidgetModel("label", name="home_title", x=10, y=10, width=120, height=24)
        detail_button = WidgetModel("button", name="detail_cta", x=10, y=48, width=80, height=32)

        project, roots = build_test_project_with_page_widgets(
            "ProjectWidgetDemo",
            pages=["home", "detail"],
            page_widgets={
                "home": [home_label],
                "detail": [detail_button],
            },
        )

        assert project.app_name == "ProjectWidgetDemo"
        assert list(roots) == ["home", "detail"]
        assert roots["home"].children == [home_label]
        assert roots["detail"].children == [detail_button]

    def test_build_test_project_with_page_widgets_applies_page_customizers(self):
        home_label = WidgetModel("label", name="home_title", x=10, y=10, width=120, height=24)
        detail_button = WidgetModel("button", name="detail_cta", x=10, y=48, width=80, height=32)

        def _setup_home(page, root):
            page.user_fields = [{"name": "counter", "type": "int", "default": "0"}]
            assert root.children == [home_label]

        def _setup_detail(page, root):
            page.timers = [{"name": "tick", "callback": "on_tick", "delay_ms": "500", "period_ms": "500", "auto_start": True}]
            assert root.children == [detail_button]

        project, roots = build_test_project_with_page_widgets(
            "ProjectWidgetDemo",
            page_widgets={
                "home": [home_label],
                "detail": [detail_button],
            },
            page_customizers={
                "home": _setup_home,
                "detail": _setup_detail,
            },
        )
        home_page, _ = require_project_page_root(project, "home")
        detail_page, _ = require_project_page_root(project, "detail")

        assert project.app_name == "ProjectWidgetDemo"
        assert list(roots) == ["home", "detail"]
        assert roots["home"].children == [home_label]
        assert roots["detail"].children == [detail_button]
        assert home_page.user_fields == [{"name": "counter", "type": "int", "default": "0"}]
        assert detail_page.timers == [{"name": "tick", "callback": "on_tick", "delay_ms": "500", "period_ms": "500", "auto_start": True}]

    def test_build_test_project_with_page_widgets_applies_project_customizer(self):
        home_label = WidgetModel("label", name="home_title", x=10, y=10, width=120, height=24)
        detail_button = WidgetModel("button", name="detail_cta", x=10, y=48, width=80, height=32)

        def _customize_project(project):
            project.resource_catalog.add_image("hero.png")

        project, roots = build_test_project_with_page_widgets(
            "ProjectWidgetDemo",
            page_widgets={
                "home": [home_label],
                "detail": [detail_button],
            },
            project_customizer=_customize_project,
        )

        assert project.app_name == "ProjectWidgetDemo"
        assert roots["home"].children == [home_label]
        assert roots["detail"].children == [detail_button]
        assert project.resource_catalog.has_image("hero.png") is True

    def test_build_test_project_only_with_page_widgets_returns_populated_project(self):
        home_label = WidgetModel("label", name="home_title", x=10, y=10, width=120, height=24)
        detail_button = WidgetModel("button", name="detail_cta", x=10, y=48, width=80, height=32)

        project = build_test_project_only_with_page_widgets(
            "ProjectWidgetDemo",
            page_widgets={
                "home": [home_label],
                "detail": [detail_button],
            },
        )
        _home_page, home_root = require_project_page_root(project, "home")
        _detail_page, detail_root = require_project_page_root(project, "detail")

        assert project.app_name == "ProjectWidgetDemo"
        assert home_root.children == [home_label]
        assert detail_root.children == [detail_button]

    def test_build_test_project_with_widget_attaches_basic_widget_to_selected_page(self):
        project, page, widget = build_test_project_with_widget(
            "ProjectWidgetDemo",
            "button",
            page_name="home",
            name="cta",
            x=16,
            y=24,
            width=96,
            height=40,
        )

        assert project.app_name == "ProjectWidgetDemo"
        assert page.name == "home"
        assert widget.name == "cta"
        assert widget.widget_type == "button"
        assert widget in page.root_widget.children

    def test_build_test_project_with_widget_applies_page_and_project_customizers(self):
        def _customize_page(page, root):
            assert [child.name for child in root.children] == ["cta"]
            page.timers = [{"name": "tick", "callback": "on_tick", "delay_ms": "500", "period_ms": "500", "auto_start": True}]

        def _customize_project(project):
            project.string_catalog.set("greeting", "Hello", "default")

        project, page, widget = build_test_project_with_widget(
            "ProjectWidgetDemo",
            "button",
            page_name="home",
            name="cta",
            x=16,
            y=24,
            width=96,
            height=40,
            page_customizer=_customize_page,
            project_customizer=_customize_project,
        )

        assert project.app_name == "ProjectWidgetDemo"
        assert page.name == "home"
        assert widget.name == "cta"
        assert page.timers == [{"name": "tick", "callback": "on_tick", "delay_ms": "500", "period_ms": "500", "auto_start": True}]
        assert project.string_catalog.get("greeting", "default") == "Hello"

    def test_build_test_project_and_page_with_widget_returns_project_and_page(self):
        project, page = build_test_project_and_page_with_widget(
            "ProjectWidgetDemo",
            "button",
            page_name="home",
            name="cta",
            x=16,
            y=24,
            width=96,
            height=40,
        )

        assert project.app_name == "ProjectWidgetDemo"
        assert page.name == "home"
        assert [child.name for child in page.root_widget.children] == ["cta"]
        assert page.root_widget.children[0].widget_type == "button"

    def test_build_test_project_only_with_widget_returns_project_for_requested_widget(self):
        project = build_test_project_only_with_widget(
            "ProjectWidgetDemo",
            "button",
            page_name="home",
            name="cta",
            x=16,
            y=24,
            width=96,
            height=40,
        )
        page, root = require_project_page_root(project, "home")

        assert project.app_name == "ProjectWidgetDemo"
        assert page.name == "home"
        assert [child.name for child in root.children] == ["cta"]
        assert root.children[0].widget_type == "button"
