from fastapi import HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession
from sql_app import models
from sqlalchemy.orm import selectinload
from schemas.layers import LayerGroupCreate, LayerCreate
from sqlmodel import select, delete
from pathlib import Path
import datetime
import os


class LayersRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_layer_group(self, layer_group: LayerGroupCreate):
        new_layer_group = models.LayerGroups(**layer_group.model_dump())

        self.db.add(new_layer_group)
        await self.db.commit()
        await self.db.refresh(new_layer_group)
        return new_layer_group

    async def update_layer_group(self, layer_group: LayerGroupCreate, id:str):
        existing_layer_group = await self.get_layer_group_by_id(id)

        if not existing_layer_group:
            raise HTTPException(status_code=404, detail="Layer group not found")

        for key, value in layer_group.model_dump().items():
            setattr(existing_layer_group, key, value)

        existing_layer_group.updated_at = datetime.datetime.now()
        await self.db.commit()
        await self.db.refresh(existing_layer_group)

        return existing_layer_group
    
    async def delete_layer_group(self, id: str):
        existing_layer_group = await self.get_layer_group_by_id(id)
        if not existing_layer_group:
            raise HTTPException(status_code=404, detail="Grupo de camadas não encontrado")
        
        existing_sub_groups = await self.get_group_by_group_id(id)
        if existing_sub_groups:
            raise HTTPException(status_code=400, detail="Não é possível excluir um grupo que possui subgrupos.")
        
        existing_layers = await self.get_layer_by_group_id(id)
        now = datetime.datetime.now()

        for layer in existing_layers or []:
            layer.deleted_at = now

        existing_layer_group.deleted_at = now
        await self.db.commit()

        return {"detail": "Layer group deleted successfully"}
    
    async def delete_layer(self, id: str):
        existing_layer = await self.get_layer_by_id(id)
        if not existing_layer:
            raise HTTPException(status_code=404, detail="Layer not found")
        
        layer_name = existing_layer.name.replace(" ", "_")

        # Remove arquivos de ícone e shape
        icon_path = os.path.join("assets", "public", "icon", layer_name)
        shape_path = os.path.join("assets", "public", "shape", layer_name)

        for file_path in [icon_path, shape_path]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

        import json

        # Remove ocorrências nos arquivos JSON de estilos e popups
        json_files = [
            Path("assets/public/jsons/layer_style.json"),
            Path("assets/public/jsons/popups_fields.json"),
        ]

        for json_file in json_files:
            if json_file.exists():
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    data = {}

                # Se existir a chave com o nome da camada, remove
                if layer_name in data:
                    del data[layer_name]
                    with open(json_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=4)

        # Remove do banco
        await self.db.delete(existing_layer)
        await self.db.commit()

        return {"detail": "Layer deleted successfully"}

    async def create_layer(self, layer: LayerCreate):
        new_layer = models.Layer(**layer.model_dump())

        self.db.add(new_layer)
        await self.db.commit()
        await self.db.refresh(new_layer)
        return new_layer

    async def update_layer(self, layer: LayerCreate, id: str):
        existing_layer = await self.get_layer_by_id(id)

        if not existing_layer:
            raise HTTPException(status_code=404, detail="Camada não encontrada")
        
        layer_name = existing_layer.name.replace(" ", "_")

        icon_path = os.path.join("assets", "public", "icon", layer_name)
        shape_path = os.path.join("assets", "public", "shape", layer_name)

        for file_path in [icon_path, shape_path]:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass

        for key, value in layer.model_dump().items():
            setattr(existing_layer, key, value)

        await self.db.commit()
        await self.db.refresh(existing_layer)
        return existing_layer

    async def get_layer_by_id(self, id: str):
        statement = select(models.Layer).where(models.Layer.deleted_at.is_(None)).filter_by(id=id).fetch(1)
        layer = await self.db.exec(statement)
        return layer.first()
    
    async def get_layer_group_by_id(self, id: str):
        statement = select(models.LayerGroups).where(models.LayerGroups.deleted_at.is_(None)).filter_by(id=id).fetch(1)
        layer_group = await self.db.exec(statement)
        return layer_group.first()

    async def get_layer_group(self):
        statement = select(models.LayerGroups).where(models.LayerGroups.deleted_at.is_(None))
        layer_groups = await self.db.exec(statement)
        return layer_groups.all() 
    
    async def get_layer_by_group_id(self, id: str):
        statement = select(models.Layer).where(models.Layer.deleted_at.is_(None)).filter_by(layer_group_id=id)
        layer = await self.db.exec(statement)
        return layer.all()

    async def get_group_by_group_id(self, id: str):
        statement = select(models.LayerGroups).where(models.LayerGroups.deleted_at.is_(None)).filter_by(layer_group_id=id)
        group = await self.db.exec(statement)
        return group.all()

    async def get_all_groups_and_layers(self):
    # Buscar todos os grupos
        groups_stmt = select(models.LayerGroups).where(models.LayerGroups.deleted_at.is_(None))
        layers_stmt = select(models.Layer).where(models.Layer.deleted_at.is_(None))

        result_groups = await self.db.exec(groups_stmt)
        result_layers = await self.db.exec(layers_stmt)

        groups = result_groups.all()
        layers = result_layers.all()

        # Indexar layers por grupo_id
        layers_by_group = {}
        for layer in layers:
            layers_by_group.setdefault(layer.layer_group_id, []).append({
                "id": str(layer.id),
                "name": layer.name,
                "path": layer.path,
                "path_icon": layer.path_icon,
                "subtitle": layer.subtitle,
                "activated": layer.activated
            })

        # Indexar grupos por grupo pai
        subgroups_by_parent = {}
        for group in groups:
            subgroups_by_parent.setdefault(group.layer_group_id, []).append(group)

        # Função recursiva para montar árvore
        def build_group_tree(group):
            return {
                "id": str(group.id),
                "name": group.name,
                "layers": layers_by_group.get(group.id, []),
                "subgroups": [
                    build_group_tree(child) for child in subgroups_by_parent.get(group.id, [])
                ]
            }

        # Pegar grupos raiz (sem grupo pai)
        root_groups = [g for g in groups if g.layer_group_id is None]

        return [build_group_tree(g) for g in root_groups]