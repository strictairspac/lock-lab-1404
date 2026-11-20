from sqlalchemy import select
from fastapi import HTTPException
from src.models.entities import Sample
from .common import save
from . import rooms as room_svc
from src.utils.serialization import record
def listing(db): return [record(x) for x in db.scalars(select(Sample).order_by(Sample.id))]
def create(db,data,user):
    room=room_svc.get_or_create_room(db, data.location); db.flush()
    room_svc.assert_writable(db,[room.id],action='新样本登记')
    return save(db,Sample(**data.model_dump()),user,'创建样本 '+data.code)
def update(db,ident,data,user):
    obj=db.get(Sample,ident)
    if not obj: raise HTTPException(404,'样本不存在')
    old_room=room_svc.get_or_create_room(db, obj.location)
    new_room=room_svc.get_or_create_room(db, data.location); db.flush()
    # 改量与进出移位都受停写约束；若改了存放位置，源、目标两间都要可写
    room_ids=[old_room.id] if data.location==obj.location else [old_room.id,new_room.id]
    room_svc.lock_rooms(db, room_ids)
    room_svc.assert_writable(db, room_ids, action='样本改量/移位')
    for k,v in data.model_dump().items(): setattr(obj,k,v)
    return save(db,obj,user,'更新样本 '+data.code)
