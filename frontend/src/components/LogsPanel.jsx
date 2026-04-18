import React from 'react';

const AGENT_ICONS = {
  CoordinatorAgent: '🎯',
  RequestAnalyzerAgent: '🔍',
  SupplierIntelligenceAgent: '🏭',
  ProcurementGeneratorAgent: '📄',
  ApprovalAgent: '✅',
};

export default function LogsPanel({ logs }) {
  if (!logs || logs.length === 0) {
    return (
      <div className="glass-panel flex flex-col max-h-[600px]">
        <h2 className="panel-title">📋 Execution Logs</h2>
        <p className="text-slate-400 italic text-center p-8">No logs yet. Run a workflow to see agent activity...</p>
      </div>
    );
  }

  return (
    <div className="glass-panel flex flex-col max-h-[600px]">
      <h2 className="panel-title">📋 Execution Logs</h2>
      <div className="overflow-y-auto flex flex-col gap-4 pr-2">
        {logs.map((log, index) => {
          const icon = AGENT_ICONS[log.agent] || '🤖';
          return (
            <div 
              key={index} 
              className="bg-slate-800/40 border border-white/5 rounded-lg p-4 animate-[slideIn_0.3s_ease-out_forwards]" 
              style={{ animationDelay: `${index * 0.1}s`, opacity: 0, transform: 'translateY(10px)' }}
            >
              <div className="flex justify-between items-center mb-2 border-b border-white/5 pb-2">
                <span className="font-semibold text-purple-400">{icon} {log.agent}</span>
                <span className="text-xs text-slate-400">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div className="text-[0.95rem] mb-2">
                <span className="font-semibold text-blue-400">Step:</span> {log.step || "N/A"}
              </div>
              {log.output && Object.keys(log.output).length > 0 && (
                <div className="bg-slate-900/80 p-3 rounded-md text-[0.85rem] text-emerald-400 overflow-x-auto m-0">
                  <pre>{JSON.stringify(log.output, null, 2)}</pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slideIn {
          to { opacity: 1; transform: translateY(0); }
        }
      `}} />
    </div>
  );
}
