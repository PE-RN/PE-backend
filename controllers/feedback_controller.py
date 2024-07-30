from os import getenv
from typing import Annotated

from fastapi import BackgroundTasks, Depends, status
from fastapi.exceptions import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories.feedback_repository import FeedbackRepository
from schemas.email import EmailMessage
from schemas.feedback import FeedbackCreate
from services.email_service import EmailService
from sql_app.database import get_db


class FeedbackController:

    def __init__(self, repository: FeedbackRepository, email_service: EmailService, background_tasks: BackgroundTasks):

        self.repository = repository
        self.email_service = email_service
        self.background_tasks = background_tasks

    @staticmethod
    async def inject_controller(background_tasks: BackgroundTasks, db: Annotated[AsyncSession, Depends(get_db)]):

        return FeedbackController(
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

        content = {}
        content['contato'] = f'<h3 style="color:#0dace3;"> Um novo contato de {feedback.name} com email {feedback.email}'
        content['contato'] += f' <a style="display: inline-block;"><br> Menssagem:<br>{feedback.message}</a> !! <h3>'

        content['opniao'] = f"""<h3 style="color:#0dace3;"> Uma nova opnião de avaliação {feedback.platform_rate}
                        com intuitivade {feedback.intuitivity}"""
        content['opniao'] += f' <a style="display: inline-block;"><br> Menssagem:<br>{feedback.message}</a><h3>'

        return EmailMessage.with_default_logo_images(html_content=content[feedback.type], subject="Novo feedback enviado", to_email=to_email)

    def _send_feedback_email(self, email_message: EmailMessage):

        self.email_service.send_email_account_confirmation(email_message)
