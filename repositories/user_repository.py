from sqlalchemy.orm import Session
from schemas.user import UserCreate
from sql_app.models import User


class UserRepository:

    def __init__(self, db: Session):
        self.db = db

    def create_user(self, user: UserCreate):
        db_user = User(email=user.email, password=user.password, ocupation=user.ocupation, group_id=user.group_id)
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        return db_user
