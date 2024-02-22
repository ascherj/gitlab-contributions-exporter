import os

from dotenv import load_dotenv
import gitlab

class App():
    def __init__(self, token: str) -> None:
        self.token = token

    def establish_connection(self) -> None:
        self.gl = gitlab.Gitlab(private_token=self.token)

    def authenticate(self) -> None:
        self.gl.auth()
        user = self.gl.user
        print(f"Authenticated as {user.name} ({user.username})")

    def run(self) -> None:
        self.establish_connection()
        self.authenticate()


if __name__ == "__main__":
    if not load_dotenv():
        raise Exception("No environment variables found.")
    token = os.getenv("PRIVATE-TOKEN")
    app = App(token)
    app.run()
