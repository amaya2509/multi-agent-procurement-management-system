import React, { useState } from 'react';
import InputPanel from './components/InputPanel';
import LogsPanel from './components/LogsPanel';
import OutputPanel from './components/OutputPanel';
import StateViewer from './components/StateViewer';
import { runMas } from './services/api';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [logs, setLogs] = useState(null);
  const [result, setResult] = useState(null);
  const [rawState, setRawState] = useState(null);
  const [error, setError] = useState(null);

  const handleRunWorkflow = async (query) => {
    setIsLoading(true);
    setError(null);
    setLogs([]);
    setResult(null);
    setRawState(null);

    try {
      const data = await runMas(query);
      setLogs(data.logs);
      setResult(data.result);
      setRawState(data.state);
      
      if (data.state && data.state.error) {
        setError(data.state.error);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col gap-8">
      <header className="text-center mb-4">
        <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent mb-2">
          Agentic Procurement
        </h1>
        <p className="text-slate-400 text-lg">Interactive LangGraph Orchestration</p>
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
          <OutputPanel result={result} inProgress={isLoading} />
        </div>
        <div>
          <LogsPanel logs={logs} />
        </div>
      </div>

      <StateViewer state={rawState} />
    </div>
  );
}

export default App;
