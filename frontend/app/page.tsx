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
  AreaChart,
  Area,
  XAxis,
  YAxis
, BarChart, Bar, CartesianGrid } from "recharts";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// High-fidelity Simulator Mock Dataset for offline capabilities
const MOCK_REPORTS: Record<string, any> = {
  "nvidia_sim": {
    report_id: "nvidia_sim",
    company_name: "NVIDIA",
    filename: "NVIDIA_10K_2025.pdf",
    current_step: "Complete",
    status: "complete",
    logs: [
      "🟢 Initializing multi-agent ingest engine...",
      "✅ Loaded NVIDIA_10K_2025.pdf (12.4 KB)",
      "💡 Extracting narrative sections (Risk Factors, MD&A, Forward Looking)...",
      "✅ Section Item 1A (Risk Factors) parsed successfully.",
      "✅ Section Item 7 (MD&A) parsed successfully.",
      "💡 Computing sentence-level embeddings with BAAI/bge-large-en-v1.5...",
      "✅ Hydrated ChromaDB collection 'nvidia_filings' with 14 chunks.",
      "🧠 Invoking Financial Intelligence Agent (Qwen2.5 7B-Instruct)...",
      "🔥 Sentiment analysis running on CUDA core via FinBERT...",
      "💡 Agent triggered Scraping Tool: Fetching competitor AMD & Intel previous filings...",
      "🔎 Validator Agent: Approving SEC source authenticity (Status: Verified)",
      "📊 Generating comparative financial analytics and benchmarks...",
      "✅ Platform analysis complete! UI fully populated."
    ],
    result: {
      sections: {
        risk_factors: "NVIDIA Corporation Annual Report 10-K.\n\nITEM 1A. RISK FACTORS.\n\nWe rely on TSMC for all semiconductor fabrication. Natural disasters, geopolitical issues in Taiwan, or CoWoS advanced packaging shortages would drastically impact product shipments.\n\nExport restrictions on H100 and A100 GPUs to China have forced design of lower-performance alternatives.\n\nCompetition from AMD Instinct accelerators and open-source ROCm threatens CUDA software moat. High hardware margins attract rapid new entrants in generative AI ASICs.\n\nOperational expansion demands highly robust electricity supplies, presenting secondary climate risks for localized server hubs.",
        mda: "ITEM 7. MD&A (Management's Discussion and Analysis of Financial Condition).\n\nData Center revenues surged 250% year-over-year. Gross margins reached a record 74% driven by CUDA ecosystem pricing power and high demand for Hopper architecture chips.\n\nOperating cash flow exceeded $28 billion, providing substantial capital leverage for strategic long-term supply agreements.",
        forward_looking: "FORWARD LOOKING STATEMENTS.\n\nWe expect our next-generation Blackwell platforms to begin ramping in late 2025. Gross margins may moderate slightly to approximately 72-73% as advanced thermal packaging capacities scale up at our foundries."
      },
      sentiment: {
        score: 0.38,
        classification: "Cautious Optimism",
        metrics: {
          optimism: 0.65,
          pessimism: 0.15,
          cautiousness: 0.45,
          uncertainty: 0.30
        }
      },
      risks: [
        {
          category: "Supply Chain & Packaging",
          risk_name: "TSMC Fabrication & CoWoS Dependency",
          severity: "High",
          implication: "Geopolitical Taiwan disruptions or CoWoS advanced packaging supply shortages immediately stall global GPU shipments.",
          evidence: "We rely on TSMC for all semiconductor fabrication. Natural disasters, geopolitical issues in Taiwan, or CoWoS advanced packaging shortages would drastically impact product shipments."
        },
        {
          category: "Geopolitical & Regulations",
          risk_name: "China GPU Export Controls",
          severity: "High",
          implication: "Ongoing export restrictions to key Asian markets shrink target addressable segments, forcing expensive hardware redesigns.",
          evidence: "Export restrictions on H100 and A100 GPUs to China have forced design of lower-performance alternatives."
        },
        {
          category: "Market Competition",
          risk_name: "AMD Instinct GPU & ROCm Ecosystem",
          severity: "Medium",
          implication: "Rival AI chip alternatives combined with active open-source compiler frameworks challenge NVIDIA's proprietary software pricing power.",
          evidence: "Competition from AMD Instinct accelerators and open-source ROCm threatens CUDA software moat."
        }
      ],
      final_comparative_analysis: {
        competitor_benchmarks: [
          { metric_name: "AI GPU Gross Margin", target_company: "74.0%", comparison_value: "47.0% (AMD)" },
          { metric_name: "Data Center Rev Growth", target_company: "+250%", comparison_value: "+80% (AMD)" },
          { metric_name: "R&D Intensity % of Rev", target_company: "18.5%", comparison_value: "22.1% (AMD)" },
          { metric_name: "Supply Chain Moat Rating", target_company: "Premium", comparison_value: "Moderate (AMD)" }
        ],
        tone_shifts: [
          { comparison_target: "AMD", shift_direction: "Fierce Expansion", details: "NVIDIA exhibits highly aggressive revenue-capturing strategies while maintaining robust software pricing moats." },
          { comparison_target: "Intel", shift_direction: "Total Tech Displacement", details: "Rapid shift of standard CPU server budgets directly into highly accelerated GPU platforms." }
        ]
      }
    }
  },
  "amd_sim": {
    report_id: "amd_sim",
    company_name: "AMD",
    filename: "AMD_10K_2025.pdf",
    current_step: "Complete",
    status: "complete",
    logs: [
      "🟢 Initializing multi-agent ingest engine...",
      "✅ Loaded AMD_10K_2025.pdf (11.8 KB)",
      "💡 Extracting narrative sections (Risk Factors, MD&A, Forward Looking)...",
      "✅ Section Item 1A (Risk Factors) parsed successfully.",
      "✅ Section Item 7 (MD&A) parsed successfully.",
      "💡 Computing sentence-level embeddings with BAAI/bge-large-en-v1.5...",
      "✅ Hydrated ChromaDB collection 'amd_filings' with 11 chunks.",
      "🧠 Invoking Financial Intelligence Agent (Qwen2.5 7B-Instruct)...",
      "🔥 Sentiment analysis running on CUDA core via FinBERT...",
      "💡 Agent triggered Scraping Tool: Fetching competitor NVIDIA previous filings...",
      "🔎 Validator Agent: Approving SEC source authenticity (Status: Verified)",
      "📊 Generating comparative financial analytics and benchmarks...",
      "✅ Platform analysis complete! UI fully populated."
    ],
    result: {
      sections: {
        risk_factors: "AMD Inc Annual Report 10-K.\n\nITEM 1A. RISK FACTORS.\n\nWe face intense competition from NVIDIA in high-performance computing and Intel in microprocessors. We rely on TSMC for all semiconductor fabrication.\n\nCoWoS capacity constraints at TSMC could severely limit revenue growth and lead to supply shortfalls.\n\nExport controls on AI chips to China present substantial risk to our long-term hardware sales expansion in international segments.\n\nGaming segment revenue declined 48% due to lower console chip demand from Sony and Microsoft.",
        mda: "ITEM 7. MD&A (Management's Discussion and Analysis of Financial Condition).\n\nData Center segment grew 80% driven by Instinct MI300X GPU accelerators. Gross margin expanded to 47% reflecting high enterprise computing demand.\n\nOur client segment saw solid recovery driven by Ryzen processor market share gains.",
        forward_looking: "FORWARD LOOKING STATEMENTS.\n\nWe project MI300X supply capacity to increase sequentially throughout 2025. Achieving our targeted full-year AI goals relies heavily on our packaging partners meeting yield standards."
      },
      sentiment: {
        score: 0.12,
        classification: "Neutral Cautious",
        metrics: {
          optimism: 0.48,
          pessimism: 0.25,
          cautiousness: 0.60,
          uncertainty: 0.42
        }
      },
      risks: [
        {
          category: "Market Competition",
          risk_name: "NVIDIA Dominance in AI GPU Hardware",
          severity: "High",
          implication: "NVIDIA's proprietary software ecosystem (CUDA) limits accelerated client adoption of AMD's hardware alternatives.",
          evidence: "We face intense competition from NVIDIA in high-performance computing and Intel in microprocessors."
        },
        {
          category: "Supply Chain & Yields",
          risk_name: "Advanced TSMC CoWoS Capacity",
          severity: "High",
          implication: "Limited packaging slot allocations restrict maximum revenue capacity, regardless of actual customer interest.",
          evidence: "CoWoS capacity constraints at TSMC could severely limit revenue growth."
        },
        {
          category: "Product Slump",
          risk_name: "Gaming Console Segment Contraction",
          severity: "Medium",
          implication: "Late-stage gaming console lifecycles cause double-digit declines in gaming revenues, dragging overall corporate margins.",
          evidence: "Gaming segment revenue declined 48% due to lower console chip demand."
        }
      ],
      final_comparative_analysis: {
        competitor_benchmarks: [
          { metric_name: "AI GPU Gross Margin", target_company: "47.0%", comparison_value: "74.0% (NVIDIA)" },
          { metric_name: "Data Center Rev Growth", target_company: "+80%", comparison_value: "+250% (NVIDIA)" },
          { metric_name: "R&D Intensity % of Rev", target_company: "22.1%", comparison_value: "18.5% (NVIDIA)" },
          { metric_name: "Supply Chain Moat Rating", target_company: "Moderate", comparison_value: "Premium (NVIDIA)" }
        ],
        tone_shifts: [
          { comparison_target: "NVIDIA", shift_direction: "Catch-Up Mode", details: "AMD uses cooperative open-source software strategies (ROCm) to counteract NVIDIA's closed software ecosystem." },
          { comparison_target: "Intel", shift_direction: "Aggressive Share Capture", details: "Ryzen CPU client segments consistently take market share from Intel in enterprise markets." }
        ]
      }
    }
  }
};

