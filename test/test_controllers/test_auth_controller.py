import random
import string
from datetime import datetime, timedelta, timezone
from os import getenv
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import anyio
import bcrypt
import pytest
from fastapi import BackgroundTasks
from fastapi.exceptions import HTTPException
from jose import jwt

from controllers.auth_controller import AuthController
from schemas.email import EmailMessage
from schemas.token import Token
from services.email_service import EmailService
from sql_app import models


@pytest.mark.anyio
async def test_get_user_from_token_invalid_token(auth_repository):

    # Arrange
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    invalid_token = 'huehueheuheu'
    authorization = f"Bearer {invalid_token}"
    auth_repository.get_user_by_email = AsyncMock(return_value=user)

    # Act
    with pytest.raises(HTTPException, match="Token inválido!") as error:
        await AuthController.get_user_from_token(auth_repository, authorization)

    # Assert
    assert error.value.status_code == 401


@pytest.mark.anyio
async def test_get_user_from_token_expired_token(auth_repository):

    # Arrange
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    to_encode = {"sub": user_email}
    acess_token_expires_time = datetime.now(timezone.utc)
    to_encode.update({"exp": acess_token_expires_time})
    access_token = f'Bearer {jwt.encode(to_encode, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))}'
    await anyio.sleep(1)

    # Act
    with pytest.raises(HTTPException, match="Token expirado!") as error:
        await AuthController.get_user_from_token(auth_repository, access_token)

    # Assert
    assert error.value.status_code == 401


@pytest.mark.anyio
async def test_get_user_from_token_invalid_authorization_token(auth_repository):

    # Arrange
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    invalid_token = 'huehueheuheu'
    authorization = f"Bearer{invalid_token}"
    auth_repository.get_user_by_email = AsyncMock(return_value=user)

    # Act
    with pytest.raises(HTTPException, match="Token inválido!") as error:
        await AuthController.get_user_from_token(auth_repository, authorization)

    # Assert
    assert error.value.status_code == 401


@pytest.mark.anyio
async def test_get_user_from_token_without_sub_token(auth_repository):

    # Arrange
    to_encode = {}
    acess_token_expires_time = datetime.now(timezone.utc) + timedelta(seconds=200)
    to_encode.update({"exp": acess_token_expires_time})
    access_token = f'Bearer {jwt.encode(to_encode, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))}'

    # Act
    with pytest.raises(HTTPException, match="Token inválido!") as error:
        await AuthController.get_user_from_token(auth_repository, access_token)

    # Assert
    assert error.value.status_code == 401


@pytest.mark.anyio
async def test_get_user_from_token(auth_repository):

    # Arrange
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    to_encode = {"sub": user_email}
    acess_token_expires_time = datetime.now(timezone.utc) + timedelta(hours=6)
    to_encode.update({"exp": acess_token_expires_time})
    access_token = f'Bearer {jwt.encode(to_encode, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))}'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    auth_repository.get_user_by_email = AsyncMock(return_value=user)
    auth_repository.get_anonymous_user_by_id = AsyncMock(return_value=None)

    # Act
    user_response = await AuthController.get_user_from_token(auth_repository, access_token)

    # Assert
    assert user == user_response


@pytest.mark.anyio
async def test_verify_password_check(auth_repository):

    # Arrange
    password = 'test'
    bytes_pass = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hash = bcrypt.hashpw(bytes_pass, salt)
    hashed_password = hash.decode('utf-8')
    auth_controller = AuthController(
        repository=auth_repository,
        background_tasks=BackgroundTasks(),
        email_service=EmailService(
            host=getenv("SMTP_HOST"),
            port=getenv("SMTP_PORT"),
            email=getenv("EMAIL_SMTP"),
            password=getenv("PASSWORD_SMTP")
        )
    )

    # Act
    response = auth_controller.verify_password_hash(password, hashed_password)

    # Assert
    assert response is True


@pytest.mark.anyio
async def test_verify_password_invalid_check(auth_repository):

    # Arrange
    password = 'test'
    bytes_pass = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hash = bcrypt.hashpw(bytes_pass, salt)
    hashed_password = hash.decode('utf-8')
    auth_controller = AuthController(
        repository=auth_repository,
        background_tasks=0,
        email_service=0
    )

    # Act
    response = auth_controller.verify_password_hash(password + 'bbb', hashed_password)

    # Assert
    assert response is False


