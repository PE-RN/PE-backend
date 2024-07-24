from os import getenv
from typing import Annotated

from asyncer import syncify
from fastapi import BackgroundTasks, Depends, status
from fastapi.exceptions import HTTPException
from sentry_sdk import capture_exception
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories.feedback_repository import FeedbackRepository
from schemas.email import EmailMessage
from schemas.feedback import FeedbackCreate
from services.email_service import EmailService
from sql_app.database import get_db



class UserController:

    def __init__(self, repository: FeedbackRepository, email_service: EmailService, background_tasks: BackgroundTasks):

        self.repository = repository
        self.email_service = email_service
        self.background_tasks = background_tasks

    @staticmethod
    async def inject_controller(background_tasks: BackgroundTasks, db: Annotated[AsyncSession, Depends(get_db)]):

        return UserController(
            repository=FeedbackRepository(db=db),
            email_service=EmailService(
                host=getenv("SMTP_HOST"),
                port=getenv("SMTP_PORT"),
                email=getenv("EMAIL_SMTP"),
                password=getenv("PASSWORD_SMTP")
            ),
            background_tasks=background_tasks
        )

    async def create_feedback(self, feedback: FeedbackCreate):

        created_feedback = await self.repository.create_feedback(feedback)
        if not created_feedback:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não foi possível criar o feedback")
        
        email_message = self._create_feedback_email_message(
            'platenergiasrn@isi-er.com.br',
            created_feedback
        )

        if getenv('ENVIRONMENT') != 'local':
            self.background_tasks.add_task(
                self._send_feedback_email,
                email_message=email_message,
            )

        return created_feedback

    def _create_feedback_email_message(self, to_email, feedback) -> EmailMessage:

        content = []
        content['contato'] = 'a'
        content['opniao'] = 'a'
        content['contato'] = f'<h3 style="color:#0dace3;"> {ocupation.capitalize()} para confirmar seu email na plataforma por favor click  no link'
        content['contato'] += f' <a style="display: inline-block;" href="{link_url}">LINK</a> !! <h3>'

        return EmailMessage(html_content=content[feedback.type], subject="Confirmação de email Plataforma Atlas", to_email=to_email)

    def _send_feedback_email(self, email_message: EmailMessage):

        self.email_service.send_email_account_confirmation(email_message)
