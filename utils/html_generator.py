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

    def get_password_reset_link(
        self,
        reset_link: str,
        user_email: str,
        contact_link: str,
        img_isi_er_cid: str,
        img_state_cid: str,
        img_logo_cid: str,
    ) -> str:
        return recovery_password.reset_password_link_email(
            style=recovery_password.style(),
            reset_link=reset_link,
            user_email=user_email,
            contact_link=contact_link,
            img_isi_er_cid=img_isi_er_cid,
            img_state_cid=img_state_cid,
            img_logo_cid=img_logo_cid,
        )

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
