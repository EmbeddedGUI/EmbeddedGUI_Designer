"""Resource catalog model for EmbeddedGUI Designer.

Manages the project-level resource catalog (resources.xml) which lists
all available source files (images, fonts, text files) in
.eguiproject/resources/.
"""

import os
import xml.etree.ElementTree as ET

from ..utils.resource_config_overlay import is_designer_resource_path
from ..utils.xml_utils import element_to_xml_string


# Image file extensions
IMAGE_EXTENSIONS = {".png", ".bmp", ".jpg", ".jpeg", ".gif"}
# Font file extensions
FONT_EXTENSIONS = {".ttf", ".otf"}
# Text file extensions
TEXT_EXTENSIONS = {".txt"}


class ResourceCatalog:
    """Manages the project-level resource catalog (resources.xml).

    This is a pure catalog of available source files - no per-resource
    configuration parameters. Configuration is stored at the widget level
    in layout XMLs.
    """

    def __init__(self):
        self.images = []       # list of filenames: ["star.png", "test_1.png"]
        self.fonts = []        # list of filenames: ["test.ttf"]
        self.text_files = []   # list of filenames: ["supported_text.txt"]

    # ── Image management ──────────────────────────────────────────

    def add_image(self, filename):
        """Add an image file to the catalog."""
        if filename not in self.images:
            self.images.append(filename)
            self.images.sort()

    def remove_image(self, filename):
        """Remove an image file from the catalog."""
        if filename in self.images:
            self.images.remove(filename)

    def has_image(self, filename):
        """Check if an image file is in the catalog."""
        return filename in self.images

    # ── Font management ───────────────────────────────────────────

    def add_font(self, filename):
        """Add a font file to the catalog."""
        if filename not in self.fonts:
            self.fonts.append(filename)
            self.fonts.sort()

    def remove_font(self, filename):
        """Remove a font file from the catalog."""
        if filename in self.fonts:
            self.fonts.remove(filename)

    def has_font(self, filename):
        """Check if a font file is in the catalog."""
        return filename in self.fonts

    # ── Text file management ──────────────────────────────────────

    def add_text_file(self, filename):
        """Add a text file to the catalog."""
        if is_designer_resource_path(filename):
            return
        if filename not in self.text_files:
            self.text_files.append(filename)
            self.text_files.sort()

    def remove_text_file(self, filename):
        """Remove a text file from the catalog."""
        if filename in self.text_files:
            self.text_files.remove(filename)

    def has_text_file(self, filename):
        """Check if a text file is in the catalog."""
        return filename in self.text_files

    # ── Auto-detect file type and add ─────────────────────────────

    def add_file(self, filename):
        """Add a file to the appropriate category based on extension."""
        if is_designer_resource_path(filename):
            return
        ext = os.path.splitext(filename)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            self.add_image(filename)
        elif ext in FONT_EXTENSIONS:
            self.add_font(filename)
        elif ext in TEXT_EXTENSIONS:
            self.add_text_file(filename)

    def remove_file(self, filename):
        """Remove a file from any category."""
        self.remove_image(filename)
        self.remove_font(filename)
        self.remove_text_file(filename)

    # ── Serialization ─────────────────────────────────────────────

    def to_xml_string(self):
        """Serialize the catalog to a resources.xml string."""
        root = ET.Element("Resources")

        if self.images:
            images_elem = ET.SubElement(root, "Images")
            for img in self.images:
                elem = ET.SubElement(images_elem, "ImageFile")
                elem.set("file", img)

        if self.fonts:
            fonts_elem = ET.SubElement(root, "Fonts")
            for font in self.fonts:
                elem = ET.SubElement(fonts_elem, "FontFile")
                elem.set("file", font)

        if self.text_files:
            texts_elem = ET.SubElement(root, "TextFiles")
            for txt in self.text_files:
                if is_designer_resource_path(txt):
                    continue
                elem = ET.SubElement(texts_elem, "TextFile")
                elem.set("file", txt)

        return element_to_xml_string(root)

    def save(self, project_dir):
        """Save catalog to resources.xml in project directory."""
        xml_path = os.path.join(project_dir, "resources.xml")
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(self.to_xml_string())

    @classmethod
    def load(cls, project_dir):
        """Load catalog from resources.xml in project directory.

        Returns None if resources.xml does not exist.
        """
        xml_path = os.path.join(project_dir, "resources.xml")
        if not os.path.isfile(xml_path):
            return None

        catalog = cls()
        tree = ET.parse(xml_path)
        root = tree.getroot()

        images_elem = root.find("Images")
        if images_elem is not None:
            for elem in images_elem.findall("ImageFile"):
                filename = elem.get("file", "")
                if filename:
                    catalog.images.append(filename)

        fonts_elem = root.find("Fonts")
        if fonts_elem is not None:
            for elem in fonts_elem.findall("FontFile"):
                filename = elem.get("file", "")
                if filename:
                    catalog.fonts.append(filename)

        texts_elem = root.find("TextFiles")
        if texts_elem is not None:
            for elem in texts_elem.findall("TextFile"):
                filename = elem.get("file", "")
                if filename and not is_designer_resource_path(filename):
                    catalog.text_files.append(filename)

        return catalog

    @classmethod
    def from_directory(cls, src_dir):
        """Create a catalog by scanning a directory for source resource files.

        Supports the structured layout (.eguiproject/resources/):
          - images/ subfolder for image files
          - fonts and text files in the root
        """
        catalog = cls()
        if not os.path.isdir(src_dir):
            return catalog

        # Scan images/ subfolder first (new layout)
        images_dir = os.path.join(src_dir, "images")
        if os.path.isdir(images_dir):
            for fname in sorted(os.listdir(images_dir)):
                ext = os.path.splitext(fname)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    catalog.images.append(fname)

        # Scan root for all file types; images/ takes precedence when present.
        for fname in sorted(os.listdir(src_dir)):
            fpath = os.path.join(src_dir, fname)
            if not os.path.isfile(fpath):
                continue
            if is_designer_resource_path(fname):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext in IMAGE_EXTENSIONS and fname not in catalog.images:
                catalog.images.append(fname)
            elif ext in FONT_EXTENSIONS:
                catalog.fonts.append(fname)
            elif ext in TEXT_EXTENSIONS:
                catalog.text_files.append(fname)

        return catalog
