from os import getenv
from uvicorn import run


if __name__ == '__main__':
    run(port=int(getenv('PORT','5000')),app='main:app',workers=4)