"""Router para CRUD de Anticipos."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Anticipo, Obra
from app.schemas import AnticipoCreate, AnticipoOut, AnticipoUpdate

router = APIRouter(tags=["Anticipos"])


@router.get("/obras/{obra_id}/anticipos", response_model=List[AnticipoOut])
def listar_anticipos_de_obra(obra_id: int, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    return (
        db.query(Anticipo)
        .filter(Anticipo.obra_id == obra_id)
        .order_by(Anticipo.fecha.desc(), Anticipo.id.desc())
        .all()
    )


@router.post("/obras/{obra_id}/anticipos", response_model=AnticipoOut, status_code=status.HTTP_201_CREATED)
def crear_anticipo(obra_id: int, data: AnticipoCreate, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra no encontrada.")

    anticipo = Anticipo(
        obra_id=obra_id,
        importe=data.importe,
        comprobante=data.comprobante.strip(),
        fecha=data.fecha,
    )
    db.add(anticipo)
    db.flush()
    return anticipo


@router.get("/anticipos/{anticipo_id}", response_model=AnticipoOut)
def obtener_anticipo(anticipo_id: int, db: Session = Depends(get_db)):
    ant = db.query(Anticipo).filter(Anticipo.id == anticipo_id).first()
    if not ant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anticipo no encontrado.")
    return ant


@router.patch("/anticipos/{anticipo_id}", response_model=AnticipoOut)
def actualizar_anticipo(anticipo_id: int, data: AnticipoUpdate, db: Session = Depends(get_db)):
    ant = db.query(Anticipo).filter(Anticipo.id == anticipo_id).first()
    if not ant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anticipo no encontrado.")

    datos = data.model_dump(exclude_unset=True)
    for campo, valor in datos.items():
        if isinstance(valor, str):
            valor = valor.strip()
        setattr(ant, campo, valor)

    db.flush()
    return ant


@router.delete("/anticipos/{anticipo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_anticipo(anticipo_id: int, db: Session = Depends(get_db)):
    ant = db.query(Anticipo).filter(Anticipo.id == anticipo_id).first()
    if not ant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Anticipo no encontrado.")

    db.delete(ant)
    db.flush()
    return None
