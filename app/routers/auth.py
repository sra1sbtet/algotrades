from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from app.services.auth import create_access_token, get_password_hash, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory user store for demo (use database in production)
users_db = {}

class UserRegister(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    username: str  # email
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/register", response_model=Token)
async def register(user: UserRegister):
    if user.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_password = get_password_hash(user.password)
    users_db[user.email] = {"email": user.email, "hashed_password": hashed_password}
    
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token}

@router.post("/login", response_model=Token)
async def login(user: UserLogin):
    if user.username not in users_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    stored_user = users_db[user.username]
    if not verify_password(user.password, stored_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token}