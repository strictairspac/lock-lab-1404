from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Text, UniqueConstraint
from datetime import datetime, timezone
from src.config.database import Base
def now(): return datetime.now(timezone.utc)
class User(Base):
    __tablename__='users'
    id=Column(Integer,primary_key=True);email=Column(String(120),unique=True,nullable=False)
    password=Column(String(300),nullable=False);role=Column(String(20),nullable=False)
class Sample(Base):
    __tablename__='samples'
    id=Column(Integer,primary_key=True);code=Column(String(80),unique=True,nullable=False)
    title=Column(String(160),nullable=False);quantity=Column(Integer,nullable=False);location=Column(String(120),nullable=False)
    # 同一保管间内同名批次唯一：并发跨间移位据此保证接收批次只建一行
    __table_args__=(UniqueConstraint('location','title',name='uq_sample_location_title'),)
class Transfer(Base):
    __tablename__='transfers'
    id=Column(Integer,primary_key=True);code=Column(String(80),unique=True,nullable=False)
    sample_id=Column(Integer,ForeignKey('samples.id'),nullable=False);destination=Column(String(120),nullable=False)
    quantity=Column(Integer,nullable=False);note=Column(String(300),default='')
class Trial(Base):
    __tablename__='trials'
    id=Column(Integer,primary_key=True);name=Column(String(120),nullable=False)
    transfer_id=Column(Integer,ForeignKey('transfers.id'),nullable=False);timeout_ms=Column(Integer,nullable=False)
    status=Column(String(20),default='queued',nullable=False);result=Column(JSON,nullable=True)
    created_at=Column(DateTime(timezone=True),default=now);error=Column(Text,default='')
class TrialBalance(Base):
    __tablename__='trial_balances'
    trial_id=Column(Integer,ForeignKey('trials.id'),primary_key=True);remaining=Column(Integer,nullable=False);received=Column(Integer,nullable=False,default=0)
class Receipt(Base):
    __tablename__='receipts'
    id=Column(Integer,primary_key=True);trial_id=Column(Integer,ForeignKey('trials.id'),nullable=False)
    actor=Column(String(20),nullable=False);quantity=Column(Integer,nullable=False)
    __table_args__=(UniqueConstraint('trial_id','actor'),)
class Audit(Base):
    __tablename__='audit_logs'
    id=Column(Integer,primary_key=True);actor=Column(String(120),nullable=False);action=Column(String(160),nullable=False)
    created_at=Column(DateTime(timezone=True),default=now)

# ---- 冷藏间换柜：停写/封存与跨间移位 ----
class Room(Base):
    """保管间，以样本 location 自然键（如“冷藏间 A-03”）注册。
    当前生效封存不设指针列（避免与封存单循环外键），由 freeze_orders 中该间
    最近一张 freezing/sealed 单派生。"""
    __tablename__='rooms'
    id=Column(Integer,primary_key=True)
    location=Column(String(120),unique=True,nullable=False)
    created_at=Column(DateTime(timezone=True),default=now)
class FreezeOrder(Base):
    """停写/封存单：freezing 等待在途写入办完 → sealed 已封 → released 已解封。"""
    __tablename__='freeze_orders'
    id=Column(Integer,primary_key=True)
    room_id=Column(Integer,ForeignKey('rooms.id'),nullable=False,index=True)
    code=Column(String(80),unique=True,nullable=False)
    status=Column(String(20),default='freezing',nullable=False,index=True)
    reason=Column(String(300),default='')
    actor=Column(String(120),nullable=False)
    created_at=Column(DateTime(timezone=True),default=now)
    sealed_at=Column(DateTime(timezone=True),nullable=True)
    released_at=Column(DateTime(timezone=True),nullable=True)
class Relocation(Base):
    """跨间移位：moving 在途（已受理未入账）→ posted 整笔落账。"""
    __tablename__='relocations'
    id=Column(Integer,primary_key=True)
    code=Column(String(80),unique=True,nullable=False)
    sample_id=Column(Integer,ForeignKey('samples.id'),nullable=False)
    source_room_id=Column(Integer,ForeignKey('rooms.id'),nullable=False)
    target_room_id=Column(Integer,ForeignKey('rooms.id'),nullable=False)
    quantity=Column(Integer,nullable=False)
    status=Column(String(20),default='moving',nullable=False,index=True)
    note=Column(String(300),default='')
    actor=Column(String(120),nullable=False)
    created_at=Column(DateTime(timezone=True),default=now)
    posted_at=Column(DateTime(timezone=True),nullable=True)
    result=Column(JSON,nullable=True)
    __table_args__=(UniqueConstraint('code',name='uq_relocation_code'),)
