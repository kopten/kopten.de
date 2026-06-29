#!/usr/bin/env python3
"""One-shot XML migration: wraps <bischof> and <priester> in a new <ansprechpartner> container.

Changes:
- <bischof> and <priester> → children of <ansprechpartner>
- <priester><person>…</person></priester> flattened: each <person> becomes a direct <priester>
- <bischof><weitere_priester><priester>text</priester> extracted as structured <priester> siblings

Run once:
    cd /path/to/kopten.de && python3 scripts/migrate_ansprechpartner.py
"""

import xml.etree.ElementTree as ET

XML_PATH = "data/kopten_gemeinden.xml"

HOEXTER_WEITERE = [
    {
        "name": "Pater Girgis El Moharaki",
        "funktion": "Generalvikar der Diözese",
        "mobil": "0049-(0)171 436 0460",
    },
    {
        "name": "Pater Bolikarbos El Moharaky",
        "mobil": "0049-(0)173 9902 895",
    },
]

PERSON_TAGS = ["name", "funktion", "mobil", "email", "postanschrift"]


def copy_tags(src, dst, tags):
    for tag in tags:
        el = src.find(tag)
        if el is not None and el.text and el.text.strip():
            sub = ET.SubElement(dst, tag)
            sub.text = el.text.strip()


def make_priester_from_data(data):
    el = ET.Element("priester")
    for tag in PERSON_TAGS:
        if data.get(tag):
            sub = ET.SubElement(el, tag)
            sub.text = data[tag]
    return el


def migrate_gemeinde(g):
    bischof_el = g.find("bischof")
    priester_el = g.find("priester")

    if bischof_el is None and priester_el is None:
        return

    children = list(g)
    b_idx = children.index(bischof_el) if bischof_el is not None else None
    p_idx = children.index(priester_el) if priester_el is not None else None
    insert_idx = min(x for x in [b_idx, p_idx] if x is not None)

    ansp = ET.Element("ansprechpartner")

    if bischof_el is not None:
        new_b = ET.SubElement(ansp, "bischof")
        copy_tags(bischof_el, new_b, PERSON_TAGS)

        weitere_el = bischof_el.find("weitere_priester")
        if weitere_el is not None and g.get("id") == "hoexter":
            for data in HOEXTER_WEITERE:
                ansp.append(make_priester_from_data(data))

    if priester_el is not None:
        person_els = priester_el.findall("person")
        if person_els:
            for pe in person_els:
                new_p = ET.SubElement(ansp, "priester")
                copy_tags(pe, new_p, PERSON_TAGS)
        elif any(priester_el.find(t) is not None for t in PERSON_TAGS):
            new_p = ET.SubElement(ansp, "priester")
            copy_tags(priester_el, new_p, PERSON_TAGS)
        # empty <priester> with no data → skip

    # Remove old elements (higher index first to preserve lower index)
    to_remove = sorted(
        [(el, idx) for el, idx in [(bischof_el, b_idx), (priester_el, p_idx)] if el is not None],
        key=lambda x: x[1],
        reverse=True,
    )
    for el, _ in to_remove:
        g.remove(el)

    g.insert(insert_idx, ansp)


def main():
    tree = ET.parse(XML_PATH)
    root = tree.getroot()

    count = 0
    for g in root.findall("gemeinde"):
        migrate_gemeinde(g)
        count += 1

    ET.indent(root, space="  ")

    with open(XML_PATH, "w", encoding="utf-8") as f:
        f.write("<?xml version='1.0' encoding='utf-8'?>\n")
        f.write(ET.tostring(root, encoding="unicode"))
        f.write("\n")

    print(f"Migration complete. Processed {count} gemeinden.")
    print(f"Updated: {XML_PATH}")


if __name__ == "__main__":
    main()
