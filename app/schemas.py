from pydantic import BaseModel
from typing import Optional

class DocumentCreate(BaseModel):
    title : str
    source : str
    content : str




class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    source: Optional[str] = None
    content: Optional[str] = None