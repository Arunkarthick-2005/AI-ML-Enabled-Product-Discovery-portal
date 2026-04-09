from typing import Optional, Dict, List, Any
from pydantic import BaseModel, EmailStr, Field, validator
import re
import ast

class UserRegister(BaseModel):
    name: str = Field(..., min_length=3)
    email: EmailStr
    mobile: str
    password: str

    @validator("mobile")
    def validate_mobile(cls, v):
        if not re.fullmatch(r"\d{10}", v):
            raise ValueError("Mobile number must be exactly 10 digits")
        return v

    @validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain an uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain a lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain a special character")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: EmailStr
    name: str


class Product(BaseModel):
    pid: str
    title: str
    brand: Optional[str]
    category: Dict[str, Optional[str]]
    price: Dict[str, Optional[int]]
    rating: Dict[str, Optional[float]]
    description: Optional[str]
    specifications: Optional[Any]
    images: List[str]
