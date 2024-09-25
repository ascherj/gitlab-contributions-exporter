from pydantic import BaseModel

class GitlabContribution(BaseModel):
    contribution_type: str
    message: str
    project_id: int
    date: str
    instance: str
