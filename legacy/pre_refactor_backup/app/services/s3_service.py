import os
import re
import uuid
from datetime import datetime
from typing import Optional
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME") or os.getenv("AWS_S3_BUCKET_NAME", "construction-invoices-bucket")


def get_s3_client():
    """Inicializa y retorna el cliente de AWS S3 configurado."""
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        return boto3.client(
            "s3",
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
        )
    return None


def upload_file_to_s3(file_bytes: bytes, filename: str) -> str:
    """
    Función sincrónica para subir un archivo PDF a un bucket privado de AWS S3.
    Retorna la clave del objeto S3 (object_key), NO la URL pública.
    Ejemplo de retorno: 'invoices/2026/10/a1b2c3d4_factura.pdf'
    """
    clean_filename = re.sub(r'[^a-zA-Z0-9_\.\-]', '_', filename)
    year_month = datetime.now().strftime("%Y/%m")
    unique_id = uuid.uuid4().hex[:10].upper()
    object_key = f"invoices/{year_month}/{unique_id}_{clean_filename}"

    s3_client = get_s3_client()
    if s3_client:
        try:
            s3_client.put_object(
                Bucket=AWS_BUCKET_NAME,
                Key=object_key,
                Body=file_bytes,
                ContentType="application/pdf",
            )
            return object_key
        except (BotoCoreError, ClientError) as err:
            print(f"[AWS S3 Error] Error al subir archivo a S3: {err}. Usando clave simulada.")

    # Retorno de clave simulada para desarrollo local si no hay credenciales
    return object_key


def generate_presigned_url(object_key: Optional[str], expiration: int = 3600) -> Optional[str]:
    """
    Genera una URL prefirmada (Presigned URL) segura con caducidad temporal (1 hora por defecto)
    para permitir la visualización o descarga segura del archivo desde el bucket privado.
    """
    if not object_key:
        return None

    # Si ya es una URL completa (por datos previos en DB), retornarla directamente
    if object_key.startswith("http://") or object_key.startswith("https://"):
        return object_key

    s3_client = get_s3_client()
    if s3_client:
        try:
            presigned_url = s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params={
                    "Bucket": AWS_BUCKET_NAME,
                    "Key": object_key,
                },
                ExpiresIn=expiration,
            )
            return presigned_url
        except (BotoCoreError, ClientError) as err:
            print(f"[AWS S3 Error] Error al generar presigned URL para '{object_key}': {err}")

    # Fallback seguro para desarrollo local
    return f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{object_key}"


# Alias de compatibilidad hacia atrás
upload_pdf_to_s3 = upload_file_to_s3