@pytest.mark.anyio
async def test_generate_access_token(auth_repository):

    # Arrange
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    to_encode = {"sub": user_email}
    acess_token_expires_time = datetime.now(timezone.utc) + timedelta(minutes=int(getenv("ACCESS_TOKEN_EXPIRE_MINUTES")))
    to_encode.update({"exp": acess_token_expires_time})
    jwt_encoded = jwt.encode(to_encode, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))
    auth_controller = AuthController(
        repository=auth_repository,
        background_tasks=None,
        email_service=None
    )

    # Act
    response = auth_controller.generate_access_token(user_email)

    # Assert
    assert response == jwt_encoded


@pytest.mark.anyio
async def test_generate_access_refresh(auth_repository):

    # Arrange
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    to_encode = {"sub": user_email}
    acess_token_expires_time = datetime.now(timezone.utc) + timedelta(minutes=int(getenv("REFRESH_TOKEN_EXPIRE_MINUTES")))
    to_encode.update({"exp": acess_token_expires_time})
    jwt_encoded = jwt.encode(to_encode, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))
    auth_controller = AuthController(
        repository=auth_repository,
        background_tasks=None,
        email_service=None
    )

    # Act
    response = auth_controller.generate_refresh_token(user_email)

    # Assert
    assert response == jwt_encoded


@pytest.mark.anyio
async def test_get_token_user_not_found(auth_repository):

    # Arrange
    auth_controller = AuthController(
        repository=auth_repository,
        email_service=None,
        background_tasks=None
    )
    auth_controller.authenticate_user = AsyncMock(return_value=None)

    # Act
    with pytest.raises(HTTPException, match="Usuário não encontrado!") as error:
        await auth_controller.get_token_user("test@gmail.com", "senhatest")

    # Assert
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_get_token_user(auth_repository):

    # Arrange
    auth_controller = AuthController(
        repository=auth_repository,
        email_service=None,
        background_tasks=None
    )
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    token = 'token'
    refresh_token = 'refresh_token'
    auth_controller.authenticate_user = AsyncMock(return_value=user)
    auth_controller.generate_access_token = Mock(return_value=token)
    auth_controller.generate_refresh_token = Mock(return_value=refresh_token)

    # Act
    response = await auth_controller.get_token_user(user.email, user.password)

    # Assert
    assert response == Token(access_token=token, refresh_token=refresh_token)


@pytest.mark.anyio
async def test_authentication_user_wrong_user(auth_repository):

    # Arrange
    auth_controller = AuthController(
        repository=auth_repository,
        email_service=None,
        background_tasks=None
    )
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    auth_controller.authenticate_user = AsyncMock(return_value=None)

    # Act
    response = await auth_controller.authenticate_user(user.email, user.password)

    # Assert
    assert response == None


@pytest.mark.anyio
async def test_authentication_user(auth_repository):

    # Arrange
    auth_controller = AuthController(
        repository=auth_repository,
        email_service=None,
        background_tasks=None
    )
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    auth_controller.authenticate_user = AsyncMock(return_value=user)

    # Act
    response = await auth_controller.authenticate_user(user.email, user.password)

    # Assert
    assert response == user


@pytest.mark.anyio
async def test_confirm_email_without_temporary_user(auth_repository):

    # Arrange
    auth_controller = AuthController(
        repository=auth_repository,
        email_service=None,
        background_tasks=None
    )
    auth_repository.get_temporary_user_by_id = AsyncMock(return_value=False)

    # Act
    with pytest.raises(HTTPException, match="Usuário não encontrado!") as error:
        await auth_controller.confirm_email(uuid4())

    # Assert
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_confirmed_email_without_temporary_user(auth_repository):

    # Arrange
    auth_controller = AuthController(
        repository=auth_repository,
        email_service=None,
        background_tasks=None
    )
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    auth_repository.get_temporary_user_by_id = AsyncMock(return_value=user)
    auth_repository.get_user_by_email = AsyncMock(return_value=True)

    # Act
    with pytest.raises(HTTPException, match="Usuário já confirmado!") as error:
        await auth_controller.confirm_email(uuid4())

    # Assert
    assert error.value.status_code == 409


