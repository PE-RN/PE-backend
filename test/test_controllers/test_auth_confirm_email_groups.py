import random
import string
from os import getenv
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse

from controllers.auth_controller import AuthController
from repositories.auth_repository import AuthRepository
from sql_app import models


def build_temporary_user(email: str) -> models.TemporaryUser:
    return models.TemporaryUser(
        email=email,
        password="password",
        ocupation="pesquisador",
        group_id=None,
        gender="masculino",
        education="superior",
        institution="isi",
        age="30",
        user="Teste",
    )


@pytest.mark.anyio
async def test_confirm_email_assigns_authenticated_group(auth_repository):
    auth_controller = AuthController(
        repository=auth_repository,
        email_service=None,
        background_tasks=None,
    )
    rand_str = "".join(random.choices(string.ascii_lowercase, k=6))
    user_email = f"test{rand_str}@example.com"
    temporary_user = build_temporary_user(user_email)
    authenticated_group = models.Group(
        name="authenticated",
        description="Usuarios autenticados",
    )

    auth_repository.get_temporary_user_by_id = AsyncMock(return_value=temporary_user)
    auth_repository.get_user_by_email = AsyncMock(return_value=False)
    auth_repository.get_authenticated_group = AsyncMock(
        return_value=authenticated_group
    )
    auth_repository.create_user_from_temporary = AsyncMock(return_value=None)
    auth_repository.delete_temporary_user = AsyncMock(return_value=None)

    response = await auth_controller.confirm_email(uuid4())
    expected = RedirectResponse(
        url=f"{getenv('FRONT_URL')}pages/login/login.html",
        status_code=status.HTTP_302_FOUND,
    )

    assert expected.status_code == response.status_code
    assert expected.body == response.body
    auth_repository.get_authenticated_group.assert_awaited_once_with()
    auth_repository.create_user_from_temporary.assert_awaited_once_with(
        temporary_user,
        group_id=authenticated_group.id,
    )


@pytest.mark.anyio
async def test_confirm_email_raises_when_authenticated_group_is_missing(auth_repository):
    auth_controller = AuthController(
        repository=auth_repository,
        email_service=None,
        background_tasks=None,
    )
    rand_str = "".join(random.choices(string.ascii_lowercase, k=6))
    user_email = f"test{rand_str}@example.com"
    temporary_user = build_temporary_user(user_email)

    auth_repository.get_temporary_user_by_id = AsyncMock(return_value=temporary_user)
    auth_repository.get_user_by_email = AsyncMock(return_value=False)
    auth_repository.get_authenticated_group = AsyncMock(return_value=None)
    auth_repository.create_user_from_temporary = AsyncMock(return_value=None)
    auth_repository.delete_temporary_user = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await auth_controller.confirm_email(uuid4())

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    auth_repository.create_user_from_temporary.assert_not_awaited()
    auth_repository.delete_temporary_user.assert_not_awaited()


@pytest.mark.anyio
async def test_get_authenticated_group_uses_seeded_group_name():
    repository = AuthRepository(db=None)
    authenticated_group = models.Group(
        name="authenticated",
        description="Usuarios autenticados",
    )

    repository.get_group_by_name = AsyncMock(return_value=authenticated_group)

    response = await repository.get_authenticated_group()

    assert response == authenticated_group
    repository.get_group_by_name.assert_awaited_once_with("authenticated")
