import os
from uvicorn import run


def main():
    run(host='localhost', port=int(os.getenv('PORT', '5000')), app='main:app', workers=4)


if __name__ == '__main__':
    main()
