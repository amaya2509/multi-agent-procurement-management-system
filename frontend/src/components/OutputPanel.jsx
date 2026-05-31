import React from 'react';
import { generatePurchaseOrderPDF } from '../utils/pdfGenerator';

export default function OutputPanel({ result, poData, inProgress }) {
  if (inProgress) {
    return (
      <div className="glass-panel flex flex-col">
        <h2 className="panel-title">✨ Final Result</h2>
        <div className="flex flex-col items-center gap-4 text-center text-slate-400 italic p-8">
          <div className="w-12 h-12 rounded-full bg-blue-500 animate-[pulse_1.5s_infinite]"></div>
          <p>Agents are processing your request...</p>
        </div>
        <style dangerouslySetInnerHTML={{__html: `
          @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 15px rgba(59, 130, 246, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
          }
        `}} />
      </div>
    );
  }

  if (!result) {
    return (
      <div className="glass-panel flex flex-col">
        <h2 className="panel-title">✨ Final Result</h2>
        <p className="text-center text-slate-400 italic p-8">Result will appear here when complete.</p>
      </div>
    );
  }

  const isPO = result.po_number;
  const isApproval = result.formal_notice;

  return (
    <div className="glass-panel flex flex-col">
      <h2 className="panel-title">✨ Final Result</h2>
      <div className="animate-[slideUp_0.4s_ease-out_forwards] opacity-0 translate-y-5" style={{animationFillMode: 'forwards'}}>
        {isApproval ? (
          <div className={`p-6 rounded-xl border border-glass-border bg-slate-900/50 border-l-4 ${result.approved ? 'border-l-emerald-500' : 'border-l-red-500'}`}>
            <div className="flex justify-between items-start mb-2">
              <h3 className={`text-xl ${result.approved ? 'text-emerald-500' : 'text-red-500'}`}>
                {result.approved ? '✅ APPROVED' : '❌ REJECTED'}
              </h3>
              {result.approved && poData && (
                <button 
                  onClick={() => generatePurchaseOrderPDF(poData)}
                  className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold py-1.5 px-4 rounded-lg flex items-center gap-2 transition-colors cursor-pointer"
                >
                  ⬇️ Download PDF
                </button>
              )}
            </div>
            <p className="text-slate-400 mb-4">{result.reason}</p>
            {result.formal_notice && (
              <div className="bg-black/20 p-4 rounded-lg mb-4">
                <h4 className="mb-1 text-slate-300">Formal Notice</h4>
                <p className="text-slate-100 italic">{result.formal_notice}</p>
              </div>
            )}
            <div className="flex gap-6 mb-4 text-sm">
              <span><strong>PO Total:</strong> ${result.po_total?.toFixed(2)}</span>
              <span><strong>Limit:</strong> ${result.department_budget_limit?.toFixed(2)}</span>
            </div>
            {result.action_required && (
              <div className="bg-amber-500/10 text-amber-400 p-3 rounded-lg text-sm">
                <strong>Action: </strong> {result.action_required}
              </div>
            )}
          </div>
        ) : isPO ? (
          <div className="p-6 rounded-xl bg-slate-900/50 border border-glass-border border-l-4 border-l-blue-400">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-blue-400 text-xl font-semibold">📄 PO: {result.po_number}</h3>
              <button 
                onClick={() => generatePurchaseOrderPDF(result)}
                className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold py-1.5 px-4 rounded-lg flex items-center gap-2 transition-colors cursor-pointer"
              >
                ⬇️ Download PDF
              </button>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><strong>Supplier:</strong> {result.supplier_name}</div>
              <div><strong>Delivery:</strong> {result.expected_delivery_date}</div>
              <div><strong>Subtotal:</strong> ${result.subtotal?.toFixed(2)}</div>
              <div className="text-emerald-400 text-lg"><strong>Total:</strong> ${result.total?.toFixed(2)} {result.currency}</div>
            </div>
          </div>
        ) : (
          <div className="bg-slate-900/80 p-4 rounded-lg text-purple-400 overflow-x-auto">
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </div>
        )}
      </div>
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slideUp {
          to { opacity: 1; transform: translateY(0); }
        }
      `}} />
    </div>
  );
}
