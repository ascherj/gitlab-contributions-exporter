import os
from datetime import datetime
import json

from dotenv import load_dotenv
import gitlab
from git import Repo
import dateutil.parser as dp

class GitlabAPI:
    def __init__(self, instance: str, token: str) -> None:
        self.instance = instance
        self.token = token
        self.gl = None
        self.user = None

    def establish_connection(self):
        """
        Establishes a connection to the GitLab API using the private token.
        """
        self.gl = gitlab.Gitlab(url=self.instance, private_token=self.token)

    def authenticate(self):
        """
        Authenticates the user and sets the user attribute to the authenticated user.
        """
        self.gl.auth()
        self.user = self.gl.user
        print(f"Authenticated as {self.user.name} ({self.user.username}) on {self.instance}")

    def get_valid_user_events(self) -> list:
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
        return events_as_dicts

    def get_projects(self) -> list:
        """
        Gets all projects for the user.
        """
        projects = self.gl.projects.list(all=True, membership=True, sort="asc")
        print(f"Found {len(projects)} projects")
        projects_as_dicts = [project.attributes for project in projects]
        return projects_as_dicts

    def get_user_commits_for_projects(self, projects: list, author_email: str) -> list:
        """
        Gets all commits for the user in the specified projects.
        """
        commits = []
        for project in projects:
            commits += self._get_commits(project["id"], project["created_at"], author_email)
        print(f"Found {len(commits)} commits by {author_email} in {len(projects)} projects")
        return commits

    def _get_commits(self, project_id: int, project_created_at: str, author_email: str) -> list:
        """
        Gets all commits for a project by the author.
        """
        try:
            commits = self.gl.projects.get(project_id).commits.list(author=author_email, all=True)
            print(f"Found {len(commits)} commits by {author_email} in project {project_id}")
            # Filter out commits that were created before the project was created
            commits_as_dicts = [commit.attributes for commit in commits if dp.parse(commit.attributes["committed_date"]) > dp.parse(project_created_at)]
            print(f"Kept {len(commits_as_dicts)} commits")
            return commits_as_dicts
        except gitlab.exceptions.GitlabError as e:
            print(f"Error: {e}")
            return []

class App:

    def __init__(self, instance: str, token: str) -> None:
        self.api = GitlabAPI(instance, token)
        self.contributions = None
        self.events = None
        self.merge_requests = None

    def check_for_existing_exports(self) -> None:
        """
        Checks for existing exports and updates instance attributes if found.
        """
        if os.path.exists("EXPORT_events.json"):
            print("Found existing events export")
            with open("EXPORT_events.json", "r") as f:
                self.events = json.load(f)
        if os.path.exists("EXPORT_merge_requests.json"):
            print("Found existing merge requests export")
            with open("EXPORT_merge_requests.json", "r") as f:
                self.merge_requests = json.load(f)
        if os.path.exists("EXPORT_projects.json"):
            print("Found existing projects export")
            with open("EXPORT_projects.json", "r") as f:
                self.projects = json.load(f)
        if os.path.exists("EXPORT_clean_commits.json"):
            print("Found existing clean commits export")
            with open("EXPORT_clean_commits.json", "r") as f:
                self.commits = json.load(f)


    def create_repo(self) -> Repo:
        """
        Creates a new repository. If a repository already exists, it will be deleted and a new one will be created.
        """
        if os.path.exists("new_repo"):
            print("Deleting existing repository")
            os.system("rm -rf new_repo")
        repo = Repo.init("new_repo")
        print(f"Created new repository at {repo.working_dir}")
        return repo

    def create_commit(self, contribution: dict) -> None:
        """
        Creates a commit from the contribution.
        """
        if self.repo:
            commit = self.repo.index.commit(
                message=contribution["message"] + f' {contribution["project_id"]}',
                author_date=dp.parse(contribution["date"]),
            )
            print(f"Created commit {commit.hexsha} for contribution at {datetime.fromtimestamp(commit.authored_date)}")
        else:
            raise Exception("No repository found")

    def create_commits_from_contributions(self) -> None:
        """
        Creates commits from the contributions.
        """
        for contribution in self.contributions:
            self.create_commit(contribution)


    # def create_commits_from_events(self) -> None:
    #     """
    #     Creates commits from the filtered events.
    #     """
    #     for event in self.events:
    #         self.create_commit(event, "event")

    # def create_commits_from_merge_requests(self) -> None:
    #     """
    #     Creates commits from the merge requests.
    #     """
    #     for merge_request in self.merge_requests:
    #         self.create_commit(merge_request, "merge_request")

    # def create_commits_from_commits(self) -> None:
    #     """
    #     Creates commits from the user's commits.
    #     """
    #     for commit in self.commits:
    #         self.create_commit(commit, "commit")

    def export_dicts_to_file(self, dicts, filename) -> None:
        """
        Exports the list of dictionaries to a file.
        """
        with open(f"EXPORT_{filename}.json", "w") as f:
            json_to_write = [d for d in dicts]
            f.write(json.dumps(json_to_write, indent=4))

    def process_contributions(self, events, merge_requests, commits) -> None:
        """
        Process the contributions into uniform dictionaries sorted by contribution time.
        """
        contributions = []
        for event in events:
            contributions.append({
                "type": "event",
                "message": "Created project" if event["action_name"] == "created" else "Opened merge request in project",
                "project_id": event["project_id"],
                "date": event["created_at"]
            })

        for merge_request in merge_requests:
            contributions.append({
                "type": "merge_request",
                "message": "Merged merge request in project",
                "project_id": merge_request["project_id"],
                "date": merge_request["merged_at"]
            })

        for commit in commits:
            contributions.append({
                "type": "commit",
                "message": "Committed to project",
                "project_id": commit["project_id"],
                "date": commit["committed_date"]
            })

        contributions.sort(key=lambda x: x["date"])
        self.contributions = contributions


    def run(self) -> None:
        """
        Runs the application.
        """
        # self.check_for_existing_exports()

        self.api.establish_connection()
        self.api.authenticate()

        # Get events (not including commits)
        self.events = self.api.get_valid_user_events()
        self.export_dicts_to_file(self.events, "events")

        # Get projects (to retrieve individual commits)
        self.projects = self.api.get_projects()
        self.export_dicts_to_file(self.projects, "projects")

        # Get commits
        self.commits = self.api.get_user_commits_for_projects(self.projects, self.api.user.commit_email)
        self.export_dicts_to_file(self.commits, "commits")

        # self.process_contributions(self.events, self.merge_requests, self.commits)

        # self.repo = self.create_repo()
        # self.create_commits_from_contributions()

if __name__ == "__main__":
    if not load_dotenv():
        raise Exception("No environment variables found.")
    instance = os.getenv("GITLAB-INSTANCE")
    token = os.getenv("GITLAB-TOKEN") if "galvanize" not in instance else os.getenv("GITLAB-GALVANIZE-TOKEN")
    app = App(instance, token)
    app.run()
