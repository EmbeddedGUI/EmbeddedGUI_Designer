"""Tests for shared XML serialization helpers."""

import xml.etree.ElementTree as ET

from ui_designer.utils.xml_utils import element_to_xml_string, write_xml_file


def test_element_to_xml_string_uses_standard_header_without_trailing_newline():
    root = ET.Element("Project")
    ET.SubElement(root, "Pages")

    xml = element_to_xml_string(root)

    assert xml.startswith('<?xml version="1.0" encoding="utf-8"?>\n')
    assert xml.endswith("</Project>")


def test_write_xml_file_supports_optional_trailing_newline(tmp_path):
    root = ET.Element("resources")
    ET.SubElement(root, "string", {"name": "app_name"}).text = "Demo"
    xml_path = tmp_path / "strings.xml"

    write_xml_file(xml_path, root, trailing_newline=True)

    content = xml_path.read_text(encoding="utf-8")
    assert content.startswith('<?xml version="1.0" encoding="utf-8"?>\n')
    assert content.endswith("</resources>\n")
