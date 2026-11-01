"""Bounded, read-only sharing inspection. Returned values are untrusted plain text."""

from __future__ import annotations

import time
import zlib
from itertools import islice
from pathlib import Path
from xml.parsers import expat

import pikepdf

from priveopdf.domain.share_inspection import (
    CATEGORIES,
    MetadataProperty,
    ShareInspection,
)

MAX_METADATA_BYTES = 1024 * 1024
MAX_PROPERTIES = 128
MAX_VALUE_CHARS = 1024
XMP_COMMON = {
    "http://purl.org/dc/elements/1.1/|title": "Title",
    "http://purl.org/dc/elements/1.1/|creator": "Author",
    "http://purl.org/dc/elements/1.1/|description": "Subject",
    "http://purl.org/dc/elements/1.1/|subject": "Keywords",
    "http://ns.adobe.com/pdf/1.3/|Keywords": "Keywords",
    "http://ns.adobe.com/pdf/1.3/|Producer": "Producer",
    "http://ns.adobe.com/xap/1.0/|CreatorTool": "Creator",
    "http://ns.adobe.com/xap/1.0/|CreateDate": "CreationDate",
    "http://ns.adobe.com/xap/1.0/|ModifyDate": "ModDate",
}


def _bounded_xmp(stream: object) -> bytes:
    if not isinstance(stream, pikepdf.Stream):
        raise ValueError("invalid metadata stream")
    if int(stream.get("/Length", 0)) > MAX_METADATA_BYTES:
        raise OverflowError
    data = stream.read_raw_bytes()
    if len(data) > MAX_METADATA_BYTES:
        raise OverflowError
    filters = stream.get("/Filter")
    if filters is None:
        return data
    if isinstance(filters, pikepdf.Array) and len(filters) == 1:
        filters = filters[0]
    if filters != pikepdf.Name.FlateDecode or stream.get("/DecodeParms") is not None:
        raise ValueError("unsupported metadata encoding")
    decoder = zlib.decompressobj()
    output = decoder.decompress(data, MAX_METADATA_BYTES + 1)
    if len(output) > MAX_METADATA_BYTES or decoder.unconsumed_tail:
        raise OverflowError
    if not decoder.eof or decoder.unused_data:
        raise ValueError("invalid metadata encoding")
    return output


def _xml_properties(data: bytes) -> list[tuple[str, str]]:
    # Expat never fetches resources; reject declarations, including internal entities.
    parser = expat.ParserCreate(namespace_separator="|")
    properties: list[tuple[str, str]] = []
    stack: list[str] = []
    chunks: list[str] = []
    property_name: str | None = None
    property_depth = 0
    nodes = 0
    rdf_description = "http://www.w3.org/1999/02/22-rdf-syntax-ns#|Description"

    def reject(*_args):
        raise ValueError("XML declarations are not supported")

    def start(name, attrs):
        nonlocal property_name, property_depth, nodes, chunks
        nodes += 1
        if nodes > 4096 or len(stack) >= 32:
            raise OverflowError
        if stack and stack[-1] == rdf_description and property_name is None:
            property_name, property_depth, chunks = name, len(stack) + 1, []
        if name == rdf_description:
            for key, value in attrs.items():
                if not key.startswith("http://www.w3.org/1999/02/22-rdf-syntax-ns#|"):
                    properties.append((key, value))
        stack.append(name)

    def end(_name):
        nonlocal property_name
        if property_name is not None and len(stack) == property_depth:
            properties.append((property_name, "".join(chunks)))
            property_name = None
        elif property_name is not None and stack[-1].endswith("|li"):
            chunks.append("\n")
        stack.pop()
        if len(properties) > MAX_PROPERTIES:
            raise OverflowError

    def characters(value):
        if property_name is not None:
            chunks.append(value)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = characters
    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.Parse(data, True)
    return properties


def metadata(pdf: pikepdf.Pdf) -> tuple[str, str, tuple[MetadataProperty, ...]]:
    properties: list[MetadataProperty] = []
    display_remaining = 60_000

    def add(origin, name, value):
        nonlocal display_remaining
        limit = min(MAX_VALUE_CHARS, display_remaining)
        display_remaining -= min(len(value), limit)
        properties.append(
            MetadataProperty(
                origin,
                name[:256],
                value[:limit],
                len(name) > 256 or len(value) > limit,
            )
        )

    info_state = "absent"
    if "/Info" in pdf.trailer:
        info_state = "present"
        try:
            info = pdf.trailer["/Info"]
            if not isinstance(info, pikepdf.Dictionary):
                raise ValueError
            if len(info) > MAX_PROPERTIES:
                info_state = "limited"
            for key, value in islice(info.items(), MAX_PROPERTIES):
                if isinstance(value, (pikepdf.String, pikepdf.Name, int, float, bool)):
                    add("Info", key.lstrip("/"), str(value))
                elif value is None:
                    add("Info", key.lstrip("/"), "")
                else:
                    info_state = "unreadable"
        except (ValueError, TypeError, pikepdf.PdfError):
            info_state = "unreadable"
    xmp_state = "absent"
    if "/Metadata" in pdf.Root:
        xmp_state = "present"
        try:
            for name, value in _xml_properties(_bounded_xmp(pdf.Root["/Metadata"])):
                add("XMP", XMP_COMMON.get(name, name), value.rstrip("\n"))
        except OverflowError:
            xmp_state = "limited"
        except (expat.ExpatError, ValueError, TypeError, pikepdf.PdfError, zlib.error):
            xmp_state = "unreadable"
    return info_state, xmp_state, tuple(properties)


