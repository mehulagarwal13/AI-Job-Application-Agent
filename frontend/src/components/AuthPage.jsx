import { useState } from "react";
import { BrainCircuit, Mail, Lock, Loader2, LogIn, UserPlus } from "lucide-react";
import { api, auth } from "../api";

export default function AuthPage({ onAuthed }) {
  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!email || !password) return setError("Enter your email and password.");
    setBusy(true);
    setError("");
    try {
      const r = mode === "signup"
        ? await api.signup(email, password)
        : await api.login(email, password);
      auth.setToken(r.access_token);
      onAuthed({ email: r.email });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Brand */}
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-4 rounded-2xl bg-gradient-to-br from-indigo-500 to-fuchsia-500 p-3.5 shadow-lg shadow-indigo-500/30">
            <BrainCircuit size={30} className="text-white" />
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white">
            AI Job <span className="grad-text">Agent</span>
          </h1>
          <p className="mt-1.5 text-sm text-slate-500">
            Your resume, matched against the live job market.
          </p>
        </div>

        <div className="glass animate-fade-up p-7">
          {/* Mode switch */}
          <div className="mb-6 flex gap-1 rounded-xl border border-white/10 bg-slate-900/50 p-1">
            {[["login", "Log in"], ["signup", "Create account"]].map(([m, label]) => (
              <button key={m} type="button"
                onClick={() => { setMode(m); setError(""); }}
                className={`flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition ${
                  mode === m ? "bg-indigo-500/25 text-indigo-200" : "text-slate-500 hover:text-slate-300"}`}>
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            <div className="relative">
              <Mail size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
              <input className="input-dark !pl-10" type="email" placeholder="you@example.com"
                value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </div>
            <div className="relative">
              <Lock size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500" />
              <input className="input-dark !pl-10" type="password"
                placeholder={mode === "signup" ? "Password (min 8 characters)" : "Password"}
                value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "signup" ? "new-password" : "current-password"} />
            </div>

            {error && (
              <p className="animate-fade-up rounded-xl border border-rose-400/30 bg-rose-500/10 px-3.5 py-2.5 text-xs text-rose-300">
                {error}
              </p>
            )}

            <button type="submit" className="btn-primary w-full justify-center" disabled={busy}>
              {busy ? <Loader2 size={16} className="animate-spin" />
                : mode === "signup" ? <UserPlus size={16} /> : <LogIn size={16} />}
              {busy ? "Please wait..." : mode === "signup" ? "Create account" : "Log in"}
            </button>
          </form>

          <p className="mt-5 text-center text-xs text-slate-600">
            {mode === "login" ? "New here? " : "Already have an account? "}
            <button type="button" className="font-semibold text-indigo-400 hover:text-indigo-300"
              onClick={() => { setMode(mode === "login" ? "signup" : "login"); setError(""); }}>
              {mode === "login" ? "Create an account" : "Log in instead"}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
