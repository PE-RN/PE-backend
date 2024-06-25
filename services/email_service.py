import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import ssl
from schemas.email import EmailMessage


class EmailService:

    def __init__(self, host: str, port: str, email: str, password: str):
        self.host = host
        self.port = port
        self.email = email
        self.password = password

    def _replace_safety_url_for_sender_pattern(self, url: str) -> str:
        return url.replace("&", "&amp;").replace("?", "&quest;")

    def _send_email(self, to_email: str, subject: str, content_html: str) -> None:

        """
            If has error raise exeception to be handled on controller layer , but try catch is used to enforce quit connection SMTP
        """

        server = smtplib.SMTP(host=self.host, port=self.port)
        try:
            context = ssl.create_default_context()
            server.ehlo()
            server.starttls(context=context)
            server.login(self.email, self.password)

            email_msg = MIMEMultipart()
            email_msg['From'] = self.email
            email_msg['To'] = to_email
            email_msg['Subject'] = subject
            email_msg.attach(MIMEText(content_html, 'html'))
            server.sendmail(email_msg['From'], email_msg['To'], email_msg.as_string())
        except Exception as e:
            server.quit()
            raise e

    def send_email_account_confirmation(self, email_message: EmailMessage) -> None:

        self._send_email(email_message.to_email, email_message.subject, email_message.html_content)

    def send_email_recovery_password(self, email_message: EmailMessage) -> None:

        self._send_email(email_message.to_email, email_message.subject, email_message.html_content)
