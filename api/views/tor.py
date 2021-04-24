from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import SecurityScopes
from starlette.requests import Request

from api import utils
from api.db import get_db
from api.ext import tor as tor_ext

router = APIRouter()


@router.get("/services")
async def get_services(request: Request, db=Depends(get_db)):
    try:
        user = await utils.authorization.AuthDependency()(request, SecurityScopes(["server_management"]), db=db)
    except HTTPException:
        user = None
    key = "services_dict" if user else "anonymous_services_dict"
    async with utils.redis.wait_for_redis():
        return await tor_ext.get_data(key, {}, json_decode=True)
