# GitLab Contributions Exporter

This project is a GitLab Contributions Exporter that connects to GitLab instances, retrieves user events, projects, and commits, and processes them into a uniform format. The processed contributions are then committed to a new Git repository.

## Features

- Connects to multiple GitLab instances
- Authenticates users using private tokens
- Retrieves user events, projects, and commits
- Processes contributions into a uniform format
- Creates a new Git repository and commits the contributions

## Requirements

- Python 3.6+
- Git
- GitLab API access tokens
- Environment variables for GitLab instances and tokens

## Installation

1. Clone the repository:

    ```sh
    git clone <repository-url>
    cd <repository-directory>
    ```

2. Create a virtual environment and activate it:

    ```sh
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the required packages:

    ```sh
    pip install -r requirements.txt
    ```

4. Create a `.env` file in the root directory with the following content:

    ```env
    GITLAB-INSTANCE=<your-gitlab-instance-urls-comma-separated>
    GITLAB-TOKEN=<your-gitlab-tokens-comma-separated>
    ```

## Usage

1. Run the application:

    ```sh
    python main.py
    ```

2. The application will:
    - Check for existing exports and load them if available
    - Establish connections to the GitLab instances
    - Authenticate the user
    - Retrieve user events, projects, and commits
    - Process the contributions into a uniform format
    - Create a new Git repository and commit the contributions

## File Structure

- `main.py`: The main application script
- `db/`: Directory containing exported JSON files
- `requirements.txt`: List of required Python packages

## Classes and Methods

### `GitlabAPI`

- `__init__(self, instance: str, token: str) -> None`: Initializes the GitLabAPI instance
- `establish_connection(self) -> None`: Establishes a connection to the GitLab API using the private token
- `authenticate(self) -> None`: Authenticates the user and sets the user attribute to the authenticated user
- `get_valid_user_events(self) -> list`: Gets events for the user and filters to only include specific `action_name`s
- `get_projects(self) -> list`: Gets all projects for the user
- `get_user_commits_for_projects(self, projects: list) -> list`: Gets all commits for the user in the specified projects
- `_get_commits(self, project_id: int, project_created_at: str) -> list`: Gets all commits for a project by the author

### `App`

- `__init__(self, instances: list, tokens: list) -> None`: Initializes the App instance
- `check_for_existing_exports(self) -> None`: Checks for existing exports and updates instance attributes if found
- `create_repo(self) -> Repo`: Creates a new repository. If a repository already exists, it will be deleted and a new one will be created
- `create_commit(self, contribution: dict) -> None`: Creates a commit from the contribution
- `create_commits_from_contributions(self) -> None`: Creates commits from the contributions
- `export_dicts_to_file(self, dicts: list[dict], filename: str) -> None`: Exports the list of dictionaries to a file
- `process_contributions(self) -> None`: Processes the contributions into uniform dictionaries sorted by contribution time
- `run(self) -> None`: Runs the application

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
