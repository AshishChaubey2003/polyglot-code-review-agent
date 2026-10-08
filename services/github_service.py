"""
GitHub integration -- DEFERRED per the master prompt's own phasing
("do not implement until the core review/repair pipeline is stable").

This is a genuine stub: calling anything here raises NotImplementedError
with a note on what it will do, not a fake success. The intended shape
(for whoever picks this up next):
  - `fetch_pr_diff(repo, pr_number)` -- pull the changed files/lines
  - `post_review_comment(repo, pr_number, finding)` -- one comment per
    finding, anchored to its file/line, not one giant dump
  - `post_fix_suggestion(repo, pr_number, proposed_fix)` -- GitHub's
    "suggested change" comment format, only for an already-approved
    ProposedFix (never for a pending one)
This would need its own guardrail: never post a comment containing a
fix for a finding the human hasn't approved in human_loop/approval.py.
"""

from __future__ import annotations


class GitHubServiceError(Exception):
    """Raised by every function in this module -- it is not implemented yet."""


def fetch_pr_diff(repo: str, pr_number: int):
    raise GitHubServiceError(
        "GitHub integration is deferred -- fetch_pr_diff() is not implemented. "
        "See this module's docstring for the intended shape."
    )


def post_review_comment(repo: str, pr_number: int, finding):
    raise GitHubServiceError(
        "GitHub integration is deferred -- post_review_comment() is not implemented."
    )


def post_fix_suggestion(repo: str, pr_number: int, proposed_fix):
    raise GitHubServiceError(
        "GitHub integration is deferred -- post_fix_suggestion() is not implemented."
    )
