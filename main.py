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
        self.gl = gitlab.Gitlab(private_token=self.token)

    def authenticate(self) -> None:
        self.gl.auth()
        self.user = self.gl.user
        print(f"Authenticated as {self.user.name} ({self.user.username})")

    def get_user_events(self) -> None:
        events = self.gl.events.list(per_page=10)
        print(f"Found {len(events)} events")
        events_as_dicts = [event.attributes for event in events]
        self.events = events_as_dicts

    def run(self) -> None:
        self.establish_connection()
        self.authenticate()
        self.get_user_events()
        print(self.events)


if __name__ == "__main__":
    if not load_dotenv():
        raise Exception("No environment variables found.")
    token = os.getenv("PRIVATE-TOKEN")
    app = App(token)
    app.run()
