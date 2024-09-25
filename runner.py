import os
from datetime import datetime
import json
from typing import Union
from custom_types import GitlabEvent, GitlabProject, GitlabCommit, GitlabContribution, GitlabCounts

from dotenv import load_dotenv
from git import Repo
import dateutil.parser as dp

from api import GitlabAPIWrapper

class GitlabContributionProcessor:

    def __init__(self, instances: list, tokens: list) -> None:
        self.apis = [GitlabAPIWrapper(instance, token) for instance, token in zip(instances, tokens)]
        self.contributions: list[GitlabContribution] = []
        self.events: list[GitlabEvent] = []
        self.projects: list[GitlabProject] = []
        self.commits: list[GitlabCommit] = []
        self.repo: Repo = None
        self.counts: GitlabCounts = {
            "projects": {
                "created": 0,
            },
            "merge_requests": {
                "opened": 0,
                "accepted": 0
            },
            "issues": {
                "opened": 0,
            },
            "commits": 0
        }

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

    def create_commit(self, contribution: GitlabContribution) -> None:
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

    def export_dicts_to_file(self, dicts: list[Union[GitlabEvent, GitlabProject, GitlabCommit]], file_suffix: str) -> None:
        """
        Exports the list of dictionaries to a file.
        """
        os.makedirs("db", exist_ok=True)
        with open(f"db/EXPORT_{file_suffix}.json", "w") as f:
            json_to_write = [d for d in dicts]
            f.write(json.dumps(json_to_write, indent=4))

    def process_contributions(self) -> None:
        """
        Process the contributions into uniform dictionaries sorted by contribution time.
        """
        contributions: list[GitlabContribution] = []

        for event in self.events:
            if event["action_name"] == "created":
                self.counts["projects"]["created"] += 1
                contributions.append({
                    "contribution_type": "project",
                    "message": "Created project",
                    "project_id": event["project_id"],
                    "date": event["created_at"],
                    "instance": event["instance"]
                })
            elif event["action_name"] == "opened":
                if event["target_type"] == "MergeRequest":
                    self.counts["merge_requests"]["opened"] += 1
                    contributions.append({
                        "contribution_type": "merge_request",
                        "message": "Opened merge request",
                        "project_id": event["project_id"],
                        "date": event["created_at"],
                        "instance": event["instance"]
                    })
                elif event["target_type"] == "Issue":
                    self.counts["issues"]["opened"] += 1
                    contributions.append({
                        "contribution_type": "issue",
                        "message": "Opened issue",
                        "project_id": event["project_id"],
                        "date": event["created_at"],
                        "instance": event["instance"]
                    })
                else:
                    raise Exception(f"Unknown target type: {event['target_type']}")
            elif event["action_name"] == "accepted":
                self.counts["merge_requests"]["accepted"] += 1
                contributions.append({
                    "contribution_type": "merge_request",
                    "message": "Accepted merge request",
                    "project_id": event["project_id"],
                    "date": event["created_at"],
                    "instance": event["instance"]
                })
            else:
                raise Exception(f"Unknown action name: {event['action_name']}")

        for commit in self.commits:
            self.counts["commits"] += 1
            contributions.append({
                "contribution_type": "commit",
                "message": "Committed to project",
                "project_id": commit["project_id"],
                "date": commit["committed_date"],
                "instance": commit["instance"]
            })

        contributions.sort(key=lambda x: x["date"])
        self.contributions = contributions

    def _get_total_counts(self) -> int:
        """
        Gets the total counts for the contributions.
        """
        return sum(count for category in self.counts.values() for count in (category.values() if isinstance(category, dict) else [category]))

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
    app = GitlabContributionProcessor(instances, tokens)
    app.run()
    print("Finished processing all instances")