def inspect_share(path: Path, *, max_nodes: int = 50_000, timeout: float = 10.0) -> ShareInspection:
    try:
        size = path.stat().st_size
        with pikepdf.open(path, suppress_warnings=True) as pdf:
            return inspect_open_share(pdf, size, max_nodes=max_nodes, timeout=timeout)
    except pikepdf.PasswordError:
        return ShareInspection(encrypted=True, warnings=("encrypted",))
    except (OSError, ValueError, TypeError, pikepdf.PdfError):
        return ShareInspection(warnings=("analysis_failed",))


def _field_properties(obj):
    field_type = value = None
    seen = set()
    for _ in range(32):
        if not isinstance(obj, pikepdf.Dictionary):
            return field_type, value
        if obj.is_indirect:
            if obj.objgen in seen:
                raise ValueError("cyclic field parent")
            seen.add(obj.objgen)
        if field_type is None:
            field_type = obj.get("/FT")
        if value is None:
            value = obj.get("/V")
        obj = obj.get("/Parent")
    raise ValueError("field ancestry limit")


def inspect_open_share(
    pdf: pikepdf.Pdf, size: int, *, max_nodes=50_000, timeout=10.0
) -> ShareInspection:
    started = time.monotonic()
    info, xmp, properties = metadata(pdf)
    counts = dict.fromkeys(CATEGORIES, 0)
    pending = [(pdf.Root, "")]
    seen = set()
    attachments = set()
    complete = True
    warnings = []
    nodes = 0
    try:
        while pending:
            nodes += 1
            if nodes > max_nodes or time.monotonic() - started > timeout:
                complete = False
                break
            obj, role = pending.pop()
            if not isinstance(obj, (pikepdf.Dictionary, pikepdf.Array, pikepdf.Stream)):
                continue
            if obj.is_indirect:
                if obj.objgen in seen:
                    continue
                seen.add(obj.objgen)
            if isinstance(obj, pikepdf.Array):
                children = ((child, role) for child in obj)
            else:
                subtype = str(obj.get("/Subtype", ""))
                if obj.get("/Type") == pikepdf.Name.Annot or ("/Rect" in obj and subtype):
                    kind = (
                        "links"
                        if subtype == "/Link"
                        else "widgets"
                        if subtype == "/Widget"
                        else "comments"
                    )
                    counts[kind] += 1
                field_type, field_value = (
                    _field_properties(obj) if "/FT" in obj or subtype == "/Widget" else (None, None)
                )
                if field_type is not None and not obj.get("/Kids"):
                    counts["forms"] += 1
                    if field_type == pikepdf.Name.Sig and not field_value:
                        counts["empty_signatures"] += 1
                if (
                    obj.get("/Type") in (pikepdf.Name.Sig, pikepdf.Name.DocTimeStamp)
                    or "/ByteRange" in obj
                    or role == "signature_value"
                ):
                    value = obj.get("/Contents")
                    if isinstance(value, pikepdf.String) and any(bytes(value)):
                        counts["signatures"] += 1
                    elif "/ByteRange" in obj:
                        complete = False
                ef = obj.get("/EF")
                if isinstance(ef, pikepdf.Dictionary):
                    # Same embedded stream through a name tree, AF or annotation counts once.
                    for embedded in ef.values():
                        if isinstance(embedded, pikepdf.Stream):
                            attachments.add(embedded.objgen)
                action = str(obj.get("/S", ""))
                if role == "action" or action in {
                    "/JavaScript",
                    "/Launch",
                    "/URI",
                    "/GoToR",
                    "/SubmitForm",
                    "/ImportData",
                    "/GoToE",
                }:
                    category = (
                        "internal_navigation"
                        if action in {"/GoTo", "/Named"}
                        else "external_references"
                        if action in {"/URI", "/GoToR", "/GoToE"}
                        else "active_actions"
                        if action
                        in {
                            "/JavaScript",
                            "/Launch",
                            "/SubmitForm",
                            "/ImportData",
                            "/ResetForm",
                            "/Hide",
                            "/SetOCGState",
                            "/Rendition",
                            "/Movie",
                            "/Sound",
                            "/Trans",
                        }
                        else "unknown_actions"
                    )
                    counts[category] += 1
                if isinstance(obj.get("/OpenAction"), pikepdf.Array) or "/Dest" in obj:
                    counts["internal_navigation"] += 1
                if "/F" in obj and isinstance(obj, pikepdf.Stream):
                    counts["external_references"] += 1
                children = (
                    (
                        child,
                        "signature_value"
                        if key == "/V" and obj.get("/FT") == pikepdf.Name.Sig
                        else "action"
                        if key in {"/A", "/OpenAction", "/Next"}
                        else "additional_actions"
                        if key == "/AA"
                        else "action"
                        if role == "additional_actions"
                        else "",
                    )
                    for key, child in obj.items()
                )
            for child in children:
                if len(pending) + nodes >= max_nodes:
                    complete = False
                    break
                pending.append(child)
            if not complete:
                break
    except (ValueError, TypeError, pikepdf.PdfError, RecursionError):
        complete = False
    if not complete:
        warnings.append("analysis_incomplete")
    counts["attachments"] = len(attachments)
    return ShareInspection(
        len(pdf.pages),
        size,
        pdf.is_encrypted,
        info,
        xmp,
        properties,
        tuple(counts.values()),
        complete,
        tuple(warnings),
    )
