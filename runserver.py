import os
from uvicorn import run


def main():
    run(host=os.getenv('HOST', 'localhost'), port=int(os.getenv('PORT', '5000')), app='main:app', workers=1)


if __name__ == '__main__':
    main()
