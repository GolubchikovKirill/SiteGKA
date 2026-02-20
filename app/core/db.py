from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


def init_db(session: Session) -> None:
    from sqlmodel import select

    from app.core.security import get_password_hash
    from app.models import User

    user = session.exec(select(User).where(User.email == settings.FIRST_SUPERUSER_EMAIL)).first()

    if not user:
        user = User(
            email=settings.FIRST_SUPERUSER_EMAIL,
            hashed_password=get_password_hash(settings.FIRST_SUPERUSER_PASSWORD),
            full_name="Admin",
            is_superuser=True,
            is_active=True,
        )
        session.add(user)
        session.commit()
