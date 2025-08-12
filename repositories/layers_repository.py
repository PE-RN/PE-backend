from sqlmodel.ext.asyncio.session import AsyncSession
from sql_app import models
from sqlalchemy.orm import selectinload
from schemas.layers import LayerGroupCreate, LayerCreate
from sqlmodel import select, delete
import datetime


class LayersRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_layer_group(self, layer_group: LayerGroupCreate):
        new_layer_group = models.LayerGroups(**layer_group.model_dump())

        self.db.add(new_layer_group)
        await self.db.commit()
        await self.db.refresh(new_layer_group)
        return new_layer_group
    
    async def create_layer(self, layer: LayerCreate):
        new_layer = models.Layer(**layer.model_dump())

        self.db.add(new_layer)
        await self.db.commit()
        await self.db.refresh(new_layer)
        return new_layer
    
    async def get_layer_by_id(self, id: str):
        statement = select(models.Layer).filter_by(id=id).fetch(1)
        layer = await self.db.exec(statement)
        return layer.first()

    async def get_layer_group(self):
        statement = select(models.LayerGroups)
        layer_groups = await self.db.exec(statement)
        return layer_groups.all() 
    
    async def get_layer_by_group_id(self, id: str):
        statement = select(models.Layer).filter_by(layer_group_id=id).fetch(1)
        layer = await self.db.exec(statement)
        return layer.first()

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