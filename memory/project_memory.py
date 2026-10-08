"""
Project memory -- DEFERRED per the master prompt's phasing. Intended
shape: persist per-project context across review sessions (recurring
findings, previously-approved fix patterns, project-specific coding
conventions) so repeated reviews of the same codebase get sharper over
time instead of starting cold every request. Needs a real storage
decision (which database, how memory is scoped and invalidated) before
it's worth building -- not implemented here, a genuine stub.
"""

from __future__ import annotations


class ProjectMemoryNotImplementedError(Exception):
    pass


def get_project_context(project_id: str):
    raise ProjectMemoryNotImplementedError(
        "Project memory is deferred. See this module's docstring for the intended shape."
    )


def record_review_outcome(project_id: str, review_result):
    raise ProjectMemoryNotImplementedError(
        "Project memory is deferred. See this module's docstring for the intended shape."
    )
