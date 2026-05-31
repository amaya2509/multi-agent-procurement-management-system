import React, { useState } from 'react';
import InputPanel from './components/InputPanel';
import LogsPanel from './components/LogsPanel';
import OutputPanel from './components/OutputPanel';
import StateViewer from './components/StateViewer';
import HistoryModal from './components/HistoryModal';
import { streamMas } from './services/api';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [logs, setLogs] = useState(null);
  const [result, setResult] = useState(null);
  const [rawState, setRawState] = useState(null);
  const [error, setError] = useState(null);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);

  const handleRunWorkflow = async (query) => {
    setIsLoading(true);
    setError(null);
    setLogs([]);
    setResult(null);
    setRawState({ logs: [] });
    
    let currentState = { logs: [] };

    const onUpdate = (partialUpdate) => {
      const nodeName = Object.keys(partialUpdate)[0];
      if (!nodeName) return;
      
      const updateData = partialUpdate[nodeName];
      
      // Update running state
      currentState = { ...currentState, ...updateData };
      if (updateData.logs) {
        currentState.logs = updateData.logs;
        setLogs([...currentState.logs]);
      }
      setRawState({ ...currentState });

      if (updateData.error) {
        setError(updateData.error);
      }

      // Progressively update partial results
      if (updateData.approval_status) setResult(updateData.approval_status);
      else if (updateData.purchase_order && !currentState.approval_status) setResult(updateData.purchase_order);
      else if (updateData.selected_supplier && !currentState.purchase_order) setResult(updateData.selected_supplier);
      else if (updateData.parsed_request && !currentState.selected_supplier) setResult(updateData.parsed_request);
    };

    const onComplete = () => {
      setIsLoading(false);
    };

    const onError = (err) => {
      setError(err.message);
      setIsLoading(false);
    };

    streamMas(query, onUpdate, onComplete, onError);
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col gap-8">
      <header className="text-center mb-4 relative">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
          Agentic Procurement
        </h1>
        <p className="text-slate-400 text-lg">Interactive LangGraph Orchestration</p>
        <button 
          onClick={() => setIsHistoryOpen(true)}
          className="absolute right-0 top-2 px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-300 text-sm font-semibold hover:bg-slate-700 transition-colors flex items-center gap-2"
        >
          🕒 View System Logs
        </button>
      </header>

      {error && (
        <div className="glass-panel border-l-4 border-l-red-500">
          <h3 className="text-red-500 font-semibold mb-2">Workflow Error</h3>
          <p className="text-slate-200">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="flex flex-col gap-6">
          <InputPanel onSubmit={handleRunWorkflow} isLoading={isLoading} />
          <OutputPanel result={result} poData={rawState?.purchase_order} inProgress={isLoading} />
        </div>
        <div>
          <LogsPanel logs={logs} />
        </div>
      </div>

      <StateViewer state={rawState} />
      
      <HistoryModal isOpen={isHistoryOpen} onClose={() => setIsHistoryOpen(false)} />
    </div>
  );
}

export default App;
