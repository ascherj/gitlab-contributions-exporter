import os

from dotenv import load_dotenv
import gitlab

class App():

    def __init__(self, token: str) -> None:
        self.token = token
        self.gl = None
        self.user = None
        self.events = None

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

    def get_and_filter_user_events(self) -> None:
        """
        Gets events for the user and filters out "left" and "deleted" events
        as those are not likely counted as "contributions" in GitHub.
        """
        events = self.gl.events.list(per_page=100)
        print(f"Found {len(events)} events")
        events_as_dicts = [event.attributes for event in events]
        print(events_as_dicts)
        filtered_events = [
            event for event in events_as_dicts
            if event["action_name"] != "left" and event["action_name"] != "deleted"
        ]
        print(f"Filtered down to {len(filtered_events)} events")

    def run(self) -> None:
        """
        Runs the application.
        """
        self.establish_connection()
        self.authenticate()
        self.get_and_filter_user_events()


if __name__ == "__main__":
    if not load_dotenv():
        raise Exception("No environment variables found.")
    token = os.getenv("PRIVATE-TOKEN")
    app = App(token)
    app.run()
