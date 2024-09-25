import gitlab
import dateutil.parser as dp
from custom_types import GitlabEvent, GitlabProject, GitlabCommit

class GitlabAPIWrapper:
    def __init__(self, instance: str, private_token: str | None = None, oauth_token: str | None = None) -> None:
        self.instance = instance
        self.private_token = private_token
        self.oauth_token = oauth_token
        self.gl = None
        self.user = None

    def establish_connection(self):
        """
        Establishes a connection to the GitLab API using the private token, OAuth token, or neither if not provided.
        """
        if self.private_token:
            self.gl = gitlab.Gitlab(url=self.instance, private_token=self.private_token)
        elif self.oauth_token:
            self.gl = gitlab.Gitlab(url=self.instance, oauth_token=self.oauth_token)
        else:
            raise ValueError("Authentication requires either a private token or an OAuth token")

    def authenticate(self):
        """
        Authenticates the user and sets the user attribute to the authenticated user.
        """
        self.gl.auth()
        self.user = self.gl.user
        print(f"Authenticated as {self.user.name} ({self.user.username}) on {self.instance}")

    def get_valid_user_events(self) -> list[GitlabEvent]:
        """
        Gets events for the user. Filters to only include events with the following `action_name`s:
        - "opened": Merge requests, issues, etc.
        - "created": Projects
        - "accepted": Merge requests
        """
        events = self.gl.events.list(sort="asc", all=True, action="created")
        events.extend(self.gl.events.list(sort="asc", all=True, action="merged"))
        print(f"Found {len(events)} events")
        events_as_dicts = [event.attributes for event in events]
        events_as_gitlab_events = [GitlabEvent(**event) for event in events_as_dicts]
        return events_as_gitlab_events

    def get_projects(self) -> list[GitlabProject]:
        """
        Gets all projects for the user.
        """
        projects = self.gl.projects.list(all=True, membership=True, sort="asc")
        print(f"Found {len(projects)} projects")
        projects_as_dicts = [project.attributes for project in projects]
        projects_as_gitlab_projects = [GitlabProject(**project) for project in projects_as_dicts]
        return projects_as_gitlab_projects

    def get_user_commits_for_projects(self, projects: list) -> list[GitlabCommit]:
        """
        Gets all commits for the user in the specified projects.
        """
        commits = []
        for project in projects:
            commits += self._get_commits(project["id"], project["created_at"])
        print(f"Found {len(commits)} commits by {self.user.commit_email} in {len(projects)} projects")
        return commits

    def _get_commits(self, project_id: int, project_created_at: str) -> list[GitlabCommit]:
        """
        Gets all commits for a project by the author.
        """
        try:
            commits = self.gl.projects.get(project_id).commits.list(author=self.user.commit_email, all=True)
            print(f"Found {len(commits)} commits by {self.user.commit_email} in project {project_id}")
            # Filter out commits that were created before the project was created
            commits_as_dicts = [commit.attributes for commit in commits if dp.parse(commit.attributes["committed_date"]) > dp.parse(project_created_at)]
            print(f"Kept {len(commits_as_dicts)} commits")
            commits_as_gitlab_commits = [GitlabCommit(**commit) for commit in commits_as_dicts]
            return commits_as_gitlab_commits
        except gitlab.exceptions.GitlabError as e:
            print(f"Error: {e}")
            return []
