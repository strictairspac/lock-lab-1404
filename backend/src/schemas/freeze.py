from pydantic import BaseModel, Field
class FreezeInput(BaseModel):
    location: str=Field(min_length=1,max_length=120)
    reason: str=Field(default='换柜停写',max_length=300)
class ReleaseInput(BaseModel):
    order_id: int=Field(gt=0)
