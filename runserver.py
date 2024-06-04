import os
from uvicorn import run


def main():
    run(host='127.0.0.1', port=int(os.getenv('PORT', '5000')), app='main:app', workers=4)


if __name__ == '__main__':
    main()
