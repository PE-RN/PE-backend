# Cálculo de Energia Solar

## Variáveis para o Cálculo de Energia Solar

- **Taxa de ocupação**: 55 MW/km² (Capacidade instalada por área)

### Perdas no Sistema Solar (% do total)
- **Perdas por sujidade**: 3.5%
- **Perdas por sombreamento**: 3%
- **Perdas por descasamento (Mismatch)**: 1.5%
- **Perdas por LID (Degradação inicial)**: 1.5%
- **Perdas por resistência ôhmica**: 1%
- **Perdas por degradação anual**: 2.4%
- **Ganho por sobrepotência no inversor**: 0.5% (considerar como um ganho)
- **Perdas por ventilação insuficiente**: 0.25%
- **Perdas por indisponibilidade do sistema**: 0.35%
- **Perdas no inversor**: 1.3%
- **Coeficiente de temperatura**: -0.35%/°C (variação de potência com temperatura)

---

## Cálculo da Potência Gerada por Sistemas Solares

O cálculo da potência gerada por um sistema solar segue os passos:

1. **Interpolação do valor de GHI (Global Horizontal Irradiance)** na curva de potência do painel fotovoltaico para obter a potência bruta.
2. **Aplicação das perdas no sistema** (sujidade, sombreamento, etc.), multiplicando pela potência interpolada.

---

## Cálculo do Fator de Capacidade (FC) Solar

O fator de capacidade é um indicador da eficiência da usina solar ao longo do ano e é calculado pela fórmula:

$
\text{Fator de Capacidade (FC)} = \frac{\text{Potência Calculada com Perdas} \times 8760}{\text{Potência Nominal} \times 8760}
$

Onde **8760** é o número total de horas em um ano.

---



# Cálculo de Energia Eólica

## Curvas de Potência das Turbinas Eólicas

As curvas de potência para turbinas eólicas utilizadas no cálculo são obtidas a partir do repositório da NREL. Seguem os modelos:

- **Turbina Eólica Offshore**: [2020ATB NREL Reference 15MW_240](https://github.com/NREL/turbine-models)
- **Turbina Eólica Onshore**: [2020ATB NREL Reference 4MW_150](https://github.com/NREL/turbine-models)

---

## Variáveis para o Cálculo de Energia Eólica Onshore

- **Densidade do ar padrão**: 1.225 kg/m³
- **Taxa de ocupação**: 4.5 MW/km² (Capacidade instalada por área)

### Perdas no Sistema Eólico Onshore (% do total)
- **Indisponibilidade do sistema**: 4.68%
- **Perdas elétricas**: 3%
- **Degradação anual**: 1.3%
- **Perdas aerodinâmicas**: 6%

---

## Variáveis para o Cálculo de Energia Eólica Offshore

- **Densidade do ar padrão**: 1.225 kg/m³
- **Taxa de ocupação**: 5.5 MW/km² (Capacidade instalada por área)

### Perdas no Sistema Eólico Offshore (% do total)
- **Indisponibilidade do sistema**: 5%
- **Perdas elétricas**: 4.5%
- **Degradação anual**: 2%
- **Perdas aerodinâmicas**: 8%

---

## Cálculo de Densidade de Potência Eólica

A densidade de potência de uma turbina eólica é calculada pela seguinte fórmula:

$
\text{Densidade de Potência} = 0.5 \times \text{densidade do ar} \times \text{velocidade do vento}^3
$

---

## Ajuste da Velocidade do Vento pela Densidade do Ar

A velocidade do vento deve ser ajustada de acordo com a densidade do ar da região em análise:

$
\text{Velocidade ajustada} = \text{velocidade do vento} \times \left(\frac{\text{densidade padrão}}{\text{densidade da região}}\right)^3
$

---

## Cálculo da Potência Gerada por Turbinas Eólicas

O processo de cálculo da potência gerada por uma turbina eólica envolve:

1. **Interpolação da velocidade do vento ajustada** na curva de potência da turbina para obter a potência inicial.
2. **Aplicação das perdas**, multiplicando a potência calculada pelas perdas na seguinte ordem:

$
\text{Potência com perdas} = \left(\text{Potência Inicial} \times (1 - \text{perdas aero})\right) \times (1 - \text{perdas elet}) \times (1 - \text{perdas indisp}) \times (1 - \text{perdas degrad})
$

---

## Cálculo do Fator de Capacidade (FC) Eólico

O fator de capacidade é um indicador da eficiência da usina eólica ao longo do ano e é calculado pela fórmula:

$
\text{Fator de Capacidade (FC)} = \frac{\text{Potência Calculada com Perdas} \times 8760}{\text{Potência Nominal} \times 8760}
$

Onde **8760** é o número total de horas em um ano.


# Funcionamento de "dash_data.py"

O retorno de "dash_data.py" é a média dos valores das variáveis de todos os pixels selecionados. As variáveis K e C são excessões pois o retorno para esses dois é o maior C com o K associado e o menor C com o K associado.

O cálculo do potencial é feito no front usando a área da região selecionada e o Fator de capacidade médio.


###Exemplo de retorno do "dash_data.py"

```json
{
	"type": "ResponseData",
	"properties": {
		"name": "MACAU",
		"regionValues": {
			"mys": 8.41,
			"mms": [
				7.01, 5.77, 3.89, 5.75, 6.71, 9.02, 10.65, 11.39, 13.49, 10.23, 8.57, 8.32
			],
			"mmd": [
				117.51, 118.05, 128.09, 126.62, 131.52, 133.69, 137.38, 132.26, 134.61, 119.79, 104.82, 103.32
			],
			"ms": [
				3.92, 3.7, 4.22, 5.94, 8.03, 12.66, 3.69, 2.13, 1.9, 2.18, 2.61, 2.72
			],
			"mpd": [
				78.8, 59.66, 74.6, 179.41, 492.43, 1723.93, 176.02, 17.7, 13.83, 10.86, 22.55, 23.19
			],
			"hmd": [
				126.73, 130.4, 133.37, 134.78, 136.8, 138.17, 139.66, 134.33, 125.02, 123.11, 
				122.14, 120.18, 118.31, 118.14, 115.58, 116.89, 115.55, 115.02, 116.28, 116.09, 
				115.75, 119.46, 121.16, 123.3
			],
			"hms": [
				9.53, 9.1, 8.75, 8.43, 8.22, 8.12, 7.98, 8.24, 8.48, 8.28, 7.8, 7.3, 
				7.01, 6.94, 7.08, 7.47, 8.15, 8.51, 8.62, 8.93, 9.36, 9.83, 9.92, 9.9
			],
			"fc": 0.51,
			"dp": [
				0.34, 1.87, 6.19, 20.9, 36.15, 28.55, 1.44, 0.73, 1.12, 1.34, 0.87, 0.5
			]
		},
		"pixels": 16,
		"C_max": 13.173706036001299,
		"K_max": 2.243549615452991,
		"C_min": 7.283122929041943,
		"K_min": 1.618981782531334,
		"area": 69.26
	}
}



