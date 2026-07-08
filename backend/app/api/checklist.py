from dataclasses import dataclass
from typing import Literal, Optional

from fastapi import APIRouter

from app.models.schemas import (
    ChecklistItem,
    ChecklistRequest,
    ChecklistResponse,
    ChecklistSection,
)
from app.rag.vector_store import lookup_source_by_title

router = APIRouter(tags=["checklist"])

DISCLAIMER = (
    "This is a general checklist based on public sources. "
    "Check official pages for your individual situation."
)

Condition = Optional[Literal["international", "on_campus"]]


@dataclass(frozen=True)
class TaskTemplate:
    task: str
    source_title: str
    condition: Condition = None


# Each template's source_title is looked up live against the vector store
# (see _build_item) rather than hardcoding a URL — if a source's URL ever
# changes in sources.json, re-running the ingestion pipeline picks it up
# here automatically, with no code change.
SECTIONS: list[tuple[str, list[TaskTemplate]]] = [
    (
        "Before Arrival",
        [
            TaskTemplate("Review New Student Orientation information.", "New Student Orientation"),
            TaskTemplate(
                "Review the ISSS New Student Checklist for pre-arrival steps.",
                "ISSS New Student Checklist",
                "international",
            ),
            TaskTemplate(
                "Review the University Housing New Resident FAQ.",
                "University Housing New Resident FAQ",
                "on_campus",
            ),
        ],
    ),
    (
        "Before Classes Start",
        [
            TaskTemplate("Review the Welcome Week schedule.", "Welcome Week"),
        ],
    ),
    (
        "Move-In Week",
        [
            TaskTemplate(
                "Review Move-In week logistics.", "University Housing Move-In", "on_campus"
            ),
            TaskTemplate("Get your i-card.", "i-card Information"),
        ],
    ),
    (
        "First Week",
        [
            TaskTemplate(
                "Complete International Student Check-In.",
                "International Student Check-In",
                "international",
            ),
            TaskTemplate("Learn how to ride MTD buses with your i-card.", "MTD Fares and Passes"),
        ],
    ),
    (
        "First Month",
        [
            TaskTemplate(
                "Review immunization requirements and general health resources.",
                "McKinley Immunization Information",
            ),
            TaskTemplate(
                "Learn about accessibility accommodations if you need them.",
                "DRES Accommodations",
            ),
        ],
    ),
]


def _applies(template: TaskTemplate, request: ChecklistRequest) -> bool:
    if template.condition == "international":
        return request.student_status == "international"
    if template.condition == "on_campus":
        return request.housing == "on-campus"
    return True


def _build_item(template: TaskTemplate) -> ChecklistItem:
    source = lookup_source_by_title(template.source_title)
    return ChecklistItem(
        task=template.task,
        source_title=source["source_title"] if source else None,
        source_url=source["source_url"] if source else None,
    )


@router.post("/checklist/generate", response_model=ChecklistResponse)
def generate_checklist(request: ChecklistRequest) -> ChecklistResponse:
    """Generate a general onboarding checklist. No identifying fields are
    accepted (see ChecklistRequest) — only student_type, student_status,
    term, and housing. Source links are pulled live from the vector store
    (see lookup_source_by_title) and gracefully omitted, not errored, if
    the index hasn't been built yet.
    """
    sections = [
        ChecklistSection(
            title=title,
            items=[_build_item(t) for t in templates if _applies(t, request)],
        )
        for title, templates in SECTIONS
    ]

    return ChecklistResponse(disclaimer=DISCLAIMER, sections=sections)
