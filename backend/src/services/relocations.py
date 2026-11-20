"""跨间移位。

受理（accept）：在单事务内对源、目标两间按 id 排序加行锁，两间都 normal 才受理，
否则整笔回滚——绝不出现只扣一间的半成品。
落账（post）：源批次扣量，目标间生成/并入接收批次，数量守恒；幂等可恢复。
"""
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from src.models.entities import Room, Relocation, Sample, Audit
from src.utils.serialization import record
from src.services import rooms as room_svc

def now(): return datetime.now(timezone.utc)

def listing(db):
    return [record(x) for x in db.scalars(select(Relocation).order_by(Relocation.id.desc()))]

def _locked_dest(db, location, title, rel_id):
    """返回目标间同名接收批次，并保证当前事务持有该行 FOR UPDATE 锁。
    行不存在时在保存点内首建；并发撞 (location,title) 唯一约束则回滚保存点、
    重新读取并加锁——确保并发事务最终并入同一持锁行，不重复建、不丢失更新。"""
    for attempt in range(5):
        dest=db.scalar(select(Sample).where(
            Sample.location==location, Sample.title==title).with_for_update())
        if dest is not None:
            db.refresh(dest, with_for_update=True)  # 读到对手已提交的最新数量并持锁
            return dest
        sp=db.begin_nested()
        try:
            dest=Sample(code=f'REL-{rel_id}-{attempt}',title=title,quantity=0,location=location)
            db.add(dest); db.flush()
            db.refresh(dest, with_for_update=True)
            return dest
        except IntegrityError:
            sp.rollback()  # 对手已先建出该行；回滚子事务后循环重读并加锁
    raise HTTPException(500,'接收批次并发创建失败，请重试')

def _post(db, rel):
    """把一笔 moving 移位整笔落账；已 posted 直接返回（幂等，重启/重放安全）。
    数量增减全部用数据库原子 UPDATE（quantity = quantity +/- n）并以 FOR UPDATE 持锁，
    既保证加锁顺序固定（源→目标）避免死锁，也杜绝 ORM 读-改-写的丢失更新。"""
    if rel.status=='posted':
        return rel
    source=db.scalar(select(Sample).where(Sample.id==rel.sample_id).with_for_update())
    if not source: raise HTTPException(404,'源样本批次不存在')
    if source.quantity < rel.quantity:
        raise HTTPException(422,'源批次可用量不足，移位无法落账')
    target_room=db.get(Room, rel.target_room_id)
    dest=_locked_dest(db, target_room.location, source.title, rel.id)
    # 原子增减：在 SQL 层完成，并发事务的增量不会互相覆盖
    db.execute(update(Sample).where(Sample.id==source.id).values(quantity=Sample.quantity-rel.quantity))
    db.execute(update(Sample).where(Sample.id==dest.id).values(quantity=Sample.quantity+rel.quantity))
    db.refresh(source); db.refresh(dest)
    rel.status='posted'; rel.posted_at=now()
    rel.result={'source_sample_id':source.id,'target_sample_id':dest.id,
                'source_remaining':source.quantity,'target_quantity':dest.quantity,
                'conservation':source.quantity>=0}
    db.add(Audit(actor=rel.actor,action=f'跨间移位落账 {rel.code}（{rel.quantity} 份 → {target_room.location}）'))
    return rel

def create(db, data, user):
    source=db.get(Sample, data.sample_id)
    if not source: raise HTTPException(404,'样本批次不存在')
    if data.target_location==source.location:
        raise HTTPException(422,'目标间与当前位置相同，无需跨间移位')
    if data.quantity>source.quantity:
        raise HTTPException(422,'移位份数超过源批次可用量')
    if db.scalar(select(Relocation).where(Relocation.code==data.code)):
        raise HTTPException(409,'移位单编号已存在')
    # 确保两间都已注册
    src_room=room_svc.get_or_create_room(db, source.location)
    dst_room=room_svc.get_or_create_room(db, data.target_location)
    db.flush()
    # 单事务内按 id 排序对两间加行锁；任一非 normal 即抛 409 整笔回滚
    locked=room_svc.lock_rooms(db, [src_room.id, dst_room.id])
    room_svc.assert_writable(db, [src_room.id, dst_room.id], action='跨间移位')
    rel=Relocation(code=data.code,sample_id=source.id,source_room_id=src_room.id,
                   target_room_id=dst_room.id,quantity=data.quantity,status='moving',
                   note=data.note,actor=user.email)
    db.add(rel); db.flush()
    db.add(Audit(actor=user.email,action=f'受理跨间移位 {rel.code}（两间均正常，在途 {rel.quantity} 份）'))
    if data.hold:
        # 受控测试：保留在途状态，等待恢复/重启后续办
        db.commit()
        return record(rel)
    _post(db, rel)
    db.commit()
    # 落账后协调两间可能等待中的封存单
    room_svc.reconcile_room(db, src_room.id)
    room_svc.reconcile_room(db, dst_room.id)
    return record(rel)

def resume(db, relocation_id, user):
    rel=db.get(Relocation, relocation_id)
    if not rel: raise HTTPException(404,'移位单不存在')
    if rel.status=='posted':
        return {'idempotent':True,'relocation':record(rel)}
    # 恢复续办：对两间加锁后落账（停写等待不阻止已受理在途单办完）
    room_svc.lock_rooms(db, [rel.source_room_id, rel.target_room_id])
    _post(db, rel)
    db.commit()
    room_svc.reconcile_room(db, rel.source_room_id)
    room_svc.reconcile_room(db, rel.target_room_id)
    db.add(Audit(actor=user.email,action=f'恢复并落账移位 {rel.code}')); db.commit()
    return {'idempotent':False,'relocation':record(rel)}

def resume_all_moving(db):
    """启动恢复：把所有停在 moving 的移位单续办完（服务中断点之后的自动续办）。"""
    moving=list(db.scalars(select(Relocation).where(Relocation.status=='moving')))
    for rel in moving:
        room_svc.lock_rooms(db, [rel.source_room_id, rel.target_room_id])
        _post(db, rel)
    if moving: db.commit()
    for rel in moving:
        room_svc.reconcile_room(db, rel.source_room_id)
        room_svc.reconcile_room(db, rel.target_room_id)
    return len(moving)
