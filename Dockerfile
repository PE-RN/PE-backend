# Use Miniconda base image
FROM continuumio/miniconda3

WORKDIR /usr/src/app

# Copy the application files
COPY . .

# Install Mamba from Conda-Forge
RUN conda install mamba -n base -c conda-forge

# Use Mamba to create an environment and install packages
RUN mamba create -n atlas python=3.11.8 -c conda-forge --yes
RUN echo "source activate atlas" > ~/.bashrc
ENV PATH /opt/conda/envs/atlas/bin:$PATH

# Use Mamba to install packages
RUN mamba install pip gdal rasterio -n atlas -c conda-forge --yes
RUN pip install -r requirements.txt

# Expose the port the app runs on
EXPOSE 8000

# Environment variable
ENV NAME PLEN

# Command to run the app
CMD ["python", "-m", "uvicorn", "main:app", "--host=0.0.0.0", "--port=8000", "--workers=4"]