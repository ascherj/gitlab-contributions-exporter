import os
from datetime import datetime, timedelta
from contextlib import contextmanager
from typing import Generator
from dotenv import load_dotenv
import httpx

import jwt
from jwt.exceptions import InvalidTokenError

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
from schemas import GitlabContribution, UserBase

# Load environment variables
load_dotenv()


# Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
DATABASE_URL = "sqlite:///./test.db"
CLIENT_ID = os.getenv("GITLAB_CLIENT_ID")
CLIENT_SECRET = os.getenv("GITLAB_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
FRONTEND_URL = "http://localhost:5173"
GITLAB_AUTHORIZE_URL = "https://gitlab.com/oauth/authorize"
GITLAB_TOKEN_URL = "https://gitlab.com/oauth/token"
GITLAB_USER_URL = "https://gitlab.com/api/v4/user"
GITLAB_EVENTS_URL = "https://gitlab.com/api/v4/events"

# Database setup
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Database models
class UserDBModel(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)


# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class UserCreate(BaseModel):
    username: str
    password: str

class UserInDB(UserCreate):
    hashed_password: str

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# FastAPI setup
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2 setup
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Database functions
def get_user_db() -> Generator[Session, None, None]:
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_user(username: str, db: Session = Depends(get_user_db)) -> UserDBModel | None:
    return db.query(UserDBModel).filter(UserDBModel.username == username).first()

def authenticate_user(username: str, password: str, db: Session = Depends(get_user_db)) -> UserDBModel | None:
    user = get_user(username, db)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_user_db)) -> UserDBModel:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(username=token_data.username, db=db)
    if not user:
        raise credentials_exception
    return user

def create_user(db: Session, user: UserCreate) -> UserDBModel:
    hashed_password = get_password_hash(user.password)
    db_user = UserDBModel(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# Routes
@app.get("/")
def read_root():
    return {"message": "Welcome to the GitLab Contributions Exporter!"}

@app.post("/signup")
def signup(user: UserCreate, db: Session = Depends(get_user_db)):
    db_user = get_user(username=user.username, db=db)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    return create_user(db=db, user=user)

@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_user_db)):
    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")

@app.get("/users/me")
async def read_users_me(current_user: UserDBModel = Depends(get_current_user)):
    return current_user

@app.get("/gitlab/login")
def gitlab_login():
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

@app.get("/profile", response_model=UserBase)
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
