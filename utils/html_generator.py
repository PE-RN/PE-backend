from .htmls import recovery_password, confirmation_account


class HtmlGenerator:

    def __init__(self):
        pass

    def get_password_recovery(self, user_email, enter_link, contact_link, img_isi_er_cid, img_state_cid,
                              img_logo_cid, new_password, reset_password_link) -> str:
        return recovery_password.recovery_password(
            style=recovery_password.style(),
            enter_link=enter_link,
            img_isi_er_cid=img_isi_er_cid,
            img_state_cid=img_state_cid,
            new_password=new_password,
            img_logo_cid=img_logo_cid,
            user_email=user_email,
            contact_link=contact_link,
            reset_password_link=reset_password_link
        )

    def get_password_reset_link(self, reset_link: str, user_email: str) -> str:
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;font-size:14px;color:#333;background-color:#f4f4f4;padding:20px;">
  <div style="max-width:600px;margin:0 auto;background:#fff;border:1px solid #ddd;border-radius:4px;">
    <div style="background-color:#396581;padding:30px 40px;color:#fff;">
      <p style="font-size:24px;margin:0;">Plataforma de Energias RN</p>
      <p style="font-size:14px;margin:8px 0 0 0;">Recuperação de senha</p>
    </div>
    <div style="padding:30px 40px;">
      <p>Olá,</p>
      <p>Recebemos uma solicitação de redefinição de senha para a conta associada
         ao e-mail <strong>{user_email}</strong>.</p>
      <p>Clique no botão abaixo para criar uma nova senha.
         Este link é válido por <strong>1 hora</strong>.</p>
      <div style="text-align:center;margin:30px 0;">
        <a href="{reset_link}"
           style="background-color:#396581;color:#fff;padding:12px 30px;
                  text-decoration:none;border-radius:4px;font-size:16px;">
          Redefinir senha
        </a>
      </div>
      <p>Se você não solicitou a redefinição de senha, ignore este e-mail.
         Sua senha permanecerá a mesma.</p>
      <p>Por segurança, nunca compartilhe este link com ninguém.</p>
    </div>
  </div>
</body>
</html>"""

    def confirmation_account(self, user_email, contact_link, confirmation_email_link, img_isi_er_cid, img_state_cid, img_logo_cid) -> str:
        return confirmation_account.get_confirmation_email_html(
            style=confirmation_account.get_style(),
            confirmation_email_link=confirmation_email_link,
            contact_link=contact_link,
            img_isi_er_cid=img_isi_er_cid,
            img_state_cid=img_state_cid,
            user_email=user_email,
            img_logo_cid=img_logo_cid
        )
