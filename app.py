from fastapi import FastAPI, Depends, HTTPException, Response, Cookie, status
from fastapi.responses import RedirectResponse
from fastapi.security.oauth2 import OAuth2AuthorizationCodeBearer
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLIENT_ID = os.getenv("GITLAB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITLAB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
FRONTEND_URL = "http://localhost:5173"
GITLAB_AUTHORIZE_URL = "https://gitlab.com/oauth/authorize"
GITLAB_TOKEN_URL = "https://gitlab.com/oauth/token"
GITLAB_USER_URL = "https://gitlab.com/api/v4/user"

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=GITLAB_AUTHORIZE_URL,
    tokenUrl=GITLAB_TOKEN_URL
)

class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    id: int
    username: str
    email: str
    name: str

@app.get("/")
def read_root():
    return {"message": "Welcome to the GitLab Contributions Exporter!"}

@app.get("/login")
def login():
    return RedirectResponse(
        f"{GITLAB_AUTHORIZE_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=api"
    )

@app.get("/login/callback")
async def login_callback(code: str, response: Response):
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GITLAB_TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        print("token_data", token_data)
        access_token = token_data["access_token"]

        user_response = await client.get(
            GITLAB_USER_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_response.raise_for_status()
        user_data = user_response.json()
        print("user_data", user_data)


    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax")

    return RedirectResponse(f"{FRONTEND_URL}/profile")


async def get_token_from_cookie(access_token: str = Cookie(None)):
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return access_token

@app.get("/profile", response_model=User)
async def profile(token: str = Depends(get_token_from_cookie)):
    async with httpx.AsyncClient() as client:
        user_response = await client.get(
            GITLAB_USER_URL,
            headers={"Authorization": f"Bearer {token}"},
        )
        user_response.raise_for_status()
        user_data = user_response.json()
    return {
        "id": user_data["id"],
        "name": user_data["name"],
        "username": user_data["username"],
        "email": user_data["email"]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
