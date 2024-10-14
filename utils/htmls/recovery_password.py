

def style():
    return """
        <style>
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

            .content {
                padding: 40px 80px;
                color: black;
            }

            .content p {
                align-items: justify;
                font-size: 20px;
                line-height: 24px;
            }

            .pass {
                display: inline-block;
                text-align: center;
                width: 100%;
                font-size: 32px;
                line-height: 40px;
                color: #396581;
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
                padding: 20px 80px;
            }

            .footer p {
                font-size: 12px;
                line-height: 24px;
                color: #666;
            }

            .footer footer{
                padding-top: 40px;
                display: flex;
                justify-content: center;
                align-items: flex-end;
                gap: 80px;
            }
    </style>
        """


def recovery_password(user_email, new_password, style, enter_link, img_isi_er_cid, img_state_cid, img_logo_cid, contact_link, reset_password_link):

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Redefinição de senha</title>
    {style}
    </head>

    <body>
        <table class="container">
            <tr>
                <td>
                    <table>
                        <tr>
                            <td>
                                <div class="nav">
                                    <div class="logo">
                                        <img src="cid:{img_logo_cid}" alt="#">
                                    </div>
                                </div>
                                <div class="content">
                                    <h1>Recuperação de senha</h1>
                                    <p>
                                        Olá, {user_email},
                                        <br>
                                        <br>
                                        Você recebeu uma nova senha para acessar a <strong>Plataforma de Energias do RN.</strong> Sua
                                        <strong>senha temporária</strong> é:
                                        <br>
                                        <br>
                                        <a class="pass">{new_password}</a>
                                        <br>
                                        <br>
                                        Agora, basta clicar no botão e usar sua nova senha:
                                    </p>
                                </div>

                                <div class="btn">
                                    <a target="_blank" href="{enter_link}">Entrar</a>
                                </div>

                                <div class="content">
                                    <p>
                                        Você poderá alterar esta senha posteriormente utilizando a opção <a href="{reset_password_link}">
                                        Redefinir Senha</a> na
                                        Plataforma.
                                        <br>
                                        <br>
                                        Caso você não tenha solicitado essa alteração, entre em Contato conosco o mais
                                        rápido possível.
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
                                    <img src="cid:{img_state_cid}" width="140px" alt="Logotipo do Governo do Rio Grande do Norte e Secretaria de Estado do Desenvolvimento Econômico - SEDEC">
                                    <img src="cid:{img_isi_er_cid}" width="180px" alt="Logotipo do SENAI ISI-ER | Instituto de Inovação em Energias Renováveis">
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
