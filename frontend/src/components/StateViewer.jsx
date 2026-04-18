import React, { useState } from 'react';

export default function StateViewer({ state }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!state) return null;

  return (
    <div className="glass-panel mt-4">
      <div className="flex justify-between items-center cursor-pointer py-2" onClick={() => setIsOpen(!isOpen)}>
        <h2 className="text-xl font-semibold m-0 border-none p-0 flex items-center gap-2">
          🗃️ Raw State Viewer (Debug)
        </h2>
        <button className="bg-transparent border border-glass-border text-slate-50 py-1 px-3 rounded-md cursor-pointer text-sm hover:bg-white/10 transition-colors">
          {isOpen ? '▲ Hide' : '▼ Show'}
        </button>
      </div>
      
      {isOpen && (
        <div className="mt-4 animate-[slideDown_0.3s_ease-out]">
          <pre className="bg-slate-900/80 p-4 rounded-lg text-slate-300 text-sm overflow-x-auto max-h-[400px] overflow-y-auto">
            {JSON.stringify(state, null, 2)}
          </pre>
        </div>
      )}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slideDown {
          from { opacity: 0; transform: translateY(-10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}} />
    </div>
  );
}
