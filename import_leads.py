"""CSV parsing and validation without any network activity."""

import csv
import io

from leads import validate_lead


def parse_lead_csv(text: str) -> list[tuple[int, dict]]:
    if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > 500_000:
        raise ValueError("Choose a non-empty CSV file up to 500 KB.")
    fields = ("name", "company", "language", "note")
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    result, seen = [], set()
    try:
        for row in reader:
            if not row or all(not value.strip() for value in row):
                continue
            if not result and tuple(value.strip().lower() for value in row) == fields:
                continue
            if len(row) != 4:
                raise ValueError(f"CSV row {reader.line_num} must contain name, company, language, and note.")
            try:
                lead = validate_lead(dict(zip(fields, row)))
            except ValueError as error:
                raise ValueError(f"CSV row {reader.line_num}: {error}") from None
            identity = (lead["name"].casefold(), lead["company"].casefold())
            if identity in seen:
                raise ValueError(f"CSV row {reader.line_num} repeats a lead already in this file.")
            seen.add(identity)
            result.append((reader.line_num, lead))
            if len(result) > 100:
                raise ValueError("Upload at most 100 leads at a time.")
    except csv.Error:
        raise ValueError("CSV formatting is invalid. Quote notes containing commas or newlines.") from None
    if not result:
        raise ValueError("The CSV must contain at least one lead row.")
    return result
