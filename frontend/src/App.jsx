import { useEffect, useState, useCallback } from "react";
import { BrainCircuit, CheckCircle2, AlertCircle, Info, X, LogOut, Loader2 } from "lucide-react";
import { api, auth, setUnauthorizedHandler } from "./api";
import AuthPage from "./components/AuthPage";
import UploadPanel from "./components/UploadPanel";
import JobsPanel from "./components/JobsPanel";
import MatchesPanel from "./components/MatchesPanel";

let toastId = 0;

export default function App() {
  const [user, setUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [resume, setResume] = useState(null);
  const [health, setHealth] = useState(null);
  const [toasts, setToasts] = useState([]);

  const toast = useCallback((message, type = "info") => {
    const id = ++toastId;
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);

  const logout = useCallback(() => {
    auth.clear();
    setUser(null);
    setResume(null);
  }, []);

  // Restore session: validate stored token, then pull the user's latest resume
  useEffect(() => {
    setUnauthorizedHandler(() => { setUser(null); setResume(null); });
    if (!auth.getToken()) {
      setAuthChecking(false);
      return;
    }
    api.me()
      .then((me) => {
        setUser({ email: me.email });
        return api.listResumes();
      })
      .then((r) => {
        const latest = r?.resumes?.[0];
        if (latest) setResume({ id: latest.resume_id, filename: latest.original_filename });
      })
      .catch(() => auth.clear())
      .finally(() => setAuthChecking(false));
  }, []);

  useEffect(() => {
    const check = () => api.health().then(setHealth).catch(() => setHealth({ status: "down" }));
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  async function handleAuthed(u) {
    setUser(u);
    try {
      const r = await api.listResumes();
      const latest = r?.resumes?.[0];
      if (latest) {
        setResume({ id: latest.resume_id, filename: latest.original_filename });
        toast(`Welcome back — restored "${latest.original_filename}".`, "info");
      }
    } catch { /* fresh account, nothing to restore */ }
  }

  if (authChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 size={28} className="animate-spin text-indigo-400" />
      </div>
    );
  }

  if (!user) return <AuthPage onAuthed={handleAuthed} />;

  const healthColor =
    health?.status === "ok" ? "bg-emerald-400" : health?.status === "degraded" ? "bg-amber-400" : "bg-rose-500";

  return (
    <div className="mx-auto max-w-7xl px-4 pb-16 sm:px-6">
      {/* Header */}
      <header className="flex items-center justify-between py-6">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 p-2.5 shadow-lg shadow-indigo-500/30">
            <BrainCircuit size={24} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-extrabold tracking-tight text-white">
              AI Job <span className="grad-text">Agent</span>
            </h1>
            <p className="text-xs text-slate-500">Resume intelligence · live job scraping · AI matching</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3.5 py-1.5 text-xs sm:flex">
            <span className={`h-2 w-2 rounded-full ${healthColor} ${health?.status === "ok" ? "animate-pulse" : ""}`} />
            <span className="text-slate-400">
              {health?.status === "ok" ? "Online" : health?.status === "degraded" ? "DB unreachable" : "Offline"}
            </span>
          </div>
          <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] py-1.5 pl-3.5 pr-1.5 text-xs">
            <span className="max-w-[160px] truncate text-slate-300">{user.email}</span>
            <button onClick={logout} title="Log out"
              className="rounded-full p-1.5 text-slate-500 transition hover:bg-white/10 hover:text-white">
              <LogOut size={14} />
            </button>
          </div>
        </div>
      </header>

      {/* Layout: left rail (resume + jobs) / right (matches) */}
      <main className="grid gap-5 lg:grid-cols-[400px_1fr]">
        <div className="space-y-5">
          <UploadPanel resume={resume} setResume={setResume} toast={toast} />
          <JobsPanel toast={toast} />
        </div>
        <MatchesPanel resume={resume} toast={toast} />
      </main>

      {/* Toasts */}
      <div className="fixed bottom-5 right-5 z-[60] flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id}
            className={`glass animate-fade-up flex items-start gap-2.5 p-3.5 text-sm ${
              t.type === "success" ? "!border-emerald-400/30" :
              t.type === "error" ? "!border-rose-400/30" : "!border-indigo-400/30"}`}>
            {t.type === "success" && <CheckCircle2 size={17} className="mt-0.5 shrink-0 text-emerald-400" />}
            {t.type === "error" && <AlertCircle size={17} className="mt-0.5 shrink-0 text-rose-400" />}
            {t.type === "info" && <Info size={17} className="mt-0.5 shrink-0 text-indigo-400" />}
            <span className="flex-1 leading-snug text-slate-300">{t.message}</span>
            <button onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}
              className="text-slate-600 transition hover:text-slate-300">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
