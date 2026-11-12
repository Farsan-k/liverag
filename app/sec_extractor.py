
from pathlib import Path
from bs4 import BeautifulSoup
from typing import Any


def load_sec_report(file_path: str | Path) -> BeautifulSoup:
    """
    Load an SEC 10-K XHTML/iXBRL report.

    Args:
        file_path: Path to the SEC report.

    Returns:
        Parsed BeautifulSoup XML document.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"SEC report not found: {path}")

    if not path.is_file():
        raise ValueError(f"Expected a file, got: {path}")

    content = path.read_text(
        encoding="utf-8",
        errors="replace"
    )

    return BeautifulSoup(content, "xml")



def extract_contexts(soup: BeautifulSoup) -> dict[str, dict[str, Any]]:
    """
    Extract XBRL contexts, including dimensional axes and members.
    """
    contexts = {}

    for context in soup.find_all(
        lambda tag: tag.name and tag.name.lower().endswith("context")
    ):
        context_id = context.get("id")

        if not context_id:
            continue

        context_data = {
            "identifier": None,
            "start_date": None,
            "end_date": None,
            "instant": None,
            "dimensions": []
        }

        for child in context.find_all(recursive=True):
            name = (child.name or "").lower()
            value = child.get_text(" ", strip=True)

            if name.endswith("identifier"):
                context_data["identifier"] = value

            elif name.endswith("startdate"):
                context_data["start_date"] = value

            elif name.endswith("enddate"):
                context_data["end_date"] = value

            elif name.endswith("instant"):
                context_data["instant"] = value

            elif name.endswith("explicitmember"):
                context_data["dimensions"].append({
                    "type": "explicit",
                    "axis": child.parent.name,
                    "member": value
                })

            elif name.endswith("typedmember"):
                context_data["dimensions"].append({
                    "type": "typed",
                    "axis": child.parent.name,
                    "member": value
                })

        contexts[context_id] = context_data

    return contexts


def extract_numeric_facts(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """
    Extract raw numeric XBRL facts from an SEC report.
    Preserves original values and metadata.
    """
    facts = []

    for tag in soup.find_all(
        lambda element: element.name
        and element.name.lower().endswith("nonfraction")
    ):
        attributes = {
            key.lower(): value
            for key, value in tag.attrs.items()
        }

        fact = {
            "name": attributes.get("name"),
            "context_ref": attributes.get("contextref"),
            "unit_ref": attributes.get("unitref"),
            "scale": attributes.get("scale"),
            "sign": attributes.get("sign"),
            "decimals": attributes.get("decimals"),
            "format": attributes.get("format"),
            "fact_id": attributes.get("id"),
            "raw_value": tag.get_text("", strip=True)
        }

        facts.append(fact)

    return facts


def enrich_facts_with_contexts(
    facts: list[dict[str, Any]],
    contexts: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Attach reporting context information to each numeric fact.
    """
    enriched_facts = []

    for fact in facts:
        context_ref = fact.get("context_ref")

        enriched_fact = {
            **fact,
            "context": contexts.get(context_ref)
        }

        enriched_facts.append(enriched_fact)

    return enriched_facts


def normalize_numeric_value(fact: dict[str, Any]) -> float | None:
    """
    Convert an XBRL numeric fact into its scaled numeric value.
    """
    raw_value = fact.get("raw_value")

    if not raw_value:
        return None

    try:
        value = float(raw_value.replace(",", "").strip())

        scale = int(fact.get("scale") or 0)
        value *= 10 ** scale

        if fact.get("sign") == "-":
            value = -abs(value)

        return value

    except (ValueError, TypeError):
        return None