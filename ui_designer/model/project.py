"""Project save/load for EmbeddedGUI Designer 鈥?XML format (.egui).

Project structure on disk (inside app directory, e.g. example/HelloDesigner/):

    HelloDesigner.egui      - project metadata (XML, single entry file)
    .eguiproject/
        layout/
            main_page.xml   - one file per page
        resources/
            resources.xml   - resource catalog
            images/         - source image files (.png, .bmp, .jpg)
            values/
                strings.xml - default locale i18n strings
            values-zh/
                strings.xml - Chinese locale i18n strings
            *.ttf, *.otf    - font source files
            *.txt           - text source files
        mockup/             - mockup images (design-time only)
    resource/
        src/                - synced from .eguiproject/resources/ for generation
        img/                - generated
        font/               - generated
"""

import os
import shutil
import xml.etree.ElementTree as ET

from .build_metadata import collect_sdk_fingerprint
from .widget_model import WidgetModel
from .page import Page
from .resource_catalog import ResourceCatalog
from .string_resource import StringResourceCatalog
from ..utils.scaffold import (
    RESOURCE_CATALOG_FILENAME,
    project_app_config_path,
    project_build_mk_path,
    project_config_dir,
    project_config_images_dir,
    project_config_layout_dir,
    project_config_layout_xml_relpath,
    project_config_mockup_dir,
    project_designer_dir,
    project_designer_resource_dir,
    project_config_resource_dir,
    preferred_resource_source_dir,
    project_file_path,
    project_generated_font_dir,
    project_generated_img_dir,
    project_generated_resource_dir,
    project_resource_src_dir,
    project_user_resource_config_path,
    sdk_example_paths,
)
from ..utils.resource_config_overlay import is_designer_resource_path
from ..utils.xml_utils import element_to_xml_string
from .workspace import normalize_path, resolve_project_sdk_root, serialize_sdk_root
from .sdk_fingerprint import SdkFingerprint


_SDK_VERSION_ELEMENT = "SdkVersion"


def _sdk_revision_text(fingerprint) -> str:
    if not isinstance(fingerprint, SdkFingerprint):
        return ""
    for value in (fingerprint.revision, fingerprint.commit_short, fingerprint.commit):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _serialize_sdk_fingerprint(root, fingerprint) -> None:
    if not _sdk_revision_text(fingerprint):
        return

    sdk_elem = ET.SubElement(root, _SDK_VERSION_ELEMENT)
    if fingerprint.source_kind:
        sdk_elem.set("source_kind", str(fingerprint.source_kind))
    if fingerprint.revision:
        sdk_elem.set("revision", str(fingerprint.revision))
    if fingerprint.commit:
        sdk_elem.set("commit", str(fingerprint.commit))
    if fingerprint.commit_short:
        sdk_elem.set("commit_short", str(fingerprint.commit_short))
    if fingerprint.dirty:
        sdk_elem.set("dirty", "1")


def _parse_sdk_fingerprint(root) -> SdkFingerprint:
    sdk_elem = root.find(_SDK_VERSION_ELEMENT)
    if sdk_elem is None:
        return SdkFingerprint()

    dirty_value = str(sdk_elem.get("dirty", "")).strip().lower()
    return SdkFingerprint(
        source_kind=str(sdk_elem.get("source_kind", "") or "").strip(),
        revision=str(sdk_elem.get("revision", "") or "").strip(),
        commit=str(sdk_elem.get("commit", "") or "").strip(),
        commit_short=str(sdk_elem.get("commit_short", "") or "").strip(),
        dirty=dirty_value in {"1", "true", "yes", "on"},
    )


