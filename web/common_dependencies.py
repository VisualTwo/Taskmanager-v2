from services.common_service import CommonService
from fastapi import Depends
from web.dependencies import get_repository

def get_common_service(repository = Depends(get_repository)):
    return CommonService(repository)