const HISTORICAL_MARGIN_TRENDS = [
  { year: "2021", Target: 54.0, Competitor: 43.5, Intel: 52.8 },
  { year: "2022", Target: 57.2, Competitor: 45.1, Intel: 48.2 },
  { year: "2023", Target: 61.5, Competitor: 46.0, Intel: 42.0 },
  { year: "2024", Target: 74.0, Competitor: 47.0, Intel: 41.5 }
];

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

export default function Home() {
  // Navigation & theme states
  const [showDashboard, setShowDashboard] = useState<boolean>(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [activeWorkspace, setActiveWorkspace] = useState<"ingest" | "audit" | "benchmarking">("ingest");

  // Core application states
  const [activeReportId, setActiveReportId] = useState<string | null>(null);
  const [reportsList, setReportsList] = useState<any[]>([]);
  const [activeReport, setActiveReport] = useState<any>(null);
  
  // Pipeline status tracking
  const [processingStatus, setProcessingStatus] = useState<"idle" | "processing" | "complete" | "failed">("idle");
  const [currentStep, setCurrentStep] = useState<string>("");
  const [pipelineLogs, setPipelineLogs] = useState<string[]>([]);
  
  // Narrative section navigator
  const [activeFilingTab, setActiveFilingTab] = useState<"risk_factors" | "mda" | "forward_looking">("risk_factors");
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

  // Benchmarking states
  const [compareInput, setCompareInput] = useState<string>("");
  const [compareStatus, setCompareStatus] = useState<"idle" | "loading" | "done">("idle");
  const [compareTarget, setCompareTarget] = useState<string>("");
  
  // Backend connectivity status
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  
  // Operational risks indexes expanded
  const [expandedRiskIdx, setExpandedRiskIdx] = useState<number | null>(null);

  // DOM Refs for scrollbars
  const filingContentRef = useRef<HTMLDivElement>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Scroll logs helper
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [pipelineLogs]);

  // Scroll chat helper
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Initialize theme and API validations
  useEffect(() => {
    // Force dark theme only
    setTheme("dark");
    document.documentElement.className = "dark";

    fetch("http://localhost:8000/api/reports")
      .then(r => { if (r.ok) { setBackendOnline(true); return r.json(); } throw new Error(); })
      .then(list => setReportsList(list))
      .catch(() => { 
        setBackendOnline(false); 
        console.warn("Backend offline. Aegis running in high-fidelity simulator mode."); 
        setReportsList([
          { report_id: "nvidia_sim", company_name: "NVIDIA", filename: "NVIDIA_10K_2025.pdf" },
          { report_id: "amd_sim", company_name: "AMD", filename: "AMD_10K_2025.pdf" }
        ]);
      });
  }, []);

  // Theme toggle removed — app is fixed to dark theme

  const useSimulator = backendOnline === false;

  const selectReport = useCallback(async (id: string, companyName: string) => {
    setActiveReportId(id);
    setProcessingStatus("complete");
    
    if (useSimulator && MOCK_REPORTS[id]) {
      setActiveReport(MOCK_REPORTS[id]);
      setPipelineLogs(MOCK_REPORTS[id].logs);
      setCurrentStep(MOCK_REPORTS[id].current_step);
      setChatMessages([{
        id: 1, role: "assistant",
        content: `Analysis of ${MOCK_REPORTS[id].company_name}'s filing is complete. [SIMULATOR ACTIVE] Ask me about risks, margins, sentiment, or competitor comparisons.`,
        citations: []
      }]);
      return;
    }

    try {
      const res = await fetch(`http://localhost:8000/api/reports/${id}`);
      if (res.ok) {
        const fullReport = await res.json();
        setActiveReport(fullReport);
        setPipelineLogs(fullReport.logs || []);
        setCurrentStep(fullReport.current_step || "Complete");
        setChatMessages([{
          id: 1, role: "assistant",
          content: `Analysis of ${fullReport.company_name}'s filing is complete. Ask me about risks, margins, sentiment, or competitor comparisons.`,
          citations: []
        }]);
      }
    } catch (err) {
      console.error("Error loading report:", err);
    }
  }, [useSimulator]);

  const handleTemplateClick = async (company: "NVIDIA" | "AMD") => {
    const simId = company === "NVIDIA" ? "nvidia_sim" : "amd_sim";
    
    if (useSimulator) {
      setProcessingStatus("processing");
      setPipelineLogs(["Uploading filing to Aegis backend... [SIMULATOR]"]);
      setCurrentStep("Uploading...");
      setActiveReport(null);
      setCompareStatus("idle");
      
      const targetLogs = MOCK_REPORTS[simId].logs;
      let logIndex = 0;
      
      const interval = setInterval(() => {
        if (logIndex < targetLogs.length - 1) {
          setPipelineLogs(prev => [...prev, targetLogs[logIndex]]);
          const words = targetLogs[logIndex].split(" ");
          setCurrentStep(words[words.length - 1].replace("...", ""));
          logIndex++;
        } else {
          clearInterval(interval);
          selectReport(simId, company);
        }
      }, 250);
      return;
    }

    const filingText = company === "NVIDIA"
      ? "NVIDIA Corporation Annual Report 10-K. ITEM 1A. RISK FACTORS. We rely on TSMC for all semiconductor fabrication. Natural disasters, geopolitical issues in Taiwan, or CoWoS advanced packaging shortages would drastically impact product shipments. Export restrictions on H100 and A100 GPUs to China have forced design of lower-performance alternatives. Competition from AMD Instinct accelerators and open-source ROCm threatens CUDA software moat. ITEM 7. MD&A. Data Center revenues surged 250%. Gross margins reached a record 74% driven by CUDA ecosystem pricing power. Operating cash flow exceeded $28 billion."
      : "AMD Inc Annual Report 10-K. ITEM 1A. RISK FACTORS. We face intense competition from NVIDIA in high-performance computing and Intel in microprocessors. We rely on TSMC for all semiconductor fabrication. CoWoS capacity constraints at TSMC could severely limit revenue growth. Export controls on AI chips to China present substantial risk. ITEM 7. MD&A. Data Center segment grew 80% driven by Instinct MI300X GPU accelerators. Gross margin expanded to 47%. Gaming segment revenue declined 48% due to lower console chip demand.";
    const blob = new Blob([filingText], { type: "application/pdf" });
    const formData = new FormData();
    formData.append("file", new File([blob], `${company}_10K_2025.pdf`, { type: "application/pdf" }));
    formData.append("company_name", company);
    formData.append("user_query", "Analyze all risks and sentiment. Compare against key industry peers and generate competitive benchmarks.");
    await runUploadAndPoll(formData, company);
  };

  const pollUntilComplete = useCallback((repId: string): Promise<void> => {
    return new Promise((resolve, reject) => {
      const iv = setInterval(async () => {
        try {
          const r = await fetch(`http://localhost:8000/api/reports/${repId}/status`);
          if (!r.ok) { clearInterval(iv); reject(); return; }
          const d = await r.json();
          setPipelineLogs(d.logs || []);
          setCurrentStep(d.current_step || "Processing...");
          if (d.status === "complete") { clearInterval(iv); resolve(); }
          else if (d.status === "failed") { clearInterval(iv); reject(new Error("Pipeline failed")); }
        } catch (e) { clearInterval(iv); reject(e); }
      }, 900);
      setTimeout(() => { clearInterval(iv); resolve(); }, 300_000);
    });
  }, []);

  const runUploadAndPoll = async (formData: FormData, companyHint: string) => {
    setProcessingStatus("processing");
    setPipelineLogs(["Uploading filing to Aegis backend..."]);
    setCurrentStep("Uploading...");
    setActiveReport(null);
    setCompareStatus("idle");
    try {
      const r = await fetch("http://localhost:8000/api/upload", { method: "POST", body: formData });
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail || "Upload failed"); }
      const { report_id, company_name } = await r.json();
      setActiveReportId(report_id);
      await pollUntilComplete(report_id);
      await selectReport(report_id, company_name || companyHint);
      const listRes = await fetch("http://localhost:8000/api/reports");
      if (listRes.ok) setReportsList(await listRes.json());
    } catch (err: any) {
      setProcessingStatus("failed");
      setCurrentStep(`Error: ${err.message}`);
      console.error(err);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (useSimulator) {
      setProcessingStatus("processing");
      setPipelineLogs(["Uploading PDF file... [SIMULATOR ENABLED]"]);
      setCurrentStep("Parsing PDF metadata...");
      setActiveReport(null);
      setCompareStatus("idle");
      
      setTimeout(() => {
        setPipelineLogs(prev => [...prev, `✅ Successfully parsed: ${file.name}`]);
        setPipelineLogs(prev => [...prev, "💡 Ingesting text segments into virtual vector index..."]);
        
        setTimeout(() => {
          selectReport("nvidia_sim", "NVIDIA");
        }, 1200);
      }, 800);
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("user_query", "Analyze all operational risks and sentiment. Compare against key industry competitors and generate comprehensive benchmarks.");
    await runUploadAndPoll(formData, file.name.replace(/\.pdf$/i, ""));
  };

  const handleRetriggerAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!retriggerQuery.trim() || !activeReportId) return;
    
    setIsRetriggering(true);
    setProcessingStatus("processing");
    setCurrentStep("Re-triggering pipeline...");
    setPipelineLogs(prev => [...prev, `💡 Re-triggering pipeline with query: "${retriggerQuery}"`]);

    if (useSimulator) {
      setTimeout(() => {
        setIsRetriggering(false);
        setProcessingStatus("complete");
        setPipelineLogs(prev => [...prev, "✅ Simulated re-analysis completed successfully!"]);
        setRetriggerQuery("");
      }, 1500);
      return;
    }

    try {
      const res = await fetch("http://localhost:8000/api/reports/trigger", {
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

    if (useSimulator) {
      setTimeout(() => {
        setIsChatLoading(false);
        setChatMessages(prev => [...prev, {
          id: newId + 1,
          role: "assistant",
          content: `In ${activeReport?.company_name || "NVIDIA"}'s Item 1A, our RAG extraction highlights that single-source advanced semiconductor lithography and advanced packaging (specifically TSMC's CoWoS yield constraints) represent major system bottlenecks. Secondary risks pertain to federal export licensing controls in critical APAC territories.`,
          citations: [
            { citation_id: "CIT-TSMC-01", company: activeReport?.company_name || "NVIDIA", chunk_index: 0, content: "We rely on TSMC for all semiconductor fabrication." },
            { citation_id: "CIT-CHINA-02", company: activeReport?.company_name || "NVIDIA", chunk_index: 1, content: "Export restrictions on H100 and A100 GPUs to China have forced design of lower-performance alternatives." }
          ]
        }]);
      }, 800);
      return;
    }

    try {
      const res = await fetch("http://localhost:8000/api/chat", {
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

  const handleRiskCardClick = (evidenceText: string, highlightId: string) => {
    setActiveEvidenceText(evidenceText);
    setActiveHighlightId(highlightId);
    setActiveFilingTab("risk_factors");
    
    setTimeout(() => {
      const element = document.getElementById(highlightId);
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    }, 100);
  };

  const renderHighlightedText = (text: string, tab: string) => {
    if (!text) return <p className="text-slate-500 italic dark:text-slate-400">No text extracted for this section.</p>;
    
    if (activeEvidenceText && tab === "risk_factors") {
      const cleanEvidence = activeEvidenceText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      try {
        const regex = new RegExp(`(${cleanEvidence})`, "i");
        const parts = text.split(regex);
        if (parts.length > 1) {
          return (
            <div className="whitespace-pre-line leading-relaxed text-slate-800 dark:text-slate-200 text-xs font-light">
              {parts.map((part, index) => {
                if (regex.test(part)) {
                  return (
                    <span 
                      key={index} 
                      id={activeHighlightId || "evidence-highlighter"} 
                      className="highlight-risk highlight-active rounded px-1 text-white font-medium animate-pulse"
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

    if (searchQuery.trim() && text.toLowerCase().includes(searchQuery.toLowerCase())) {
      const escapedQuery = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      try {
        const regex = new RegExp(`(${escapedQuery})`, "gi");
        const parts = text.split(regex);
        return (
          <div className="whitespace-pre-line leading-relaxed text-slate-800 dark:text-slate-200 text-xs font-light">
            {parts.map((part, index) => (
              regex.test(part) ? (
                <span key={index} className="bg-rose-500/20 border-b border-rose-500 text-[#0f172a] dark:text-white font-semibold px-0.5 rounded">
                  {part}
                </span>
              ) : part
            ))}
          </div>
        );
      } catch (err) {
        console.error("Search highlight error:", err);
      }
    }

    return (
      <div className="whitespace-pre-line leading-relaxed text-slate-800 dark:text-slate-200 space-y-4 text-xs font-light">
        {text.split('\n\n').map((paragraph, pIdx) => {
          let parts: any[] = [paragraph];
          const keywords = [
            { term: "TSMC", class: "text-amber-500 dark:text-amber-300 font-bold border-b border-amber-400/40" },
            { term: "export restrictions", class: "text-rose-500 font-bold border-b border-rose-500/30" },
            { term: "export controls", class: "text-rose-500 font-bold border-b border-rose-500/30" },
            { term: "competition", class: "text-[#4F772D] dark:text-[#90A955] font-bold border-b border-green-400/40" },
            { term: "CUDA", class: "text-lime-600 dark:text-[#ECF39E] font-bold border-b border-lime-400/40" },
            { term: "CoWoS", class: "text-amber-500 dark:text-amber-300 font-bold border-b border-amber-400/40" }
          ];

          keywords.forEach(({ term, class: cls }) => {
            const tempParts: any[] = [];
            parts.forEach(p => {
              if (typeof p === "string") {
                const regex = new RegExp(`(${term})`, "gi");
                const splitArray = p.split(regex);
                splitArray.forEach((sub, sIdx) => {
                  if (sub.toLowerCase() === term.toLowerCase()) {
                    tempParts.push(<span key={`${term}-${sIdx}`} className={cls}>{sub}</span>);
                  } else {
                    tempParts.push(sub);
                  }
                });
              } else {
                tempParts.push(p);
              }
            });
            parts = tempParts;
          });

          return (
            <p key={pIdx} className="leading-6">
              {parts}
            </p>
          );
        })}
      </div>
    );
  };

  const getRadarData = () => {
    if (!activeReport?.result?.sentiment?.metrics) return [];
    const m = activeReport.result.sentiment.metrics;
    const isAMD = activeReport.company_name === "AMD";
    return [
      { subject: "Optimism",     Target: (m.optimism     ?? 0) * 100, Competitor: isAMD ? 65 : 48 },
      { subject: "Pessimism",    Target: (m.pessimism    ?? 0) * 100, Competitor: isAMD ? 15 : 25 },
      { subject: "Cautiousness", Target: (m.cautiousness ?? 0) * 100, Competitor: isAMD ? 45 : 60 },
      { subject: "Uncertainty",  Target: (m.uncertainty  ?? 0) * 100, Competitor: isAMD ? 30 : 42 },
    ];
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
                  onClick={() => setShowDashboard(true)}
                  className="px-6 py-3.5 rounded-xl bg-[#4F772D] text-white font-semibold text-xs tracking-wider uppercase hover:bg-[#31572C] hover:shadow-lg hover:shadow-green-500/25 active:scale-95 transition flex items-center justify-center gap-2"
                >
                  Enter Operational Workspace
                  <ArrowRight className="w-4 h-4" />
                </button>
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
                onClick={() => setShowDashboard(false)}
                className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-900 dark:hover:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 active:scale-95 transition"
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
                { id: "benchmarking", label: "Peer Benchmarking & Chat", icon: Layers }
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
                  disabled={processingStatus === "processing"}
                  className="text-sm font-bold px-3 py-1.5 rounded-lg text-[#0f172a] dark:text-white bg-white dark:bg-slate-950 border border-slate-200 dark:border-slate-700 hover:border-[#90A955]/50 hover:bg-[#4F772D]/5 transition disabled:opacity-50 flex items-center gap-1.5 shadow-sm"
                >
                  <Cpu className="w-3 h-3 text-[#4F772D]" />
                  NVIDIA
                </button>
                <button 
                  onClick={() => handleTemplateClick("AMD")}
                  disabled={processingStatus === "processing"}
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
                  disabled={processingStatus === "processing"}
                />
              </label>

              {/* Theme toggle removed */}
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
                                   <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono"><Clock className="w-2.5 h-2.5 inline mr-1" />{new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}</span>
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

                  <div className="grid grid-cols-3 gap-2 mb-5 p-1.5 bg-slate-100 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-[#90A955]/15">
                    {[
                      { key: "risk_factors", label: "Risk Factors (1A)" },
                      { key: "mda", label: "MD&A (Item 7)" },
                      { key: "forward_looking", label: "Forward Statements" }
                    ].map(tab => (
                      <button
                        key={tab.key}
                        onClick={() => { setActiveFilingTab(tab.key as any); setActiveEvidenceText(null); }}
                        className={`text-center py-2.5 px-2 rounded-lg text-xs font-bold transition duration-200 ${
                          activeFilingTab === tab.key 
                            ? "bg-white dark:bg-[#31572C] text-[#31572C] dark:text-[#ECF39E] border border-slate-200 dark:border-[#90A955]/45 shadow-sm" 
                            : "text-[#0f172a] dark:text-slate-400 hover:text-[#4F772D] dark:hover:text-[#ECF39E]"
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
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

                  <div 
                    ref={filingContentRef}
                    className="flex-grow overflow-y-auto bg-slate-50/50 dark:bg-slate-950/50 border border-slate-200 dark:border-slate-700 rounded-lg p-6 leading-relaxed relative scroll-smooth"
                  >
                    {!activeReport ? (
                      <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-3">
                        <FileText className="w-14 h-14 text-[#4F772D]/30" />
                        <p className="text-sm font-semibold text-[#0f172a] dark:text-white">No document loaded</p>
                        <p className="text-xs text-[#6b7280] dark:text-slate-400 font-light max-w-xs">
                          Select NVIDIA or AMD above to parse SEC filing narratives.
                        </p>
                      </div>
                    ) : (
                      <div className="text-sm text-slate-700 dark:text-slate-300 leading-loose space-y-4">
                        {renderHighlightedText(activeReport.result.sections[activeFilingTab], activeFilingTab)}
                      </div>
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
                            <Bar dataKey="Competitor" name="Industry Avg" fill="#fb7185" fillOpacity={0.65} radius={[0, 4, 4, 0]} barSize={12} />
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
              </>
            )}

            {/* ── WORKSPACE 3: PEER BENCHMARKING & CHAT ── */}
            {activeWorkspace === "benchmarking" && (
              <>
                {/* Benchmark tools */}
                <div className="col-span-12 lg:col-span-6 glass-panel p-6 flex flex-col h-[calc(100vh-170px)] min-h-[500px] border-slate-200 dark:border-[#90A955]/20 bg-white dark:bg-slate-950/70 shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-200 dark:border-[#90A955]/15 pb-4 mb-5">
                    <h2 className="text-sm font-bold tracking-wider text-[#0f172a] dark:text-green-200 uppercase flex items-center gap-2.5">
                      <div className="w-2.5 h-2.5 rounded-full bg-[#ECF39E]" />
                      Competitive Analysis
                    </h2>
                  </div>

                  {!activeReport ? (
                    <div className="flex-grow flex flex-col items-center justify-center text-center p-8 space-y-4">
                      <div className="w-14 h-14 rounded-2xl bg-[#90A955]/15 flex items-center justify-center">
                        <Layers className="w-7 h-7 text-[#4F772D]/60" />
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400 font-light">Load filing context to analyze competitor benchmarks.</p>
                    </div>
                  ) : (
                    <div className="flex-grow flex flex-col overflow-hidden justify-between space-y-4">
                      
                      {/* Peer Selection */}
                      <div className="space-y-2.5">
                        <span className="text-xs text-[#90A955] font-bold uppercase tracking-widest block">Select Comparison Target</span>
                        <div className="flex flex-wrap gap-2">
                          {["AMD", "Intel", "Qualcomm", "TSMC", "Apple"].map(co => (
                            <button
                              key={co}
                              onClick={() => setCompareInput(co)}
                              disabled={compareStatus === "loading"}
                              className={`text-xs font-bold px-3 py-1.5 rounded-lg border transition active:scale-95 disabled:opacity-40 uppercase tracking-widest font-mono shadow-sm ${
                                compareInput === co
                                  ? "bg-[#4F772D] border-[#90A955] text-white"
                                  : "bg-slate-100 dark:bg-slate-900 border-slate-200 dark:border-[#90A955]/20 text-slate-600 dark:text-slate-300 hover:border-[#90A955]/50"
                              }`}
                            >
                              {co}
                            </button>
                          ))}
                        </div>

                        <form
                          onSubmit={async (e) => {
                            e.preventDefault();
                            const company = compareInput.trim();
                            if (!company || !activeReportId) return;
                            setCompareStatus("loading");
                            setCompareTarget(company);
                            
                            if (useSimulator) {
                              setTimeout(() => {
                                setCompareStatus("done");
                                setPipelineLogs(prev => [...prev, `✅ Comparison with ${company} completed in simulator.`]);
                              }, 900);
                              return;
                            }

                            try {
                              const res = await fetch("http://localhost:8000/api/reports/trigger", {
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
                          className="flex gap-2 pt-1.5"
                        >
                          <input
                            type="text"
                            placeholder="Search company..." 
                            value={compareInput}
                            onChange={e => setCompareInput(e.target.value)}
                            disabled={compareStatus === "loading"}
                            className="flex-grow bg-slate-100 dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-sm text-[#0f172a] dark:text-white placeholder-slate-400 focus:outline-none focus:border-[#90A955]/60 transition"
                          />
                          <button
                            type="submit"
                            disabled={compareStatus === "loading" || !compareInput.trim() || !activeReportId}
                            className="text-xs font-bold px-4 py-2 rounded-lg bg-[#4F772D] text-white hover:bg-[#31572C] transition disabled:opacity-50 flex items-center gap-2 shrink-0 uppercase tracking-widest shadow-sm"
                          >
                            {compareStatus === "loading" ? (
                              <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Compare</>
                            ) : (
                              <><Activity className="w-3.5 h-3.5" /> Compare</>
                            )}
                          </button>
                        </form>
                      </div>

                      <div className="flex-1 overflow-y-auto space-y-4">
                        {/* Benchmarking Table */}
                        <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-[#90A955]/20 p-5 shadow-sm">
                          <span className="text-xs text-[#90A955] font-bold uppercase block tracking-widest mb-4 font-mono">Performance Metrics</span>
                          <div className="overflow-x-auto">
                            <table className="w-full text-sm text-left">
                              <thead>
                                <tr className="border-b border-slate-200 dark:border-[#90A955]/15 text-slate-500 dark:text-green-200/80 uppercase text-xs tracking-wider font-semibold">
                                  <th className="pb-3 px-2">Metric</th>
                                  <th className="pb-3 px-2 text-center">{activeReport.company_name}</th>
                                  <th className="pb-3 px-2 text-right">Peer Avg</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
                                {activeReport.result?.final_comparative_analysis?.competitor_benchmarks?.slice(0, 4).map((bm: any, bIdx: number) => (
                                  <tr key={bIdx} className="hover:bg-slate-50 dark:hover:bg-[#4F772D]/10 transition">
                                    <td className="py-3 px-2 font-medium text-[#0f172a] dark:text-slate-100">{bm.metric_name}</td>
                                    <td className="py-3 px-2 text-center text-[#31572C] dark:text-[#ECF39E] font-bold">{bm.target_company}</td>
                                    <td className="py-3 px-2 text-right text-[#4F772D] dark:text-[#90A955] font-medium">{bm.comparison_value}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>

                        {/* Margin Trend Chart */}
                        <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-[#90A955]/20 p-5 shadow-sm">
                          <span className="text-xs text-[#ECF39E] font-bold uppercase block tracking-widest mb-4 font-mono">Margin Trend (4-Year)</span>
                          <div className="w-full h-[180px]">
                            <ResponsiveContainer width="100%" height="100%">
                              <AreaChart data={HISTORICAL_MARGIN_TRENDS} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                <defs>
                                  <linearGradient id="colorTarget" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#4F772D" stopOpacity={0.32}/>
                                    <stop offset="95%" stopColor="#4F772D" stopOpacity={0}/>
                                  </linearGradient>
                                  <linearGradient id="colorPeer" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%" stopColor="#90A955" stopOpacity={0.24}/>
                                    <stop offset="95%" stopColor="#90A955" stopOpacity={0}/>
                                  </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                                <XAxis dataKey="year" fontSize={11} stroke="#ECF39E" tickLine={false} axisLine={false} />
                                <YAxis domain={[30, 80]} hide />
                                <Tooltip contentStyle={{ background: '#111827', border: '1px solid rgba(144, 169, 85, 0.35)', color: '#fff', fontSize: '11px', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }} />
                                <Area type="monotone" dataKey="Target" name={activeReport.company_name} stroke="#4F772D" fillOpacity={1} fill="url(#colorTarget)" strokeWidth={3} />
                                <Area type="monotone" dataKey="Competitor" name="Peer Avg" stroke="#90A955" fillOpacity={1} fill="url(#colorPeer)" strokeWidth={2} strokeDasharray="5 5" />
                              </AreaChart>
                            </ResponsiveContainer>
                          </div>
                        </div>
                      </div>

                    </div>
                  )}
                </div>

                {/* Chat cockpit */}
                <div className="col-span-12 lg:col-span-6 glass-panel p-5 flex flex-col h-[calc(100vh-170px)] min-h-[500px] border-slate-200 dark:border-[#ECF39E]/20 bg-white dark:bg-slate-950/70 shadow-sm">
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
                        <p className="text-xs text-slate-400 font-light">Interactive chatbot cockpit. Hydrate vector parameters by parsing files.</p>
                      </div>
                    ) : (
                      chatMessages.map((msg: any) => (
                        <div key={msg.id} className={`flex flex-col ${msg.role === "user" ? "items-end" : "items-start"}`}>
                          <div className="flex items-center gap-1.5 mb-1 px-1 text-xs text-slate-500 font-mono">
                            {msg.role === "user" ? <User className="w-3 h-3 text-[#4F772D]" /> : <Bot className="w-3 h-3 text-[#90A955]" />}
                            {msg.role === "user" ? "Analyst" : "Aegis RAG Intelligence"}
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
                            
                            {msg.citations && msg.citations.length > 0 && (
                              <div className="mt-3 pt-2.5 border-t border-slate-200 dark:border-[#ECF39E]/15 space-y-1">
                                <span className="text-xs text-[#ECF39E] font-bold block uppercase tracking-widest font-mono">Audit Source Evidence:</span>
                                <div className="flex flex-wrap gap-1">
                                  {msg.citations.map((cit: any, cIdx: number) => (
                                    <button
                                      key={cIdx}
                                      onClick={() => handleRiskCardClick(cit.content, `highlight-${cit.company}-${cit.chunk_index}`)}
                                      className="text-xs px-2.5 py-0.5 rounded-lg bg-white hover:bg-slate-50 dark:bg-slate-900 dark:hover:bg-[#90A955]/10 border border-slate-200 dark:border-[#ECF39E]/30 text-[#4F772D] dark:text-[#90A955] font-mono transition flex items-center gap-1 active:scale-95 shadow-sm"
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
                      <div className="flex items-center space-x-2 text-sm text-[#ECF39E] font-mono p-2 animate-pulse">
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        <span>Querying vector indices...</span>
                      </div>
                    )}
                    <div ref={chatEndRef} />
                  </div>

                  <form onSubmit={handleSendMessage} className="flex gap-2">
                    <input
                      type="text"
                      placeholder="Ask RAG comparative questions..."
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

