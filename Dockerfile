# Use Miniconda base image
FROM continuumio/miniconda3

# Configurações para evitar travamentos do Conda e plugins
ENV CONDA_NO_PLUGINS=true
ENV CONDA_AUTO_UPDATE_CONDA=false

# 1. Instalar o Mamba com as flags de segurança e limpar o índice
# O mamba-org/mamba é o caminho mais estável atualmente
RUN conda clean -i && \
    conda install -n base -c conda-forge mamba -y && \
    conda clean --all -f -y

# 2. Copiar apenas os arquivos de dependência primeiro
# Isso evita que qualquer mudança no código invalide o cache da instalação
COPY requirements.txt .

# 3. Criar o ambiente e instalar dependências em um único passo
# Adicionei o pip, gdal e rasterio aqui para o Mamba resolver tudo de uma vez
RUN mamba create -n atlas python=3.11.8 gdal rasterio pip -c conda-forge --yes && \
    mamba clean --all -f -y

# Configurar o PATH para o ambiente 'atlas'
ENV PATH /opt/conda/envs/atlas/bin:$PATH

# Garantir que o shell use o ambiente correto
SHELL ["/bin/bash", "-c"]

# 4. Instalar o restante das dependências via pip
RUN pip install --no-cache-dir -r requirements.txt

# 5. Só agora copiamos o restante dos arquivos (código-fonte)
COPY . .

EXPOSE 5000

# Removi o --reload para produção (VPS), pois consome CPU desnecessária
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "8"]