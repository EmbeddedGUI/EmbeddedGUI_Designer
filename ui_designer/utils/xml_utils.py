"""Shared XML serialization helpers."""

import xml.etree.ElementTree as ET


_XML_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>\n'


def element_to_xml_string(root, *, indent="    ", trailing_newline=False):
    """Serialize an XML element with the project's standard header."""
    ET.indent(root, space=indent)
    xml_text = _XML_DECLARATION + ET.tostring(root, encoding="unicode")
    if trailing_newline:
        xml_text += "\n"
    return xml_text


def write_xml_file(filepath, root, *, indent="    ", trailing_newline=False):
    """Write an XML element to disk using the project's standard formatting."""
    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        f.write(
            element_to_xml_string(
                root,
                indent=indent,
                trailing_newline=trailing_newline,
            )
        )
