import { useState } from "react";
import { MapPin, Building2, ExternalLink, Bookmark, XCircle, ChevronDown } from "lucide-react";
import ScoreRing from "./ScoreRing";

function Bar({ label, value, color }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-[11px]">
        <span className="text-slate-500">{label}</span>
        <span className="font-semibold text-slate-300">{Math.round(value * 100)}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.07]">
        <div className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.round(value * 100)}%`, transition: "width 0.8s cubic-bezier(0.22,1,0.36,1)" }} />
      </div>
    </div>
  );
}

export default function MatchCard({ match, onStatus }) {
  const [open, setOpen] = useState(false);
  const isSaved = match.status === "saved";
  const isDismissed = match.status === "dismissed";

  return (
    <div className={`glass glass-hover p-5 ${isDismissed ? "opacity-50" : ""}`}>
      <div className="flex items-start gap-4">
        <ScoreRing value={match.blended_score} label="match" />

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h3 className="truncate font-bold text-white">{match.title}</h3>
              <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-500">
                {match.company && <span className="flex items-center gap-1"><Building2 size={12} />{match.company}</span>}
                {match.location && <span className="flex items-center gap-1"><MapPin size={12} />{match.location}</span>}
              </p>
            </div>
            {isSaved && <span className="chip shrink-0 bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-400/25">saved</span>}
            {isDismissed && <span className="chip shrink-0 bg-rose-500/15 text-rose-300 ring-1 ring-rose-400/25">dismissed</span>}
          </div>

          <div className="mt-3 grid grid-cols-3 gap-3">
            <Bar label="Semantic" value={match.vector_similarity} color="bg-gradient-to-r from-indigo-400 to-indigo-300" />
            <Bar label="Skills" value={match.skill_overlap_ratio} color="bg-gradient-to-r from-fuchsia-400 to-pink-300" />
            <Bar label="ATS" value={match.ats_score} color="bg-gradient-to-r from-sky-400 to-cyan-300" />
          </div>
        </div>
      </div>

      {match.explanation && (
        <p className="mt-3 rounded-xl border border-white/[0.06] bg-slate-950/40 px-3 py-2 text-xs leading-relaxed text-slate-400">
          {match.explanation}
        </p>
      )}

      <button onClick={() => setOpen(!open)}
        className="mt-3 flex w-full items-center justify-center gap-1 text-xs text-slate-500 transition hover:text-slate-300">
        {match.matched_skills.length} matched · {match.missing_skills.length} missing skills
        <ChevronDown size={14} className={`transition-transform duration-300 ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="mt-3 animate-fade-up space-y-2">
          <div className="flex flex-wrap gap-1.5">
            {match.matched_skills.map((s) => (
              <span key={s} className="chip bg-emerald-500/12 text-emerald-300 ring-1 ring-emerald-400/20">{s}</span>
            ))}
            {match.missing_skills.map((s) => (
              <span key={s} className="chip bg-rose-500/10 text-rose-300/90 ring-1 ring-rose-400/20">{s}</span>
            ))}
          </div>
          {match.ats_missing_keywords.length > 0 && (
            <p className="text-[11px] text-slate-500">
              ATS keywords to add: {match.ats_missing_keywords.slice(0, 8).join(", ")}
            </p>
          )}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-3">
        <div className="flex-1" />
        {!isSaved && (
          <button className="btn-ghost !px-3 !py-1.5 text-xs !text-emerald-300 hover:!border-emerald-400/40"
            onClick={() => onStatus(match, "saved")}>
            <Bookmark size={14} /> Save
          </button>
        )}
        {!isDismissed && (
          <button className="btn-ghost !px-3 !py-1.5 text-xs !text-rose-300/80 hover:!border-rose-400/40"
            onClick={() => onStatus(match, "dismissed")}>
            <XCircle size={14} /> Dismiss
          </button>
        )}
        {match.apply_url && (
          <a href={match.apply_url} target="_blank" rel="noreferrer" className="btn-primary !px-3 !py-1.5 text-xs">
            Apply <ExternalLink size={13} />
          </a>
        )}
      </div>
    </div>
  );
}
