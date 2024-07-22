def get_style():
    return """<style>
            /* Estilos globais */
            body {
                font-family: Arial, sans-serif;
                font-size: 14px;
                line-height: 1.6;
                color: #333;
            }

            .container {
                width: 720px;
                height: 1200px;
                border: 1px solid #ddd;
            }

            .nav {
                color: #F4F4F4;
                background-color: #396581;
                justify-content: space-between;
                align-items: center;
                padding: 40px 80px 20px 80px;
            }

            .nav p {
                font-size: 36px;
                line-height: 42px;
                margin-bottom: 20px;
            }

            .logo {
                font-size: 80px;
            }

            .content {
                padding: 40px 80px;
                color: black;
            }

            .content p {
                align-items: justify;
                font-size: 20px;
                line-height: 24px;
            }

            .btn {
                    display: flex;
                    justify-content: center;
                }

            .btn a{
                display: block;
                width: 240px;
                height: 40px;
                text-align: center;
                text-decoration: none;
                background-color: #396581;
                color: #F4F4F4;
                border-radius: 8px;
                font-size: 20px;
                line-height: 40px;
                cursor: pointer;
                margin: 0 auto;
            }

            .pass {
                display: inline-block;
                text-align: center;
                width: 100%;
                font-size: 32px;
                line-height: 40px;
                color: #396581;
            }

            .footer {
                background-color: #f0f0f0;
                padding: 40px 80px;
            }

            .footer p {
                font-size: 20px;
                line-height: 24px;
                color: #666;
            }

            .footer footer{
                padding-top: 40px;
                text-align: center;
            }
        </style>
    """


def get_confirmation_email_html(style, user_email, confirmation_email_link, contact_link, img_isi_er_cid, img_state_cid, img_logo_cid):
    return f"""
    <!DOCTYPE html>
    <html>

    <head>
        <meta charset="utf-8">
        <title>Confirmação de email</title>
        {style}
    </head>

    <body>
        <table align="center" class="container">
            <tr>
                <td>
                    <table>
                        <tr>
                            <td>
                                <div class="nav">
                                    <div class="logo">
                                        <img src="cid:{img_logo_cid}" alt="#">
                                    </div>
                                    <p>Confirmação de E-mail</p>
                                </div>
                                <div class="content">
                                    <p>
                                        Olá, {user_email},
                                        <br>
                                        <br>
                                        Sua conta na <strong>Plataforma de Energias do RN</strong> está quase pronta. Para ativá-la,
                                        pedimos que confirme seu endereço de e-mail clicando no botão abaixo:
                                    </p>
                                </div>

                                <div class="btn">
                                    <a target="_blank" href="{confirmation_email_link}">Confirmar meu e-mail</a>
                                </div>

                                <div class="content">
                                    <p>
                                        Por favor, note que sua conta não será ativada até que seu e-mail seja confirmado.
                                        <br>
                                        <br>
                                        Se você não se cadastrou na <strong>Plataforma de Energias do RN</strong> recentemente,
                                        por favor ignore este e-mail.
                                        <br>
                                        <br>
                                        Atenciosamente,
                                        <br>
                                        <br>
                                        <strong>Plataforma de Energias do Rio Grande do Norte</strong>
                                        <br>
                                        <br>

                                    </p>
                                </div>
                            </td>
                        </tr>
                        <!-- Rodapé do email -->
                        <tr>
                            <td class="footer">
                                <p>
                                    Por favor, não responda a este e-mail,
                                    pois é uma mensagem automática e não é possível dar continuidade
                                    ao seu atendimento por este canal.
                                    <br>
                                    <br>
                                    Se tiver alguma dúvida, acesse o menu <a href="{contact_link}">Contato</a> diretamente na Plataforma.
                                </p>
                                <footer>
                                    <img src="cid:{img_state_cid}" alt="#" style="margin-right: 120px;">
                                    <img src="cid:{img_isi_er_cid}" alt="#" style="margin-left: 120px;">
                                </footer>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>

    </html>
    """
