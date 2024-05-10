import os
import subprocess
from uvicorn import run

def install_dependencies():
    # Install system dependencies, uncomment and modify according to your needs
    # subprocess.run(["sudo", "apt-get", "update"], check=True)
    # subprocess.run(["sudo", "apt-get", "install", "-y", "libgdal-dev"], check=True)
    # Environment variables needed for GDAL
    # os.environ['CPLUS_INCLUDE_PATH'] = '/usr/include/gdal'
    # os.environ['C_INCLUDE_PATH'] = '/usr/include/gdal'
    
    # Install Python packages
   # Installing GDAL directly through nix which includes most required libs
    #subprocess.run(["nix-env", "-iA", "nixpkgs.gdal"], check=True)
    #subprocess.run(["pip", "install", "GDAL", "rasterio"], check=True)  # Add other packages as needed
    
def main():
    # Install dependencies before starting the server
    install_dependencies()
    
    # Run the FastAPI application with Uvicorn
    run(host='0.0.0.0', port=int(os.getenv('PORT', '5000')), app='main:app', workers=4)

if __name__ == '__main__':
    main()

