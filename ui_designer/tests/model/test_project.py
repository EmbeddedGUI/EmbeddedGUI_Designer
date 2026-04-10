"""Tests for ui_designer.model.project.Project."""

import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from ui_designer.model.project import Project
from ui_designer.model.page import Page
from ui_designer.model.sdk_fingerprint import SdkFingerprint
from ui_designer.model.widget_model import WidgetModel
from ui_designer.model.workspace import normalize_path


class TestProjectDefaults:
    """Tests for default Project construction."""

    def test_create_defaults(self):
        proj = Project()
        assert proj.screen_width == 240
        assert proj.screen_height == 320
        assert proj.app_name == "HelloDesigner"
        assert proj.sdk_root == ""
        assert proj.project_dir == ""
        assert proj.page_mode == "easy_page"
        assert proj.startup_page == "main_page"
        assert proj.pages == []
        assert proj.resource_catalog is not None
        assert proj.string_catalog is not None


class TestPageManagement:
    """Tests for add_page, remove_page, get_page_by_name."""

    def test_add_page(self, simple_page):
        proj = Project()
        proj.add_page(simple_page)
        assert len(proj.pages) == 1
        assert proj.pages[0] is simple_page

    def test_remove_page(self, simple_page):
        proj = Project()
        proj.add_page(simple_page)
        assert len(proj.pages) == 1

        proj.remove_page(simple_page)
        assert len(proj.pages) == 0

    def test_get_page_by_name(self, simple_page):
        proj = Project()
        proj.add_page(simple_page)

        found = proj.get_page_by_name("main_page")
        assert found is simple_page

    def test_get_page_by_name_not_found(self, simple_page):
        proj = Project()
        proj.add_page(simple_page)

        found = proj.get_page_by_name("nonexistent_page")
        assert found is None


class TestStartupPage:
    """Tests for startup page resolution."""

    def test_get_startup_page(self, simple_project):
        startup = simple_project.get_startup_page()
        assert startup is not None
        assert startup.name == "main_page"

    def test_get_startup_page_fallback(self):
        proj = Project()
        proj.startup_page = "nonexistent_page"

        root = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
        fallback_page = Page(file_path="layout/fallback.xml", root_widget=root)
        proj.add_page(fallback_page)

        startup = proj.get_startup_page()
        assert startup is fallback_page


class TestCreateNewPage:
    """Tests for create_new_page."""

    def test_create_new_page(self):
        proj = Project(screen_width=320, screen_height=480)
        page = proj.create_new_page("settings")

        assert page is not None
        assert page.name == "settings"
        assert page.root_widget is not None
        assert page.root_widget.widget_type == "group"
        assert page.root_widget.width == 320
        assert page.root_widget.height == 480
        assert page in proj.pages

    def test_duplicate_page_copies_page_content(self):
        proj = Project(screen_width=320, screen_height=480)

        original = proj.create_new_page("settings")
        label = WidgetModel("label", name="title", x=12, y=18, width=180, height=32)
        label.properties["text"] = "Settings"
        original.root_widget.add_child(label)
        original.user_fields.append({"name": "counter", "type": "int", "default": 3})
        original.timers.append(
            {
                "name": "refresh_timer",
                "callback": "tick_refresh",
                "delay_ms": "500",
                "period_ms": "1000",
                "auto_start": True,
            }
        )
        original.mockup_image_path = "mockup/settings.png"
        original.mockup_image_visible = False
        original.mockup_image_opacity = 0.5

        duplicated = proj.duplicate_page("settings", "settings_copy")

        assert duplicated is not original
        assert duplicated.name == "settings_copy"
        assert duplicated.file_path == "layout/settings_copy.xml"
        assert duplicated.dirty is True
        assert duplicated.root_widget is not original.root_widget
        assert len(duplicated.root_widget.children) == 1
        assert duplicated.root_widget.children[0].name == "title"
        assert duplicated.root_widget.children[0].properties["text"] == "Settings"
        assert duplicated.user_fields == [{"name": "counter", "type": "int", "default": "3"}]
        assert duplicated.timers == [
            {
                "name": "refresh_timer",
                "callback": "tick_refresh",
                "delay_ms": "500",
                "period_ms": "1000",
                "auto_start": True,
            }
        ]
        assert duplicated.mockup_image_path == "mockup/settings.png"
        assert duplicated.mockup_image_visible is False
        assert duplicated.mockup_image_opacity == 0.5
        assert duplicated in proj.pages


