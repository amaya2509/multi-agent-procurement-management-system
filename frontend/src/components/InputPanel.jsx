import React, { useState } from 'react';

export default function InputPanel({ onSubmit, isLoading }) {
  const [query, setQuery] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    onSubmit(query);
  };

  return (
    <div className="glass-panel">
      <h2 className="panel-title">🎯 Procurement Request</h2>
      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <textarea
            placeholder="e.g. Need 10 laptops for IT with budget 15000..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            disabled={isLoading}
            rows={4}
            className="w-full p-4 rounded-xl bg-slate-900/70 border border-glass-border text-slate-50 font-sans text-base resize-y min-h-[100px] outline-none transition-colors duration-300 focus:border-blue-500 disabled:opacity-75"
          />
        </div>
        <button 
          type="submit" 
          disabled={isLoading || !query.trim()}
          className="w-full p-3.5 flex justify-center items-center rounded-xl bg-blue-500 text-white font-semibold transition-all duration-300 hover:bg-blue-600 hover:-translate-y-[1px] disabled:bg-slate-600 disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:translate-y-0"
        >
          {isLoading ? (
            <span className="w-6 h-6 border-4 border-white/30 border-t-white rounded-full animate-spin"></span>
          ) : (
            "Run Workflow"
          )}
        </button>
      </form>
    </div>
  );
}
