import datetime
from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, Integer, String, JSON, Boolean

SQLALCHEMY_DATABASE_URL = "sqlite:///./example.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

Base = declarative_base()


class TorchModel(Base):
    __tablename__ = "torch_models"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    hf_name = Column(String)
    name = Column(String)
    path = Column(String)
    scan_status = Column(String)
    scan_results = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class OffloadConfig(Base):
    __tablename__ = "offload_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    model_id = Column(Integer)
    name = Column(String)
    offload_layers = Column(JSON)
    quantize: bool = Column(Boolean, default=False)
    quantize_dtype: str = Column(String, default="float8")
    enable_scale: bool = Column(Boolean, default=False)
    enable_bias: bool = Column(Boolean, default=False)


Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
