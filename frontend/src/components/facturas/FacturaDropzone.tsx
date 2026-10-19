import React, { useRef, useState } from 'react'
import { UploadCloud, FileText, CheckCircle2, AlertTriangle, X } from 'lucide-react'
import { Button } from '@/components/ui/Button'

interface ArchivoConPareja {
  file: File
  tipo: 'xml' | 'pdf'
  nombre: string
  tienePareja: boolean
  parejaNombre?: string
}

interface DropzoneProps {
  onFilesSelected: (files: File[]) => void
  isUploading: boolean
}

export function FacturaDropzone({ onFilesSelected, isUploading }: DropzoneProps) {
  const [dragActive, setDragActive] = useState(false)
  const [archivosEnCola, setArchivosEnCola] = useState<ArchivoConPareja[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)

  const procesarArchivos = (fileList: FileList | File[]) => {
    const seleccionados = Array.from(fileList).filter((f) => {
      const lower = f.name.toLowerCase()
      return lower.endsWith('.xml') || lower.endsWith('.pdf')
    })

    if (seleccionados.length === 0) return

    // Emparejamiento local para retroalimentación visual inmediata antes de subir
    const xmls = seleccionados.filter((f) => f.name.toLowerCase().endsWith('.xml'))
    const pdfs = seleccionados.filter((f) => f.name.toLowerCase().endsWith('.pdf'))

    // Mapear por nombre base (stem)
    const pdfPorStem = new Map<string, File>()
    pdfs.forEach((p) => {
      const stem = p.name.replace(/\.[^/.]+$/, '').toLowerCase().trim()
      pdfPorStem.set(stem, p)
    })

    const emparejados: ArchivoConPareja[] = []
    const pdfsAsociados = new Set<string>()

    xmls.forEach((x) => {
      const stem = x.name.replace(/\.[^/.]+$/, '').toLowerCase().trim()
      const match = pdfPorStem.get(stem)
      if (match) {
        pdfsAsociados.add(match.name)
        emparejados.push({
          file: x,
          tipo: 'xml',
          nombre: x.name,
          tienePareja: true,
          parejaNombre: match.name,
        })
      } else {
        emparejados.push({
          file: x,
          tipo: 'xml',
          nombre: x.name,
          tienePareja: false,
        })
      }
    })

    pdfs.forEach((p) => {
      if (pdfsAsociados.has(p.name)) {
        emparejados.push({
          file: p,
          tipo: 'pdf',
          nombre: p.name,
          tienePareja: true,
        })
      } else {
        emparejados.push({
          file: p,
          tipo: 'pdf',
          nombre: p.name,
          tienePareja: false,
        })
      }
    })

    setArchivosEnCola(emparejados)
  }

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      procesarArchivos(e.dataTransfer.files)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      procesarArchivos(e.target.files)
    }
  }

  const handleSubirLote = () => {
    const files = archivosEnCola.map((a) => a.file)
    onFilesSelected(files)
  }

  const limpiarCola = () => {
    setArchivosEnCola([])
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const totalXmls = archivosEnCola.filter((a) => a.tipo === 'xml').length
  const totalPdfs = archivosEnCola.filter((a) => a.tipo === 'pdf').length
  const xmlsConPdf = archivosEnCola.filter((a) => a.tipo === 'xml' && a.tienePareja).length
  const xmlsSolos = totalXmls - xmlsConPdf
  const pdfsSolos = archivosEnCola.filter((a) => a.tipo === 'pdf' && !a.tienePareja).length

  return (
    <div className="space-y-4">
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => !isUploading && fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer ${
          dragActive
            ? 'border-zinc-900 bg-zinc-50/80 scale-[0.99]'
            : 'border-zinc-300 hover:border-zinc-400 bg-white'
        } ${isUploading ? 'opacity-50 pointer-events-none' : ''}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".xml,.pdf"
          onChange={handleFileChange}
          className="hidden"
          disabled={isUploading}
        />

        <div className="flex flex-col items-center justify-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-zinc-100 flex items-center justify-center text-zinc-600">
            <UploadCloud className="w-6 h-6" />
          </div>
          <div>
            <p className="text-sm font-semibold text-zinc-900">
              Arrastra aquí tus archivos XML y PDF o haz clic para examinar
            </p>
            <p className="text-xs text-zinc-500 mt-1">
              Puedes subir múltiples facturas simultáneamente. El XML es obligatorio; el PDF es opcional pero recomendado.
            </p>
          </div>
          <div className="flex items-center space-x-2 text-[11px] text-zinc-400 font-mono">
            <span className="px-2 py-0.5 bg-zinc-100 rounded text-zinc-600 font-medium">CFDI XML</span>
            <span>+</span>
            <span className="px-2 py-0.5 bg-zinc-100 rounded text-zinc-600 font-medium">Representación PDF</span>
          </div>
        </div>
      </div>

      {archivosEnCola.length > 0 && (
        <div className="bg-white border border-zinc-200 rounded-lg p-4 space-y-4 shadow-xs">
          <div className="flex items-center justify-between pb-3 border-b border-zinc-100">
            <div>
              <h3 className="text-sm font-semibold text-zinc-900">Archivos seleccionados ({archivosEnCola.length})</h3>
              <p className="text-xs text-zinc-500 mt-0.5">
                {totalXmls} {totalXmls === 1 ? 'XML' : 'XMLs'} &bull; {totalPdfs} {totalPdfs === 1 ? 'PDF' : 'PDFs'}
              </p>
            </div>
            <div className="flex items-center space-x-2">
              <Button variant="ghost" size="sm" onClick={limpiarCola} disabled={isUploading}>
                <X className="w-3.5 h-3.5 mr-1" />
                Limpiar
              </Button>
              <Button size="sm" onClick={handleSubirLote} disabled={isUploading || totalXmls === 0}>
                {isUploading ? 'Procesando archivos...' : `Procesar ${totalXmls} ${totalXmls === 1 ? 'factura' : 'facturas'}`}
              </Button>
            </div>
          </div>

          {/* Resumen del emparejamiento */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
            <div className="p-2.5 rounded-md bg-emerald-50/70 border border-emerald-100 flex items-start space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold text-emerald-900">{xmlsConPdf} parejas completas</p>
                <p className="text-[11px] text-emerald-700">XML y PDF correspondientes</p>
              </div>
            </div>

            <div className="p-2.5 rounded-md bg-zinc-50 border border-zinc-200 flex items-start space-x-2">
              <FileText className="w-4 h-4 text-zinc-500 mt-0.5 shrink-0" />
              <div>
                <p className="font-semibold text-zinc-800">{xmlsSolos} XML sin PDF</p>
                <p className="text-[11px] text-zinc-500">Se procesarán normalmente</p>
              </div>
            </div>

            <div
              className={`p-2.5 rounded-md border flex items-start space-x-2 ${
                pdfsSolos > 0
                  ? 'bg-amber-50/70 border-amber-200 text-amber-900'
                  : 'bg-zinc-50 border-zinc-200 text-zinc-600'
              }`}
            >
              <AlertTriangle
                className={`w-4 h-4 mt-0.5 shrink-0 ${pdfsSolos > 0 ? 'text-amber-600' : 'text-zinc-400'}`}
              />
              <div>
                <p className="font-semibold">{pdfsSolos} PDF sin XML</p>
                <p className="text-[11px] opacity-80">
                  {pdfsSolos > 0 ? 'No se crearán facturas sin su XML' : 'Todo emparejado'}
                </p>
              </div>
            </div>
          </div>

          {totalXmls === 0 && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md text-xs text-red-800 flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-red-600 shrink-0" />
              <span>Debes incluir al menos un archivo XML para poder registrar gastos de facturas.</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
