from fastapi import APIRouter,Depends
from src.config.database import db_session
from src.utils.security import current,writer
from src.schemas.freeze import FreezeInput,ReleaseInput
from src.services import rooms as service
router=APIRouter()
@router.get('/rooms')
def listing(db=Depends(db_session),user=Depends(current)): return service.listing(db)
@router.get('/freeze-orders')
def orders(db=Depends(db_session),user=Depends(current)): return service.freeze_orders(db)
@router.post('/rooms/freeze',status_code=201)
def freeze(data:FreezeInput,db=Depends(db_session),user=Depends(writer)):
    return service.start_freeze(db,data.location,data.reason,user)
@router.post('/rooms/release')
def release(data:ReleaseInput,db=Depends(db_session),user=Depends(writer)):
    return service.release_freeze(db,data.order_id,user)
