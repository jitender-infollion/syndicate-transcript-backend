from sqlalchemy import Column, Integer, String, Text

from services.database.postgres.connection import Base


class Author(Base):
    __tablename__ = "authors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    experience = Column(Text, nullable=True)
