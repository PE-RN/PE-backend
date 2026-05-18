import json
from repositories.layers_repository import LayersRepository
from typing import Annotated
from sqlmodel.ext.asyncio.session import AsyncSession

from schemas.layers import LayerCreate,LayerGroupCreate
from pathlib import Path
from fastapi import Depends, HTTPException, status, UploadFile
from sql_app.database import get_db
from utils.utils import Utils
import shutil


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ASSETS_DIR = BACKEND_ROOT / "assets" / "public"


def _public_asset_path(*parts: str) -> Path:
    return PUBLIC_ASSETS_DIR.joinpath(*parts)


def _stored_asset_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None

    asset_path = Path(path_value)
    if asset_path.is_absolute():
        return asset_path

    return (BACKEND_ROOT / asset_path).resolve()


def _stored_asset_ref(path: Path) -> str:
    return path.relative_to(BACKEND_ROOT).as_posix()

class LayersController:
    def __init__(self, repository: LayersRepository):
        self.repository = repository

    @staticmethod
    async def inject_controller(db: Annotated[AsyncSession, Depends(get_db)]):
        return LayersController(
            repository=LayersRepository(db=db)
        )    

    async def create_layer_group(self, layer_group: LayerGroupCreate):
        return await self.repository.create_layer_group(layer_group)

    async def update_layer_group(self, layer_group: LayerGroupCreate, id:str):
        return await self.repository.update_layer_group(layer_group, id)
    
    async def delete_layer_group(self, id:str):
        return await self.repository.delete_layer_group(id)
    
    async def delete_layer(self, id:str):
        return await self.repository.delete_layer(id)

    async def get_layer_by_group_id(self, id: str):
        return await self.repository.get_layer_by_group_id(id)
    
    async def get_layer_by_id(self, id: str):
        layer = await self.repository.get_layer_by_id(id)

        if not layer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer não encontrada")

        popup_path = _public_asset_path("jsons", "popups_fields.json")
        style_path = _public_asset_path("jsons", "layers_style.json")

        if popup_path.exists():
            with open(popup_path, "r", encoding="utf-8") as f:
                existing_popup = json.load(f)   

        if style_path.exists():
            with open(style_path, "r", encoding="utf-8") as f:
                existing_style = json.load(f) 
                
        layer_name = Utils().format_layer_name(layer.name) 

        if existing_popup and layer_name in existing_popup:
            popup = existing_popup[layer_name]   

        if existing_style and layer_name in existing_style:
            style = existing_style[layer_name]
        
        return {
            "layer": layer,
            "popup": popup if 'popup' in locals() else None,
            "style": style if 'style' in locals() else None
        }                       
    
    async def get_layer_groups(self):
        return await self.repository.get_all_groups_and_layers()
    
    async def get_all_layer_groups(self):
        return await self.repository.get_layer_group()

    async def create_layer(self, layer: LayerCreate, file: UploadFile, file_icon: UploadFile):
        await self.create_layer_files(layer, file, file_icon)

        return await self.repository.create_layer(layer)
    
    async def update_layer(self, layer: LayerCreate, file: UploadFile, file_icon: UploadFile, id: str):
        await self.create_layer_files(layer, file, file_icon)

        return await self.repository.update_layer(layer, id)
    
    async def create_layer_popup(self, id: str, fields: dict):
        layer = await self.repository.get_layer_by_id(id)

        if not layer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
        
        import json

        layer_path = _stored_asset_path(layer.path)
        if layer_path is None or not layer_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer file not found")

        with open(layer_path, "r", encoding="utf-8", errors="replace") as file:
            data = json.load(file)

        data = data.get('features', [])

        layer_name = Utils().format_layer_name(layer.name)

        fields_popup = {}
        if len(data) > 0:
            properties = data[0].get('properties', {})
            for key, value in properties.items():
                if key in fields["fields"].keys():
                    data = fields["fields"][key]
                    fields_popup[data.get("title", key)] = {"property": key, "unit": data.get("unit", ""), "decimal": data.get("decimal", 0)}

        new_popup = {
            layer_name: {
                "title": fields["title"],
                "fields": fields_popup,
                "titleProperty": fields["titleProperty"],
                "tooltipOffset": [0, -22]
            }
        }

        json_path = _public_asset_path("jsons", "popups_fields.json")

        if json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = {}
        else:
            existing_data = {}

        existing_data.update(new_popup)

        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)

        return new_popup

    async def create_layer_style(self, id: str, style: dict):
        layer = await self.repository.get_layer_by_id(id)
        if not layer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Layer not found")
        layer_name = Utils().format_layer_name(layer.name)

        style_path = _public_asset_path("jsons", "layers_style.json")
        if style_path.exists():
            with open(style_path, "r", encoding="utf-8") as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = {}
        else:
            existing_data = {}
        existing_data[layer_name] = style

        style_path.parent.mkdir(parents=True, exist_ok=True)
        with open(style_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)

        return existing_data
    
    async def create_layer_files(self, layer: LayerCreate, file: UploadFile, file_icon: UploadFile):
        if file:
            private_directory = _public_asset_path("layers")
            private_directory.mkdir(parents=True, exist_ok=True)

            layer_name = Utils().format_layer_name(layer.name)

            file_location = private_directory / f"{layer_name}.geojson"

            try:
                with open(file_location, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving file: {str(e)}")

            layer.path = _stored_asset_ref(file_location)

        if file_icon:
            private_directory = _public_asset_path("icons")
            private_directory.mkdir(parents=True, exist_ok=True)

            layer_name = Utils().format_layer_name(layer.name)

            file_extension = Path(file_icon.filename).suffix
            file_location = private_directory / f"{layer_name}{file_extension}"
            
            try:
                with open(file_location, "wb") as buffer:
                    shutil.copyfileobj(file_icon.file, buffer)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error saving file: {str(e)}")

            layer.path_icon = _stored_asset_ref(file_location)