from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    invite_code: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class User(BaseModel):
    id: int
    email: EmailStr
    created_at: str


class AuthResponse(BaseModel):
    user: User
    token: str
