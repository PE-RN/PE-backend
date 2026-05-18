import os
from functools import lru_cache
from pathlib import Path

import rasterio


@lru_cache(maxsize=1)
def ensure_rasterio_proj_data() -> str | None:
    proj_data_path = Path(rasterio.__file__).resolve().parent / "proj_data"
    if not proj_data_path.exists():
        return None

    os.environ["PROJ_DATA"] = str(proj_data_path)

    current_proj_lib = os.environ.get("PROJ_LIB")
    if current_proj_lib:
        try:
            if Path(current_proj_lib).resolve() != proj_data_path.resolve():
                os.environ.pop("PROJ_LIB", None)
        except OSError:
            os.environ.pop("PROJ_LIB", None)

    return str(proj_data_path)