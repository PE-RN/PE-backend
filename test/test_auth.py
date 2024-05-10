import pytest
from schemas.user import UserCreate
from passlib.context import CryptContext
from passlib.hash import bcrypt_sha256
import os

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
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    pwd_context.update(bcrypt__salt_size=22)

    user = await user_repository.create_user(UserCreate(
        email="rodolfobez15@gmail.com", password=bcrypt_sha256.hash("test"+os.environ.get("SECRET_KEY")), group_id=None, ocupation="Bolsista"))
    print(user.password)
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    body = {"email": "rodolfobez15@gmail.com", "password": "test"}

    #Act 
    response = await async_client.post("/token", json=body)

    #Assert
    assert response.status_code == 200
    assert 'acess_token' in response.json()
    assert 'token_type' in response.json()

    


