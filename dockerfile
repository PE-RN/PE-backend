# Use an official Miniconda runtime as a parent image
FROM continuumio/miniconda3:4.12.0

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Create Conda environment and install all packages
RUN conda create --name atlas python=3.11.8 pip -y \
    && echo "source activate atlas" > ~/.bashrc \
    && . /opt/conda/etc/profile.d/conda.sh \
    && conda activate atlas \
    && conda install -c conda-forge gdal rasterio -y \
    && pip install -r requirements.txt
    

# Set PATH to use the Conda environment
ENV PATH /opt/conda/envs/atlas/bin:$PATH

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV NAME PLEN

# Run app.py when the container launches
CMD ["python", "-m", "uvicorn", "main:app", "--host=0.0.0.0", "--port=8000", "--workers=4"]
