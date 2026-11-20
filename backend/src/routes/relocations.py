from fastapi import APIRouter,Depends
from src.config.database import db_session
from src.utils.security import current,writer
from src.schemas.relocation import RelocationInput,RelocationResume
from src.services import relocations as service
router=APIRouter()
@router.get('/relocations')
def listing(db=Depends(db_session),user=Depends(current)): return service.listing(db)
@router.post('/relocations',status_code=201)
def create(data:RelocationInput,db=Depends(db_session),user=Depends(writer)):
    return service.create(db,data,user)
@router.post('/relocations/resume')
def resume(data:RelocationResume,db=Depends(db_session),user=Depends(writer)):
    return service.resume(db,data.relocation_id,user)
