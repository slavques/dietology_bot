from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .models import Base

engine = create_engine('sqlite:///bot.db')
SessionLocal = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)
