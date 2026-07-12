import { X } from "lucide-react";

export default function Modal({ title, subtitle, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={onClose} />
      <div className="glass relative z-10 flex max-h-[85vh] w-full max-w-2xl animate-fade-up flex-col overflow-hidden">
        <div className="flex items-start justify-between border-b border-white/10 px-6 py-4">
          <div>
            <h3 className="text-lg font-bold text-white">{title}</h3>
            {subtitle && <p className="mt-0.5 text-sm text-slate-400">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-slate-400 transition hover:bg-white/10 hover:text-white">
            <X size={18} />
          </button>
        </div>
        <div className="overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  );
}
