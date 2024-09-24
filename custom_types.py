from typing import TypedDict
from typing_extensions import NotRequired


class GitlabEvent(TypedDict):
    id: int
    project_id: int
    action_name: str
    target_type: str
    created_at: str
    instance: NotRequired[str]

class GitlabProject(TypedDict):
    id: int
    created_at: str
    instance: NotRequired[str]

class GitlabCommit(TypedDict):
    id: int
    created_at: str
    author_email: str
    title: str
    message: str
    url: str
    instance: NotRequired[str]

class GitlabContribution(TypedDict):
    contribution_type: str
    message: str
    project_id: int
    date: str
    instance: str

class Projects(TypedDict):
    created: int

class MergeRequests(TypedDict):
    opened: int
    accepted: int

class Issues(TypedDict):
    opened: int

class GitlabCounts(TypedDict):
    projects: Projects
    merge_requests: MergeRequests
    issues: Issues
    commits: int
