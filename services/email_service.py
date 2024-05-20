import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


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
            server.ehlo()
            server.starttls()
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

    def send_account_confirmation_account(self, to_email: str, ocupation: str, link_url: str) -> None:

        link_url = self._replace_safety_url_for_sender_pattern(link_url)
        content = f'<h3 style="color:#0dace3;"> {ocupation.capitalize()} para confirmar seu email na plataforma por favor click  no link'
        content += f' <a style="display: inline-block;" href="{link_url}">LINK</a> !! <h3>'

        self._send_email(to_email, "Confirmação de email Plataforma Atlas", content)

    def send_email_recovery_password(self, to_email: str, new_password: str) -> None:

        content = '<h3 style="color:#0dace3;">você pode trocar esta senha futuramente usando a opção de troca, sua senha temporaria SENHA:'
        content += f' <h2 style="color:black;">{new_password}<h2/><h3/>'

        self._send_email(to_email, "Recuperação de senha Plataforma Atlas", content)
