import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppLayout } from '@/components/layout/AppLayout';
import { ObrasPage } from '@/pages/ObrasPage';
import { ObraDetailPage } from '@/pages/ObraDetailPage';
import { CargaFacturasPage } from '@/pages/CargaFacturasPage';
import { TrabajadoresPage } from '@/pages/TrabajadoresPage';
import { ProveedoresPage } from '@/pages/ProveedoresPage';
import { ConfiguracionPage } from '@/pages/ConfiguracionPage';
import { AsistenteMemoriaPage } from '@/pages/AsistenteMemoriaPage';
import { MemoriaImprimirPage } from '@/pages/MemoriaImprimirPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 seconds
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

// Placeholder component for stage D
function ComingSoonPage({ title, stage }: { title: string; stage: string }) {
  return (
    <div className="p-8 max-w-2xl mx-auto text-center">
      <div className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-800 border border-amber-200 mb-4">
        Próxima Etapa ({stage})
      </div>
      <h1 className="text-2xl font-serif font-bold text-stone-900 mb-2">{title}</h1>
      <p className="text-sm text-stone-600 mb-6">
        Esta sección se integrará en la etapa programada correspondiente ({stage}).
      </p>
      <a
        href="/"
        className="inline-flex items-center text-sm font-medium text-stone-700 hover:text-stone-900 underline underline-offset-4"
      >
        ← Volver al panel de obras
      </a>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppLayout />}>
            <Route path="/" element={<ObrasPage />} />
            <Route path="/obras/:id" element={<ObraDetailPage />} />

            {/* Stage B: Carga y revisión de facturas CFDI */}
            <Route path="/obras/:id/facturas/nueva" element={<CargaFacturasPage />} />

            {/* Stage C: Catálogos y configuración */}
            <Route path="/trabajadores" element={<TrabajadoresPage />} />
            <Route path="/proveedores" element={<ProveedoresPage />} />
            <Route path="/configuracion" element={<ConfiguracionPage />} />

            {/* Stage D: Asistente de Memorias (Entrega D1: Pasos 1 y 2) */}
            <Route path="/obras/:id/memorias/nueva" element={<AsistenteMemoriaPage />} />
            <Route path="/obras/:id/memorias/asistente" element={<AsistenteMemoriaPage />} />
            <Route path="/obras/:id/memorias/:memoriaId" element={<AsistenteMemoriaPage />} />
          </Route>

          {/* Standalone Carta print view (no header/sidebar) */}
          <Route path="/memorias/:id/imprimir" element={<MemoriaImprimirPage />} />

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
