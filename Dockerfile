# Use Miniconda base image
FROM continuumio/miniconda3

# Evita o erro de plugin e força o solver clássico para a instalação inicial
ENV CONDA_NO_PLUGINS=true
ENV CONDA_SOLVER=classic

# Instalar o mamba forçando o solver clássico
RUN conda install -n base -c conda-forge mamba -y && \
    conda clean --all -f -y

# Agora que o mamba está instalado, voltamos para a lógica normal
# Copiar apenas o arquivo de dependências para otimizar o cache
COPY requirements.txt .

# Criar o ambiente usando mamba (que é muito mais rápido e estável)
RUN mamba create -n atlas python=3.11.8 gdal rasterio pip -c conda-forge --yes && \
    mamba clean --all -f -y

# Configurar o PATH
ENV PATH /opt/conda/envs/atlas/bin:$PATH

# Instalar o restante das dependências via pip
RUN pip install --no-cache-dir -r requirements.txt

# Só agora copiamos o código-fonte
COPY . .

EXPOSE 5000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "8"]