class TestRootWidgets:
    """Tests for root_widgets compatibility property."""

    def test_root_widgets(self, simple_project):
        widgets = simple_project.root_widgets
        assert len(widgets) == 1
        assert widgets[0].widget_type == "group"


class TestPathHelpers:
    """Tests for get_app_dir, get_resource_dir, get_eguiproject_dir."""

    def test_get_app_dir(self):
        proj = Project(app_name="TestApp")
        proj.sdk_root = "/home/user/EmbeddedGUI"

        expected = os.path.join(normalize_path("/home/user/EmbeddedGUI"), "example", "TestApp")
        assert proj.get_app_dir() == expected

    def test_get_app_dir_empty_root(self):
        proj = Project(app_name="TestApp")
        assert proj.get_app_dir() == ""

    def test_get_resource_dir(self):
        proj = Project(app_name="TestApp")
        proj.sdk_root = "/home/user/EmbeddedGUI"

        expected = os.path.join(normalize_path("/home/user/EmbeddedGUI"), "example", "TestApp", "resource")
        assert proj.get_resource_dir() == expected

    def test_get_eguiproject_dir(self):
        proj = Project(app_name="TestApp")
        proj.sdk_root = "/home/user/EmbeddedGUI"

        expected = os.path.join(normalize_path("/home/user/EmbeddedGUI"), "example", "TestApp", ".eguiproject")
        assert proj.get_eguiproject_dir() == expected

    def test_get_app_dir_prefers_project_dir(self):
        proj = Project(app_name="TestApp")
        proj.project_dir = normalize_path("/workspace/TestApp")
        proj.sdk_root = "/home/user/EmbeddedGUI"
        assert proj.get_app_dir() == normalize_path("/workspace/TestApp")

    def test_sdk_root_assignment_normalizes_path(self):
        proj = Project(app_name="TestApp")
        proj.sdk_root = "/home/user/EmbeddedGUI"
        assert proj.sdk_root == normalize_path("/home/user/EmbeddedGUI")


class TestResourceSync:
    """Tests for syncing .eguiproject resources into resource/src."""

    def test_sync_resources_to_src_skips_designer_reserved_files(self, tmp_path):
        project_dir = tmp_path / "project"
        resources_dir = project_dir / ".eguiproject" / "resources"
        images_dir = resources_dir / "images"
        images_dir.mkdir(parents=True)

        (resources_dir / "kept.txt").write_text("abc\n", encoding="utf-8")
        (resources_dir / "_generated_text_demo_16_4.txt").write_text("designer\n", encoding="utf-8")
        (resources_dir / "resources.xml").write_text("<resources />\n", encoding="utf-8")
        (images_dir / "icon.png").write_bytes(b"PNG")
        (images_dir / "_generated_text_preview.png").write_bytes(b"BAD")

        proj = Project()
        proj.sync_resources_to_src(str(project_dir))

        target_src_dir = project_dir / "resource" / "src"
        assert (target_src_dir / "kept.txt").is_file()
        assert (target_src_dir / "icon.png").is_file()
        assert not (target_src_dir / "_generated_text_demo_16_4.txt").exists()
        assert not (target_src_dir / "_generated_text_preview.png").exists()
        assert not (target_src_dir / "resources.xml").exists()


class TestGetAllWidgets:
    """Tests for get_all_widgets across multiple pages."""

    def test_get_all_widgets(self, multi_page_project):
        all_widgets = multi_page_project.get_all_widgets()

        # Page1: root_group + title label = 2
        # Page2: root_group + back_btn = 2
        # Total = 4
        assert len(all_widgets) == 4


