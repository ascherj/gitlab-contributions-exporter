import os
from datetime import datetime
import json

from dotenv import load_dotenv
import gitlab
from git import Repo
import dateutil.parser as dp

class GitlabAPI:
    def __init__(self, token) -> None:
        self.token = token
        self.gl = None
        self.user = None

    def establish_connection(self):
        """
        Establishes a connection to the GitLab API using the private token.
        """
        self.gl = gitlab.Gitlab(private_token=self.token)

    def authenticate(self):
        """
        Authenticates the user and sets the user attribute to the authenticated user.
        """
        self.gl.auth()
        self.user = self.gl.user
        print(f"Authenticated as {self.user.name} ({self.user.username})")

    def get_valid_user_events(self) -> list:
        """
        Gets events for the user. Filters to only include events with the following `action_name`s:
        - "opened": Merge requests, issues, etc.
        - "created": Projects
        """
        events = self.gl.events.list(sort="asc", all=True, action="created")
        print(f"Found {len(events)} events")
        events_as_dicts = [event.attributes for event in events]
        return events_as_dicts

    def get_merged_merge_requests(self) -> list:
        """
        Gets all merge requests that have been merged by the user.
        """
        merge_requests = self.gl.mergerequests.list(merge_user_username=self.user.username, sort="asc")
        print(f"Found {len(merge_requests)} merged merge requests")
        merge_requests_as_dicts = [mr.attributes for mr in merge_requests]
        return merge_requests_as_dicts

    def get_projects(self) -> list:
        """
        Gets all projects for the user.
        """
        projects = self.gl.projects.list(all=True, membership=True, sort="asc")
        print(f"Found {len(projects)} projects")
        projects_as_dicts = [project.attributes for project in projects]
        return projects_as_dicts

    def get_user_commits_for_projects(self, projects: list, author: str) -> list:
        """
        Gets all commits for the user in the specified projects.
        """
        commits = []
        for project in projects:
            if "forked_from_project" in project and self.user.username not in project["path_with_namespace"]:
                print(f"Skipping forked project {project['id']}")
                continue
            commits += self._get_commits(project["id"], author)
        print(f"Found {len(commits)} commits by {author} in {len(projects)} projects")
        clean_commits = self._remove_duplicate_commits(commits)
        return clean_commits

    def _get_commits(self, project_id: int, author: str) -> list:
        """
        Gets all commits for a project by the author.
        """
        try:
            commits = self.gl.projects.get(project_id).commits.list(author=author, all=True)
            print(f"Found {len(commits)} commits by {author} in project {project_id}")
            commits_as_dicts = [commit.attributes for commit in commits]
            return commits_as_dicts
        except gitlab.exceptions.GitlabError as e:
            print(f"Error: {e}")
            return []

    def _remove_duplicate_commits(self, commits) -> list:
        """
        Removes duplicate commits from the list of commits.
        """
        clean_commits = []
        commit_hashes = set()
        for commit in commits:
            if commit["id"] not in commit_hashes:
                clean_commits.append(commit)
                commit_hashes.add(commit["id"])
        print(f"Removed {len(commits) - len(clean_commits)} duplicate commits")
        return clean_commits

class App:

    def __init__(self, token: str) -> None:
        self.api = GitlabAPI(token)
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


    def create_commits_from_events(self) -> None:
        """
        Creates commits from the filtered events.
        """
        for event in self.events:
            self.create_commit(event, "event")

    def create_commits_from_merge_requests(self) -> None:
        """
        Creates commits from the merge requests.
        """
        for merge_request in self.merge_requests:
            self.create_commit(merge_request, "merge_request")

    def create_commits_from_commits(self) -> None:
        """
        Creates commits from the user's commits.
        """
        for commit in self.commits:
            self.create_commit(commit, "commit")

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

        # self.establish_connection()
        # self.authenticate()
        self.api.establish_connection()
        self.api.authenticate()

        # self.get_valid_user_events()
        # self.export_dicts_to_file(self.events, "events")
        self.events = self.api.get_valid_user_events()

        # self.get_merged_merge_requests()
        # self.export_dicts_to_file(self.merge_requests, "merge_requests")
        self.merge_requests = self.api.get_merged_merge_requests()

        # self.get_projects()
        # self.export_dicts_to_file(self.projects, "projects")
        self.projects = self.api.get_projects()

        # self.get_user_commits_for_projects(self.projects, "jake.ascher@galvanize.com")
        # self.export_dicts_to_file(self.commits, "commits")
        self.commits = self.api.get_user_commits_for_projects(self.projects, "jake.ascher@galvanize.com")

        # self.remove_duplicate_commits()
        # self.export_dicts_to_file(self.commits, "clean_commits")

        self.process_contributions(self.events, self.merge_requests, self.commits)

        self.repo = self.create_repo()
        # self.create_commits_from_events()
        # self.create_commits_from_merge_requests()
        # self.create_commits_from_commits()
        self.create_commits_from_contributions()

if __name__ == "__main__":
    if not load_dotenv():
        raise Exception("No environment variables found.")
    token = os.getenv("PRIVATE-TOKEN")
    app = App(token)
    app.run()
