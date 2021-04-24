from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from passlib.context import CryptContext
from sqlalchemy import select
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from api import models
from api.db import database_dep

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


async def authenticate_user(email: str, password: str):
    user = await models.User.query.where(models.User.email == email).gino.first()
    if not user:
        return False, 404
    if not verify_password(password, user.hashed_password):
        return False, 401
    return user, 200


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/token",
    scopes={
        "server_management": "Edit server settings",
        "token_management": "Create, list or edit tokens",
        "wallet_management": "Create, list or edit wallets",
        "store_management": "Create, list or edit stores",
        "discount_management": "Create, list or edit discounts",
        "product_management": "Create, list or edit products",
        "invoice_management": "Create, list or edit invoices",
        "notification_management": "Create, list or edit notification providers",
        "template_management": "Create, list or edit templates",
        "full_control": "Full control over what current user has",
    },
)


def check_selective_scopes(request, scope, token):
    model_id = request.path_params.get("model_id", None)
    if model_id is None:
        return False
    return f"{scope}:{model_id}" in token.permissions


class AuthDependency:
    def __init__(self, enabled: bool = True, token: Optional[str] = None):
        self.enabled = enabled
        self.token = token

    async def __call__(self, request: Request, security_scopes: SecurityScopes, return_token=False, db=database_dep):
        if not self.enabled:
            return None
        if security_scopes.scopes:
            authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
        else:
            authenticate_value = "Bearer"
        token: str = await oauth2_scheme(request) if not self.token else self.token
        data = (await db.execute(select(models.User, models.Token).join(models.Token).where(models.Token.id == token))).first()
        if data is None:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": authenticate_value},
            )
        user, token = data  # first validate data, then unpack
        forbidden_exception = HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
            headers={"WWW-Authenticate": authenticate_value},
        )
        if "full_control" not in token.permissions:
            for scope in security_scopes.scopes:
                if scope not in token.permissions and not check_selective_scopes(request, scope, token):
                    raise forbidden_exception
        if "server_management" in security_scopes.scopes and not user.is_superuser:
            raise forbidden_exception
        if return_token:
            return user, token
        return user
