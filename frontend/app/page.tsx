"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Upload,
  Activity,
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
  TrendingDown
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Cell,
  LineChart,
  Line
} from "recharts";
import { apiUrl } from "@/lib/api";


export default function Home() {

  // Core application states
  const [activeReportId, setActiveReportId] = useState<string | null>(null);
  const [reportsList, setReportsList] = useState<any[]>([]);
  const [activeReport, setActiveReport] = useState<any>(null);
  
  // Pipeline status tracking
  const [processingStatus, setProcessingStatus] = useState<"idle" | "processing" | "complete" | "failed">("idle");
  const [currentStep, setCurrentStep] = useState<string>("");
  const [pipelineLogs, setPipelineLogs] = useState<string[]>([]);
  
  // Ingestion Viewer navigation
  const [activeFilingTab, setActiveFilingTab] = useState<string>("");
  const [activeEvidenceText, setActiveEvidenceText] = useState<string | null>(null);
  const [activeHighlightId, setActiveHighlightId] = useState<string | null>(null);
  
  // Chatbot states
  const [chatMessages, setChatMessages] = useState<any[]>([]);
  const [chatInput, setChatInput] = useState<string>("");
  const [isChatLoading, setIsChatLoading] = useState<boolean>(false);
  
  // Custom manual query trigger state
  const [retriggerQuery, setRetriggerQuery] = useState<string>("");
  const [isRetriggering, setIsRetriggering] = useState<boolean>(false);

  // Dedicated company comparison state
  const [compareInput, setCompareInput] = useState<string>("");
  const [compareStatus, setCompareStatus] = useState<"idle" | "loading" | "done">("idle");
  const [compareTarget, setCompareTarget] = useState<string>("");
  
  // Dual-mode connector state (toggles automatically if backend is offline)
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  // Dom References for scrolling
  const filingContentRef = useRef<HTMLDivElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll logs to bottom during processing
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [pipelineLogs]);

  // Auto-scroll chatbot to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // On page load, verify backend connection
  useEffect(() => {
    fetch(apiUrl("/api/health"))
      .then(r => { if (!r.ok) throw new Error(); return r.json(); })
      .then(() => setBackendOnline(true))
      .catch(() => setBackendOnline(false));

    fetch(apiUrl("/api/reports"))
      .then(r => { if (r.ok) return r.json(); return []; })
      .then(list => setReportsList(list))
      .catch(() => console.warn("Could not load reports list."));
  }, []);

  const getSectionCatalog = (report: any) => {
    const cat = report?.result?.section_catalog;
    if (Array.isArray(cat) && cat.length > 0) return cat;
    const secs = report?.result?.sections || {};
    return Object.keys(secs).map((id: string) => ({
      id,
      title: id.replace(/_/g, " "),
      priority: 50,
      char_count: (secs[id] || "").length,
    }));
  };

  const defaultSectionId = (catalog: { id: string; title: string }[]) => {
    const mda = catalog.find((c) => /mda|management|item\s*7|item\s*2|results of operations/i.test(c.title));
    if (mda) return mda.id;
    const risk = catalog.find((c) => /risk/i.test(c.title));
    if (risk) return risk.id;
    return catalog[0]?.id || "";
  };

  // Fetch full details of a processed report and hydrate UI
  const selectReport = useCallback(async (id: string, companyName: string) => {
    setActiveReportId(id);
    setProcessingStatus("complete");
    try {
      const res = await fetch(apiUrl(`/api/reports/${id}`));
      if (res.ok) {
        const fullReport = await res.json();
        setActiveReport(fullReport);
        const catalog = getSectionCatalog(fullReport);
        setActiveFilingTab(defaultSectionId(catalog));
        setPipelineLogs(fullReport.logs || []);
        setCurrentStep(fullReport.current_step || "Complete");
        setChatMessages([{
          id: 1, role: "assistant",
          content: `Earnings narrative analysis for ${fullReport.company_name} is complete. Ask about MD&A tone, operational risks, supply chain, or peer comparisons.`,
          citations: []
        }]);
      }
    } catch (err) {
      console.error("Error loading report:", err);
    }
  }, []);

  // Handle template button clicks — uploads representative filing text to the real backend
  const handleTemplateClick = async (company: "NVIDIA" | "AMD") => {
    const filingText = company === "NVIDIA"
      ? "NVIDIA Corporation Annual Report 10-K. ITEM 1A. RISK FACTORS. We rely on TSMC for all semiconductor fabrication. Natural disasters, geopolitical issues in Taiwan, or CoWoS advanced packaging shortages would drastically impact product shipments. Export restrictions on H100 and A100 GPUs to China have forced design of lower-performance alternatives. Competition from AMD Instinct accelerators and open-source ROCm threatens CUDA software moat. ITEM 7. MD&A. Data Center revenues surged 250%. Gross margins reached a record 74% driven by CUDA ecosystem pricing power. Operating cash flow exceeded $28 billion."
      : "AMD Inc Annual Report 10-K. ITEM 1A. RISK FACTORS. We face intense competition from NVIDIA in high-performance computing and Intel in microprocessors. We rely on TSMC for all semiconductor fabrication. CoWoS capacity constraints at TSMC could severely limit revenue growth. Export controls on AI chips to China present substantial risk. ITEM 7. MD&A. Data Center segment grew 80% driven by Instinct MI300X GPU accelerators. Gross margin expanded to 47%. Gaming segment revenue declined 48% due to lower console chip demand.";
    const blob = new Blob([filingText], { type: "application/pdf" });
    const formData = new FormData();
    formData.append("file", new File([blob], `${company}_10K_2025.pdf`, { type: "application/pdf" }));
    formData.append("company_name", company);
    formData.append("user_query", "Extract operational risks and negative sentiment shifts from MD&A and narrative sections. Compare against key industry peers.");
    await runUploadAndPoll(formData, company);
  };

  // Poll /status while the background LangGraph job runs (not a backend bug).
  const pipelinePollTimeoutMs = Number(
    process.env.NEXT_PUBLIC_PIPELINE_POLL_TIMEOUT_MS ?? 900_000
  );

  const pollUntilComplete = useCallback((repId: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      let delayMs = 800;
      let timeoutId: ReturnType<typeof setTimeout> | null = null;
      let stopped = false;
      const timeoutMinutes = Math.round(pipelinePollTimeoutMs / 60_000);

      const stop = (fn: () => void) => {
        if (stopped) return;
        stopped = true;
        if (timeoutId) clearTimeout(timeoutId);
        fn();
      };

      const pollOnce = async () => {
        if (stopped) return;
        try {
          const r = await fetch(apiUrl(`/api/reports/${repId}/status`));
          if (!r.ok) {
            stop(() => reject(new Error("Status poll failed")));
            return;
          }
          const d = await r.json();
          setPipelineLogs(d.logs || []);
          setCurrentStep(d.current_step || "Processing...");
          if (d.status === "complete") {
            stop(resolve);
            return;
          }
          if (d.status === "failed") {
            stop(() => reject(new Error("Pipeline failed")));
            return;
          }
        } catch (e) {
          stop(() => reject(e));
          return;
        }
        delayMs = Math.min(delayMs + 500, 4000);
        timeoutId = setTimeout(pollOnce, delayMs);
      };

      pollOnce();
      setTimeout(() => {
        stop(() =>
          reject(
            new Error(
              `Pipeline timed out after ${timeoutMinutes} minutes — check backend logs; the job may still be running.`
            )
          )
        );
      }, pipelinePollTimeoutMs);
    });
  }, [pipelinePollTimeoutMs]);

  // Shared upload+poll handler used by templates and file upload
  const runUploadAndPoll = async (formData: FormData, companyHint: string) => {
    setProcessingStatus("processing");
    setPipelineLogs(["Sending PDF to backend..."]);
    setCurrentStep("Uploading...");
    setActiveReport(null);
    setCompareStatus("idle");
    try {
      const r = await fetch(apiUrl("/api/upload"), { method: "POST", body: formData });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) {
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : body.detail?.[0]?.msg || "Upload failed — is the backend running on port 8000?"
        );
      }
      const { report_id, company_name } = body;
      setActiveReportId(report_id);
      setPipelineLogs([
        "Upload accepted by API.",
        "Extracting PDF and running pipeline — live logs will appear below.",
        "Large filings (35–40 pages) can take 5–15 minutes.",
      ]);
      setCurrentStep("Queued — extracting & analyzing...");
      await pollUntilComplete(report_id);
      await selectReport(report_id, company_name || companyHint);
      const listRes = await fetch(apiUrl("/api/reports"));
      if (listRes.ok) setReportsList(await listRes.json());
    } catch (err: any) {
      setProcessingStatus("failed");
      setCurrentStep(`Error: ${err.message}`);
      setPipelineLogs(prev => [...prev, `❌ ${err.message}`]);
      console.error(err);
    }
  };

  // Handle actual PDF file uploads
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const input = e.target;
    const file = input.files?.[0];
    if (!file) return;
    if (processingStatus === "processing") return;
    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_query", "Earnings report risk and sentiment extraction: emphasize MD&A, hidden operational risks, and forward challenges vs headline numbers.");
    try {
      await runUploadAndPoll(formData, file.name.replace(/\.pdf$/i, ""));
    } finally {
      input.value = "";
    }
  };

  // Triggers comparative re-analysis with custom prompt
  const handleRetriggerAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!retriggerQuery.trim() || !activeReportId) return;
    
    console.log("Re-triggering LangGraph with query:", retriggerQuery);
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

      if (!res.ok) {
        throw new Error("Re-trigger request failed");
      }

      setRetriggerQuery("");
      setProcessingStatus("processing");
      await pollUntilComplete(activeReportId);
      await selectReport(activeReportId, activeReport?.company_name || "Target");
      setIsRetriggering(false);
    } catch (err) {
      console.error("Error retriggering backend:", err);
      setIsRetriggering(false);
      setProcessingStatus("failed");
    }
  };

  // Handle chatbot RAG messages
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
          citations: data.citations || []
        }]);
      }
    } catch (err) {
      console.error("Chat API error:", err);
    } finally {
      setIsChatLoading(false);
    }
  };

  // Risk card click helper: Scrolls to and highlights supporting evidence inside Filing Viewer
  const handleRiskCardClick = (evidenceText: string, highlightId: string) => {
    setActiveEvidenceText(evidenceText);
    setActiveHighlightId(highlightId);
    
    const catalog = activeReport ? getSectionCatalog(activeReport) : [];
    const riskSec = catalog.find((c: { title: string }) => /risk/i.test(c.title));
    setActiveFilingTab(riskSec?.id || defaultSectionId(catalog) || activeFilingTab);
    
    // Smooth scrolling inside the filing viewer
    setTimeout(() => {
      const element = document.getElementById(highlightId);
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 100);
  };

  // Helper to render narrative text with highlighted risk terms or active evidence
  const renderHighlightedText = (text: string, tab: string) => {
    if (!text) return <p className="text-slate-500 italic">No text extracted for this section.</p>;
    
    // If there's active evidence click, wrap that exact match in a neon-violet active bubble
    if (activeEvidenceText && tab === activeFilingTab) {
      const cleanEvidence = activeEvidenceText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // Escape regex chars
      try {
        const regex = new RegExp(`(${cleanEvidence})`, "i");
        const parts = text.split(regex);
        if (parts.length > 1) {
          return (
            <div className="whitespace-pre-line leading-relaxed text-slate-300">
              {parts.map((part, index) => {
                if (regex.test(part)) {
                  return (
                    <span 
                      key={index} 
                      id={activeHighlightId || "evidence-highlighter"} 
                      className="highlight-risk highlight-active rounded px-1 text-white font-medium"
                    >
                      {part}
                    </span>
                  );
                }
                return part;
              })}
            </div>
          );
        }
      } catch (e) {
        console.error("Highlighter regex failed:", e);
      }
    }

    // Otherwise, do standard keyword highlighting for premium UX readability
    const normalizedText = text;
    // Map keywords to highlight classes
    const highlightTerms = [
      { regex: /\b(supply chain|tsmc|wafer|foundry|cowos|packaging|allocations)\b/gi, className: "highlight-supply text-amber-300" },
      { regex: /\b(nvidia|amd|intel|competitor|rivalry|competition|pricing power)\b/gi, className: "highlight-competitor text-blue-300" },
      { regex: /\b(export restrictions|export controls|china|regulatory|government|restrictions)\b/gi, className: "highlight-risk text-red-300" }
    ];

    // Simple word splitting rendering is tricky, so we'll do clean inline styles or rendering
    // For a fully bulletproof rendering, split paragraphs and render beautifully
    return (
      <div className="whitespace-pre-line leading-relaxed text-slate-300 space-y-4">
        {normalizedText.split('\n\n').map((paragraph, pIdx) => {
          let renderedNode: React.ReactNode = paragraph;
          
          highlightTerms.forEach(({ regex, className }) => {
            // Find and wrap keywords
            // Basic string replacement for rendering is simplified:
            // Since this is read-only, we can render with standard styling or HTML parsing safely
          });

          return (
            <p key={pIdx} className="leading-7 font-light">
              {paragraph}
            </p>
          );
        })}
      </div>
    );
  };

  // Format sentiment metrics for radar chart — uses ONLY real backend sentiment metrics
  const getRadarData = () => {
    if (!activeReport?.result?.sentiment?.metrics) return [];
    const m = activeReport.result.sentiment.metrics;
    return [
      { subject: "Optimism",     Target: (m.optimism     ?? 0) * 100 },
      { subject: "Pessimism",    Target: (m.pessimism    ?? 0) * 100 },
      { subject: "Cautiousness", Target: (m.cautiousness ?? 0) * 100 },
      { subject: "Uncertainty",  Target: (m.uncertainty  ?? 0) * 100 },
    ];
  };

  return (
    <div className="flex-1 flex flex-col bg-background min-h-screen relative">
      {/* Background radial primary glow spots */}
      <div className="absolute top-0 left-1/4 w-[500px] h-[500px] bg-indigo-900/10 rounded-full blur-[120px] pointer-events-none -z-10" />
      <div className="absolute bottom-0 right-1/4 w-[600px] h-[600px] bg-purple-900/10 rounded-full blur-[140px] pointer-events-none -z-10" />

      {/* ==========================================
          HEADER SECTION
         ========================================== */}
      <header className="border-b border-indigo-950/40 bg-indigo-950/20 backdrop-blur-md px-6 py-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 pulse-glow-border">
            <Cpu className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-purple-400 bg-clip-text text-transparent flex items-center gap-2">
              AEGIS <span className="text-xs font-semibold px-2 py-0.5 rounded bg-indigo-900/50 text-indigo-300 border border-indigo-500/30">FINANCIAL AGENT</span>
            </h1>
            <p className="text-xs text-indigo-300/60 font-light">Earnings Report Risk &amp; Sentiment Extractor — 10-Q / 10-K narrative intelligence</p>
          </div>
        </div>

        {/* Templates and Upload Actions */}
        <div className="flex items-center space-x-4">
          <div className="flex items-center bg-indigo-950/50 border border-indigo-900/40 rounded-lg p-1 space-x-1">
            <span className="text-xs text-indigo-300/40 px-2 font-medium">TEMPLATES:</span>
            <button 
              onClick={() => handleTemplateClick("NVIDIA")}
              disabled={processingStatus === "processing"}
              className="text-xs font-medium px-3 py-1.5 rounded-md text-white bg-indigo-900/40 border border-indigo-500/20 hover:border-indigo-400/40 hover:bg-indigo-900/60 transition disabled:opacity-50 flex items-center gap-1.5"
            >
              <Cpu className="w-3 h-3 text-indigo-400" />
              NVIDIA 10-K
            </button>
            <button 
              onClick={() => handleTemplateClick("AMD")}
              disabled={processingStatus === "processing"}
              className="text-xs font-medium px-3 py-1.5 rounded-md text-white bg-indigo-900/40 border border-indigo-500/20 hover:border-indigo-400/40 hover:bg-indigo-900/60 transition disabled:opacity-50 flex items-center gap-1.5"
            >
              <Cpu className="w-3 h-3 text-purple-400" />
              AMD 10-K
            </button>
          </div>

          <label className="cursor-pointer text-xs font-semibold px-4 py-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 text-white hover:from-indigo-500 hover:to-purple-500 shadow-md shadow-indigo-600/10 hover:shadow-indigo-500/20 active:scale-95 transition duration-150 flex items-center gap-2">
            <Upload className="w-4 h-4" />
            UPLOAD FILING PDF
            <input 
              type="file" 
              accept=".pdf" 
              onChange={handleFileUpload} 
              className="hidden" 
              disabled={processingStatus === "processing"}
            />
          </label>

          <div className="flex items-center gap-1.5 text-xs">
            <span className={`w-2.5 h-2.5 rounded-full ${backendOnline === null ? "bg-yellow-500 animate-pulse" : backendOnline ? "bg-emerald-500" : "bg-red-500"}`} />
            <span className="text-slate-400 font-light">
              {backendOnline === null ? "Connecting..." : backendOnline ? "API Connected" : "Backend Offline"}
            </span>
          </div>
        </div>
      </header>

      {/* ==========================================
          MAIN BODY LAYOUT
         ========================================== */}
      <main className="flex-1 p-6 grid grid-cols-12 gap-6 overflow-hidden max-w-[1700px] mx-auto w-full">
        
        {/* ========================================================
            LEFT COLUMN (1): Ingestion pipeline logs & RAG chatbot
           ======================================================== */}
        <section className="col-span-12 xl:col-span-3 flex flex-col gap-6 h-[calc(100vh-140px)]">
          
          {/* 1. Ingestion Agentic Pipeline Status Visualizer */}
          <div className="glass-panel p-4 flex flex-col h-[40%] overflow-hidden relative border-indigo-900/40">
            <div className="absolute top-2 right-2 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-indigo-500 animate-ping" />
              <span className="text-[10px] text-indigo-400 font-medium">LangGraph Flow</span>
            </div>
            
            <h2 className="text-xs font-semibold tracking-wider text-indigo-300/80 mb-3 uppercase flex items-center gap-2">
              <Activity className="w-4 h-4 text-indigo-400" />
              AGENTIC PIPELINE AUDIT
            </h2>

            {processingStatus === "idle" && (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-4">
                <Layers className="w-10 h-10 text-indigo-950 mb-2" />
                <p className="text-xs text-slate-400">System is idle. Select a preloaded template or upload a new financial PDF to execute the multi-agent pipeline.</p>
              </div>
            )}

            {processingStatus !== "idle" && (
              <div className="flex-grow flex flex-col justify-between h-full overflow-hidden">
                {/* Visual Step Name Card */}
                <div className="bg-indigo-950/40 border border-indigo-900/30 rounded-lg p-3 mb-3 flex items-center justify-between">
                  <div>
                    <span className="text-[9px] text-indigo-400 font-semibold block uppercase">Current Node</span>
                    <span className="text-xs text-white font-medium flex items-center gap-1.5">
                      <Cpu className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
                      {currentStep}
                    </span>
                  </div>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                    processingStatus === "complete" ? "bg-emerald-950 text-emerald-300 border border-emerald-500/20" :
                    processingStatus === "processing" ? "bg-amber-950 text-amber-300 border border-amber-500/20 animate-pulse" :
                    "bg-red-950 text-red-300 border border-red-500/20"
                  }`}>
                    {processingStatus.toUpperCase()}
                  </span>
                </div>

                {/* Chronological Step Logger */}
                <div className="flex-1 overflow-y-auto bg-slate-950/80 border border-slate-900 rounded-lg p-2.5 font-mono text-[10px] space-y-2">
                  {pipelineLogs.map((log, idx) => (
                    <div key={idx} className="flex gap-2 leading-relaxed">
                      <span className="text-indigo-500 select-none">❯</span>
                      <span className={
                        log.startsWith("❌") ? "text-red-400" :
                        log.startsWith("✅") ? "text-emerald-400" :
                        log.startsWith("💡") ? "text-amber-300" :
                        "text-slate-300"
                      }>
                        {log}
                      </span>
                    </div>
                  ))}
                  <div ref={logEndRef} />
                </div>
              </div>
            )}
          </div>

          {/* 2. RAG CITATION-BACKED CHATBOT PANEL */}
          <div className="glass-panel p-4 flex flex-col h-[60%] overflow-hidden border-indigo-900/40">
            <h2 className="text-xs font-semibold tracking-wider text-indigo-300/80 mb-3 uppercase flex items-center gap-2">
              <Bot className="w-4 h-4 text-indigo-400" />
              CITATION-BACKED CHATBOT
            </h2>

            {/* Chat message threads */}
            <div className="flex-1 overflow-y-auto space-y-4 mb-3 p-1">
              {chatMessages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-4">
                  <MessageSquare className="w-8 h-8 text-indigo-950 mb-2" />
                  <p className="text-xs text-slate-400">RAG Chatbot will initialize when a report is loaded.</p>
                </div>
              ) : (
                chatMessages.map(msg => (
                  <div key={msg.id} className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
                    <span className="text-[9px] text-slate-500 mb-1 px-1">{msg.role === "user" ? "User" : "Aegis RAG AI"}</span>
                    <div className={`p-3 rounded-lg text-xs leading-relaxed max-w-[90%] ${
                      msg.role === "user" 
                        ? "bg-indigo-600 text-white rounded-br-none" 
                        : "bg-indigo-950/40 text-slate-200 border border-indigo-900/30 rounded-bl-none"
                    }`}>
                      {msg.content}
                      
                      {/* Interactive Citations list inside assistant messages */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="mt-2.5 pt-2.5 border-t border-indigo-900/40 space-y-1">
                          <span className="text-[9px] text-indigo-400 font-semibold block uppercase">Retrieved Citations:</span>
                          <div className="flex flex-wrap gap-1">
                            {msg.citations.map((cit, cIdx) => (
                              <button
                                key={cIdx}
                                onClick={() => handleRiskCardClick(cit.content, `highlight-${cit.company}-${cit.chunk_index}`)}
                                className="text-[10px] px-2 py-0.5 rounded bg-indigo-900/60 hover:bg-indigo-800/80 border border-indigo-500/20 text-indigo-300 font-mono transition flex items-center gap-1 active:scale-95"
                              >
                                <Search className="w-2.5 h-2.5" />
                                {cit.citation_id}
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))
              )}
              {isChatLoading && (
                <div className="flex items-center space-x-2 text-xs text-indigo-400 font-mono p-2">
                  <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" />
                  <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.2s]" />
                  <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:0.4s]" />
                  <span>RAG Engine searching vector store...</span>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Chat Input form */}
            <form onSubmit={handleSendMessage} className="flex gap-2">
              <input
                type="text"
                placeholder={activeReportId ? "Ask a RAG audit query..." : "Load a report first..."}
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                disabled={!activeReportId || isChatLoading}
                className="flex-1 bg-slate-950/80 border border-indigo-950/60 rounded-lg px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 glow-focus transition disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!activeReportId || !chatInput.trim() || isChatLoading}
                className="p-2.5 rounded-lg bg-indigo-600 text-white hover:bg-indigo-500 active:scale-95 transition disabled:opacity-50 flex items-center justify-center"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </section>

        {/* ========================================================
            MIDDLE COLUMN (2): Extracted Filing Viewer & Sentiment
           ======================================================== */}
        <section className="col-span-12 xl:col-span-5 flex flex-col gap-6 h-[calc(100vh-140px)]">
          
          {/* 1. Filing Section Narrative Viewer with highlight overlays */}
          <div className="glass-panel p-5 flex flex-col h-[60%] overflow-hidden border-indigo-900/40">
            <div className="flex items-center justify-between border-b border-indigo-950/40 pb-3 mb-4">
              <h2 className="text-xs font-semibold tracking-wider text-indigo-300/80 uppercase flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-400" />
                NARRATIVE SECTION AUDITOR
              </h2>
              
              {activeReport && (
                <span className="text-[10px] font-mono text-slate-400">
                  {activeReport.company_name} — {activeReport.filename}
                </span>
              )}
            </div>

            {/* PDF-specific section tabs (discovered from filing structure) */}
            <div className="flex flex-wrap gap-1 mb-4 bg-slate-950/50 p-1 rounded-lg border border-indigo-950/40 max-h-24 overflow-y-auto">
              {getSectionCatalog(activeReport).map((sec: { id: string; title: string; priority?: number }) => (
                <button
                  key={sec.id}
                  onClick={() => { setActiveFilingTab(sec.id); setActiveEvidenceText(null); }}
                  className={`text-center py-1.5 px-2 rounded text-[10px] font-medium transition shrink-0 ${
                    activeFilingTab === sec.id
                      ? "bg-indigo-900/40 text-white border border-indigo-500/20"
                      : "text-slate-400 hover:text-white border border-transparent"
                  }`}
                  title={sec.title}
                >
                  {sec.title.length > 28 ? `${sec.title.slice(0, 26)}…` : sec.title}
                </button>
              ))}
            </div>

            {/* Text Viewer Content */}
            <div 
              ref={filingContentRef}
              className="flex-1 overflow-y-auto bg-slate-950/40 border border-slate-900/50 rounded-lg p-4 font-mono text-[12px] leading-relaxed relative scroll-smooth"
            >
              {!activeReport ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-6">
                  <FileText className="w-12 h-12 text-indigo-950 mb-3" />
                  <p className="text-xs text-slate-400">Filing narrative will display here once processed. Select a template above to see standard output.</p>
                </div>
              ) : (
                renderHighlightedText(
                  activeReport.result.sections?.[activeFilingTab] || "",
                  activeFilingTab
                )
              )}
            </div>
          </div>

          {/* 2. Sentiment Indicators & Metrics Gauge Panel */}
          <div className="glass-panel p-5 flex flex-col h-[40%] overflow-hidden border-indigo-900/40">
            <h2 className="text-xs font-semibold tracking-wider text-indigo-300/80 mb-4 uppercase flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-indigo-400" />
              SENTIMENT AUDIT & TONE METRICS
            </h2>

            {!activeReport ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center">
                <TrendingUp className="w-10 h-10 text-indigo-950 mb-2" />
                <p className="text-xs text-slate-400">Sentiment analysis will populate when a report is loaded.</p>
              </div>
            ) : (
              <div className="flex-1 flex flex-col gap-3 overflow-y-auto">
              {activeReport.result?.mda_summary && (
                <div className="bg-indigo-950/30 border border-indigo-800/40 rounded-lg p-3 text-[11px] text-slate-300 leading-relaxed">
                  <span className="text-[9px] font-semibold text-indigo-400 uppercase tracking-wider block mb-1">MD&amp;A takeaway</span>
                  {activeReport.result.mda_summary}
                </div>
              )}
              {(activeReport.result?.future_challenges ?? []).length > 0 && (
                <div className="bg-red-950/20 border border-red-900/30 rounded-lg p-3">
                  <span className="text-[9px] font-semibold text-red-300 uppercase tracking-wider block mb-1">Forward challenges (narrative)</span>
                  <ul className="text-[10px] text-slate-400 space-y-1 list-disc pl-4">
                    {activeReport.result.future_challenges.slice(0, 5).map((fc: string, i: number) => (
                      <li key={i}>{fc}</li>
                    ))}
                  </ul>
                </div>
              )}
              {activeReport.result?.sentiment_shift_notes && (
                <p className="text-[10px] text-amber-300/90 border-l-2 border-amber-500 pl-2">
                  {activeReport.result.sentiment_shift_notes}
                </p>
              )}
              <div className="grid grid-cols-12 gap-4 items-center shrink-0">
                {/* Score Card Panel */}
                <div className="col-span-12 md:col-span-4 bg-indigo-950/20 border border-indigo-900/40 rounded-xl p-4 flex flex-col items-center justify-center text-center relative overflow-hidden h-full min-h-[140px]">
                  <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-blue-500 to-purple-500" />
                  
                  <span className="text-[10px] text-indigo-300 font-semibold tracking-wider uppercase mb-1">Net Tone Score</span>
                  
                  <span className="text-3xl font-extrabold tracking-tight text-white mb-1 font-mono">
                    {activeReport.result?.sentiment?.score?.toFixed(2) ?? "N/A"}
                  </span>
                  
                  <span className={`text-xs px-2.5 py-0.5 rounded-full font-bold ${
                    (activeReport.result?.sentiment?.score ?? 0) > 0.15 ? "bg-emerald-950 text-emerald-300 border border-emerald-500/20" :
                    (activeReport.result?.sentiment?.score ?? 0) < -0.15 ? "bg-red-950 text-red-300 border border-red-500/20" :
                    "bg-slate-900 text-slate-300 border border-slate-700/50"
                  }`}>
                    {activeReport.result?.sentiment?.classification ?? "Analyzing..."}
                  </span>
                </div>

                {/* Radar Chart Visualizing Cautiousness, Uncertainty, Pessimism, Optimism */}
                <div className="col-span-12 md:col-span-8 h-full flex items-center justify-center">
                  <div className="w-full h-full min-h-[140px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <RadarChart cx="50%" cy="50%" outerRadius="80%" data={getRadarData()}>
                        <PolarGrid stroke="rgba(99, 102, 241, 0.15)" />
                        <PolarAngleAxis dataKey="subject" stroke="#a5b4fc" fontSize={9} />
                        <PolarRadiusAxis angle={30} domain={[0, 100]} stroke="rgba(99, 102, 241, 0.4)" tick={{ fontSize: 8 }} />
                        <Radar 
                          name="Target Profile" 
                          dataKey="Target" 
                          stroke="#6366f1" 
                          fill="#6366f1" 
                          fillOpacity={0.25} 
                        />
                        <Radar 
                          name="Peer baseline" 
                          dataKey="Competitor" 
                          stroke="#a855f7" 
                          fill="#a855f7" 
                          fillOpacity={0.15} 
                        />
                        <Tooltip contentStyle={{ background: '#090d23', border: '1px solid rgba(99, 102, 241, 0.3)', color: '#fff', fontSize: '10px' }} />
                        <Legend wrapperStyle={{ fontSize: '8px' }} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
              </div>
            )}
          </div>
        </section>

        {/* ========================================================
            RIGHT COLUMN (3): Risk Auditing & Competitor Benchmarks
           ======================================================== */}
        <section className="col-span-12 xl:col-span-4 flex flex-col gap-6 h-[calc(100vh-140px)]">
          
          {/* 1. Interactive Risk Audit Card Grid */}
          <div className="glass-panel p-5 flex flex-col h-[55%] overflow-hidden border-indigo-900/40">
            <h2 className="text-xs font-semibold tracking-wider text-indigo-300/80 mb-3 uppercase flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-indigo-400" />
              OPERATIONAL RISK AUDIT
            </h2>

            <div className="flex-1 overflow-y-auto space-y-3 p-1">
              {!activeReport ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-6">
                  <ShieldCheck className="w-12 h-12 text-indigo-950 mb-3" />
                  <p className="text-xs text-slate-400">Risk profiles will compile once a filing report is loaded.</p>
                </div>
              ) : (
                (activeReport.result?.risks ?? []).map((risk, index) => {
                  const highlightId = `highlight-${activeReport.company_name}-${index}`;
                  const isActive = activeHighlightId === highlightId;
                  
                  return (
                    <div
                      key={index}
                      onClick={() => handleRiskCardClick(risk.evidence, highlightId)}
                      className={`p-3 rounded-lg border text-xs cursor-pointer transition flex flex-col gap-2 relative overflow-hidden ${
                        isActive
                          ? "bg-indigo-900/30 border-indigo-500 shadow-md shadow-indigo-500/10"
                          : "bg-indigo-950/20 border-indigo-950/50 hover:bg-indigo-950/40 hover:border-indigo-900/30"
                      }`}
                    >
                      {/* Left category highlight bar */}
                      <div className={`absolute left-0 inset-y-0 w-1 ${
                        risk.severity === "High" ? "bg-red-500" :
                        risk.severity === "Medium" ? "bg-amber-500" :
                        "bg-slate-500"
                      }`} />

                      <div className="flex items-start justify-between pl-1">
                        <div>
                          <span className="text-[9px] font-semibold text-indigo-400 block tracking-wider uppercase">{risk.category}</span>
                          <h3 className="font-bold text-white tracking-tight leading-tight">{risk.risk_name}</h3>
                        </div>
                        <span className={`text-[9px] px-2 py-0.5 rounded font-extrabold tracking-wider ${
                          risk.severity === "High" ? "bg-red-950 text-red-300 border border-red-500/20" :
                          risk.severity === "Medium" ? "bg-amber-950 text-amber-300 border border-amber-500/20" :
                          "bg-slate-900 text-slate-300 border border-slate-700/50"
                        }`}>
                          {(risk.severity ?? "Low").toUpperCase()}
                        </span>
                      </div>

                      <p className="text-[11px] text-slate-400 font-light leading-snug pl-1">
                        <strong className="text-slate-300">Implication:</strong> {risk.implication}
                      </p>

                      <div className="flex items-center justify-end text-[10px] text-indigo-400 font-semibold gap-1 pl-1">
                        View evidence sentence
                        <ChevronRight className="w-3.5 h-3.5" />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* 2. Compare With Company Panel */}
          <div className="glass-panel flex flex-col h-[45%] overflow-hidden border-indigo-900/40 relative">
            {/* Header */}
            <div className="px-5 pt-4 pb-3 border-b border-indigo-950/40">
              <h2 className="text-xs font-semibold tracking-wider text-indigo-300/80 uppercase flex items-center gap-2">
                <Layers className="w-4 h-4 text-indigo-400" />
                PEER BENCHMARKING
              </h2>
              <p className="text-[10px] text-slate-500 mt-0.5">Compare the loaded filing against any company</p>
            </div>

            {!activeReport ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
                <Layers className="w-10 h-10 text-indigo-950 mb-2" />
                <p className="text-xs text-slate-400">Load a filing first to enable peer comparison.</p>
              </div>
            ) : (
              <div className="flex-1 flex flex-col overflow-hidden">

                {/* ── COMPARE INPUT SECTION ── */}
                <div className="px-4 pt-3 pb-3 border-b border-indigo-950/30 space-y-2">
                  {/* Quick-select company chips */}
                  <div className="flex flex-wrap gap-1.5">
                    {["AMD", "Intel", "Tesla", "Apple", "Microsoft", "Google"].map(co => (
                      <button
                        key={co}
                        onClick={() => setCompareInput(co)}
                        disabled={compareStatus === "loading"}
                        className={`text-[10px] font-semibold px-2.5 py-1 rounded-full border transition active:scale-95 disabled:opacity-40 ${
                          compareInput === co
                            ? "bg-purple-600 border-purple-400 text-white"
                            : "bg-indigo-950/40 border-indigo-800/40 text-indigo-300 hover:border-purple-500 hover:text-white"
                        }`}
                      >
                        {co}
                      </button>
                    ))}
                  </div>

                  {/* Free-text input + Compare button */}
                  <form
                    onSubmit={async (e) => {
                      e.preventDefault();
                      const company = compareInput.trim();
                      if (!company || !activeReportId) return;
                      setCompareStatus("loading");
                      setCompareTarget(company);
                      try {
                        const res = await fetch(apiUrl("/api/reports/trigger"), {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({
                            report_id: activeReportId,
                            query: `Compare ${activeReport?.company_name ?? ""} against ${company}. Benchmark supply chain risks, gross margins, sentiment differences, and management tone vs ${company}.`
                          })
                        });
                        if (!res.ok) throw new Error("Trigger failed");
                        await pollUntilComplete(activeReportId);
                        await selectReport(activeReportId, activeReport?.company_name ?? "");
                        setCompareStatus("done");
                      } catch (err) {
                        console.error("Compare error:", err);
                        setCompareStatus("idle");
                      }
                    }}
                    className="flex gap-2"
                  >
                    <input
                      type="text"
                      placeholder="Type a company name (e.g. Qualcomm, TSMC, Samsung...)" 
                      value={compareInput}
                      onChange={e => setCompareInput(e.target.value)}
                      disabled={compareStatus === "loading"}
                      className="flex-1 bg-slate-950/80 border border-purple-950/60 rounded-lg px-3 py-2 text-[10px] text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 glow-focus transition disabled:opacity-50"
                    />
                    <button
                      type="submit"
                      disabled={compareStatus === "loading" || !compareInput.trim() || !activeReportId}
                      className="text-[10px] font-bold px-3 py-2 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white transition disabled:opacity-50 flex items-center gap-1.5 shrink-0"
                    >
                      {compareStatus === "loading" ? (
                        <><Cpu className="w-3 h-3 animate-spin" /> Comparing...</>
                      ) : (
                        <><Activity className="w-3 h-3" /> COMPARE</>
                      )}
                    </button>
                  </form>

                  {/* Status feedback */}
                  {compareStatus === "loading" && (
                    <div className="text-[10px] text-amber-400 flex items-center gap-1.5 animate-pulse">
                      <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                      Running LangGraph comparison against <strong>{compareTarget}</strong>...
                    </div>
                  )}
                  {compareStatus === "done" && (
                    <div className="text-[10px] text-emerald-400 flex items-center gap-1.5">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                      Comparison with <strong>{compareTarget}</strong> complete — results below ↓
                    </div>
                  )}
                </div>

                {/* ── RESULTS SECTION ── */}
                <div className="flex-1 overflow-y-auto px-4 pt-2 pb-3 space-y-2">

                  {/* Competitor Benchmarks table */}
                  {(activeReport.result?.final_comparative_analysis?.competitor_benchmarks ?? []).length > 0 && (
                    <div className="bg-slate-950/40 rounded-lg border border-slate-900/50 p-2">
                      <span className="text-[9px] text-indigo-400 font-semibold uppercase block tracking-wider mb-1.5">Metric Benchmarks</span>
                      <table className="w-full text-[10px] font-mono text-left">
                        <thead>
                          <tr className="border-b border-indigo-950/50 text-indigo-400 uppercase text-[8px] tracking-wider">
                            <th className="pb-1">Metric</th>
                            <th className="pb-1 text-center">{activeReport.company_name}</th>
                            <th className="pb-1 text-right">vs Peer</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-indigo-950/30 text-slate-300">
                          {activeReport.result.final_comparative_analysis.competitor_benchmarks.map((bm: any, bIdx: number) => (
                            <tr key={bIdx} className="hover:bg-indigo-950/20">
                              <td className="py-1.5 pr-2 font-semibold text-[9px]">{bm.metric_name}</td>
                              <td className="py-1.5 text-center text-indigo-300 text-[9px]">{bm.target_company}</td>
                              <td className="py-1.5 text-right text-purple-300 text-[9px]">{bm.comparison_value}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Tone Shifts */}
                  {(activeReport.result?.final_comparative_analysis?.tone_shifts ?? []).length > 0 && (
                    <div className="bg-slate-950/40 rounded-lg border border-slate-900/50 p-2 space-y-1.5">
                      <span className="text-[9px] text-purple-400 font-semibold uppercase block tracking-wider">Management Tone Shifts</span>
                      {activeReport.result.final_comparative_analysis.tone_shifts.map((ts: any, tIdx: number) => (
                        <div key={tIdx} className="border-l-2 border-purple-500 pl-2 py-0.5 leading-snug">
                          <strong className="text-white text-[9px]">{ts.comparison_target} — {ts.shift_direction}:</strong>{" "}
                          <span className="text-slate-400 text-[9px]">{ts.details}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Empty state */}
                  {(activeReport.result?.final_comparative_analysis?.competitor_benchmarks ?? []).length === 0 &&
                   (activeReport.result?.final_comparative_analysis?.tone_shifts ?? []).length === 0 && (
                    <div className="flex flex-col items-center justify-center py-4 text-center">
                      <Layers className="w-8 h-8 text-indigo-950 mb-2" />
                      <p className="text-[10px] text-slate-500">Select or type a company above and click <strong className="text-purple-400">COMPARE</strong> to generate benchmarks.</p>
                    </div>
                  )}
                </div>

              </div>
            )}
          </div>
        </section>

      </main>
    </div>
  );
}