class TestSaveLoad:
    """Tests for save/load file I/O."""

    def test_to_xml_string_supports_explicit_stored_sdk_root(self):
        proj = Project(screen_width=320, screen_height=480, app_name="XmlDemo")
        proj.startup_page = "home"
        proj.add_page(Page.create_default("home", screen_width=320, screen_height=480))
        proj.add_page(Page.create_default("detail", screen_width=320, screen_height=480))

        xml = proj.to_xml_string(stored_sdk_root="../../sdk/EmbeddedGUI")

        assert xml.startswith('<?xml version="1.0" encoding="utf-8"?>\n')
        assert 'sdk_root="../../sdk/EmbeddedGUI"' in xml
        assert '<PageRef file="layout/home.xml"' in xml
        assert '<PageRef file="layout/detail.xml"' in xml
        assert 'startup="home"' in xml

    @pytest.mark.integration
    def test_save_load_round_trip_preserves_sdk_version_metadata(self, tmp_path, monkeypatch):
        proj = Project(screen_width=320, screen_height=480, app_name="VersionedApp")
        proj.sdk_root = str(tmp_path / "sdk")
        proj.create_new_page("main_page")

        monkeypatch.setattr(
            "ui_designer.model.project.collect_sdk_fingerprint",
            lambda sdk_root: SdkFingerprint(
                source_kind="submodule",
                revision="sdk-main-123",
                commit="abcdef1234567890",
                commit_short="abcdef1",
            ),
        )

        project_dir = str(tmp_path / "VersionedApp")
        proj.save(project_dir)

        loaded = Project.load(project_dir)

        assert loaded.sdk_fingerprint.source_kind == "submodule"
        assert loaded.sdk_fingerprint.revision == "sdk-main-123"
        assert loaded.sdk_fingerprint.commit == "abcdef1234567890"
        assert loaded.sdk_fingerprint.commit_short == "abcdef1"

    @pytest.mark.integration
    def test_save_preserves_existing_sdk_version_metadata(self, tmp_path, monkeypatch):
        proj = Project(app_name="PinnedSdkApp")
        proj.sdk_root = str(tmp_path / "sdk")
        proj.sdk_fingerprint = SdkFingerprint(
            source_kind="submodule",
            revision="sdk-old-111",
            commit="1111111111111111",
            commit_short="1111111",
        )
        proj.create_new_page("main_page")

        monkeypatch.setattr(
            "ui_designer.model.project.collect_sdk_fingerprint",
            lambda sdk_root: SdkFingerprint(
                source_kind="submodule",
                revision="sdk-new-222",
                commit="2222222222222222",
                commit_short="2222222",
            ),
        )

        project_dir = str(tmp_path / "PinnedSdkApp")
        proj.save(project_dir)

        loaded = Project.load(project_dir)

        assert loaded.sdk_fingerprint.revision == "sdk-old-111"
        assert loaded.sdk_fingerprint.commit == "1111111111111111"
        assert loaded.sdk_fingerprint.commit_short == "1111111"

    @pytest.mark.integration
    def test_save_load_round_trip(self, tmp_path):
        proj = Project(screen_width=320, screen_height=480, app_name="RoundTripApp")
        proj.sdk_root = str(tmp_path / "sdk")
        proj.startup_page = "home"

        root1 = WidgetModel("group", name="root_group", x=0, y=0, width=320, height=480)
        label1 = WidgetModel("label", name="title", x=10, y=10, width=200, height=30)
        label1.properties["text"] = "Home Page"
        root1.add_child(label1)
        page1 = Page(file_path="layout/home.xml", root_widget=root1)

        root2 = WidgetModel("group", name="root_group", x=0, y=0, width=320, height=480)
        page2 = Page(file_path="layout/about.xml", root_widget=root2)

        proj.add_page(page1)
        proj.add_page(page2)

        project_dir = str(tmp_path / "RoundTripApp")
        proj.save(project_dir)

        loaded = Project.load(project_dir)

        assert loaded.screen_width == 320
        assert loaded.screen_height == 480
        assert loaded.app_name == "RoundTripApp"
        assert loaded.project_dir == normalize_path(project_dir)
        assert loaded.sdk_root == normalize_path(str(tmp_path / "sdk"))
        assert loaded.startup_page == "home"
        assert len(loaded.pages) == 2

        home_page = loaded.get_page_by_name("home")
        assert home_page is not None
        assert len(home_page.root_widget.children) == 1
        assert home_page.root_widget.children[0].properties["text"] == "Home Page"

    @pytest.mark.integration
    def test_save_writes_only_canonical_sdk_root_attribute(self, tmp_path):
        proj = Project(app_name="CanonicalSdkAttrApp")
        proj.sdk_root = str(tmp_path / "sdk")
        proj.create_new_page("main_page")

        project_dir = str(tmp_path / "CanonicalSdkAttrApp")
        proj.save(project_dir)

        egui_file = Path(project_dir) / "CanonicalSdkAttrApp.egui"
        content = egui_file.read_text(encoding="utf-8")

        assert 'sdk_root="' in content
        assert 'egui_root="' not in content

    @pytest.mark.integration
    def test_load_ignores_legacy_egui_root_project_attribute(self, tmp_path):
        proj = Project(app_name="LegacyProjectAttrIgnored")
        proj.sdk_root = str(tmp_path / "sdk")
        proj.create_new_page("main_page")

        project_dir = Path(tmp_path) / "LegacyProjectAttrIgnored"
        proj.save(str(project_dir))

        egui_file = project_dir / "LegacyProjectAttrIgnored.egui"
        tree = ET.parse(str(egui_file))
        root = tree.getroot()
        root.set("egui_root", root.get("sdk_root", ""))
        root.attrib.pop("sdk_root", None)
        ET.indent(root, space="    ")
        with open(egui_file, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n')
            tree.write(f, encoding="unicode", xml_declaration=False)

        loaded = Project.load(str(project_dir))

        assert loaded.sdk_root == ""
        assert loaded.pages[0].name == "main_page"

    @pytest.mark.integration
    def test_save_creates_files(self, tmp_path):
        proj = Project(app_name="FileCheckApp")

        root = WidgetModel("group", name="root_group", x=0, y=0, width=240, height=320)
        page = Page(file_path="layout/main_page.xml", root_widget=root)
        proj.add_page(page)

        project_dir = str(tmp_path / "FileCheckApp")
        proj.save(project_dir)

        # Verify .egui project file exists
        egui_file = os.path.join(project_dir, "FileCheckApp.egui")
        assert os.path.isfile(egui_file)

        # Verify layout XML was created
        layout_xml = os.path.join(project_dir, ".eguiproject", "layout", "main_page.xml")
        assert os.path.isfile(layout_xml)

    @pytest.mark.integration
    def test_load_ignores_legacy_resource_src_inputs(self, tmp_path):
        proj = Project(app_name="LegacySrcIgnored")
        proj.create_new_page("main_page")

        project_dir = tmp_path / "LegacySrcIgnored"
        proj.save(str(project_dir))

        legacy_src_dir = project_dir / "resource" / "src"
        (legacy_src_dir / "legacy.png").write_bytes(b"PNG")
        values_dir = legacy_src_dir / "values"
        values_dir.mkdir(parents=True, exist_ok=True)
        (values_dir / "strings.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<resources>\n"
            '    <string name="legacy_key">legacy value</string>\n'
            "</resources>\n",
            encoding="utf-8",
        )

        loaded = Project.load(str(project_dir))

        assert loaded.pages[0].name == "main_page"
        assert loaded.resource_catalog.images == []
        assert not loaded.string_catalog.has_strings
        assert not (project_dir / ".eguiproject" / "resources" / "images" / "legacy.png").exists()
        assert not (project_dir / ".eguiproject" / "resources" / "values" / "strings.xml").exists()

    @pytest.mark.integration
    def test_load_ignores_legacy_eguiproject_root_resources(self, tmp_path):
        proj = Project(app_name="LegacyEguiprojectIgnored")
        proj.create_new_page("main_page")

        project_dir = tmp_path / "LegacyEguiprojectIgnored"
        proj.save(str(project_dir))

        shutil.rmtree(project_dir / ".eguiproject" / "resources")
        (project_dir / ".eguiproject" / "resources.xml").write_text(
            "<Resources>\n"
            "    <Images>\n"
            '        <ImageFile file="legacy_root.png" />\n'
            "    </Images>\n"
            "</Resources>\n",
            encoding="utf-8",
        )
        legacy_values_dir = project_dir / ".eguiproject" / "values"
        legacy_values_dir.mkdir(parents=True, exist_ok=True)
        (legacy_values_dir / "strings.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<resources>\n"
            '    <string name="legacy_key">legacy value</string>\n'
            "</resources>\n",
            encoding="utf-8",
        )

        loaded = Project.load(str(project_dir))

        assert loaded.pages[0].name == "main_page"
        assert loaded.resource_catalog.images == []
        assert not loaded.string_catalog.has_strings
        assert not (project_dir / ".eguiproject" / "resources").exists()

    @pytest.mark.integration
    def test_load_bundled_example_with_manual_widget_descriptor_fallback(self):
        repo_root = Path(__file__).resolve().parents[3]
        project_dir = repo_root / "examples" / "HelloWidgetFallbackDemo"

        loaded = Project.load(str(project_dir))

        assert loaded.app_name == "HelloWidgetFallbackDemo"
        page = loaded.get_page_by_name("main_page")
        assert page is not None
        assert page.root_widget is not None
        assert len(page.root_widget.children) == 2
        pill = page.root_widget.children[1]
        assert pill.widget_type == "fallback_pill"
        assert pill.properties["text"] == "Manual widget active"
        assert pill.properties["emphasis"] is True
