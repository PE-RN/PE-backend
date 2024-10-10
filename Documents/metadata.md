# Tabelas que descrevem as unidades e descrição de cada variável do arquivo ".geojson" armazenado no BD.

## Wind

| Variável | Unidade | Descrição                                |
|----------|---------|------------------------------------------|
| hms      | m/s     | Velocidade média horária                 |
| hmd      | degrees | Direção média horária                    |
| mms      | m/s     | Velocidade média mensal                  |
| mmd      | degrees | Direção média mensal                     |
| dp       | %       | Probabilidade de ocorrência de setor     |
| mys      | m/s     | Velocidade média anual                   |
| ms       | m/s     | Velocidade média por setor               |
| mpd      | W/m²    | Densidade de potência média por setor    |
| fc       | None    | Fator de capacidade com perdas           |

## Solar

| Variável | Unidade  | Descrição                                |
|----------|----------|------------------------------------------|
| hmg      | W/m²     | GHI médio horário                        |
| hmp      | MWh      | Potência média horária                   |
| mmg      | W/m²     | GHI médio mensal                         |
| mmp      | MWh      | Potência média mensal                    |
| fc       | None     | Fator de capacidade com perdas           |



###Exemplo geojson:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-37.261409759521484, -4.85125732421875]
      },
      "properties": {
        "hms": [
          8.853, 8.314, 7.842, 7.539, 7.363, 7.139, 6.937, 7.153, 7.448, 7.358, 
          7.277, 7.318, 7.537, 7.96, 8.357, 8.61, 8.756, 8.822, 9.167, 9.735, 
          10.159, 10.295, 9.937, 9.438
        ],
        "hmd": [
          113.014, 118.314, 122.989, 127.659, 131.522, 135.207, 138.144, 135.044, 
          127.367, 117.083, 103.374, 89.133, 78.28, 71.42, 68.487, 67.422, 67.774, 
          71.813, 77.431, 82.507, 90.442, 97.229, 103.012, 107.506
        ],
        "mms": [
          8.619, 7.733, 6.455, 6.861, 6.842, 7.645, 7.782, 9.045, 9.633, 9.836, 
          10.109, 9.073
        ],
        "mmd": [
          89.072, 96.634, 91.802, 99.885, 102.445, 120.274, 137.625, 103.378, 
          108.879, 97.038, 88.066, 85.818
        ],
        "dp": [
          0.091, 2.306, 25.046, 23.801, 33.95, 11.027, 3.288, 0.263, 0.034, 
          0.057, 0.091, 0.046
        ],
        "ms": [
          5.204, 6.426, 8.467, 9.169, 8.426, 7.003, 5.958, 3.939, 3.61, 5.033, 
          4.112, 4.395
        ],
        "mpd": [
          96.334, 179.684, 398.759, 532.489, 393.258, 229.481, 149.242, 43.033, 
          28.217, 102.563, 43.732, 50.709
        ],
        "mys": 8.305,
        "fc": 0.413,
        "k": 4.2152812366083365,
        "c": 9.318323662320736
      }
    }
  ]
}
