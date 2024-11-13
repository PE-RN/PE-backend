# Subir arquivos no banco de dados

- **Ao usar esse código os arquivos serão adicionados, mas NÃO substituirão existentes com os mesmos nomes.**

- Colocar todos os arquivos em uma pasta e substitiur o caminho da pasta na variável _**folder_path**_.
- Executar esse código usando os parametros corretos em _**db_params**_, nome _**dbname**_,  _**user**_, _**password**_, _**host**_ e _**port**_ do banco.
- O código listará todos os arquivos da pasta _**folder_path**_ que terminam com _**'.geojson'**_ e inserirá um a um no banco.

## Código Python para subir os arquivos geojson para o banco de dados

```python

import os
import json
import psycopg2


def load_geojson(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def insert_geojson_to_db(geojson_data, filename, db_params):
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    sql = """
    INSERT INTO "GeoJsonData" (name, data)
    VALUES (%s, %s)
    """

    name = os.path.splitext(filename)[0]
    data = json.dumps(geojson_data)
    values = (name, data)

    cursor.execute(sql, values)
    conn.commit()

    cursor.close()
    conn.close()


def process_folder(folder_path, db_params):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)

        if os.path.isfile(file_path) and filename.endswith('.geojson'):
            print(f"Processing file: {filename}")
            geojson_data = load_geojson(file_path)
            insert_geojson_to_db(geojson_data, filename, db_params)
            print(f"Inserted data from {filename} into the database.")


# Especificar o caminho da pasta
folder_path = "C:/Users/XXXX/"

# Parametros de conexao DB
db_params = {
    'dbname': 'atlas',
    'user': 'postgres',
    'password': 'XXXXXXX',
    'host': 'XXXXX',
    'port': XXXX
}

# Processa todos os arquivos na pasta
process_folder(folder_path, db_params)

```
