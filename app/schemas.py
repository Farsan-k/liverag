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

class SearchRequest(BaseModel):
    query: str
    limit: int = 3



class AskRequest(BaseModel):
    question: str
    limit: int = 3