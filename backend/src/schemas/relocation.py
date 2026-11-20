from pydantic import BaseModel, Field
class RelocationInput(BaseModel):
    code: str=Field(min_length=2,max_length=80)
    sample_id: int=Field(gt=0)
    target_location: str=Field(min_length=1,max_length=120)
    quantity: int=Field(ge=1,le=100000)
    note: str=Field(default='',max_length=300)
    # 仅受控测试使用：受理后保持在途（moving），不立即落账，用于演练“移位在途时停写/重启恢复”
    hold: bool=Field(default=False)
class RelocationResume(BaseModel):
    relocation_id: int=Field(gt=0)
