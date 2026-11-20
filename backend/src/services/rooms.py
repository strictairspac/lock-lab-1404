"""冷藏间换柜：停写/封存、解封与重启恢复的核心业务。

口径：
- 停写发起即落库为 freezing（等待），该间立即拒绝新写入；在途移位办完后 reconcile 转 sealed（已封）。
- 跨间受理对两间按 id 排序加行锁，任一间非 normal 即整笔回滚不落账。
- 解封按封存单 epoch 幂等：同一单重放不重复生效；旧单不能解开后来的新封存。
房间“当前生效封存”由 freeze_orders 中该间最近一张 freezing/sealed 单派生，不设指针列。
"""
from datetime import datetime, timezone
import os
from sqlalchemy import select
from fastapi import HTTPException
from src.models.entities import Room, FreezeOrder, Relocation, Sample, Audit
from src.utils.serialization import record

def now(): return datetime.now(timezone.utc)

# ---------- 房间注册与查询 ----------
def get_or_create_room(db, location):
    room=db.scalar(select(Room).where(Room.location==location))
    if room: return room
    db.add(Room(location=location)); db.flush()
    return db.scalar(select(Room).where(Room.location==location))

def ensure_rooms_for_samples(db):
    """为样本台账中出现的每个 location 注册房间（幂等）。"""
    locations=[r for (r,) in db.execute(select(Sample.location).distinct()).all()]
    for loc in locations: get_or_create_room(db, loc)
    db.commit()

def active_freeze(db, room_id):
    """房间当前生效的封存单（最近一张 freezing/sealed），无则 None。"""
    return db.scalar(select(FreezeOrder).where(
        FreezeOrder.room_id==room_id,
        FreezeOrder.status.in_(('freezing','sealed'))
    ).order_by(FreezeOrder.id.desc()))

def room_state(db, room):
    order=active_freeze(db, room.id)
    if not order: return 'normal'
    return 'sealed' if order.status=='sealed' else 'freezing'

def _room_payload(db, room):
    order=active_freeze(db, room.id)
    moving=db.scalar(select(Relocation).where(
        Relocation.status=='moving',
        (Relocation.source_room_id==room.id)|(Relocation.target_room_id==room.id)))
    payload=record(room)
    payload['state']=room_state(db, room)
    payload['active_freeze']=record(order) if order else None
    payload['moving_relocation_id']=moving.id if moving else None
    return payload

def listing(db):
    ensure_rooms_for_samples(db)
    rooms=list(db.scalars(select(Room).order_by(Room.id)))
    return [_room_payload(db, r) for r in rooms]

def freeze_orders(db):
    return [record(x) for x in db.scalars(select(FreezeOrder).order_by(FreezeOrder.id.desc()))]

# ---------- 行锁工具：跨间操作按 id 排序加锁，避免死锁 ----------
def lock_rooms(db, room_ids):
    ids=sorted(set(room_ids))
    locked=[]
    for rid in ids:
        room=db.scalar(select(Room).where(Room.id==rid).with_for_update())
        if not room: raise HTTPException(404,'保管间不存在')
        locked.append(room)
    return {r.id:r for r in locked}

def assert_writable(db, room_ids, action='该操作'):
    """对涉及房间逐一校验当前可写；任一间已停写则整笔拒绝（不落账）。"""
    for rid in sorted(set(room_ids)):
        order=active_freeze(db, rid)
        if order:
            label=('已封' if order.status=='sealed' else '等待停写中')
            raise HTTPException(409,f'房间已{label}（封存单 {order.code}），{action}不予受理')

# ---------- 停写发起 ----------
def start_freeze(db, location, reason, user, code=None):
    room=get_or_create_room(db, location)
    db.flush()
    room=db.scalar(select(Room).where(Room.id==room.id).with_for_update())
    existing=active_freeze(db, room.id)
    if existing:
        raise HTTPException(409,f'该房间已有生效封存单 {existing.code}（{existing.status}），请勿重复发起停写')
    code=code or f'FREEZE-{room.id}-{datetime.now().strftime("%m%d%H%M%S")}-{os.urandom(3).hex()}'
    if db.scalar(select(FreezeOrder).where(FreezeOrder.code==code)):
        raise HTTPException(409,'封存单编号已存在')
    order=FreezeOrder(room_id=room.id,code=code,status='freezing',reason=reason,actor=user.email)
    db.add(order); db.flush()
    db.add(Audit(actor=user.email,action=f'发起停写 {code}（{location}）'))
    db.commit()
    # 发起后立即协调一次：若无在途写入则直接显示已封
    reconcile_room(db, room.id)
    return _room_payload(db, db.get(Room, room.id))

# ---------- 协调：等待中的封存单，在途移位办完后转已封 ----------
def reconcile_room(db, room_id):
    order=active_freeze(db, room_id)
    if not order or order.status!='freezing': return
    moving=db.scalar(select(Relocation).where(
        Relocation.status=='moving',
        (Relocation.source_room_id==room_id)|(Relocation.target_room_id==room_id)))
    if moving is None:
        order.status='sealed'; order.sealed_at=now()
        db.add(Audit(actor='system',action=f'封存单 {order.code} 在途写入已办完，转为已封'))
        db.commit()

def reconcile_all(db):
    """启动恢复：先把所有在途移位续办完，再把可封口的等待单转已封。"""
    from src.services.relocations import resume_all_moving
    resume_all_moving(db)
    rooms=list(db.scalars(select(Room)))
    for room in rooms: reconcile_room(db, room.id)

# ---------- 解封（按封存单 epoch 幂等） ----------
def release_freeze(db, order_id, user):
    order=db.get(FreezeOrder, order_id)
    if not order: raise HTTPException(404,'封存单不存在')
    room=db.scalar(select(Room).where(Room.id==order.room_id).with_for_update())
    current=active_freeze(db, room.id)
    if order.status=='released':
        # 本单已是解封态：若后来又有新封存，旧解封不能放开后来封住的库
        if current is not None and current.id!=order.id:
            raise HTTPException(409,f'封存单 {order.code} 已过期，房间此后另有封存 {current.code}，旧解封不能放开后来封住的库')
        # 房间当前无更新封存：纯重放，幂等 no-op，不重复生效
        db.add(Audit(actor=user.email,action=f'重放解封 {order.code}（幂等，未重复生效）')); db.commit()
        return {'idempotent':True,'order':record(order),'room':_room_payload(db, room)}
    # 本单未解封却不是当前生效单：落后于后来的封存，拒绝
    if current is None or current.id != order.id:
        raise HTTPException(409,f'封存单 {order.code} 已不是该房间当前封存，旧解封不能放开后来封住的库')
    if order.status=='freezing':
        raise HTTPException(409,f'封存单 {order.code} 仍在等待在途写入，未到已封状态，不能解封')
    order.status='released'; order.released_at=now()
    db.add(Audit(actor=user.email,action=f'解封 {order.code}（{room.location}）'))
    db.commit()
    return {'idempotent':False,'order':record(order),'room':_room_payload(db, room)}
