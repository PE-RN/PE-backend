import random
import string

import bcrypt
import pytest

from schemas.user import UserCreate


@pytest.mark.anyio
async def test_token_fake_user(async_client):

    # Arrange
    body = {"email": "fake@example.com", "password": "test"}

    # Act
    response = await async_client.post("/token", json=body)

    # Assert
    assert response.status_code == 400
    assert response.json() == {"detail": "Usuário não encontrado!"}


@pytest.mark.anyio
async def test_token_user(async_client, user_repository):

    # Arrange
    password = 'test'
    bytes_pass = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hash = bcrypt.hashpw(bytes_pass, salt)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))

    user = await user_repository.create_user(UserCreate(
        email=f"rodolfo{rand_str}@is-er.com.br", password=hash.decode('utf-8'), group_id=None, ocupation="pesquisador"))

    body = {"email": user.email, "password": password}

    # Act
    response = await async_client.post("/token", json=body)

    # Assert
    assert response.status_code == 200
    assert 'access_token' in response.json()


@pytest.mark.anyio
async def test_create_user(async_client):

    # Arrange
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    body = {"email": f"rodolfobez15{rand_str}@gmail.com", "password": "test", "group_id": None, "ocupation": "pesquisador"}

    # Act
    response = await async_client.post("/users", json=body)

    # Assert
    assert response.status_code == 201
    assert all(key in {"email", "group_id", "ocupation", "created_at", "id"} for key in response.json())


@pytest.mark.anyio
async def test_create_user_with_incorrect_ocupation(async_client):

    # Arrange
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    body = {"email": f"rodolfobez15{rand_str}@gmail.com", "password": "test", "group_id": None, "ocupation": "aleatório"}

    # Act
    response = await async_client.post("/users", json=body)

    # Assert
    assert response.status_code == 422


@pytest.mark.anyio
async def test_refresh_token_user(async_client, user_repository):

    # Arrange
    password = 'test'
    bytes_pass = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hash = bcrypt.hashpw(bytes_pass, salt)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))

    user = await user_repository.create_user(UserCreate(
        email=f"rodolfo{rand_str}@is-er.com.br", password=hash.decode('utf-8'), group_id=None, ocupation="pesquisador"))

    body = {"email": user.email, "password": password}

    # Act
    response_token = await async_client.post("/token", json=body)
    access_token = response_token.json()["access_token"]
    response = await async_client.post("/refresh-token", json={"token": access_token})

    # Assert
    assert response.status_code == 200
    assert 'access_token' in response.json()


@pytest.mark.anyio
async def test_change_password(async_client, user_repository):

    # Arrange
    password = 'test'
    bytes_pass = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hash = bcrypt.hashpw(bytes_pass, salt)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))

    user = await user_repository.create_user(UserCreate(
        email=f"rodolfo{rand_str}@is-er.com.br", password=hash.decode('utf-8'), group_id=None, ocupation="pesquisador"))

    body = {"email": user.email, "password": password}
    response_token = await async_client.post("/token", json=body)
    access_token = response_token.json()["access_token"]

    new_password = 'new_test'
    body_change_password = {"password": password, "new_password": new_password}

    # Act
    response = await async_client.post("/change-password", json=body_change_password, headers={"Authorization": f"Bearer {access_token}"})

    # Assert
    assert response.status_code == 200


@pytest.mark.anyio
async def test_recovery_password(async_client, user_repository):

    # Arrange
    password = 'test'
    bytes_pass = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hash = bcrypt.hashpw(bytes_pass, salt)
    rand_str = ''.join(random.choices(string.ascii_lowercase, k=6))
    user = await user_repository.create_user(UserCreate(
        email=f"rodolfo{rand_str}@is-er.com.br", password=hash.decode('utf-8'), group_id=None, ocupation="pesquisador"))

    # Act
    response = await async_client.get(f"/recovery-password/{user.email}")

    # Assert
    assert response.status_code == 200
