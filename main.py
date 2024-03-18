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
        self.merge_requests = None
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

    def get_merged_merge_requests(self) -> None:
        """
        Gets all merge requests that have been merged by the user.
        """
        merge_requests = self.gl.mergerequests.list(merge_user_username=self.user.username)
        print(f"Found {len(merge_requests)} merged merge requests")
        merge_requests_as_dicts = [mr.attributes for mr in merge_requests]
        self.merge_requests = merge_requests_as_dicts

    def get_projects(self) -> None:
        """
        Gets all projects for the user.
        """
        projects = self.gl.projects.list(all=True, membership=True, sort="asc")
        print(f"Found {len(projects)} projects")
        projects_as_dicts = [project.attributes for project in projects]
        self.projects = projects_as_dicts

    def get_commits(self, project_id: int, author: str) -> list:
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

    def get_user_commits_for_projects(self, projects: list, author: str) -> None:
        """
        Gets all commits for the user in the specified projects.
        """
        if not projects:
            # attempt to read from file
            try:
                with open("EXPORT_projects.json", "r") as f:
                    projects = json.load(f)
            except FileNotFoundError:
                print("No projects found")
                return

        commits = []
        for project in projects:
            if "forked_from_project" in project and self.user.username not in project["path_with_namespace"]:
                print(f"Skipping forked project {project['id']}")
                continue
            commits += self.get_commits(project["id"], author)
        print(f"Found {len(commits)} commits by {author} in {len(projects)} projects")
        self.commits = commits

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

    def export_dicts_to_file(self, dicts, filename) -> None:
        """
        Exports the list of dictionaries to a file.
        """
        with open(f"EXPORT_{filename}.json", "w") as f:
            json_to_write = [d for d in dicts]
            f.write(json.dumps(json_to_write, indent=4))

    def remove_duplicate_commits(self) -> None:
        """
        Removes duplicate commits from the list of commits.
        """
        clean_commits = []
        commit_hashes = set()
        for commit in self.commits:
            if commit["id"] not in commit_hashes:
                clean_commits.append(commit)
                commit_hashes.add(commit["id"])
        print(f"Removed {len(self.commits) - len(clean_commits)} duplicate commits")
        self.commits = clean_commits

    # def process_contributions(self) -> None:
    #     """
    #     Convert user's events, merge requests, and commits to a list of contributions.
    #     Contributions should be sorted by date in ascending order. Contributions should be
    #     dictionaries with the following keys
    #     - "date": The date of the contribution
    #     - "type": The type of contribution ("created project", "opened merge request", "merged merge request", "commit")
    #     - "project_id": The project ID of the contribution
    #     - "commit_hash": The commit hash of the contribution, if applicable
    #     """



    def run(self) -> None:
        """
        Runs the application.
        """
        self.establish_connection()
        self.authenticate()

        # self.get_valid_user_events()
        # self.export_dicts_to_file(self.events, "events")

        # self.get_merged_merge_requests()
        # self.export_dicts_to_file(self.merge_requests, "merge_requests")

        self.get_projects()
        self.export_dicts_to_file(self.projects, "projects")

        self.get_user_commits_for_projects(self.projects, "jake.ascher@galvanize.com")
        self.export_dicts_to_file(self.commits, "commits")
        self.remove_duplicate_commits()
        self.export_dicts_to_file(self.commits, "clean_commits")

        # self.repo = self.create_repo()
        # self.create_commits_from_events()

if __name__ == "__main__":
    if not load_dotenv():
        raise Exception("No environment variables found.")
    token = os.getenv("PRIVATE-TOKEN")
    app = App(token)
    app.run()
