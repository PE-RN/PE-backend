from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from sql_app import models


class AuthRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    
    async def create_user_and_delete_temporary(self, temporary_user: models.TemporaryUser):
        user = models.User(**temporary_user.model_dump(exclude_defaults=True))
        self.db.add(user)
        self.db.delete(temporary_user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_user_by_email(self, email: str) : 
        statment = select(models.User).filter_by(email=email)
        
        self.db.exec(select(models.User).filter_by(email=email)[0])
        return await self.db.query(models.User).filter(models.User.email == email).first()

    async def create_log_email(self,content:str , to:str, sender:str, subject:str, has_error:bool, error_message:str | None = None):
      log_email = models.LogsEmail(to=to, sender=sender, subject=subject,has_error=has_error, error_message=error_message)
      self.db.add(log_email)
      await self.db.commit()
      return await self.db.refresh(log_email)
    
    async def get_temporary_user_by_id(self, temporary_user_id):
        return await self.db.query(models.TemporaryUser).filter(models.TemporaryUser.id == temporary_user_id).first()
