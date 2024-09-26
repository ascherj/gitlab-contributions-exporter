from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str

class UserBase(BaseModel):
    id: int
    username: str
    email: str
    name: str

class GitlabContribution(BaseModel):
    contribution_type: str
    message: str
    project_id: int
    date: str
    instance: str