@pytest.mark.anyio
async def test_confirm_email_user(auth_repository):

    # Arrange
    auth_controller = AuthController(
        repository=auth_repository,
        email_service=None,
        background_tasks=None
    )
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    auth_repository.get_temporary_user_by_id = AsyncMock(return_value=user)
    auth_repository.get_user_by_email = AsyncMock(return_value=False)
    auth_repository.create_user_from_temporary = AsyncMock(return_value=None)
    auth_repository.delete_temporary_user = AsyncMock(return_value=None)

    # Act
    response = await auth_controller.confirm_email(uuid4())

    # Assert
    assert response == None


@pytest.mark.anyio
async def test_validate_and_get_email_from_refresh_token_expired(auth_repository):

    # Arrange
    auth_controller = AuthController(repository=auth_repository, background_tasks=None, email_service=None)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    to_encode = {"sub": user_email}
    acess_token_expires_time = datetime.now(timezone.utc)
    to_encode.update({"exp": acess_token_expires_time})
    refresh_token = f'{jwt.encode(to_encode, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))}'
    await anyio.sleep(1)

    # Act
    with pytest.raises(HTTPException, match="Token expirado!") as error:
        await auth_controller.validate_and_get_email_from_refresh_token(token=refresh_token)

    # Assert
    assert error.value.status_code == 401


@pytest.mark.anyio
async def test_validate_and_get_email_from_refresh_token_invalid(auth_repository):

    # Arrange
    auth_controller = AuthController(repository=auth_repository, background_tasks=None, email_service=None)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    to_encode = {"sub": user_email}
    acess_token_expires_time = datetime.now(timezone.utc) + timedelta(seconds=200)
    to_encode.update({"exp": acess_token_expires_time})
    refresh_token = f'{jwt.encode(to_encode, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))}dasdasdasdasdasd'

    # Act
    with pytest.raises(HTTPException, match="Token inválido!") as error:
        await auth_controller.validate_and_get_email_from_refresh_token(token=refresh_token)

    # Assert
    assert error.value.status_code == 401


@pytest.mark.anyio
async def test_validate_and_get_email_from_refresh_token_without_email(auth_repository):

    # Arrange
    auth_controller = AuthController(repository=auth_repository, background_tasks=None, email_service=None)
    to_encode = dict()
    acess_token_expires_time = datetime.now(timezone.utc) + timedelta(seconds=200)
    to_encode.update({"exp": acess_token_expires_time})
    refresh_token = f'{jwt.encode(to_encode, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))}'

    # Act
    with pytest.raises(HTTPException, match="Não foi possível validar as credencias!") as error:
        await auth_controller.validate_and_get_email_from_refresh_token(token=refresh_token)

    # Assert
    assert error.value.status_code == 401


@pytest.mark.anyio
async def test_validate_and_get_email_from_refresh_token_without_user(auth_repository):

    # Arrange
    auth_controller = AuthController(repository=auth_repository, background_tasks=None, email_service=None)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    to_encode = {"sub": user_email}
    acess_token_expires_time = datetime.now(timezone.utc) + timedelta(seconds=200)
    to_encode.update({"exp": acess_token_expires_time})
    refresh_token = f'{jwt.encode(to_encode, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))}'

    # Act
    with pytest.raises(HTTPException, match="Usuário não encontrado!") as error:
        await auth_controller.validate_and_get_email_from_refresh_token(token=refresh_token)

    # Assert
    assert error.value.status_code == 401


@pytest.mark.anyio
async def test_validate_and_get_email_from_refresh_token(auth_repository):

    # Arrange
    auth_controller = AuthController(repository=auth_repository, background_tasks=None, email_service=None)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    to_encode = {"sub": user_email}
    acess_token_expires_time = datetime.now(timezone.utc) + timedelta(seconds=200)
    to_encode.update({"exp": acess_token_expires_time})
    refresh_token = f'{jwt.encode(to_encode, getenv("SECRET_KEY"), algorithm=getenv("ALGORITHM"))}'
    auth_repository.get_user_by_email = AsyncMock(return_value=user)

    # Act
    response = await auth_controller.validate_and_get_email_from_refresh_token(token=refresh_token)

    # Assert
    assert response == user.email


