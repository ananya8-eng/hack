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
  const [chatLoadingComparison, setChatLoadingComparison] = useState<boolean>(false);
  
  // Custom manual query trigger state
  const [retriggerQuery, setRetriggerQuery] = useState<string>("");
  const [isRetriggering, setIsRetriggering] = useState<boolean>(false);

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
    let result: any[] = [];
    if (Array.isArray(cat) && cat.length > 0) {
      result = cat;
    } else {
      const secs = report?.result?.sections || {};
      result = Object.keys(secs).map((id: string) => ({
        id,
        title: id.replace(/_/g, " "),
        priority: 50,
        char_count: (secs[id] || "").length,
      }));
    }
    const seenTitles = new Set<string>();
    return result.filter(item => {
      const titleKey = (item.title || "").trim().toLowerCase();
      if (seenTitles.has(titleKey)) {
        return false;
      }
      seenTitles.add(titleKey);
      return true;
    });
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
          content: `Earnings narrative analysis for ${fullReport.company_name} is complete. Ask about MD&A tone, operational risks, or supply chain. To benchmark a peer, name the company in chat (e.g. "Compare against [company] on gross margins and supply chain").`,
          citations: []
        }]);
      }
    } catch (err) {
      console.error("Error loading report:", err);
    }
  }, []);

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

  // Shared upload+poll handler for PDF ingestion
  const runUploadAndPoll = async (formData: FormData, companyHint: string) => {
    setProcessingStatus("processing");
    setPipelineLogs(["Sending PDF to backend..."]);
    setCurrentStep("Uploading...");
    setActiveReport(null);
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
    formData.append("user_query", "Extract operational risks and sentiment from MD&A and narrative sections in this filing.");
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

  const isComparisonQuestion = (text: string) =>
    /\b(compare|comparison|competitor|versus|vs\.?|against|benchmark|peer|prior year|previous year)\b/i.test(text);

  // Handle chatbot RAG messages (peer comparison runs in-chat via scrape + SLM)
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !activeReportId) return;
    
    const userMsg = chatInput;
    const comparisonMode = isComparisonQuestion(userMsg);
    setChatInput("");
    setIsChatLoading(true);
    setChatLoadingComparison(comparisonMode);
    
    const newId = chatMessages.length + 1;
    setChatMessages(prev => [...prev, { id: newId, role: "user", content: userMsg }]);

    if (comparisonMode) {
      setChatMessages(prev => [...prev, {
        id: `status-${newId}`,
        role: "assistant",
        content: "Fetching peer filing data and running comparative analysis…",
        citations: [],
        isStatus: true
      }]);
    }

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
        setChatMessages(prev => {
          const withoutStatus = comparisonMode
            ? prev.filter(m => !m.isStatus)
            : prev;
          return [...withoutStatus, {
            id: newId + 1,
            role: "assistant",
            content: data.answer,
            citations: data.citations || [],
            mode: data.mode,
            comparison: data.comparison || null,
            guardrailBlocked: Boolean(data.guardrail_blocked)
          }];
        });
      } else {
        const errBody = await res.json().catch(() => ({}));
        const detailObj = errBody.detail;
        const detail = typeof detailObj === "string"
          ? detailObj
          : typeof detailObj === "object" && detailObj?.message
          ? detailObj.message
          : "Chat request failed.";
        setChatMessages(prev => [...prev.filter(m => !m.isStatus), {
          id: newId + 1,
          role: "assistant",
          content: detail,
          citations: [],
          guardrailBlocked: Boolean(detailObj?.guardrail_blocked)
        }]);
      }
    } catch (err) {
      console.error("Chat API error:", err);
      setChatMessages(prev => [...prev.filter(m => !m.isStatus), {
        id: newId + 1,
        role: "assistant",
        content: "Could not reach the chat API. Is the backend running?",
        citations: []
      }]);
    } finally {
      setIsChatLoading(false);
      setChatLoadingComparison(false);
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

    const renderTextWithHighlight = (txt: string) => {
      if (activeEvidenceText && tab === activeFilingTab) {
        const cleanEvidence = activeEvidenceText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        try {
          const regex = new RegExp(`(${cleanEvidence})`, "i");
          const parts = txt.split(regex);
          if (parts.length > 1) {
            return parts.map((part, index) => {
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
            });
          }
        } catch (e) {
          console.error("Highlighter regex failed:", e);
        }
      }
      return txt;
    };

    // Step 2 — Identify financial token lines
    const isFinancialToken = (line: string): boolean => {
      const trimmed = line.trim();
      if (trimmed === "$") return true;
      if (trimmed.toLowerCase() === "change") return true;
      if (/^\(?[0-9]{1,3}(,[0-9]{3})*\)?$/.test(trimmed)) return true;
      if (/^\(?[0-9]+\)?$/.test(trimmed)) return true;
      if (/^\(?[0-9]+(\.[0-9]+)?\s*%\)?$/.test(trimmed)) return true;
      if (/^\(?[0-9]+(\.[0-9]+)?%\)?$/.test(trimmed)) return true;
      if (/^(19|20)[0-9]{2}$/.test(trimmed)) return true;

      const monthsPattern = /^(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$/i;
      const parts = trimmed.replace(/,/g, '').split(/\s+/);
      if (parts.length === 2) {
        if (monthsPattern.test(parts[0]) && /^[0-9]{1,2}$/.test(parts[1])) return true;
      }
      return false;
    };

    const isTitleCase = (str: string): boolean => {
      const words = str.trim().split(/\s+/).filter(w => w.length > 0);
      if (words.length === 0) return false;
      const ignoreList = ["and", "or", "the", "of", "in", "for", "to", "with", "on", "at", "by", "an", "a", "from"];
      let capCount = 0;
      let letterWords = 0;
      for (const word of words) {
        const cleanWord = word.replace(/[^a-zA-Z]/g, "");
        if (cleanWord.length === 0) continue;
        letterWords++;
        if (ignoreList.includes(word.toLowerCase())) {
          capCount++;
          continue;
        }
        if (cleanWord[0] === cleanWord[0].toUpperCase()) {
          capCount++;
        }
      }
      return letterWords > 0 && capCount === letterWords;
    };

    // Step 1 — Noise patterns cleanup & clean lines
    const collapsed = text.replace(/\r\n/g, "\n").replace(/\n{3,}/g, "\n\n");
    const rawLines = collapsed.split("\n").map(l => l.trim().replace(/(\d+(?:[.,]\d+)*)\?/g, "$1"));

    const cleanLines = rawLines.filter(line => {
      if (!line) return true; // keep blank line separators initially

      // Noise patterns:
      if (/^aapl-[0-9]+$/i.test(line)) return false;
      if (/^\(\d+\)$/.test(line)) return false; // footnote markers like (1)
      if (/^[—–-]+$/.test(line)) return false; // alone em-dash/en-dash
      
      // Document metadata/page info:
      if (/^https?:\/\//i.test(line)) return false;
      if (/^---\s*PAGE\s*\d+\s*---$/i.test(line)) return false;
      if (/^\d+\/\d+$/.test(line)) return false;
      if (/^\d{1,2}\/\d{1,2}\/\d{2,4},\s*\d{1,2}:\d{2}\s*(AM|PM)$/i.test(line)) return false;
      if (/^[®\s]+$/.test(line)) return false;
      if (line.includes('|') && (line.includes('10-Q') || line.includes('10-K') || line.includes('8-K'))) return false;
      if (/^\d+$/.test(line) && line.length <= 3) return false;

      return true;
    });

    // Collapse duplicate consecutive blank lines
    const rawCleanLines: string[] = [];
    let prevEmpty = false;
    for (const line of cleanLines) {
      const isEmpty = line === "";
      if (isEmpty) {
        if (!prevEmpty) {
          rawCleanLines.push("");
          prevEmpty = true;
        }
      } else {
        rawCleanLines.push(line);
        prevEmpty = false;
      }
    }

    const dateRangeRegex = /\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b\s+\d{1,2},\s+\d{4}\s+to\s+\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b\s+\d{1,2},\s+\d{4}:?/i;

    // Fragmented PDF table column headers & date range row dividers pre-processing
    const preProcessedLines: string[] = [];
    let lIdx = 0;
    while (lIdx < rawCleanLines.length) {
      const line = rawCleanLines[lIdx];
      
      // Labelled financial row check
      const trimmedLower = line.trim().toLowerCase();
      const labelSet = new Set(["services", "products", "iphone", "mac", "ipad", "americas", "europe", "japan"]);
      if (labelSet.has(trimmedLower)) {
        lIdx++;
        let valuesStr = "";
        while (lIdx < rawCleanLines.length && isFinancialToken(rawCleanLines[lIdx])) {
          valuesStr += "   " + rawCleanLines[lIdx];
          lIdx++;
        }
        if (valuesStr) {
          valuesStr = valuesStr.replace(/\$\s+/g, "$");
          preProcessedLines.push(`[LabelledRow]:${line}    ${valuesStr.trim()}`);
        } else {
          preProcessedLines.push(line);
        }
        continue;
      }

      // Date range pattern row divider check
      if (dateRangeRegex.test(line)) {
        preProcessedLines.push(`[RowDivider]:${line}`);
        lIdx++;
        
        // Indent the values on the next lines
        if (lIdx < rawCleanLines.length) {
          let valuesStr = "";
          while (lIdx < rawCleanLines.length && isFinancialToken(rawCleanLines[lIdx])) {
            valuesStr += "   " + rawCleanLines[lIdx];
            lIdx++;
          }
          if (valuesStr) {
            valuesStr = valuesStr.replace(/\$\s+/g, "$");
            preProcessedLines.push(`[RowDividerValues]:${valuesStr.trim()}`);
          }
        }
        continue;
      }

      // Column header fragments check
      let count = 0;
      while (
        lIdx + count < rawCleanLines.length &&
        rawCleanLines[lIdx + count].trim().length > 0 &&
        rawCleanLines[lIdx + count].length < 25 &&
        !rawCleanLines[lIdx + count].includes('$') &&
        !rawCleanLines[lIdx + count].includes('%') &&
        !/\d/.test(rawCleanLines[lIdx + count]) &&
        !dateRangeRegex.test(rawCleanLines[lIdx + count])
      ) {
        count++;
      }

      if (count >= 3) {
        const groupLines = rawCleanLines.slice(lIdx, lIdx + count);
        const joinedText = groupLines.join(" ");
        preProcessedLines.push(`[MutedHeader]:${joinedText}`);
        lIdx += count;
      } else {
        preProcessedLines.push(rawCleanLines[lIdx]);
        lIdx++;
      }
    }

    // Fix duplicate rendering issue — remove consecutive duplicate lines
    const uniqueCleanLines: string[] = [];
    for (const line of preProcessedLines) {
      if (uniqueCleanLines.length === 0 || line !== uniqueCleanLines[uniqueCleanLines.length - 1]) {
        uniqueCleanLines.push(line);
      }
    }

    const finalCleanLines = uniqueCleanLines;



    // Linear O(N) search to find all maximal qualifying table blocks
    interface TableRange {
      start: number;
      end: number;
    }

    const tableRanges: TableRange[] = [];
    let rIdx = 0;
    while (rIdx < finalCleanLines.length) {
      if (isFinancialToken(finalCleanLines[rIdx])) {
        const startRun = rIdx;
        while (rIdx < finalCleanLines.length && isFinancialToken(finalCleanLines[rIdx])) {
          rIdx++;
        }
        const endRun = rIdx - 1;
        
        if (endRun - startRun + 1 >= 4) {
          let start = startRun;
          while (start > 0) {
            const prevLine = finalCleanLines[start - 1];
            if (prevLine.length > 80 || prevLine.trim() === "" || prevLine.startsWith("[RowDivider]")) {
              break;
            }
            start--;
          }
          
          let end = endRun;
          while (end + 1 < finalCleanLines.length) {
            const nextLine = finalCleanLines[end + 1];
            if (nextLine.length > 80 || nextLine.trim() === "" || nextLine.startsWith("[RowDivider]")) {
              break;
            }
            end++;
          }
          
          let startsMidSentence = false;
          if (start > 0) {
            const prevLine = finalCleanLines[start - 1].trim();
            const isPrevHeader = prevLine.length < 60 && !prevLine.includes("$") && !/\d/.test(prevLine) && (
              prevLine === prevLine.toUpperCase() || isTitleCase(prevLine)
            );
            const endsWithColon = prevLine.endsWith(":");
            if (!endsWithColon && !isPrevHeader && !prevLine.startsWith("[RowDivider]")) {
              startsMidSentence = true;
            }
          }
          
          if (!startsMidSentence) {
            tableRanges.push({ start, end });
            rIdx = end + 1;
          }
        }
      } else {
        rIdx++;
      }
    }

    interface FinalBlock {
      type: "table" | "header" | "paragraph";
      lines: string[];
    }

    const finalBlocks: FinalBlock[] = [];
    let currentPos = 0;

    for (const range of tableRanges) {
      // Process lines preceding the table
      while (currentPos < range.start) {
        const line = finalCleanLines[currentPos];
        currentPos++;
        if (!line.trim()) continue;

        const isHeader = line.length < 60 && !line.includes("$") && !/\d/.test(line) && (
          line === line.toUpperCase() || isTitleCase(line)
        );

        if (isHeader) {
          finalBlocks.push({ type: "header", lines: [line] });
        } else {
          if (finalBlocks.length > 0 && finalBlocks[finalBlocks.length - 1].type === "paragraph") {
            finalBlocks[finalBlocks.length - 1].lines.push(line);
          } else {
            finalBlocks.push({ type: "paragraph", lines: [line] });
          }
        }
      }

      // Process the table range
      const tableLines = finalCleanLines.slice(range.start, range.end + 1);
      finalBlocks.push({ type: "table", lines: tableLines });
      currentPos = range.end + 1;
    }

    // Process remaining lines after last table
    while (currentPos < finalCleanLines.length) {
      const line = finalCleanLines[currentPos];
      currentPos++;
      if (!line.trim()) continue;

      const isHeader = line.length < 60 && !line.includes("$") && !/\d/.test(line) && (
        line === line.toUpperCase() || isTitleCase(line)
      );

      if (isHeader) {
        finalBlocks.push({ type: "header", lines: [line] });
      } else {
        if (finalBlocks.length > 0 && finalBlocks[finalBlocks.length - 1].type === "paragraph") {
          finalBlocks[finalBlocks.length - 1].lines.push(line);
        } else {
          finalBlocks.push({ type: "paragraph", lines: [line] });
        }
      }
    }

    return (
      <div className="space-y-4">
        {finalBlocks.map((block, bIdx) => {
          if (block.type === "table") {
            const scannedRows: string[] = [];
            let idxLine = 0;
            while (idxLine < block.lines.length) {
              const currentLine = block.lines[idxLine];
              if (isFinancialToken(currentLine)) {
                let merged = currentLine;
                idxLine++;
                while (idxLine < block.lines.length && isFinancialToken(block.lines[idxLine])) {
                  merged += "   " + block.lines[idxLine];
                  idxLine++;
                }
                merged = merged.replace(/\$\s+/g, "$");
                scannedRows.push(merged);
              } else {
                let merged = currentLine;
                idxLine++;
                let gatheredTokens = false;
                let tokensStr = "";
                while (idxLine < block.lines.length && isFinancialToken(block.lines[idxLine])) {
                  tokensStr += "   " + block.lines[idxLine];
                  idxLine++;
                  gatheredTokens = true;
                }
                if (gatheredTokens) {
                  let fullRow = merged + "   " + tokensStr.trim();
                  fullRow = fullRow.replace(/\$\s+/g, "$");
                  scannedRows.push(fullRow);
                } else {
                  scannedRows.push(merged);
                }
              }
            }

            return (
              <pre
                key={bIdx}
                className="text-[11px] text-slate-200 bg-slate-900/60 rounded-lg p-4 border border-slate-700/50 my-3 font-mono leading-7 overflow-x-auto"
              >
                {renderTextWithHighlight(scannedRows.join("\n"))}
              </pre>
            );
          }

          if (block.type === "header") {
            return (
              <div key={bIdx} className="space-y-1">
                {block.lines.map((line, lIdx) => (
                  <p
                    key={`${bIdx}-${lIdx}`}
                    className="text-indigo-300 font-semibold text-[12px] tracking-wide mt-5 mb-1"
                  >
                    {renderTextWithHighlight(line)}
                  </p>
                ))}
              </div>
            );
          }

          // Normal Paragraphs sentence-joining logic
          const paragraphs: React.ReactNode[] = [];
          let currentParagraph = "";

          for (const line of block.lines) {
            if (line.startsWith("[MutedHeader]:")) {
              if (currentParagraph) {
                paragraphs.push(
                  <p
                    key={paragraphs.length}
                    className="text-slate-300 text-[12px] leading-7 font-light mb-3"
                  >
                    {renderTextWithHighlight(currentParagraph)}
                  </p>
                );
                currentParagraph = "";
              }
              const cleanText = line.substring("[MutedHeader]:".length);
              paragraphs.push(
                <p key={paragraphs.length} className="text-slate-500 text-[10px] italic mb-2">
                  [Table header: {renderTextWithHighlight(cleanText)}]
                </p>
              );
            } else if (line.startsWith("[RowDivider]:")) {
              if (currentParagraph) {
                paragraphs.push(
                  <p
                    key={paragraphs.length}
                    className="text-slate-300 text-[12px] leading-7 font-light mb-3"
                  >
                    {renderTextWithHighlight(currentParagraph)}
                  </p>
                );
                currentParagraph = "";
              }
              const cleanText = line.substring("[RowDivider]:".length);
              paragraphs.push(
                <p key={paragraphs.length} className="text-indigo-200 font-semibold text-[11px] mt-3 mb-1 border-t border-slate-800 pt-2">
                  {renderTextWithHighlight(cleanText)}
                </p>
              );
            } else if (line.startsWith("[RowDividerValues]:")) {
              if (currentParagraph) {
                paragraphs.push(
                  <p
                    key={paragraphs.length}
                    className="text-slate-300 text-[12px] leading-7 font-light mb-3"
                  >
                    {renderTextWithHighlight(currentParagraph)}
                  </p>
                );
                currentParagraph = "";
              }
              const cleanText = line.substring("[RowDividerValues]:".length);
              paragraphs.push(
                <p key={paragraphs.length} className="text-slate-300 text-[11px] font-mono pl-4 mb-1">
                  {renderTextWithHighlight(cleanText)}
                </p>
              );
            } else if (line.startsWith("[LabelledRow]:")) {
              if (currentParagraph) {
                paragraphs.push(
                  <p
                    key={paragraphs.length}
                    className="text-slate-300 text-[12px] leading-7 font-light mb-3"
                  >
                    {renderTextWithHighlight(currentParagraph)}
                  </p>
                );
                currentParagraph = "";
              }
              const cleanText = line.substring("[LabelledRow]:".length);
              paragraphs.push(
                <pre key={paragraphs.length} className="text-[11px] text-slate-200 bg-slate-900/60 rounded-lg p-3 border border-slate-700/50 my-2 font-mono">
                  {renderTextWithHighlight(cleanText)}
                </pre>
              );
            } else {
              if (currentParagraph) {
                currentParagraph += " " + line;
              } else {
                currentParagraph = line;
              }

              const endsWithPunctuation = /[.!?]$/.test(line);
              if (endsWithPunctuation) {
                paragraphs.push(
                  <p
                    key={paragraphs.length}
                    className="text-slate-300 text-[12px] leading-7 font-light mb-3"
                  >
                    {renderTextWithHighlight(currentParagraph)}
                  </p>
                );
                currentParagraph = "";
              }
            }
          }
          if (currentParagraph) {
            paragraphs.push(
              <p
                key={paragraphs.length}
                className="text-slate-300 text-[12px] leading-7 font-light mb-3"
              >
                {renderTextWithHighlight(currentParagraph)}
              </p>
            );
          }

          return (
            <div key={bIdx} className="space-y-3">
              {paragraphs}
            </div>
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

        <div className="flex items-center space-x-4">
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
          <div className="glass-panel p-4 flex flex-col h-[35%] overflow-hidden relative border-indigo-900/40">
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
                <p className="text-xs text-slate-400">System is idle. Upload a financial PDF (10-K / 10-Q) to run the multi-agent pipeline.</p>
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

          {/* 2. RAG chat + in-chat peer comparison */}
          <div className="glass-panel p-4 flex flex-col h-[65%] overflow-hidden border-indigo-900/40">
            <h2 className="text-xs font-semibold tracking-wider text-indigo-300/80 mb-1 uppercase flex items-center gap-2">
              <Bot className="w-4 h-4 text-indigo-400" />
              RAG CHAT &amp; PEER COMPARISON
            </h2>
            <p className="text-[10px] text-slate-500 mb-3">
              Ask filing questions or name a peer in chat to compare (live SEC/web fetch).
            </p>

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
                    <div className={`p-3 rounded-lg text-xs leading-relaxed max-w-[90%] whitespace-pre-wrap ${
                      msg.role === "user" 
                        ? "bg-indigo-600 text-white rounded-br-none" 
                        : msg.isStatus
                        ? "bg-purple-950/30 text-purple-200 border border-purple-800/40 rounded-bl-none italic"
                        : msg.guardrailBlocked
                        ? "bg-red-950/30 text-red-100 border border-red-900/50 rounded-bl-none"
                        : msg.mode === "comparison"
                        ? "bg-purple-950/25 text-slate-200 border border-purple-900/40 rounded-bl-none"
                        : "bg-indigo-950/40 text-slate-200 border border-indigo-900/30 rounded-bl-none"
                    }`}>
                      {msg.content}

                      {msg.mode === "comparison" && msg.comparison?.competitor_benchmarks?.length > 0 && (
                        <div className="mt-3 pt-2 border-t border-purple-900/40">
                          <span className="text-[9px] text-purple-300 font-semibold uppercase block mb-1.5">Benchmark table</span>
                          <table className="w-full text-[10px] font-mono">
                            <thead>
                              <tr className="text-purple-400 text-[8px] uppercase border-b border-purple-950/50">
                                <th className="pb-1 text-left">Metric</th>
                                <th className="pb-1 text-right">vs Peer</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-purple-950/30 text-slate-300">
                              {msg.comparison.competitor_benchmarks.map((bm: any, bIdx: number) => (
                                <tr key={bIdx}>
                                  <td className="py-1 pr-2">{bm.metric_name}</td>
                                  <td className="py-1 text-right text-purple-300">{bm.comparison_value}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                      
                      {/* Interactive Citations list inside assistant messages */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="mt-2.5 pt-2.5 border-t border-indigo-900/40 space-y-1">
                          <span className="text-[9px] text-indigo-400 font-semibold block uppercase">Retrieved Citations:</span>
                          <div className="flex flex-wrap gap-1">
                            {msg.citations.map((cit: any, cIdx: number) => (
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
                  <span>
                    {chatLoadingComparison
                      ? "Scraping peer filings and running SLM comparison..."
                      : "RAG engine searching vector store..."}
                  </span>
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Chat Input form */}
            <form onSubmit={handleSendMessage} className="flex gap-2">
              <input
                type="text"
                placeholder={activeReportId ? "Ask about risks, or compare vs a named company..." : "Load a report first..."}
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
                  <p className="text-xs text-slate-400">Filing narrative will display here once a PDF is processed.</p>
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
                    <ResponsiveContainer width="100%" height={140} minWidth={0}>
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
          <div className="glass-panel p-5 flex flex-col flex-1 overflow-hidden border-indigo-900/40">
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
                (activeReport.result?.risks ?? []).map((risk: any, index: number) => {
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
        </section>

      </main>
    </div>
  );
}
