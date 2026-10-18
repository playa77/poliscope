import React from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import './style.css';
declare global {
  interface Window { poliscope: { bootstrapStatus(): Promise<{state: 'starting' | 'ready' | 'failed'; detail: string}> } }
}
function App() {
  const status = useQuery({ queryKey: ['bootstrap'], queryFn: () => window.poliscope.bootstrapStatus(),
    refetchInterval: (query) => query.state.data?.state === 'starting' ? 250 : false, retry: false });
  return <main><p className="eyebrow">Poliscope</p><h1>A society, open to possibility.</h1>
    <p>The desktop foundation is in place. Civilization design and simulation are coming in later work packages.</p>
    <p role="status">{status.isError ? 'Local engine unavailable' : status.data?.detail ?? 'Starting local engine'}</p>
  </main>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider></React.StrictMode>);