@pytest.mark.anyio
async def test_refresh_tokens(auth_repository):

    # Arrange
    auth_controller = AuthController(repository=auth_repository, background_tasks=None, email_service=None)
    access_token = 'access_token'
    refresh_token = 'refresh_token'
    auth_controller.generate_access_token = Mock(return_value=access_token)
    auth_controller.generate_refresh_token = Mock(return_value=refresh_token)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    auth_controller.validate_and_get_email_from_refresh_token = AsyncMock(return_value=user_email)

    # Act
    response = await auth_controller.refresh_tokens(access_token)

    # Assert
    assert response == Token(access_token=access_token, refresh_token=refresh_token)


@pytest.mark.anyio
async def test_generate_temporary_password(auth_repository):

    # Arrange
    auth_controller = AuthController(repository=auth_repository, email_service=None, background_tasks=None)
    default_length = 9

    # Act
    response = auth_controller.generate_temporary_password()

    # Assert
    assert len(response) == default_length


@pytest.mark.anyio
async def test_hash_password():

    # Arrange
    auth_controller = AuthController(email_service=None, background_tasks=None, repository=None)

    # Act
    password = 'test'
    password_hash = auth_controller._hash_password(password)

    # Assert
    assert bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


@pytest.mark.anyio
async def test_recovery_password_not_found(auth_repository):

    # Arrange
    auth_controller = AuthController(background_tasks=None, repository=auth_repository, email_service=None)
    auth_repository.get_user_by_email = AsyncMock(return_value=None)
    user_email = 'rodolfobezerra@isi-er.com.br'

    # Act
    with pytest.raises(HTTPException, match='Usuário não encontrado!') as error:
        await auth_controller.recovery_password(user_email)

    # Assert
    assert error.value.status_code == 404


@pytest.mark.anyio
async def test_recovery_password(auth_repository):

    # Arrange
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    auth_repository.get_user_by_email = AsyncMock(return_value=user)
    auth_repository.update_user = AsyncMock(return_value=None)


@pytest.mark.anyio
async def test_change_password_incorrect_password(auth_repository):

    # Arrange
    auth_controller = AuthController(repository=auth_repository, email_service=None, background_tasks=None)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )

    # Act
    with pytest.raises(HTTPException, match="Senha atual incorreta!") as error:
        await auth_controller.change_password(user=user, actual_password="pass", new_password="passworddd")

    # Assert
    assert error.value.status_code == 400


@pytest.mark.anyio
async def test_change_password(auth_repository):

    # Arrange
    auth_controller = AuthController(repository=auth_repository, email_service=None, background_tasks=None)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user_email = f'test{rand_str}@example.com'
    user = models.User(
        email=user_email,
        password="password",
        ocupation='pesquisador',
        group_id=None,
    )
    user.password = auth_controller._hash_password(user.password)
    auth_repository.update_user = AsyncMock(return_valueu=user)

    # Act
    response = await auth_controller.change_password(user=user, actual_password='password', new_password="new_password")

    # Assert
    assert response == None


@pytest.mark.anyio
async def test_create_recovery_email_message(auth_repository):

    # Arrange
    auth_controller = AuthController(repository=auth_repository, email_service=None, background_tasks=None)
    new_password = 'new_password'
    content = '<h3 style="color:#0dace3;">você pode trocar esta senha futuramente usando a opção de troca, sua senha temporaria SENHA:'
    content += f' <h2 style="color:black;">{new_password}<h2/><h3/>'
    to_email = "rodolfobez15@gmail.com"

    # Act
    email_response = auth_controller._create_recovery_email_message(new_password, to_email)

    # Assert
    assert EmailMessage(to_email='rodolfobez15@gmail.com', subject="Recuperação de senha Plataforma Atlas", html_content=content) == email_response
