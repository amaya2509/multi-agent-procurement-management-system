import React, { useEffect, useState, useRef } from 'react';
import { getExecutionHistory } from '../services/api';

export default function HistoryModal({ isOpen, onClose }) {
  const [logsText, setLogsText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const endOfLogsRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      setIsLoading(true);
      getExecutionHistory()
        .then(data => {
          setLogsText(data.content);
        })
        .catch(err => {
          setLogsText("Error fetching logs: " + err.message);
        })
        .finally(() => {
          setIsLoading(false);
        });
    }
  }, [isOpen]);

  useEffect(() => {
    // Auto scroll to bottom when logs load
    if (endOfLogsRef.current) {
      endOfLogsRef.current.scrollIntoView();
    }
  }, [logsText, isLoading]);

  if (!isOpen) return null;

  // Simple formatter to colorize terminal lines based on keyword
  const formatLine = (line, index) => {
    let className = "text-slate-300";
    if (line.includes("ERROR") || line.includes("Traceback") || line.includes("ConnectionError")) {
      className = "text-red-400 font-semibold";
    } else if (line.includes("WARNING")) {
      className = "text-amber-400";
    } else if (line.includes("INFO")) {
      className = "text-blue-300";
    }

    // Highlight [Agent] definitions
    let formattedLine = line;
    const agentRegex = /(\[.*?Agent\])/g;
    if (agentRegex.test(line)) {
      formattedLine = line.split(agentRegex).map((part, i) => {
        if (part.match(agentRegex)) {
          return <span key={i} className="text-purple-400 font-bold">{part}</span>;
        }
        return part;
      });
    }

    return (
      <div key={index} className={`${className} py-0.5 border-b border-white/5 break-all whitespace-pre-wrap`}>
        {formattedLine}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-8 bg-black/80 backdrop-blur-md animate-[fadeIn_0.2s_ease-out]">
      <div className="w-full max-w-5xl h-full max-h-[85vh] bg-[#0c1015] border border-slate-700/50 rounded-lg flex flex-col shadow-2xl shadow-indigo-900/20 overflow-hidden animate-[slideUp_0.3s_ease-out]">
        
        {/* Terminal Header */}
        <div className="flex justify-between items-center bg-[#161b22] px-4 py-3 border-b border-slate-700/50">
          <div className="flex items-center gap-2">
            <span className="text-slate-400 font-mono text-sm">~/procurement/logs/execution.log</span>
          </div>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-white bg-transparent border border-slate-700 rounded px-3 py-1 text-sm font-mono transition-colors hover:bg-slate-800"
          >
            Exit Component [Esc]
          </button>
        </div>

        {/* Terminal Screen */}
        <div className="flex-1 bg-black p-4 overflow-y-auto font-mono text-[13px] leading-relaxed">
          {isLoading ? (
            <div className="text-blue-400 animate-pulse">Running read: execution.log...</div>
          ) : (
            <div className="flex flex-col">
              {logsText.split('\n').map((line, index) => formatLine(line, index))}
              <div ref={endOfLogsRef} className="h-4" />
            </div>
          )}
        </div>
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
      `}} />
    </div>
  );
}
