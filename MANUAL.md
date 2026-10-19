# Manual de Uso Diario: Sistema de Memorias de Gastos

Guía rápida de una página para la operación diaria del sistema en despacho de arquitectura.

---

## 1. Arranque y Detención del Sistema

- **Iniciar el sistema**: Haga doble clic en `Iniciar Memorias.bat`.
  - El sistema verifica el puerto 8000, arranca el servidor local en segundo plano y abre automáticamente la aplicación en su navegador (`http://localhost:8000`).
  - Si el sistema ya estaba en ejecución, simplemente abrirá el navegador sin duplicar procesos.
- **Detener el sistema**: Haga doble clic en `Detener Memorias.bat`.
- **Acceso rápido**: Ejecute `Crear Acceso Directo.bat` una sola vez para colocar el icono en su Escritorio de Windows.
- **Seguridad local**: La aplicación opera **100% en su equipo** y escucha exclusivamente en `127.0.0.1`. No expone ningún dato al exterior ni a la red local.

---

## 2. Primer Uso: Preparar el Sistema

Antes de capturar las obras reales del despacho, puede limpiar las obras de prueba:
1. Ingrese a **Configuración** en el menú superior.
2. Vaya a la sección **Primer Uso: Restablecer a Datos Vacíos**.
3. Haga clic en el botón rojo, escriba exactamente `BORRAR TODO` en el recuadro de confirmación y presione **Restablecer**.
4. El sistema generará **automáticamente un respaldo de seguridad previo** antes de vaciar las pruebas, dejándole la base de datos limpia y lista para sus clientes.

---

## 3. Subida de Facturas y Comprobantes

1. En la barra superior, haga clic en el botón negro **Subir Facturas**.
2. Seleccione la **Obra destino** o cárguelas de forma general.
3. Arrastre los archivos **XML** y sus correspondientes **PDF**:
   - El sistema extrae RFC, emisor, fecha, subtotal, IVA, retenciones y total.
   - Detecta si el gasto fue pagado por **Transferencia** o **Efectivo** (con base en la forma de pago SAT).
4. Verifique los conceptos y presione **Confirmar e Importar**. Los comprobantes se archivan de inmediato en la carpeta local protegida.

---

## 4. Captura de Rayas (Nómina Semanal)

1. En la ficha de la obra, acceda a la pestaña **Rayas**.
2. Presione **Capturar Raya**:
   - Indique el **Número de Semana** y el **Rango de Fechas** (ejemplo: del lunes 13/10 al domingo 19/10).
   - Agregue los trabajadores, indicando tipo (**Destajo** o **Por Día**), cantidad y tarifa.
3. Presione **Guardar Raya**. La semana queda registrada y lista para asociarse a la siguiente memoria.

---

## 5. Generar y Cerrar una Memoria de Gastos

1. En la ficha de la obra, presione **Nueva Memoria**.
2. **Paso 1 (Periodo y Folio)**: Seleccione fecha de inicio y fin. El folio de su factura de honorarios se sugiere automáticamente.
3. **Paso 2 (Revisión de Gastos y Rayas)**: Seleccione las facturas, notas y semanas de raya que correspondan a este corte.
4. **Paso 3 (Anticipos)**: Revise los anticipos recibidos del cliente que se aplicarán en este corte.
5. **Paso 4 (Resumen y Cierre)**:
   - Verifique el total de gastos, los honorarios calculados (con su IVA del 16%) y el saldo a cobrar o a favor.
   - **Guardar Borrador**: Permite pausar y seguir editando después.
   - **Cerrar Memoria**: Congela un **snapshot inmutable** de todos los renglones, fechas y cifras, garantizando que futuras ediciones en el catálogo no alteren esta rendición de cuentas histórica.

---

## 6. Descarga de Reportes (PDF y Excel)

Desde la vista de la memoria (o la lista de memorias cerradas):
- **Descargar PDF**: Genera un documento en hoja tamaño **Carta**, con márgenes exactos, foliado y resumen de transferencias, efectivo, rayas y honorarios listo para firmar o entregar al cliente.
- **Descargar Excel**: Genera un libro con dos hojas (**Cliente** y **Arquitecto**), con **fórmulas vivas** (`SUM`, `ROUND`, `IF`), importes en letra y saldo dinámico.

---

## 7. Respaldos y Restauración de Seguridad

- **Copias Automáticas**:
  - **Diaria**: Se genera automáticamente la primera vez que se abre la app cada día.
  - **Al Cerrar Memoria**: Se genera una copia completa cada vez que cierra una memoria.
  - El sistema conserva siempre las **últimas 10 copias** mediante rotación automática para proteger el espacio en disco.
- **Carpeta de Respaldos (Nube / Disco Externo)**:
  - En **Configuración**, configure una ruta como `D:\Respaldos_Memorias` o su carpeta de **OneDrive / Dropbox**.
- **Restaurar un Respaldo**:
  - En la lista de respaldos de **Configuración**, haga clic en **Restaurar** en la versión deseada.
  - El sistema generará una **copia preventiva previa** y restablecerá la base de datos y comprobantes al instante.
