import os
from datetime import datetime
import json

from dotenv import load_dotenv
import gitlab
from git import Repo
import dateutil.parser as dp

class App():

    def __init__(self, token: str) -> None:
        self.token = token
        self.gl = None
        self.user = None
        self.events = None
        self.repo = None

    def establish_connection(self) -> None:
        """
        Establishes a connection to the GitLab API using the private token.
        """
        self.gl = gitlab.Gitlab(private_token=self.token)

    def authenticate(self) -> None:
        """
        Authenticates the user and sets the user attribute to the authenticated user.
        """
        self.gl.auth()
        self.user = self.gl.user
        print(f"Authenticated as {self.user.name} ({self.user.username})")

    def get_valid_user_events(self) -> None:
        """
        Gets events for the user. Filters to only include events with the following `action_name`s:
        - "opened": Merge requests, issues, etc.
        - "created": Projects

        Other valid GitHub contributions, including commits and merged merge requests, will be
        handled via other methods.
        """
        events = self.gl.events.list(sort="asc", all=True, action="created")
        print(f"Found {len(events)} events")
        events_as_dicts = [event.attributes for event in events]
        self.events = events_as_dicts

    def create_repo(self) -> Repo:
        """
        Creates a new repository.
        """
        repo = Repo.init("new_repo")
        print(f"Created new repository at {repo.working_dir}")
        return repo

    def create_commit(self, event) -> None:
        """
        Creates a new commit from the event. The commit should not contain
        any changes or staged files, but should contain:
        - The type of action (e.g. "pushed to", "opened", "closed", etc.)
        - The action target (e.g. "branch", "issue", "merge request", etc.)
        - The associated project_id
        - The commit hash, if applicable
        The commit should be timestamped with the event's created_at attribute.
        """

        # Create a new commit

        if self.repo:
            commit = self.repo.index.commit(
                f"{event['action_name']} {event.get('target_type', None)} in project {event['project_id']}",
                author_date=dp.parse(event["created_at"])
            )
            print(f"Created commit {commit.hexsha} for event at {datetime.fromtimestamp(commit.authored_date)}")
        else:
            raise Exception("No repository found")



    def create_commits_from_events(self) -> None:
        """
        Creates commits from the filtered events.
        """
        for event in self.events:
            self.create_commit(event)

    def export_events_to_file(self) -> None:
        """
        Exports the events to a file.
        """
        with open("events.json", "w") as f:
            json_to_write = [event for event in self.events]
            f.write(json.dumps(json_to_write, indent=4))


    def run(self) -> None:
        """
        Runs the application.
        """
        self.establish_connection()
        self.authenticate()
        self.get_valid_user_events()
        self.repo = self.create_repo()
        # self.create_commits_from_events()
        self.export_events_to_file()


if __name__ == "__main__":
    if not load_dotenv():
        raise Exception("No environment variables found.")
    token = os.getenv("PRIVATE-TOKEN")
    app = App(token)
    app.run()