class Project:
    """Represents a designer project with multiple pages.

    Project files are stored in the app directory (e.g., example/HelloDesigner/).
    """

    def __init__(self, screen_width=240, screen_height=320, app_name="HelloDesigner"):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.app_name = app_name
        self._sdk_root = ""  # Path to EmbeddedGUI SDK root directory
        self.sdk_fingerprint = SdkFingerprint()  # Project scaffold SDK baseline
        self.project_dir = ""  # Path to the app/project directory
        self.page_mode = "easy_page"  # "easy_page" or "activity"
        self.startup_page = "main_page"  # filename without extension
        self.resource_catalog = ResourceCatalog()  # project resource catalog
        self.string_catalog = StringResourceCatalog()  # i18n string resources
        self.pages = []  # list[Page]

    @property
    def sdk_root(self):
        return self._sdk_root

    @sdk_root.setter
    def sdk_root(self, value):
        self._sdk_root = normalize_path(value)

    @property
    def root_widgets(self):
        """Compatibility shim: return root widgets of the startup page.

        Used by layout_engine.compute_layout() and widget_tree/preview.
        """
        page = self.get_startup_page()
        if page and page.root_widget:
            return [page.root_widget]
        return []

    # 鈹€鈹€ Page management 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def get_page_by_name(self, name):
        """Find a page by its derived name (filename without extension)."""
        for page in self.pages:
            if page.name == name:
                return page
        return None

    def add_page(self, page):
        """Add a page to the project."""
        self.pages.append(page)

    def remove_page(self, page):
        """Remove a page from the project."""
        self.pages.remove(page)

    def get_startup_page(self):
        """Get the startup page object."""
        page = self.get_page_by_name(self.startup_page)
        if page is None and self.pages:
            return self.pages[0]
        return page

    def create_new_page(self, page_name):
        """Create and add a new page with default root group."""
        page = Page.create_default(
            page_name,
            screen_width=self.screen_width,
            screen_height=self.screen_height,
        )
        self.add_page(page)
        return page

    def duplicate_page(self, source_name, new_name):
        """Duplicate an existing page under a new page name."""
        source_page = self.get_page_by_name(source_name)
        if source_page is None:
            raise ValueError(f"Page '{source_name}' does not exist.")
        if self.get_page_by_name(new_name) is not None:
            raise ValueError(f"Page '{new_name}' already exists.")

        page = Page.from_xml_string(
            source_page.to_xml_string(),
            file_path=project_config_layout_xml_relpath(new_name),
        )
        page.dirty = True
        self.add_page(page)
        return page

    # 鈹€鈹€ Path helpers 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def get_app_dir(self):
        """Get the app directory path."""
        if self.project_dir:
            return self.project_dir
        if self.sdk_root:
            return sdk_example_paths(self.sdk_root, self.app_name)["app_dir"]
        return ""

    def _resolve_project_dir_path(self, project_dir, resolver):
        project_dir = normalize_path(project_dir or self.get_app_dir())
        if not project_dir:
            return ""
        return resolver(project_dir)

    def _project_app_path(self, resolver):
        return self._resolve_project_dir_path("", resolver)

    def get_resource_dir(self):
        """Get the resource directory path (resource/).

        Used for the generation pipeline (generated output in resource/img/,
        resource/font/) and for property_panel to scan generated fonts.
        """
        return self._project_app_path(project_generated_resource_dir)

    def get_project_file_path(self):
        """Get the project metadata file path ({app_name}.egui)."""
        return self._project_app_path(
            lambda project_dir: project_file_path(project_dir, self.app_name)
        )

    def get_build_mk_path(self):
        """Get the user-owned build.mk wrapper path."""
        return self._project_app_path(project_build_mk_path)

    def get_app_config_path(self):
        """Get the user-owned app_egui_config.h wrapper path."""
        return self._project_app_path(project_app_config_path)

    def get_designer_dir(self):
        """Get the designer-managed .designer/ directory path."""
        return self._project_app_path(project_designer_dir)

    def get_generated_img_dir(self):
        """Get the generated image output directory (resource/img/)."""
        return self._project_app_path(project_generated_img_dir)

    def get_generated_font_dir(self):
        """Get the generated font output directory (resource/font/)."""
        return self._project_app_path(project_generated_font_dir)

    def get_resource_src_dir(self):
        """Get the generated resource source directory (resource/src/)."""
        return self._project_app_path(project_resource_src_dir)

    def get_user_resource_config_path(self):
        """Get the user-owned resource overlay config path."""
        return self._project_app_path(project_user_resource_config_path)

    def get_designer_resource_dir(self):
        """Get the designer-managed resource metadata directory path."""
        return self._project_app_path(project_designer_resource_dir)

    def get_eguiproject_dir(self):
        """Get the .eguiproject config directory path."""
        return self._project_app_path(project_config_dir)

    def get_eguiproject_layout_dir(self):
        """Get the .eguiproject/layout/ directory path."""
        return self._project_app_path(project_config_layout_dir)

    def get_eguiproject_mockup_dir(self):
        """Get the .eguiproject/mockup/ directory path."""
        return self._project_app_path(project_config_mockup_dir)

    def get_eguiproject_resource_dir(self):
        """Get the .eguiproject/resources/ directory path.

        This is the authoritative location for all resource files.
        Contains: resources.xml, images/, values*/, fonts, text files.
        """
        return self._project_app_path(project_config_resource_dir)

    def get_eguiproject_images_dir(self):
        """Get the .eguiproject/resources/images/ directory path.

        Authoritative location for source image files.
        """
        return self._project_app_path(project_config_images_dir)

    # 鈹€鈹€ Widgets 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def get_all_widgets(self):
        """Return flat list of all widgets across all pages."""
        result = []
        for page in self.pages:
            result.extend(page.get_all_widgets())
        return result

    # 鈹€鈹€ Save / Load (.egui XML) 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€

    def to_xml_string(self, project_dir="", *, stored_sdk_root=None):
        """Serialize project metadata to a .egui XML string."""
        project_dir = normalize_path(project_dir or self.project_dir or self.get_app_dir())

        root = ET.Element("Project")
        root.set("app_name", self.app_name)
        root.set("screen_width", str(self.screen_width))
        root.set("screen_height", str(self.screen_height))
        root.set("page_mode", self.page_mode)
        root.set("startup", self.startup_page)
        if stored_sdk_root is not None:
            sdk_value = str(stored_sdk_root or "").strip().replace("\\", "/")
        elif self.sdk_root:
            sdk_value = serialize_sdk_root(project_dir, self.sdk_root)
        else:
            sdk_value = ""
        if sdk_value:
            root.set("sdk_root", sdk_value)
        _serialize_sdk_fingerprint(root, self.sdk_fingerprint)

        pages_elem = ET.SubElement(root, "Pages")
        for page in self.pages:
            ref = ET.SubElement(pages_elem, "PageRef")
            ref.set("file", page.file_path)

        res = ET.SubElement(root, "Resources")
        res.set("catalog", RESOURCE_CATALOG_FILENAME)

        return element_to_xml_string(root)

    def save(self, project_dir):
        """Save project to directory.

        Creates:
            project_dir/{app_name}.egui        - project metadata
            project_dir/.eguiproject/resources/resources.xml  - resource catalog
            project_dir/.eguiproject/layout/*.xml   - one file per page
        """
        project_dir = normalize_path(project_dir)
        self.project_dir = project_dir
        os.makedirs(project_dir, exist_ok=True)
        eguiproject_dir = self.get_eguiproject_dir()
        os.makedirs(eguiproject_dir, exist_ok=True)

        # Save each page XML to .eguiproject/layout/
        for page in self.pages:
            page.save(eguiproject_dir)

        # Save resource catalog to .eguiproject/resources/resources.xml
        resources_dir = self.get_eguiproject_resource_dir()
        os.makedirs(resources_dir, exist_ok=True)
        self.resource_catalog.save(resources_dir)

        # Save i18n string resources to .eguiproject/resources/values*/strings.xml
        if self.string_catalog.has_strings:
            self.string_catalog.save(resources_dir)

        # Sync .eguiproject/resources/ -> resource/src/ for generation pipeline
        self.sync_resources_to_src(project_dir)

        # Build {app_name}.egui
        if self.sdk_root and not _sdk_revision_text(self.sdk_fingerprint):
            fingerprint = collect_sdk_fingerprint(self.sdk_root)
            if _sdk_revision_text(fingerprint):
                self.sdk_fingerprint = fingerprint

        eui_path = self.get_project_file_path()
        with open(eui_path, "w", encoding="utf-8") as f:
            f.write(self.to_xml_string(project_dir))

    @classmethod
    def _find_project_file(cls, directory):
        """Find the project file (.egui) in a directory.

        Returns (file_path, True) or (None, False) if not found.
        """
        if not os.path.isdir(directory):
            return None, False
        for fname in os.listdir(directory):
            if fname.endswith(".egui"):
                return os.path.join(directory, fname), True
        return None, False

    @classmethod
    def load(cls, project_path):
        """Load project from .egui file or from a directory containing one."""
        if os.path.isdir(project_path):
            project_file, found = cls._find_project_file(project_path)
            if not found:
                raise FileNotFoundError(
                    f"No .egui project file found in {project_path}"
                )
        else:
            project_file = project_path

        project_dir = os.path.dirname(os.path.abspath(project_file))

        from .widget_registry import WidgetRegistry
        WidgetRegistry.instance().load_app_local_widgets(project_dir)

        tree = ET.parse(project_file)
        root = tree.getroot()

        proj = cls(
            screen_width=int(root.get("screen_width", "240")),
            screen_height=int(root.get("screen_height", "320")),
            app_name=root.get("app_name", "HelloDesigner"),
        )
        proj.project_dir = project_dir
        proj.sdk_root = resolve_project_sdk_root(project_dir, root.get("sdk_root", ""))
        proj.sdk_fingerprint = _parse_sdk_fingerprint(root)
        proj.page_mode = root.get("page_mode", "easy_page")
        proj.startup_page = root.get("startup", "main_page")

        # Determine canonical resource directories
        config_dir = proj.get_eguiproject_dir()
        eguiproject_res_dir = proj.get_eguiproject_resource_dir()

        # Load resource catalog
        catalog = ResourceCatalog.load(eguiproject_res_dir)
        if catalog is not None:
            proj.resource_catalog = catalog
        else:
            if os.path.isdir(eguiproject_res_dir):
                proj.resource_catalog = ResourceCatalog.from_directory(eguiproject_res_dir)
            else:
                proj.resource_catalog = ResourceCatalog()

        # Load i18n string resources from the canonical resource directory only.
        proj.string_catalog = StringResourceCatalog.scan_and_load(eguiproject_res_dir)

        # Determine the authoritative source dir for page loading.
        effective_src_dir = preferred_resource_source_dir(eguiproject_res_dir) or None

        # Load pages
        pages_elem = root.find("Pages")
        if pages_elem is not None:
            WidgetModel.reset_counter()
            for ref in pages_elem.findall("PageRef"):
                file_path = ref.get("file", "")
                if not file_path:
                    continue
                try:
                    page = Page.load(config_dir, file_path, src_dir=effective_src_dir)
                    proj.pages.append(page)
                except Exception as e:
                    print(f"Warning: Failed to load page {file_path}: {e}")

        return proj

    def sync_resources_to_src(self, project_dir=""):
        """Sync .eguiproject/resources/ 鈫?resource/src/ for the generation pipeline.

        Copies source files to resource/src/ so app_resource_generate.py can
        find them.  Images live in resources/images/, fonts and text files
        live in the resources/ root.
        Only copies if source is newer or destination doesn't exist.
        """
        eguiproject_res_dir = self._resolve_project_dir_path(
            project_dir,
            project_config_resource_dir,
        )
        images_dir = self._resolve_project_dir_path(
            project_dir,
            project_config_images_dir,
        )
        target_src_dir = self._resolve_project_dir_path(
            project_dir,
            project_resource_src_dir,
        )

        if not eguiproject_res_dir or not target_src_dir or not os.path.isdir(eguiproject_res_dir):
            return

        os.makedirs(target_src_dir, exist_ok=True)

        def _sync_file(src_path, dst_path):
            if not os.path.exists(dst_path):
                shutil.copy2(src_path, dst_path)
            elif os.path.getmtime(src_path) > os.path.getmtime(dst_path):
                shutil.copy2(src_path, dst_path)

        # Sync images from resources/images/
        if os.path.isdir(images_dir):
            for fname in os.listdir(images_dir):
                src_path = os.path.join(images_dir, fname)
                if os.path.isfile(src_path):
                    if is_designer_resource_path(fname):
                        continue
                    _sync_file(src_path, os.path.join(target_src_dir, fname))

        # Sync fonts and text files from resources/ root
        for fname in os.listdir(eguiproject_res_dir):
            src_path = os.path.join(eguiproject_res_dir, fname)
            if not os.path.isfile(src_path):
                continue
            if is_designer_resource_path(fname):
                continue
            # Skip the catalog index (not a source file)
            if fname == RESOURCE_CATALOG_FILENAME:
                continue
            _sync_file(src_path, os.path.join(target_src_dir, fname))

    @classmethod
    def get_config_dir(cls, project_dir):
        """Get the .eguiproject config directory for a project."""
        return project_config_dir(project_dir)




