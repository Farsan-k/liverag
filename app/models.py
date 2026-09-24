from sqlalchemy import Column, Integer, String, Text


from app.database import Base 


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    source = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)


