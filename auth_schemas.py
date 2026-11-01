import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        value = value.strip().lower()

        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,63}", value):
            raise ValueError(
                "Username must contain 3-64 characters and use "
                "letters, numbers, periods, underscores or hyphens."
            )

        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Literal["admin", "staff"]
    is_active: bool
    created_at: datetime
