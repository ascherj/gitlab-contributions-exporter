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

    def get_user_commits_for_projects(self, projects: list) -> list:
        """
        Gets all commits for the user in the specified projects.
        """
        commits = []
        for project in projects:
            commits += self._get_commits(project["id"], project["created_at"])
        print(f"Found {len(commits)} commits by {self.user.commit_email} in {len(projects)} projects")
        return commits

    def _get_commits(self, project_id: int, project_created_at: str) -> list:
        """
        Gets all commits for a project by the author.
        """
        try:
            commits = self.gl.projects.get(project_id).commits.list(author=self.user.commit_email, all=True)
            print(f"Found {len(commits)} commits by {self.user.commit_email} in project {project_id}")
            # Filter out commits that were created before the project was created
            commits_as_dicts = [commit.attributes for commit in commits if dp.parse(commit.attributes["committed_date"]) > dp.parse(project_created_at)]
            print(f"Kept {len(commits_as_dicts)} commits")
            return commits_as_dicts
        except gitlab.exceptions.GitlabError as e:
            print(f"Error: {e}")
            return []

class App:

    def __init__(self, instances: list, tokens: list) -> None:
        self.apis = [GitlabAPI(instance, token) for instance, token in zip(instances, tokens)]
        self.contributions: list[dict] = None
        self.events: list[dict] = None
        self.projects: list[dict] = None
        self.commits: list[dict] = None
        self.repo: Repo = None

    def check_for_existing_exports(self) -> None:
        """
        Checks for existing exports and updates instance attributes if found.
        """
        if os.path.exists("db/EXPORT_events.json"):
            print("Found existing events export")
            with open("db/EXPORT_events.json", "r") as f:
                self.events = json.load(f)
        if os.path.exists("db/EXPORT_projects.json"):
            print("Found existing projects export")
            with open("db/EXPORT_projects.json", "r") as f:
                self.projects = json.load(f)
        if os.path.exists("db/EXPORT_commits.json"):
            print("Found existing commits export")
            with open("db/EXPORT_commits.json", "r") as f:
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
            message = (
                f"{contribution['message']}\n\n"
                f"Date: {contribution['date']}\n"
                f"(Project ID: {contribution['project_id']}, Instance: {contribution['instance']})"
            )
            commit_date = dp.parse(contribution["date"])
            commit = self.repo.index.commit(
                message=message,
                author_date=commit_date,
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

    def export_dicts_to_file(self, dicts: list[dict], filename: str) -> None:
        """
        Exports the list of dictionaries to a file.
        """
        os.makedirs("db", exist_ok=True)
        with open(f"db/EXPORT_{filename}.json", "w") as f:
            json_to_write = [d for d in dicts]
            f.write(json.dumps(json_to_write, indent=4))

    def process_contributions(self) -> None:
        """
        Process the contributions into uniform dictionaries sorted by contribution time.
        """
        contributions = []
        for event in self.events:
            if event["action_name"] == "created":
                contributions.append({
                    "type": "project",
                    "message": "Created project",
                    "project_id": event["project_id"],
                    "date": event["created_at"],
                    "instance": event["instance"]
                })
            elif event["action_name"] == "opened":
                if event["target_type"] == "MergeRequest":
                    contributions.append({
                        "type": "merge_request",
                        "message": "Opened merge request",
                        "project_id": event["project_id"],
                        "date": event["created_at"],
                        "instance": event["instance"]
                    })
                elif event["target_type"] == "Issue":
                    contributions.append({
                        "type": "issue",
                        "message": "Opened issue",
                        "project_id": event["project_id"],
                        "date": event["created_at"],
                        "instance": event["instance"]
                    })
                else:
                    raise Exception(f"Unknown target type: {event['target_type']}")
            elif event["action_name"] == "accepted":
                contributions.append({
                    "type": "merge_request",
                    "message": "Accepted merge request",
                    "project_id": event["project_id"],
                    "date": event["created_at"],
                    "instance": event["instance"]
                })
            else:
                raise Exception(f"Unknown action name: {event['action_name']}")

        for commit in self.commits:
            contributions.append({
                "type": "commit",
                "message": "Committed to project",
                "project_id": commit["project_id"],
                "date": commit["committed_date"],
                "instance": commit["instance"]
            })

        contributions.sort(key=lambda x: x["date"])
        self.contributions = contributions

    def run(self) -> None:
        """
        Runs the application.
        """
        self.check_for_existing_exports()

        if not self.events or not self.projects or not self.commits:
            for api in self.apis:
                api.establish_connection()
                api.authenticate()

        # Get events (not including commits)
        if not self.events:
            self.events = []
            for api in self.apis:
                events = api.get_valid_user_events()
                for event in events:
                    event["instance"] = api.instance
                self.events.extend(events)
            self.export_dicts_to_file(self.events, "events")

        # Get projects (to retrieve individual commits)
        if not self.projects:
            self.projects = []
            for api in self.apis:
                projects = api.get_projects()
                for project in projects:
                    project["instance"] = api.instance
                self.projects.extend(projects)
            self.export_dicts_to_file(self.projects, "projects")

        # Get commits
        if not self.commits:
            self.commits = []
            for api in self.apis:
                instance_projects = [p for p in self.projects if p["instance"] == api.instance]
                commits = api.get_user_commits_for_projects(instance_projects)
                for commit in commits:
                    commit["instance"] = api.instance
                self.commits.extend(commits)
            self.export_dicts_to_file(self.commits, "commits")

        self.process_contributions()

        self.repo = self.create_repo()
        self.create_commits_from_contributions()

if __name__ == "__main__":
    if not load_dotenv():
        raise Exception("No environment variables found.")
    instances = os.getenv("GITLAB-INSTANCE").split(",")
    tokens = os.getenv("GITLAB-TOKEN").split(",")
    app = App(instances, tokens)
    app.run()
    print("Finished processing all instances")
