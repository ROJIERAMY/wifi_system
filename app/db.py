from sqlmodel import Session, SQLModel, create_engine, select

from app.config import DATABASE_URL
from app.models import RouterSettings, VoucherProfile

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

# Friendly names shown as big buttons on the home screen
PRESETS: list[tuple[str, int]] = [
    ("30 min", 30 * 60),
    ("1 hour", 3600),
    ("3 hours", 3 * 3600),
    ("1 day", 86400),
]


def _ensure_presets(session: Session) -> None:
    for name, seconds in PRESETS:
        exists = session.exec(select(VoucherProfile).where(VoucherProfile.name == name)).first()
        if not exists:
            session.add(
                VoucherProfile(
                    name=name,
                    duration_seconds=seconds,
                    mikrotik_hotspot_profile="default",
                )
            )


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        rs = session.get(RouterSettings, 1)
        if rs is None:
            session.add(RouterSettings(id=1))
        _ensure_presets(session)
        session.commit()


def get_session():
    with Session(engine) as session:
        yield session
