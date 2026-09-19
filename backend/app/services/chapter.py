"""Chapter inference from the academic calendar.

Given a student profile (grade, textbook version, optional semester,
optional enrollment date), the system picks the most likely current chapter
from the configured `grade_chapters` map. The default schedule spreads
chapters evenly across the school year (Sep 1 to Jul 1 of the next calendar
year), split into 上学期 (semester 1) and 下学期 (semester 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from app.config import get_business_config


@dataclass(frozen=True)
class ChapterSuggestion:
    title: str
    order: int
    semester: Optional[int] = None
    rationale: str = ""


def _chapters_for(textbook: str, grade: str) -> list[str]:
    cfg = get_business_config()
    map_ = (cfg.get("academic") or {}).get("grade_chapters") or {}
    key = f"{textbook}-{grade}"
    return map_.get(key, [])


def _weeks_into_school_year(today: date, start_month: int) -> int:
    """Return how many weeks have elapsed since the school year started."""
    year = today.year
    start = date(year, start_month, 1)
    if today < start:
        start = date(year - 1, start_month, 1)
    delta_days = (today - start).days
    return max(0, delta_days // 7)


def _infer_semester_from_date(today: date) -> int:
    """Map a date to a semester (1 = 上学期 Sep–Jan, 2 = 下学期 Feb–Jul).

    Falls back to month-based heuristic: Aug–Jan → 1, Feb–Jul → 2.
    """
    cfg = get_business_config()
    semesters = (cfg.get("academic") or {}).get("semesters") or {}
    # Try configured ranges first.
    month_day = today.strftime("%m-%d")
    for label, info in semesters.items():
        try:
            sem_n = int(label)
        except (TypeError, ValueError):
            continue
        start = info.get("start") if isinstance(info, dict) else None
        end = info.get("end") if isinstance(info, dict) else None
        if not start or not end:
            continue
        # The configured end may wrap the new year (e.g. 01-15 for sem 1).
        if start <= end:
            if start <= month_day <= end:
                return sem_n
        else:
            if month_day >= start or month_day <= end:
                return sem_n
    # Heuristic fallback.
    return 1 if today.month <= 1 or today.month >= 8 else 2


def _semester_slice(
    chapters: list[str], semester: Optional[int]
) -> list[str]:
    """Return the half of chapters belonging to a given semester."""
    if not chapters or semester not in (1, 2):
        return list(chapters)
    mid = (len(chapters) + 1) // 2  # sem 1 gets the extra chapter if odd
    if semester == 1:
        return list(chapters[:mid])
    return list(chapters[mid:])


def chapters_for_semester(
    textbook: Optional[str], grade: Optional[str], semester: Optional[int]
) -> list[str]:
    """Chapters for (textbook, grade) filtered to the requested semester."""
    return _semester_slice(all_chapter_titles(textbook or "", grade or ""), semester)


def infer_chapter(
    *,
    textbook: Optional[str],
    grade: Optional[str],
    semester: Optional[int] = None,
    today: Optional[date] = None,
) -> Optional[ChapterSuggestion]:
    if not textbook or not grade:
        return None
    chapters = _chapters_for(textbook, grade)
    if not chapters:
        return None
    cfg = get_business_config()
    start_month = (cfg.get("academic") or {}).get("school_year_start_month", 9)
    today = today or date.today()

    # Resolve semester: explicit wins, otherwise infer from date.
    if semester not in (1, 2):
        semester = _infer_semester_from_date(today)

    sem_chapters = _semester_slice(chapters, semester)
    if not sem_chapters:
        return None

    # Position within the school-year half based on weeks since start.
    weeks_in = _weeks_into_school_year(today, start_month)
    # 20 weeks per semester ≈ a typical schedule.
    weeks_per_sem = 20
    if semester == 2:
        weeks_in_sem = max(0, weeks_in - 20)
    else:
        weeks_in_sem = min(weeks_in, 20)
    idx = min(len(sem_chapters) - 1, weeks_in_sem // max(1, weeks_per_sem // len(sem_chapters)))

    return ChapterSuggestion(
        title=sem_chapters[idx],
        order=idx + 1,
        semester=semester,
        rationale=(
            f"Inferred from {textbook} {grade} semester {semester}: "
            f"week {weeks_in} → chapter index {idx}"
        ),
    )


def all_chapter_titles(textbook: str, grade: str) -> list[str]:
    return list(_chapters_for(textbook, grade))