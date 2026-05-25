"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  TrendingUp,
  Bot,
  Sparkles,
  Search,
  Cpu,
  Layers,
  ShieldCheck,
  Check,
  ChevronRight,
  Send,
  HelpCircle,
  BarChart as BarChartIcon,
  MessageSquare,
  TrendingDown,
  Sun,
  Moon,
  ArrowRight,
  Database,
  RefreshCw,
  Clock,
  Compass,
  FileUp,
  User,
  ArrowLeft,
  Settings,
  Scale
} from "lucide-react";
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Tooltip,
  Legend,
  XAxis,
  YAxis,
  BarChart,
  Bar,
  CartesianGrid,
} from "recharts";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { apiUrl } from "@/lib/api";
import { formatFilingSectionText } from "@/lib/filingTextFormat";

function hasNarrativeText(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function AnalysisNarrativeCard({
  title,
  children,
  accent = "green",
}: {
  title: string;
  children: React.ReactNode;
  accent?: "green" | "amber" | "rose";
}) {
  const borderAccent =
    accent === "amber"
      ? "border-amber-400/20"
      : accent === "rose"
        ? "border-rose-400/20"
        : "border-[#90A955]/20";
  const labelAccent =
    accent === "amber"
      ? "text-amber-500 dark:text-amber-300"
      : accent === "rose"
        ? "text-rose-500 dark:text-rose-300"
        : "text-[#90A955]";

  return (
    <div
      className={`bg-white dark:bg-slate-900 rounded-lg border ${borderAccent} p-5 shadow-sm`}
    >
      <span
        className={`text-xs font-bold uppercase block tracking-widest mb-3 font-mono ${labelAccent}`}
      >
        {title}
      </span>
      {children}
    </div>
  );
}

function MarkdownNarrative({ content }: { content: string }) {
  return (
    <div className="prose-custom text-sm text-slate-700 dark:text-slate-300 font-light leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

function FilingSectionNarrative({
  text,
  sectionId,
  searchQuery,
  activeEvidenceText,
  activeHighlightId,
}: {
  text: string;
  sectionId: string;
  searchQuery: string;
  activeEvidenceText: string | null;
  activeHighlightId: string | null;
}) {
  const formatted = formatFilingSectionText(text);

  const wrapHighlight = (content: string, pattern: RegExp, className: string, id?: string) => {
    const parts = content.split(pattern);
    if (parts.length <= 1) return null;
    return (
      <>
        {parts.map((part, index) =>
          pattern.test(part) ? (
            <mark key={index} id={id} className={className}>
              {part}
            </mark>
          ) : (
            <span key={index}>{part}</span>
          )
        )}
      </>
    );
  };

  if (activeEvidenceText && SECTION_ID_PATTERNS.risk_factors.test(sectionId)) {
    const escaped = activeEvidenceText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    try {
      const regex = new RegExp(`(${escaped})`, "i");
      if (regex.test(formatted) && !formatted.includes("| --- |")) {
        const highlighted = wrapHighlight(
          formatted,
          regex,
          "highlight-risk highlight-active rounded px-1 text-white font-medium animate-pulse",
          activeHighlightId || "evidence-highlighter"
        );
        if (highlighted) {
          return (
            <div className="whitespace-pre-line leading-relaxed text-slate-800 dark:text-slate-200 text-xs font-light">
              {highlighted}
            </div>
          );
        }
      }
    } catch {
      /* fall through to markdown */
    }
  }

  if (searchQuery.trim() && formatted.toLowerCase().includes(searchQuery.toLowerCase())) {
    const escapedQuery = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    try {
      const regex = new RegExp(`(${escapedQuery})`, "gi");
      if (regex.test(formatted) && !formatted.includes("| --- |")) {
        const highlighted = wrapHighlight(
          formatted,
          regex,
          "bg-rose-500/20 border-b border-rose-500 text-[#0f172a] dark:text-white font-semibold px-0.5 rounded"
        );
        if (highlighted) {
          return (
            <div className="whitespace-pre-line leading-relaxed text-slate-800 dark:text-slate-200 text-xs font-light">
              {highlighted}
            </div>
          );
        }
      }
    } catch {
      /* fall through */
    }
  }

  return <MarkdownNarrative content={formatted} />;
}

const WORKSPACE_ACCENTS = {
  ingest: {
    dot: "bg-[#90A955]",
    active: "bg-white dark:bg-[#31572C] text-[#31572C] dark:text-[#ECF39E] border border-slate-200 dark:border-[#90A955]/45 shadow-sm",
    idle: "text-slate-500 dark:text-slate-400 hover:text-[#4F772D] dark:hover:text-[#ECF39E]",
  },
  audit: {
    dot: "bg-[#4F772D]",
    active: "bg-white dark:bg-[#4F772D] text-[#31572C] dark:text-[#ECF39E] border border-slate-200 dark:border-[#90A955]/45 shadow-sm",
    idle: "text-slate-500 dark:text-slate-400 hover:text-amber-700 dark:hover:text-amber-200",
  },
  benchmarking: {
    dot: "bg-[#ECF39E]",
    active: "bg-white dark:bg-[#132A13] text-[#31572C] dark:text-[#ECF39E] border border-slate-200 dark:border-[#90A955]/45 shadow-sm",
    idle: "text-slate-500 dark:text-slate-400 hover:text-[#4F772D] dark:hover:text-[#ECF39E]",
  },
} as const;

type SectionCatalogEntry = {
  id: string;
  title: string;
  priority: number;
  char_count?: number;
  source?: string;
};

const SECTION_ID_PATTERNS = {
  risk_factors: /risk_factor|item_1a/i,
  mda: /(^mda$|management.*discussion|item_7|results_of_operations)/i,
  forward_looking: /forward|cautionary|outlook/i,
} as const;

function inferSectionPriority(sectionId: string): number {
  if (SECTION_ID_PATTERNS.mda.test(sectionId)) return 100;
  if (SECTION_ID_PATTERNS.risk_factors.test(sectionId)) return 95;
  if (SECTION_ID_PATTERNS.forward_looking.test(sectionId)) return 85;
  return 40;
}

/** All discovered sections, highest priority first (matches backend section discovery). */
function buildFilingSectionList(
  sections: Record<string, string> | undefined,
  catalog: SectionCatalogEntry[] | undefined
): SectionCatalogEntry[] {
  if (catalog?.length) {
    return [...catalog].sort(
      (a, b) => b.priority - a.priority || a.title.localeCompare(b.title)
    );
  }
  if (!sections) return [];
  return Object.entries(sections)
    .map(([id, text]) => ({
      id,
      title: id.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      priority: inferSectionPriority(id),
      char_count: text?.length ?? 0,
    }))
    .sort((a, b) => b.priority - a.priority || a.title.localeCompare(b.title));
}

function resolveFilingSectionText(
  sections: Record<string, string> | undefined,
  sectionId: string
): string {
  if (!sections || !sectionId) return "";
  return sections[sectionId] ?? "";
}

function findRiskSectionId(entries: SectionCatalogEntry[]): string {
  const risk = entries.find((e) => SECTION_ID_PATTERNS.risk_factors.test(e.id));
  return risk?.id ?? entries[0]?.id ?? "";
}

const WORKSPACE_STORAGE_KEY = "aegis_workspace_v1";

type WorkspaceSnapshot = {
  showDashboard: boolean;
  activeReportId: string | null;
  processingStatus: "idle" | "processing" | "complete" | "failed";
  pipelineLogs: string[];
  currentStep: string;
};

function readWorkspaceSnapshot(): WorkspaceSnapshot | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(WORKSPACE_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as WorkspaceSnapshot;
  } catch {
    return null;
  }
}

export default function Home() {
  // Navigation & theme states (defaults must match SSR — sessionStorage restored after mount)
  const [showDashboard, setShowDashboard] = useState<boolean>(false);
  const [workspaceHydrated, setWorkspaceHydrated] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [activeWorkspace, setActiveWorkspace] = useState<"ingest" | "audit" | "benchmarking">("ingest");

  // Core application states
  const [activeReportId, setActiveReportId] = useState<string | null>(null);
  const [reportsList, setReportsList] = useState<any[]>([]);
  const [activeReport, setActiveReport] = useState<any>(null);
  
  // Pipeline status tracking
  const [processingStatus, setProcessingStatus] = useState<
    "idle" | "processing" | "complete" | "failed"
  >("idle");
  const [currentStep, setCurrentStep] = useState<string>("");
  const [pipelineLogs, setPipelineLogs] = useState<string[]>([]);
  
  // Narrative section navigator (dynamic ids from section_catalog)
  const [activeSectionId, setActiveSectionId] = useState<string>("");
  const [activeEvidenceText, setActiveEvidenceText] = useState<string | null>(null);
  const [activeHighlightId, setActiveHighlightId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  
  // Chatbot states
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [chatInput, setChatInput] = useState<string>("");
  const [isChatLoading, setIsChatLoading] = useState<boolean>(false);
  
  // Re-trigger analysis state
  const [retriggerQuery, setRetriggerQuery] = useState<string>("");
  const [isRetriggering, setIsRetriggering] = useState<boolean>(false);

  // Backend connectivity status
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  
  // Operational risks indexes expanded
  const [expandedRiskIdx, setExpandedRiskIdx] = useState<number | null>(null);

  // DOM Refs for scrollbars
  const filingContentRef = useRef<HTMLDivElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const pollingPromisesRef = useRef<Map<string, Promise<void>>>(new Map());
  const restoredWorkspaceRef = useRef(false);

  /** Long filings (embed + map-reduce) often exceed 5 minutes. */
  const PIPELINE_POLL_INTERVAL_MS = 900;
  const PIPELINE_MAX_POLL_MS = 45 * 60 * 1000;

  // Scroll logs helper
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [pipelineLogs]);

  // Scroll chat helper
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Restore workspace from sessionStorage after mount (never during SSR / first paint)
  useEffect(() => {
    const saved = readWorkspaceSnapshot();
    if (saved) {
      if (saved.showDashboard) setShowDashboard(true);
      if (saved.activeReportId) setActiveReportId(saved.activeReportId);
      if (saved.pipelineLogs?.length) setPipelineLogs(saved.pipelineLogs);
      if (saved.currentStep) setCurrentStep(saved.currentStep);
      if (saved.processingStatus) setProcessingStatus(saved.processingStatus);
    }
    setWorkspaceHydrated(true);
  }, []);

  useEffect(() => {
    if (!workspaceHydrated) return;
    const snapshot: WorkspaceSnapshot = {
      showDashboard,
      activeReportId,
      processingStatus,
      pipelineLogs: pipelineLogs.slice(-100),
      currentStep,
    };
    sessionStorage.setItem(WORKSPACE_STORAGE_KEY, JSON.stringify(snapshot));
  }, [workspaceHydrated, showDashboard, activeReportId, processingStatus, pipelineLogs, currentStep]);

  // Initialize theme and API validations
  useEffect(() => {
    // Force dark theme only
    setTheme("dark");
    document.documentElement.className = "dark";

    fetch(apiUrl("/api/health"))
      .then(r => { if (!r.ok) throw new Error(); setBackendOnline(true); return fetch(apiUrl("/api/reports")); })
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(list => setReportsList(list))
      .catch(() => {
        setBackendOnline(false);
        setReportsList([]);
      });
  }, []);

  const selectReport = useCallback(async (id: string, companyName: string) => {
    setActiveReportId(id);

    try {
      const res = await fetch(apiUrl(`/api/reports/${id}`));
      if (res.ok) {
        const fullReport = await res.json();
        setActiveReport(fullReport);
        setPipelineLogs(fullReport.logs || []);
        setCurrentStep(fullReport.current_step || "Complete");
        if (fullReport.status === "failed") {
          setProcessingStatus("failed");
        } else if (fullReport.status === "complete" && fullReport.result) {
          setProcessingStatus("complete");
        } else if (fullReport.status === "processing" || fullReport.status === "queued") {
          setProcessingStatus("processing");
        }
        const summary = fullReport.result?.executive_summary;
        const intro = hasNarrativeText(summary)
          ? `**Executive summary**\n\n${summary.trim()}\n\n---\n\nAsk me about risks, margins, sentiment, or peer comparisons.`
          : `Analysis of ${fullReport.company_name}'s filing is complete. Ask me about risks, margins, sentiment, or competitor comparisons.`;
        setChatMessages([{
          id: 1, role: "assistant",
          content: intro,
          citations: []
        }]);
      }
    } catch (err) {
      console.error("Error loading report:", err);
    }
  }, []);

  const handleTemplateClick = async (company: "NVIDIA" | "AMD") => {
    if (backendOnline !== true) return;
    const formData = new FormData();
    formData.append("company_name", company);
    formData.append(
      "user_query",
      "Analyze all risks and sentiment. Compare against key industry peers and generate competitive benchmarks."
    );
    await runIngestSecAndPoll(formData, company);
  };

  const pollUntilComplete = useCallback((repId: string): Promise<void> => {
    const inFlight = pollingPromisesRef.current.get(repId);
    if (inFlight) return inFlight;

    setProcessingStatus("processing");
    setShowDashboard(true);

    const promise = new Promise<void>((resolve, reject) => {
      let settled = false;
      const finish = (fn: () => void) => {
        if (settled) return;
        settled = true;
        clearInterval(iv);
        clearTimeout(maxTimer);
        pollingPromisesRef.current.delete(repId);
        fn();
      };

      const tick = async () => {
        try {
          const r = await fetch(apiUrl(`/api/reports/${repId}/status`));
          if (!r.ok) {
            finish(() => reject(new Error("Status poll failed")));
            return;
          }
          const d = await r.json();
          setPipelineLogs(d.logs || []);
          setCurrentStep(d.current_step || "Processing...");
          if (d.status === "complete") {
            setProcessingStatus("complete");
            finish(resolve);
          } else if (d.status === "failed") {
            setProcessingStatus("failed");
            finish(() => reject(new Error("Pipeline failed")));
          } else {
            setProcessingStatus("processing");
          }
        } catch (e) {
          finish(() => reject(e));
        }
      };

      void tick();
      const iv = setInterval(() => void tick(), PIPELINE_POLL_INTERVAL_MS);
      const maxTimer = setTimeout(() => {
        finish(() =>
          reject(
            new Error(
              "Pipeline is taking longer than expected. Check backend logs or refresh to re-sync."
            )
          )
        );
      }, PIPELINE_MAX_POLL_MS);
    });

    pollingPromisesRef.current.set(repId, promise);
    return promise;
  }, []);

  const syncPipelineWithBackend = useCallback(
    async (reportId: string) => {
      try {
        const r = await fetch(apiUrl(`/api/reports/${reportId}/status`));
        if (!r.ok) return;
        const d = await r.json();
        setPipelineLogs(d.logs || []);
        setCurrentStep(d.current_step || "Processing...");
        if (d.status === "complete") {
          setProcessingStatus("complete");
          await selectReport(reportId, "");
        } else if (d.status === "failed") {
          setProcessingStatus("failed");
        } else {
          await pollUntilComplete(reportId);
          await selectReport(reportId, "");
        }
      } catch {
        setProcessingStatus("failed");
      }
    },
    [pollUntilComplete, selectReport]
  );

  // Re-attach to in-flight backend job when workspace opens or page remounts
  useEffect(() => {
    if (!workspaceHydrated) return;
    if (backendOnline !== true || !activeReportId) return;
    if (!showDashboard && processingStatus !== "processing") return;

    if (!showDashboard) return;

    if (processingStatus === "processing") {
      void syncPipelineWithBackend(activeReportId);
      return;
    }

    if (!restoredWorkspaceRef.current) {
      restoredWorkspaceRef.current = true;
      void (async () => {
        const r = await fetch(apiUrl(`/api/reports/${activeReportId}/status`));
        if (!r.ok) return;
        const d = await r.json();
        if (d.status === "complete") {
          setProcessingStatus("complete");
          await selectReport(activeReportId, "");
        } else if (d.status === "failed") {
          setProcessingStatus("failed");
        } else if (d.status === "processing" || d.status === "queued") {
          setProcessingStatus("processing");
          await syncPipelineWithBackend(activeReportId);
        }
      })();
    }
  }, [
    workspaceHydrated,
    showDashboard,
    activeReportId,
    processingStatus,
    backendOnline,
    syncPipelineWithBackend,
    selectReport,
  ]);

  // Safety net: keep syncing UI if the main poll loop was interrupted (e.g. stale session)
  useEffect(() => {
    if (!workspaceHydrated || backendOnline !== true) return;
    if (!showDashboard || !activeReportId || processingStatus !== "processing") return;

    const watchdog = setInterval(async () => {
      try {
        const r = await fetch(apiUrl(`/api/reports/${activeReportId}/status`));
        if (!r.ok) return;
        const d = await r.json();
        setPipelineLogs(d.logs || []);
        setCurrentStep(d.current_step || "Processing...");
        if (d.status === "complete") {
          setProcessingStatus("complete");
          await selectReport(activeReportId, "");
        } else if (d.status === "failed") {
          setProcessingStatus("failed");
        }
      } catch {
        /* transient network errors — next tick retries */
      }
    }, 2000);

    return () => clearInterval(watchdog);
  }, [
    workspaceHydrated,
    backendOnline,
    showDashboard,
    activeReportId,
    processingStatus,
    selectReport,
  ]);

  const runIngestSecAndPoll = async (formData: FormData, companyHint: string) => {
    setShowDashboard(true);
    setProcessingStatus("processing");
    setPipelineLogs([`Fetching latest SEC 10-K for ${companyHint}...`]);
    setCurrentStep("SEC ingest...");
    setActiveReport(null);
    try {
      const r = await fetch(apiUrl("/api/ingest-sec"), { method: "POST", body: formData });
      if (!r.ok) {
        const e = await r.json();
        throw new Error(e.detail || "SEC ingest failed");
      }
      const { report_id, company_name } = await r.json();
      setActiveReportId(report_id);
      await pollUntilComplete(report_id);
      await selectReport(report_id, company_name || companyHint);
      const listRes = await fetch(apiUrl("/api/reports"));
      if (listRes.ok) setReportsList(await listRes.json());
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "SEC ingest failed";
      setProcessingStatus("failed");
      setCurrentStep(`Error: ${message}`);
      console.error(err);
    }
  };

  const runUploadAndPoll = async (formData: FormData, companyHint: string) => {
    setShowDashboard(true);
    setProcessingStatus("processing");
    setPipelineLogs(["Uploading filing to Aegis backend..."]);
    setCurrentStep("Uploading...");
    setActiveReport(null);
    try {
      const r = await fetch(apiUrl("/api/upload"), { method: "POST", body: formData });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || "Upload failed"); }
      const { report_id, company_name } = await r.json();
      setActiveReportId(report_id);
      await pollUntilComplete(report_id);
      await selectReport(report_id, company_name || companyHint);
      const listRes = await fetch(apiUrl("/api/reports"));
      if (listRes.ok) setReportsList(await listRes.json());
    } catch (err: any) {
      setProcessingStatus("failed");
      setCurrentStep(`Error: ${err.message}`);
      console.error(err);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || backendOnline !== true) return;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_query", "Analyze all operational risks and sentiment. Compare against key industry competitors and generate comprehensive benchmarks.");
    await runUploadAndPoll(formData, file.name.replace(/\.pdf$/i, ""));
  };

  const handleRetriggerAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!retriggerQuery.trim() || !activeReportId) return;
    
    setShowDashboard(true);
    setIsRetriggering(true);
    setProcessingStatus("processing");
    setCurrentStep("Re-triggering pipeline...");
    setPipelineLogs(prev => [...prev, `💡 Re-triggering pipeline with query: "${retriggerQuery}"`]);

    try {
      const res = await fetch(apiUrl("/api/reports/trigger"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          report_id: activeReportId,
          query: retriggerQuery
        })
      });
      
      if (res.ok) {
        setRetriggerQuery("");
        setIsRetriggering(false);
        pollUntilComplete(activeReportId).then(() => {
          selectReport(activeReportId, activeReport?.company_name || "Target");
        });
      }
    } catch (err) {
      console.error("Error retriggering backend:", err);
      setIsRetriggering(false);
      setProcessingStatus("complete");
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !activeReportId) return;
    
    const userMsg = chatInput;
    setChatInput("");
    setIsChatLoading(true);
    
    const newId = chatMessages.length + 1;
    setChatMessages(prev => [...prev, { id: newId, role: "user", content: userMsg }]);

    try {
      const res = await fetch(apiUrl("/api/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          report_id: activeReportId,
          message: userMsg
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        setChatMessages(prev => [...prev, {
          id: newId + 1,
          role: "assistant",
          content: data.answer,
          citations: data.citations || [],
          mode: data.mode || "rag",
          sourceSummary: data.source_summary || {},
          statusSteps: data.status_steps || [],
        }]);
      }
    } catch (err) {
      console.error("Chat API error:", err);
    } finally {
      setIsChatLoading(false);
    }
  };

  const filingSectionList = buildFilingSectionList(
    activeReport?.result?.sections,
    activeReport?.result?.section_catalog
  );

  useEffect(() => {
    if (!filingSectionList.length) return;
    setActiveSectionId((current) =>
      filingSectionList.some((s) => s.id === current) ? current : filingSectionList[0].id
    );
  }, [activeReport?.id, activeReport?.result?.sections, activeReport?.result?.section_catalog]);

  const handleRiskCardClick = (evidenceText: string, highlightId: string) => {
    setActiveEvidenceText(evidenceText);
    setActiveHighlightId(highlightId);
    const riskId = findRiskSectionId(filingSectionList);
    if (riskId) setActiveSectionId(riskId);
    
    setTimeout(() => {
      const element = document.getElementById(highlightId);
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 100);
  };

  const renderHighlightedText = (text: string, sectionId: string) => {
    if (!text) {
      return (
        <p className="text-slate-500 italic dark:text-slate-400">
          No text extracted for this section.
        </p>
      );
    }
    return (
      <FilingSectionNarrative
        text={text}
        sectionId={sectionId}
        searchQuery={searchQuery}
        activeEvidenceText={activeEvidenceText}
        activeHighlightId={activeHighlightId}
      />
    );
  };

  const getRadarData = () => {
    if (!activeReport?.result?.sentiment?.metrics) return [];
    const m = activeReport.result.sentiment.metrics;
    const rows = [
      { subject: "Optimism", key: "optimism" as const },
      { subject: "Pessimism", key: "pessimism" as const },
      { subject: "Cautiousness", key: "cautiousness" as const },
      { subject: "Uncertainty", key: "uncertainty" as const },
    ];
    return rows.map((row) => ({
      subject: row.subject,
      Target: (m[row.key] ?? 0) * 100,
    }));
  };

  return (
    <div className="flex-1 flex flex-col bg-background min-h-screen relative transition-colors duration-300 font-sans">
      {/* Dynamic Brand Gradients */}
      <div className="absolute inset-x-0 top-0 h-48 bg-[#132A13]/30 pointer-events-none -z-10" />
      <div className="absolute inset-x-0 bottom-0 h-52 bg-[#132A13]/20 pointer-events-none -z-10" />

      {/* ==========================================
          PORTAL GATEWAY / LANDING PAGE
         ========================================== */}
      {!showDashboard ? (
        <div className="flex-1 flex flex-col justify-between p-6 max-w-7xl mx-auto w-full min-h-[calc(100vh-20px)] animate-fade-in">
          
          <header className="flex items-center justify-between py-4 border-b border-slate-200 dark:border-[#132A13]/40">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-[#4F772D] flex items-center justify-center shadow-md">
                <Cpu className="w-5 h-5 text-white" />
              </div>
              <div>
                <span className="text-xl font-extrabold tracking-tight text-[#90A955]">AEGIS</span>
                <span className="text-sm text-slate-500 dark:text-slate-400 block tracking-widest font-mono">FINTECH PLATFORM</span>
              </div>
            </div>

              <div className="flex items-center space-x-4">
              {/* Dark theme only — toggle removed */}
            </div>
          </header>

          <div className="flex-grow flex flex-col lg:flex-row items-center justify-center gap-12 py-12">
            <div className="flex-1 space-y-6 text-left max-w-xl">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-[#4F772D]/10 border border-[#90A955]/30 text-[#4F772D] dark:text-[#ECF39E] text-xs font-semibold tracking-wide">
                <Sparkles className="w-3.5 h-3.5" />
                Multi-Agent SEC Intelligence Platform
              </div>
              
              <h1 className="text-4xl lg:text-5xl font-extrabold tracking-tight leading-[1.1] text-[#0f172a] dark:text-white">
                Filing Narrative <br />
                <span className="text-[#90A955]">Risk Auditing</span>
              </h1>
              
              <p className="text-sm text-slate-600 dark:text-slate-400 font-light leading-relaxed">
                Unlock automated SEC evaluations. Audit operational threats, map management sentiment scores, benchmark performance yields, and query vector filings with verified citation backing.
              </p>

              <div className="flex flex-col sm:flex-row gap-3 pt-2">
                <button
                  onClick={() => {
                    setShowDashboard(true);
                    if (activeReportId && processingStatus === "processing") {
                      void syncPipelineWithBackend(activeReportId);
                    }
                  }}
                  className="px-6 py-3.5 rounded-xl bg-[#4F772D] text-white font-semibold text-xs tracking-wider uppercase hover:bg-[#31572C] hover:shadow-lg hover:shadow-green-500/25 active:scale-95 transition flex items-center justify-center gap-2"
                >
                  {processingStatus === "processing" ? "Return to Active Pipeline" : "Enter Operational Workspace"}
                  <ArrowRight className="w-4 h-4" />
                </button>
                {processingStatus === "processing" && (
                  <p className="text-xs text-[#90A955] font-mono">
                    Pipeline running in background — open workspace to view live logs.
                  </p>
                )}
                {/* System Architecture link removed per request */}
              </div>
            </div>

            <div className="flex-1 w-full max-w-lg glass-panel p-6 border-[#90A955]/20">
              <h3 className="text-xs font-bold text-[#4F772D] dark:text-[#ECF39E] mb-4 uppercase tracking-widest font-mono">Agent Timeline Orchestration</h3>
              
              <div className="space-y-4 relative">
                <div className="absolute left-[19px] top-6 bottom-6 w-0.5 bg-[#90A955]/45" />

                {[
                  { title: "Ingestion & Parse Hub", desc: "Automated PDF structural rendering via PyMuPDF", icon: FileUp, color: "text-[#4F772D]", bg: "bg-[#4F772D]/10" },
                  { title: "Risk Identification Agent", desc: "Extracts severe narrative hazards with custom LLM checkpoints", icon: Cpu, color: "text-rose-500", bg: "bg-rose-500/10" },
                  { title: "BeautifulSoup Data Scraper", desc: "Retrieves peer context dynamically from official channels", icon: Database, color: "text-amber-500", bg: "bg-amber-500/10" },
                  { title: "Compliance Validator Node", desc: "Cross-checks regulatory integrity and source dates", icon: ShieldCheck, color: "text-[#90A955]", bg: "bg-[#90A955]/10" },
                  { title: "Fintech Dashboard Analytics", desc: "Deploys visual workspaces, margin lines, and citation RAG", icon: Layers, color: "text-[#4F772D]", bg: "bg-[#4F772D]/10" }
                ].map((step, sIdx) => (
                  <div key={sIdx} className="flex gap-4 items-start relative z-10 hover:translate-x-1 transition-transform duration-200">
                    <div className={`w-10 h-10 rounded-xl ${step.bg} flex items-center justify-center border border-slate-200 dark:border-slate-700`}>
                      <step.icon className={`w-5 h-5 ${step.color}`} />
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-800 dark:text-slate-100">{step.title}</h4>
                      <p className="text-sm text-slate-500 dark:text-slate-400 font-light">{step.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <footer className="border-t border-slate-200 dark:border-[#132A13]/40 py-4 flex flex-col sm:flex-row items-center justify-between text-sm text-slate-500 font-mono">
            <span>AEGIS FINTECH CO © 2026. COMPLIANCE ASSURED.</span>
            <div className="flex gap-4 mt-2 sm:mt-0">
              <a href="#" className="hover:text-[#4F772D]">SYSTEM METRICS</a>
              <a href="#" className="hover:text-[#4F772D]">PRIVACY CODE</a>
            </div>
          </footer>
        </div>
      ) : (
        
        // ==========================================
        // ACTIVE INTERACTIVE SAAS DASHBOARD
        // ==========================================
        <div className="flex-grow flex flex-col animate-fade-in">
          
          {/* Header Nav Bar */}
          <header className="border-b border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-slate-950/85 backdrop-blur-md px-6 py-4 flex flex-col lg:flex-row items-center justify-between gap-4 sticky top-0 z-50 shadow-sm dark:shadow-none">
            <div className="flex items-center space-x-3 w-full lg:w-auto">
              <button 
                onClick={() => {
                  if (
                    processingStatus === "processing" &&
                    !window.confirm(
                      "Analysis is still running. The backend will continue, but you will leave the live pipeline view. Continue?"
                    )
                  ) {
                    return;
                  }
                  setShowDashboard(false);
                }}
                className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-900 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 active:scale-95 transition"
                title={processingStatus === "processing" ? "Leave workspace (pipeline keeps running)" : "Back to home"}
              >
                <ArrowLeft className="w-3.5 h-3.5" />
              </button>
              <div className="w-8 h-8 rounded-lg bg-[#4F772D] flex items-center justify-center shadow-sm">
                <Cpu className="w-4 h-4 text-white animate-pulse" />
              </div>
              <div>
                <h1 className="text-sm font-extrabold tracking-tight text-[#0f172a] dark:text-white flex items-center gap-1.5 leading-none">
                  AEGIS
                  <span className="text-xs font-bold px-1.5 py-0.5 rounded-lg bg-[#90A955]/10 text-[#90A955] border border-[#90A955]/25 font-mono">WORKSPACE</span>
                </h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 font-light mt-1">Multi-Agent SEC Filing Audit Dashboard</p>
              </div>
            </div>

            {/* Focused Workspace Switch Tabs (Reduces visual clutter) */}
            <div className="flex bg-slate-100 dark:bg-slate-900 p-1 rounded-xl border border-slate-200 dark:border-slate-700 gap-1">
              {[
                { id: "ingest", label: "Filing Ingestion", icon: FileText },
                { id: "audit", label: "Risk & Sentiment Analysis", icon: ShieldCheck },
                { id: "benchmarking", label: "Citation Chat", icon: MessageSquare }
              ].map(workspace => {
                const accent = WORKSPACE_ACCENTS[workspace.id as keyof typeof WORKSPACE_ACCENTS];
                return (
                <button
                  key={workspace.id}
                  onClick={() => setActiveWorkspace(workspace.id as any)}
                  className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold tracking-tight transition active:scale-95 ${
                    activeWorkspace === workspace.id 
                      ? accent.active
                      : accent.idle
                  }`}
                >
                  <workspace.icon className="w-3.5 h-3.5" />
                  {workspace.label}
                </button>
              )})}
            </div>

            {/* Ingestion controllers & light mode triggers */}
            <div className="flex items-center gap-3 w-full lg:w-auto justify-end">
              <div className="flex items-center bg-slate-100 dark:bg-slate-900 p-1 rounded-xl border border-slate-200 dark:border-slate-700 gap-1">
                <button 
                  onClick={() => handleTemplateClick("NVIDIA")}
                  disabled={processingStatus === "processing" || backendOnline !== true}
                  className="text-sm font-bold px-3 py-1.5 rounded-lg text-[#0f172a] dark:text-white bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 hover:border-[#90A955]/50 hover:bg-[#4F772D]/5 transition disabled:opacity-50 flex items-center gap-1.5 shadow-sm"
                >
                  <Cpu className="w-3 h-3 text-[#4F772D]" />
                  NVIDIA
                </button>
                <button 
                  onClick={() => handleTemplateClick("AMD")}
                  disabled={processingStatus === "processing" || backendOnline !== true}
                  className="text-sm font-bold px-3 py-1.5 rounded-lg text-[#0f172a] dark:text-white bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 hover:border-[#90A955]/50 hover:bg-[#4F772D]/5 transition disabled:opacity-50 flex items-center gap-1.5 shadow-sm"
                >
                  <Cpu className="w-3 h-3 text-[#4F772D]" />
                  AMD
                </button>
              </div>

              <label className="cursor-pointer text-sm font-bold px-4 py-2.5 rounded-xl bg-[#4F772D] text-white hover:bg-[#31572C] shadow-sm active:scale-95 transition flex items-center gap-2">
                <Upload className="w-3.5 h-3.5" />
                Upload PDF
                <input 
                  type="file" 
                  accept=".pdf" 
                  onChange={handleFileUpload} 
                  className="hidden" 
                  disabled={processingStatus === "processing" || backendOnline !== true}
                />
              </label>

              {backendOnline === false && (
                <span className="text-xs text-amber-600 dark:text-amber-300 font-mono">
                  API offline — start backend on port 8000
                </span>
              )}
            </div>
          </header>

          {/* ==========================================
              DYNAMIC OPERATIONAL WORKSPACES
             ========================================== */}
          <main className="flex-1 p-6 grid grid-cols-12 gap-6 overflow-hidden max-w-[1700px] mx-auto w-full">
            
            {/* ── WORKSPACE 1: FILING INGESTION & READ ── */}
            {activeWorkspace === "ingest" && (
              <>
                {/* Timeline status auditor */}
                <div className="col-span-12 lg:col-span-4 glass-panel p-5 flex flex-col h-[calc(100vh-170px)] min-h-[500px] border-slate-200 dark:border-[#90A955]/20 bg-white dark:bg-slate-950/70 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-[#90A955]/15 pb-4 mb-5">
                    <h2 className="text-sm font-bold tracking-wider text-[#0f172a] dark:text-green-200 uppercase flex items-center gap-2.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-[#90A955] animate-pulse" />
                      Agentic Pipeline Orchestration
                    </h2>
                    <span className="text-xs text-green-200 font-bold px-2.5 py-0.5 rounded-full bg-[#31572C] border border-[#90A955]/30 font-mono">LANGGRAPH ACTIVE</span>
                  </div>

                  {processingStatus === "idle" ? (
                    <div className="flex-grow flex flex-col items-center justify-center text-center p-8 space-y-4">
                      <div className="w-16 h-16 rounded-2xl bg-[#4F772D]/15 flex items-center justify-center">
                        <Database className="w-8 h-8 text-[#90A955]/70" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-[#0f172a] dark:text-white mb-1">Ready to Analyze</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400 font-light leading-relaxed max-w-xs">
                          Select a company template or upload your own SEC filing to begin multi-agent analysis.
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex-grow flex flex-col justify-between h-full overflow-hidden gap-3">
                      {/* Pipeline Progress Header */}
                      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-[#90A955]/20 rounded-lg p-5 shadow-sm relative overflow-hidden">
                        <div className="absolute top-0 inset-x-0 h-1 bg-[#90A955]" />
                        <div className="flex items-start justify-between mb-4">
                          <div>
                            <span className="text-xs text-[#90A955] font-bold block uppercase tracking-widest mb-1.5 font-mono">Orchestration State</span>
                            <div className="flex items-center gap-2">
                              <div className={`w-2.5 h-2.5 rounded-full ${processingStatus === "complete" ? "bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]" : "bg-[#90A955] animate-pulse shadow-[0_0_10px_rgba(144,169,85,0.4)]"}`} />
                              <span className="text-sm font-semibold text-[#0f172a] dark:text-green-50">{currentStep || "Initializing Pipeline..."}</span>
                            </div>
                          </div>
                          <div className={`text-xs px-3 py-1.5 rounded-md font-bold uppercase tracking-wider font-mono ${
                            processingStatus === "complete" ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-500/20" :
                            processingStatus === "processing" ? "bg-[#90A955]/15 text-[#31572C] dark:text-[#ECF39E] border border-[#90A955]/30 animate-pulse" :
                            "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300"
                          }`}>
                            {processingStatus}
                          </div>
                        </div>
                        
                        {/* Visual Progress Bar */}
                        <div className="w-full h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full transition-all duration-700 ease-out ${
                            processingStatus === "complete" ? "w-full bg-emerald-500" :
                            "w-1/3 animate-gradient-strip"
                          }`} />
                        </div>
                      </div>

                      {/* Pipeline Timeline Viewer */}
                      <div className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950/70 border border-slate-200 dark:border-[#90A955]/20 rounded-lg p-5 font-mono shadow-inner relative">
                        {pipelineLogs.map((log: string, idx: number) => {
                           const isError = log.startsWith("❌");
                           const isSuccess = log.startsWith("✅") || log.startsWith("🟢");
                           const isAction = log.startsWith("💡");
                           const isAI = log.startsWith("🧠") || log.startsWith("🔥") || log.startsWith("🔎") || log.startsWith("📊");
                           
                           let IconComponent = Database;
                           let colorClass = "text-slate-500 dark:text-slate-400";
                           let bgClass = "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-700";
                           
                           if (isError) { IconComponent = AlertTriangle; colorClass = "text-rose-500"; bgClass = "bg-rose-50 dark:bg-rose-500/10 border-rose-200 dark:border-rose-500/20"; }
                           else if (isSuccess) { IconComponent = CheckCircle2; colorClass = "text-emerald-500"; bgClass = "bg-emerald-50 dark:bg-emerald-500/10 border-emerald-200 dark:border-emerald-500/20"; }
                           else if (isAction) { IconComponent = Layers; colorClass = "text-[#4F772D]"; bgClass = "bg-[#ECF39E]/20 dark:bg-[#4F772D]/10 border-green-200 dark:border-[#90A955]/20"; }
                           else if (isAI) { IconComponent = Cpu; colorClass = "text-[#4F772D]"; bgClass = "bg-[#ECF39E]/20 dark:bg-[#4F772D]/10 border-green-200 dark:border-[#90A955]/20"; }

                           return (
                             <div key={idx} className="relative pl-6 pb-5 last:pb-0 group animate-fade-in" style={{animationDelay: `${idx * 40}ms`}}>
                               {/* Vertical Connector Line */}
                               {idx !== pipelineLogs.length - 1 && (
                                 <div className="absolute left-[11px] top-6 bottom-[-4px] w-[2px] bg-slate-200 dark:bg-slate-700 group-hover:bg-[#90A955]/40 transition-colors" />
                               )}
                               
                               {/* Timeline Node Icon */}
                               <div className={`absolute left-0 top-0.5 w-6 h-6 rounded-full flex items-center justify-center border z-10 ${bgClass}`}>
                                 <IconComponent className={`w-3.5 h-3.5 ${colorClass}`} />
                               </div>
                               
                               {/* Log Content Card */}
                               <div className="ml-3 p-3 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 shadow-sm group-hover:border-[#90A955]/35 transition-colors">
                                 <p className={`text-xs leading-relaxed ${isError ? "text-rose-600 dark:text-rose-400 font-semibold" : "text-slate-700 dark:text-slate-300 font-medium"}`}>
                                   {log.replace(/^[🟢✅💡🧠🔥🔎📊❌]\s*/, '')}
                                 </p>
                                 <div className="mt-1.5 flex items-center gap-2">
                                   <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono" suppressHydrationWarning>
                                     <Clock className="w-2.5 h-2.5 inline mr-1" />
                                     {workspaceHydrated
                                       ? new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
                                       : ""}
                                   </span>
                                 </div>
                               </div>
                             </div>
                           );
                        })}
                        <div ref={logEndRef} />
                      </div>
                    </div>
                  )}
                </div>

                {/* Section Auditor view */}
                <div className="col-span-12 lg:col-span-8 glass-panel p-6 flex flex-col h-[calc(100vh-170px)] min-h-[500px] border-slate-200 dark:border-[#90A955]/20 bg-white dark:bg-slate-950/70 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-[#90A955]/15 pb-4 mb-5">
                    <h2 className="text-sm font-bold tracking-wider text-[#0f172a] dark:text-green-200 uppercase flex items-center gap-2.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-[#90A955]" />
                      Filing Narrative Viewer
                    </h2>
                    
                    {activeReport && (
                      <span className="text-xs font-bold text-[#31572C] dark:text-[#ECF39E] bg-[#4F772D]/15 px-3 py-1.5 rounded-lg border border-[#90A955]/25 font-mono">
                        {activeReport.company_name} 10-K
                      </span>
                    )}
                  </div>

                  <div className="mb-4 relative">
                    <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-slate-400">
                      <Search className="w-4 h-4 text-[#4F772D]" />
                    </div>
                    <input
                      type="text"
                      placeholder="Search keywords (TSMC, export, CUDA...)..."
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                      disabled={!activeReport}
                      className="w-full bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg pl-10 pr-9 py-2.5 text-sm text-[#0f172a] dark:text-white placeholder-[#6b7280] focus:outline-none focus:border-[#90A955]/60 focus:ring-1 focus:ring-[#90A955]/20 transition"
                    />
                    {searchQuery && (
                      <button 
                        onClick={() => setSearchQuery("")} 
                        className="absolute right-3.5 top-1/2 -translate-y-1/2 text-xs text-rose-500 font-bold hover:text-rose-600"
                      >
                        ✕
                      </button>
                    )}
                  </div>

                  <div className="flex flex-grow min-h-0 gap-3">
                    {!activeReport || !activeReport.result?.sections ? (
                      <div className="flex-grow flex flex-col items-center justify-center text-center p-8 space-y-3 bg-slate-50/50 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-700 rounded-lg">
                        {!activeReport ? (
                          <>
                            <FileText className="w-14 h-14 text-[#4F772D]/30" />
                            <p className="text-sm font-semibold text-[#0f172a] dark:text-white">No document loaded</p>
                            <p className="text-xs text-[#6b7280] dark:text-slate-400 font-light max-w-xs">
                              Select NVIDIA or AMD above to parse SEC filing narratives.
                            </p>
                          </>
                        ) : (
                          <>
                            {processingStatus === "failed" || activeReport.status === "failed" ? (
                              <AlertTriangle className="w-12 h-12 text-rose-500/70" />
                            ) : activeReport.status === "complete" ? (
                              <FileText className="w-12 h-12 text-[#4F772D]/40" />
                            ) : (
                              <RefreshCw className="w-12 h-12 text-[#4F772D]/60 animate-spin" />
                            )}
                            <p className="text-sm font-semibold text-[#0f172a] dark:text-white">
                              {processingStatus === "failed" || activeReport.status === "failed"
                                ? "Analysis failed"
                                : activeReport.status === "complete"
                                  ? "No narrative sections available"
                                  : "Analysis in progress"}
                            </p>
                            <p className="text-xs text-[#6b7280] dark:text-slate-400 font-light max-w-xs">
                              {processingStatus === "failed" || activeReport.status === "failed"
                                ? "Check the pipeline log for errors, then re-upload or re-run analysis."
                                : activeReport.status === "complete"
                                  ? "The filing finished processing but no section text was returned."
                                  : "Narrative sections appear after extraction, embedding, and map-reduce complete."}
                            </p>
                          </>
                        )}
                      </div>
                    ) : (
                      <>
                        <aside className="w-52 shrink-0 flex flex-col min-h-0 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-100/80 dark:bg-slate-900/80">
                          <div className="px-3 py-2 border-b border-slate-200 dark:border-slate-700">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                              Sections ({filingSectionList.length})
                            </p>
                            <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">Highest priority first</p>
                          </div>
                          <nav className="flex-1 overflow-y-auto p-1.5 space-y-1 scroll-smooth">
                            {filingSectionList.map((entry) => {
                              const isActive = activeSectionId === entry.id;
                              const isTopTier = entry.priority >= 85;
                              return (
                                <button
                                  key={entry.id}
                                  type="button"
                                  onClick={() => {
                                    setActiveSectionId(entry.id);
                                    setActiveEvidenceText(null);
                                  }}
                                  className={`w-full text-left rounded-lg px-2.5 py-2 transition duration-200 border ${
                                    isActive
                                      ? "bg-white dark:bg-[#31572C] text-[#31572C] dark:text-[#ECF39E] border-[#90A955]/45 shadow-sm"
                                      : "text-[#0f172a] dark:text-slate-300 border-transparent hover:bg-white/70 dark:hover:bg-slate-800 hover:border-slate-200 dark:hover:border-slate-600"
                                  }`}
                                >
                                  <span className="block text-[11px] font-bold leading-snug line-clamp-2">
                                    {entry.title}
                                  </span>
                                  <span className="mt-1 flex items-center gap-1.5 text-[9px] font-mono text-slate-500 dark:text-slate-400">
                                    <span
                                      className={`px-1 py-0.5 rounded ${
                                        isTopTier
                                          ? "bg-[#90A955]/20 text-[#4F772D] dark:text-[#ECF39E]"
                                          : "bg-slate-200/80 dark:bg-slate-800"
                                      }`}
                                    >
                                      P{entry.priority}
                                    </span>
                                    {entry.char_count != null && (
                                      <span>{(entry.char_count / 1000).toFixed(1)}k</span>
                                    )}
                                  </span>
                                </button>
                              );
                            })}
                          </nav>
                        </aside>

                        <div
                          ref={filingContentRef}
                          className="flex-grow min-h-0 overflow-y-auto bg-slate-50/50 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-700 rounded-lg p-6 leading-relaxed scroll-smooth"
                        >
                          {activeSectionId && (
                            <div className="mb-4 pb-3 border-b border-slate-200 dark:border-slate-700">
                              <h3 className="text-xs font-bold uppercase tracking-wide text-[#4F772D] dark:text-[#ECF39E]">
                                {filingSectionList.find((s) => s.id === activeSectionId)?.title ?? activeSectionId}
                              </h3>
                            </div>
                          )}
                          <div className="text-sm text-slate-700 dark:text-slate-300 leading-loose space-y-4">
                            {renderHighlightedText(
                              resolveFilingSectionText(activeReport.result.sections, activeSectionId),
                              activeSectionId
                            )}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* ── WORKSPACE 2: RISK FACTORS & SENTIMENT GAUGES ── */}
            {activeWorkspace === "audit" && (
              <>
                {/* Sentiment panels */}
                <div className="col-span-12 lg:col-span-5 glass-panel p-6 flex flex-col h-[calc(100vh-170px)] min-h-[500px] border-slate-200 dark:border-amber-400/20 bg-white dark:bg-slate-950/70 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-amber-400/15 pb-4 mb-5">
                    <h2 className="text-sm font-bold tracking-wider text-[#0f172a] dark:text-amber-200 uppercase flex items-center gap-2.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-[#4F772D]" />
                      Sentiment Analytics
                    </h2>
                  </div>

                  {!activeReport ? (
                    <div className="flex-grow flex flex-col items-center justify-center text-center p-8 space-y-4">
                      <div className="w-14 h-14 rounded-2xl bg-[#4F772D]/15 flex items-center justify-center">
                        <TrendingUp className="w-7 h-7 text-amber-400/60" />
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400 font-light">Load a filing to analyze sentiment and tone.</p>
                    </div>
                  ) : (
                    <div className="flex-grow flex flex-col justify-around h-full space-y-5">
                      {/* Tone Score Card */}
                      <div className="bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-[#90A955]/20 rounded-2xl p-6 flex flex-col items-center justify-center relative overflow-hidden shadow-inner">
                        <div className="absolute top-0 inset-x-0 h-1 bg-[#90A955]" />
                        
                        <span className="text-xs text-amber-300 font-extrabold tracking-widest uppercase mb-3">Net Tone Score</span>
                        <span className="text-5xl font-extrabold tracking-tight text-[#0f172a] dark:text-white mb-3 font-mono">
                          {activeReport.result?.sentiment?.score?.toFixed(2) ?? "0.00"}
                        </span>
                        <span className={`text-xs px-4 py-1.5 rounded-full font-bold uppercase tracking-wider border ${
                          (activeReport.result?.sentiment?.score ?? 0) > 0.2 ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/35" :
                          (activeReport.result?.sentiment?.score ?? 0) < -0.2 ? "bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/35" :
                          "bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/35"
                        }`}>
                          {activeReport.result?.sentiment?.classification ?? "Balanced"}
                        </span>
                      </div>

                      {/* Sentiment Metrics Bars */}
                      <div className="space-y-3">
                        {[
                          { label: "Optimism", key: "optimism", color: "bg-[#90A955]" },
                          { label: "Cautiousness", key: "cautiousness", color: "bg-[#4F772D]" },
                          { label: "Uncertainty", key: "uncertainty", color: "bg-[#31572C]" },
                          { label: "Pessimism", key: "pessimism", color: "bg-[#132A13]" }
                        ].map(metric => {
                          const value = ((activeReport.result?.sentiment?.metrics?.[metric.key as keyof typeof activeReport.result.sentiment.metrics] ?? 0) * 100).toFixed(0);
                          return (
                            <div key={metric.key} className="space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{metric.label}</span>
                                <span className="text-xs font-bold text-amber-500 dark:text-amber-300">{value}%</span>
                              </div>
                              <div className="w-full h-2.5 bg-slate-200 dark:bg-[#132A13]/60 rounded-full overflow-hidden">
                                <div 
                                  className={`h-full rounded-full ${metric.color} transition-all duration-700`}
                                  style={{ width: `${value}%` }}
                                />
                              </div>
                            </div>
                          );
                        })}
                      </div>

                      {/* Modern BarChart for Sentiment Analysis */}
                      <div className="h-[220px] flex items-center justify-center w-full mt-4">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={getRadarData()} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="rgba(255,255,255,0.05)" />
                            <XAxis type="number" domain={[0, 100]} hide />
                            <YAxis dataKey="subject" type="category" axisLine={false} tickLine={false} tick={{ fill: '#fbbf24', fontSize: 11, fontWeight: 500 }} width={80} />
                            <Tooltip cursor={{fill: 'rgba(255,255,255,0.02)'}} contentStyle={{ background: '#111827', border: '1px solid rgba(245, 158, 11, 0.3)', color: '#fff', fontSize: '11px', borderRadius: '8px' }} />
                            <Legend wrapperStyle={{ fontSize: '11px', paddingTop: '10px' }} />
                            <Bar dataKey="Target" name="Active Report" fill="#f59e0b" radius={[0, 4, 4, 0]} barSize={12} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}
                </div>

                {/* Risk lists */}
                <div className="col-span-12 lg:col-span-7 glass-panel p-6 flex flex-col h-[calc(100vh-170px)] min-h-[500px] border-slate-200 dark:border-rose-400/20 bg-white dark:bg-slate-950/70 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-rose-400/15 pb-4 mb-5">
                    <h2 className="text-sm font-bold tracking-wider text-[#0f172a] dark:text-rose-200 uppercase flex items-center gap-2.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-[#4F772D]" />
                      Risk Audit Summary
                    </h2>
                    {activeReport && (
                      <span className="text-xs font-bold text-[#31572C] dark:text-[#ECF39E] px-3 py-1 rounded-full bg-[#4F772D]/15 border border-[#90A955]/25 font-mono">
                        {activeReport.result?.risks?.length || 0} IDENTIFIED
                      </span>
                    )}
                  </div>

                  <div className="flex-1 overflow-y-auto space-y-3 p-1">
                    {!activeReport ? (
                      <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-3">
                        <div className="w-14 h-14 rounded-2xl bg-[#4F772D]/15 flex items-center justify-center">
                          <ShieldCheck className="w-7 h-7 text-rose-400/60" />
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 font-light">Load a filing to review risk factors.</p>
                      </div>
                    ) : (
                      (activeReport.result?.risks ?? []).map((risk: any, index: number) => {
                        const highlightId = `highlight-${activeReport.company_name}-${index}`;
                        const isActive = activeHighlightId === highlightId;
                        const isExpanded = expandedRiskIdx === index;
                        
                        return (
                          <div
                            key={index}
                            className={`p-4 rounded-lg border text-xs cursor-pointer transition-all duration-300 flex flex-col gap-2.5 relative overflow-hidden group ${
                              isActive
                                ? "bg-[#4F772D]/15 border-[#90A955] shadow-md"
                                : "bg-slate-50 hover:bg-slate-100 dark:bg-slate-900/70 dark:hover:bg-slate-900 border-slate-200 dark:border-slate-700"
                            }`}
                            onClick={() => {
                              setExpandedRiskIdx(isExpanded ? null : index);
                              setActiveHighlightId(highlightId);
                            }}
                          >
                            <div className={`absolute left-0 inset-y-0 w-1 transition-colors ${
                              risk.severity === "High" ? "bg-[#4F772D]" : "bg-[#90A955]"
                            }`} />

                            <div className="flex items-start justify-between pl-2">
                              <div className="flex-1">
                                <span className="text-sm font-extrabold text-rose-600 dark:text-rose-300 block tracking-widest uppercase mb-1.5">{risk.category}</span>
                                <h3 className="font-bold text-[#0f172a] dark:text-white text-sm tracking-tight leading-snug">{risk.risk_name}</h3>
                              </div>
                              <span className={`text-sm px-2.5 py-0.5 rounded font-extrabold tracking-widest uppercase whitespace-nowrap ml-2 ${
                                risk.severity === "High" 
                                  ? "bg-rose-500/15 text-rose-700 dark:text-rose-300 border border-rose-500/35" 
                                  : "bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/35"
                              }`}>
                                {risk.severity}
                              </span>
                            </div>

                            <p className="text-sm text-slate-700 dark:text-slate-300 font-light leading-relaxed pl-2">
                              <strong className="text-[#0f172a] dark:text-white font-semibold">Implication:</strong> {risk.implication}
                            </p>

                            {isExpanded && (
                              <div className="pl-3 mt-3 pt-3 border-t border-slate-200 dark:border-rose-400/15 text-xs text-slate-600 dark:text-slate-400 font-mono leading-relaxed bg-white dark:bg-slate-950/80 p-3 rounded-md">
                                <strong className="text-amber-500 dark:text-amber-300 block mb-1.5 uppercase text-xs tracking-wider font-sans">Evidence from Filing:</strong>
                                <p className="text-xs text-slate-700 dark:text-slate-300">&ldquo;{risk.evidence}&rdquo;</p>
                              </div>
                            )}

                            <div className="flex items-center justify-end text-xs text-rose-600 dark:text-rose-300 font-bold gap-1 pl-2 uppercase tracking-widest font-mono group-hover:text-amber-500 transition">
                              {isExpanded ? "Collapse" : "Details"}
                              <ChevronRight className={`w-3 h-3 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                            </div>
                          </div>
                        );
                      })
                    )}
                  </div>
                </div>

                {/* SLM filing narrative (map-reduce output) */}
                <div className="col-span-12 glass-panel p-6 flex flex-col max-h-[min(520px,45vh)] min-h-[200px] border-slate-200 dark:border-[#90A955]/20 bg-white dark:bg-slate-950/70 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-[#90A955]/15 pb-4 mb-4 shrink-0">
                    <h2 className="text-sm font-bold tracking-wider text-[#0f172a] dark:text-[#ECF39E] uppercase flex items-center gap-2.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-[#ECF39E]" />
                      SLM Filing Analysis
                    </h2>
                    <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      Post-pipeline narrative
                    </span>
                  </div>

                  <div className="flex-1 overflow-y-auto space-y-4 pr-1">
                    {!activeReport?.result ? (
                      <p className="text-xs text-slate-500 dark:text-slate-400 font-light text-center py-8">
                        Complete the ingestion pipeline to view executive summary and MD&amp;A insights.
                      </p>
                    ) : (
                      <>
                        {hasNarrativeText(activeReport.result.executive_summary) && (
                          <AnalysisNarrativeCard title="Executive Summary">
                            <MarkdownNarrative content={activeReport.result.executive_summary} />
                          </AnalysisNarrativeCard>
                        )}
                        {hasNarrativeText(activeReport.result.mda_summary) && (
                          <AnalysisNarrativeCard title="MD&A Highlights" accent="amber">
                            <MarkdownNarrative content={activeReport.result.mda_summary} />
                          </AnalysisNarrativeCard>
                        )}
                        {hasNarrativeText(activeReport.result.explainability) && (
                          <AnalysisNarrativeCard title="Explainability">
                            <MarkdownNarrative content={activeReport.result.explainability} />
                          </AnalysisNarrativeCard>
                        )}
                        {hasNarrativeText(activeReport.result.sentiment_shift_notes) && (
                          <AnalysisNarrativeCard title="Sentiment Shift Notes" accent="amber">
                            <MarkdownNarrative content={activeReport.result.sentiment_shift_notes} />
                          </AnalysisNarrativeCard>
                        )}
                        {(activeReport.result.future_challenges?.length ?? 0) > 0 && (
                          <AnalysisNarrativeCard title="Forward-Looking Challenges" accent="rose">
                            <ul className="space-y-2 text-sm text-slate-700 dark:text-slate-300 font-light list-disc pl-4">
                              {(activeReport.result.future_challenges as string[]).map((item, i) => (
                                <li key={i} className="leading-relaxed">
                                  {item}
                                </li>
                              ))}
                            </ul>
                          </AnalysisNarrativeCard>
                        )}
                        {!hasNarrativeText(activeReport.result.executive_summary) &&
                          !hasNarrativeText(activeReport.result.mda_summary) &&
                          !hasNarrativeText(activeReport.result.explainability) &&
                          !hasNarrativeText(activeReport.result.sentiment_shift_notes) &&
                          !(activeReport.result.future_challenges?.length) && (
                            <p className="text-xs text-slate-500 dark:text-slate-400 font-light text-center py-6">
                              No narrative summary was returned for this run. Check pipeline logs or re-run analysis.
                            </p>
                          )}
                      </>
                    )}
                  </div>
                </div>
              </>
            )}

            {/* ── WORKSPACE 3: CITATION CHAT (peer comparison via chat only) ── */}
            {activeWorkspace === "benchmarking" && (
              <>
                <div className="col-span-12 max-w-4xl mx-auto w-full glass-panel p-5 flex flex-col h-[calc(100vh-170px)] min-h-[500px] border-slate-200 dark:border-[#ECF39E]/20 bg-white dark:bg-slate-950/70 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-[#ECF39E]/15 pb-3 mb-4">
                    <h2 className="text-xs font-bold tracking-wider text-slate-800 dark:text-lime-200 uppercase flex items-center gap-2">
                      <Bot className="w-4 h-4 text-[#90A955]" />
                      Citation-Backed RAG Chatbot
                    </h2>
                  </div>

                  <div className="flex-grow overflow-y-auto space-y-4 mb-3.5 p-1">
                    {chatMessages.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-2">
                        <MessageSquare className="w-12 h-12 text-[#90A955]/25" />
                        <p className="text-xs text-slate-400 font-light">
                          Ask filing questions or run peer comparisons — the agent chooses tools (RAG, SEC scrape, web search) per question.
                        </p>
                      </div>
                    ) : (
                      chatMessages.map((msg: any) => (
                        <div key={msg.id} className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
                          <div className="flex items-center gap-1.5 mb-1 px-1 text-xs text-slate-500 font-mono flex-wrap">
                            {msg.role === "user" ? <User className="w-3 h-3 text-[#4F772D]" /> : <Bot className="w-3 h-3 text-[#90A955]" />}
                            {msg.role === "user" ? "Analyst" : "Aegis RAG Intelligence"}
                            {msg.role === "assistant" && msg.mode === "agent" && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-700 dark:text-violet-300 border border-violet-500/25">
                                Agent (THINK → Act → Observe)
                              </span>
                            )}
                            {msg.role === "assistant" && msg.mode === "comparison" && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/25">
                                Peer comparison (scrape + SLM)
                              </span>
                            )}
                            {msg.role === "assistant" && msg.mode === "rag" && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#90A955]/15 text-[#31572C] dark:text-[#ECF39E] border border-[#90A955]/25">
                                Filing RAG (vector DB)
                              </span>
                            )}
                          </div>
                          <div className={`p-3.5 rounded-2xl text-sm leading-relaxed max-w-[90%] shadow-sm ${
                            msg.role === "user" 
                              ? "bg-[#4F772D] text-white rounded-tr-none" 
                              : "bg-slate-100 dark:bg-[#90A955]/10 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-[#ECF39E]/20 rounded-tl-none font-light"
                          }`}>
                            {msg.role === "user" ? (
                              msg.content
                            ) : (
                              <div className="prose-custom">
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                  {msg.content}
                                </ReactMarkdown>
                              </div>
                            )}
                            
                            {msg.sourceSummary && Object.keys(msg.sourceSummary).length > 0 && (
                              <div className="mt-2 text-[10px] text-slate-500 dark:text-slate-400 font-mono space-y-0.5">
                                <span className="font-bold text-[#ECF39E] uppercase tracking-wider">Sources used</span>
                                {Object.entries(msg.sourceSummary).map(([key, count]) => (
                                  <div key={key}>
                                    • {key === "uploaded_filing" && "Uploaded filing PDF (ChromaDB)"}
                                    {key === "sec_edgar" && "SEC EDGAR live scrape"}
                                    {key === "prior_filing" && "Prior-period SEC scrape"}
                                    {key === "web_search" && "Web search scrape"}
                                    {!["uploaded_filing", "sec_edgar", "prior_filing", "web_search"].includes(key) && key}
                                    {" "}({count as number})
                                  </div>
                                ))}
                              </div>
                            )}
                            {msg.citations && msg.citations.length > 0 && (
                              <div className="mt-3 pt-2.5 border-t border-slate-200 dark:border-[#ECF39E]/15 space-y-2">
                                <span className="text-xs text-[#ECF39E] font-bold block uppercase tracking-widest font-mono">Audit source evidence</span>
                                <div className="space-y-2">
                                  {msg.citations.map((cit: any, cIdx: number) => (
                                    <button
                                      key={cIdx}
                                      type="button"
                                      onClick={() => handleRiskCardClick(cit.content, `highlight-${cit.company}-${cit.chunk_index}`)}
                                      className="w-full text-left text-xs p-2.5 rounded-lg bg-white hover:bg-slate-50 dark:bg-slate-900 dark:hover:bg-[#90A955]/10 border border-slate-200 dark:border-[#ECF39E]/30 transition active:scale-[0.99] shadow-sm"
                                    >
                                      <div className="flex items-center gap-1.5 font-mono text-[#4F772D] dark:text-[#90A955] font-bold mb-1">
                                        <Search className="w-2.5 h-2.5 shrink-0" />
                                        {cit.citation_id}
                                      </div>
                                      <div className="text-[10px] uppercase tracking-wide text-amber-700 dark:text-amber-300 font-semibold mb-1">
                                        {cit.source_label
                                          || (cit.source_type === "uploaded_filing"
                                            ? "Uploaded filing PDF (vector DB)"
                                            : cit.source_type === "sec_edgar"
                                              ? "SEC EDGAR scrape"
                                              : cit.source_type === "web_search"
                                                ? "Web search"
                                                : cit.source_type === "prior_filing"
                                                  ? "Prior-period SEC filing"
                                                  : "External source")}
                                      </div>
                                      <p className="text-slate-600 dark:text-slate-400 font-light leading-relaxed line-clamp-3">
                                        {cit.content}
                                      </p>
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}
                            {msg.statusSteps && msg.statusSteps.length > 0 && (
                              <details className="mt-3 pt-2.5 border-t border-slate-200 dark:border-[#ECF39E]/15">
                                <summary className="text-xs text-violet-600 dark:text-violet-300 font-bold uppercase tracking-widest font-mono cursor-pointer">
                                  Agent reasoning trail ({msg.statusSteps.length} steps)
                                </summary>
                                <ol className="mt-2 space-y-1 text-[11px] text-slate-500 dark:text-slate-400 font-mono list-decimal list-inside">
                                  {msg.statusSteps.map((step: string, sIdx: number) => (
                                    <li key={sIdx} className="leading-relaxed">{step}</li>
                                  ))}
                                </ol>
                              </details>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                    {isChatLoading && (
                      <div className="flex items-center space-x-2 text-sm text-[#ECF39E] font-mono p-2 animate-pulse">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Agent running tools...</span>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>

                  <form onSubmit={handleSendMessage} className="flex gap-2">
                    <input
                      type="text"
                      placeholder='Compare vs AMD, ask about risks, margins...'
                      value={chatInput}
                      onChange={e => setChatInput(e.target.value)}
                      disabled={!activeReportId || isChatLoading}
                      className="flex-grow bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-xl px-3 py-2 text-xs text-[#0f172a] dark:text-white placeholder-slate-400 focus:outline-none focus:border-[#ECF39E]/60 transition"
                    />
                    <button
                      type="submit"
                      disabled={!activeReportId || !chatInput.trim() || isChatLoading}
                      className="p-2.5 rounded-xl bg-[#4F772D] text-white hover:bg-[#31572C] active:scale-95 transition disabled:opacity-50 flex items-center justify-center shadow-sm"
                    >
                      <Send className="w-3.5 h-3.5" />
                    </button>
                  </form>
                </div>
              </>
            )}

          </main>
        </div>
      )}
    </div>
  );
}

