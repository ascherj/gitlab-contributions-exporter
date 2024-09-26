import os

from dotenv import load_dotenv
import httpx

from fastapi import FastAPI, Depends, HTTPException, Response, Cookie, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.security.oauth2 import OAuth2AuthorizationCodeBearer
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from passlib.context import CryptContext

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from runner import GitlabContributionProcessor
from pydantic_types import GitlabContribution
load_dotenv()

DATABASE_URL = "sqlite:///./test.db"
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class UserCreate(BaseModel):
    email: str
    password: str

class UserInDB(UserCreate):
    hashed_password: str

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
GITLAB_EVENTS_URL = "https://gitlab.com/api/v4/events"

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=GITLAB_AUTHORIZE_URL,
    tokenUrl=GITLAB_TOKEN_URL
)

class Token(BaseModel):
    access_token: str
    token_type: str

# class User(BaseModel):
#     id: int
#     username: str
#     email: str
#     name: str


def get_user_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def get_user(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user: UserCreate):
    hashed_password = pwd_context.hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

@app.get("/")
def read_root():
    return {"message": "Welcome to the GitLab Contributions Exporter!"}

@app.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_user_db)):
    db_user = get_user(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return create_user(db=db, user=user)

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_user_db)):
    user = get_user(db, email=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    return {"access_token": user.id, "token_type": "bearer"}

# @app.get("/login")
# def login():
#     return RedirectResponse(
#         f"{GITLAB_AUTHORIZE_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=api"
#     )

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

        # user_response = await client.get(
        #     GITLAB_USER_URL,
        #     headers={"Authorization": f"Bearer {access_token}"},
        # )
        # user_response.raise_for_status()
        # user_data = user_response.json()
        # print("user_data", user_data)


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
        print("user_data", user_data)

        return {
            "id": user_data["id"],
            "name": user_data["name"],
            "username": user_data["username"],
            "email": user_data["email"]
        }

@app.get("/contributions", response_model=list[GitlabContribution])
async def contributions(token: str = Depends(get_token_from_cookie)):
    # gitlab_api = GitlabAPIWrapper(instance="https://gitlab.com", oauth_token=token)
    # gitlab_api.establish_connection()
    # gitlab_api.authenticate()
    # events = gitlab_api.get_valid_user_events()
    # return events
    processor = GitlabContributionProcessor(instances=["https://gitlab.com"], tokens=[token])
    processor.check_for_existing_exports()
    processor.process_contributions()
    return processor.contributions



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
