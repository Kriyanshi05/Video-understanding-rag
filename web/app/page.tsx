"use client";

import React, { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// --- Types ---

type JobStatus =
  | "queued"
  | "extracting_audio"
  | "transcribing"
  | "chunking"
  | "embedding"
  | "indexing"
  | "done"
  | "failed";

interface Source {
  text: string;
  start_time: number;
  end_time: number;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  mode?: "grounded" | "general_knowledge" | "visual";
  sources?: Source[];
  fallback_used?: boolean;
}

// --- Helpers ---

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

// --- Components ---

function IngestZone({ onIngestComplete }: { onIngestComplete: (jobId: string) => void }) {
  const [tab, setTab] = useState<"file" | "url">("file");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsSubmitting(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/ingest`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        throw new Error(`Upload failed with status ${res.status}`);
      }
      const data = await res.json();
      if (data.job_id) {
        onIngestComplete(data.job_id);
      } else {
        throw new Error("No job_id returned from server");
      }
    } catch (err: any) {
      setError(err.message || "An error occurred during upload.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const res = await fetch(`${API_BASE}/ingest-url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Ingest failed with status ${res.status}`);
      }
      if (data.job_id) {
        onIngestComplete(data.job_id);
      } else {
        throw new Error("No job_id returned from server");
      }
    } catch (err: any) {
      setError(err.message || "An error occurred during URL ingest.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto flex flex-col bg-slate-900/60 backdrop-blur-sm border border-indigo-500/20 shadow-[0_8px_30px_rgb(79,70,229,0.05)] rounded-2xl overflow-hidden transition-all duration-300">
      
      {/* Tabs */}
      <div className="flex border-b border-indigo-500/10 bg-slate-950/40">
        <button 
          onClick={() => { setTab("file"); setError(null); }}
          className={`flex-1 py-4 text-sm font-medium uppercase tracking-widest transition-colors ${tab === "file" ? "text-indigo-400 border-b-2 border-indigo-500" : "text-gray-500 hover:text-gray-300"}`}
        >
          Upload File
        </button>
        <button 
          onClick={() => { setTab("url"); setError(null); }}
          className={`flex-1 py-4 text-sm font-medium uppercase tracking-widest transition-colors ${tab === "url" ? "text-indigo-400 border-b-2 border-indigo-500" : "text-gray-500 hover:text-gray-300"}`}
        >
          Paste URL
        </button>
      </div>

      <div className="p-10 md:p-14">
        {tab === "file" ? (
          <div 
            className="flex flex-col items-center justify-center py-12 px-6 border-2 border-dashed border-indigo-500/20 rounded-xl bg-slate-800/30 hover:bg-slate-800/50 hover:border-indigo-500/50 transition-all duration-300 cursor-pointer group"
            onClick={() => !isSubmitting && fileInputRef.current?.click()}
          >
            <input
              type="file"
              accept="video/mp4,video/quicktime,video/x-matroska,video/webm"
              className="hidden"
              ref={fileInputRef}
              onChange={handleFileChange}
              disabled={isSubmitting}
            />
            <div className={`text-indigo-400 mb-6 transition-transform duration-300 ${isSubmitting ? 'animate-pulse' : 'group-hover:scale-110'}`}>
              <svg className="w-16 h-16 mx-auto drop-shadow-[0_0_15px_rgba(99,102,241,0.4)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <h3 className="text-xl font-medium text-gray-200 mb-2">
              {isSubmitting ? "Uploading video..." : "Click or drag video to upload"}
            </h3>
            <p className="text-gray-500 text-sm">
              Supports .mp4, .mov, .mkv, .webm
            </p>
          </div>
        ) : (
          <form onSubmit={handleUrlSubmit} className="flex flex-col gap-6">
            <div>
              <label htmlFor="url-input" className="block text-xs uppercase tracking-widest text-gray-500 mb-3">
                YouTube or Video URL
              </label>
              <input
                id="url-input"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                disabled={isSubmitting}
                className="w-full bg-slate-950/50 border border-indigo-500/20 rounded-xl py-4 px-5 text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all shadow-inner"
              />
            </div>
            <button
              type="submit"
              disabled={isSubmitting || !url.trim()}
              className="w-full py-4 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:from-slate-800 disabled:to-slate-800 disabled:text-gray-600 text-white font-medium rounded-xl transition-all duration-150 shadow-[0_0_15px_rgba(99,102,241,0.2)] hover:shadow-[0_0_25px_rgba(99,102,241,0.5)] active:scale-[0.98] disabled:shadow-none"
            >
              {isSubmitting ? "Downloading..." : "Ingest Video"}
            </button>
          </form>
        )}

        {error && (
          <div className="mt-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm animate-in fade-in slide-in-from-bottom-2">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

const STAGES = [
  { id: "queued", label: "Queued" },
  { id: "extracting_audio", label: "Extracting Audio" },
  { id: "transcribing", label: "Transcribing" },
  { id: "chunking", label: "Chunking" },
  { id: "embedding", label: "Embedding" },
  { id: "indexing", label: "Indexing" },
  { id: "done", label: "Ready" }
];

function ProcessingStatus({ jobId, onComplete }: { jobId: string; onComplete: () => void }) {
  const [status, setStatus] = useState<string>("queued");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const pollStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/ingest/${jobId}`);
        if (!res.ok) throw new Error("Failed to fetch status");
        const data = await res.json();
        
        setStatus(data.status);
        if (data.error) setError(data.error);

        if (data.status === "done") {
          onComplete();
        }
      } catch (err: any) {
        console.error("Polling error:", err);
      }
    };

    pollStatus();
    intervalId = setInterval(pollStatus, 2000);

    return () => clearInterval(intervalId);
  }, [jobId, onComplete]);

  if (status === "failed") {
    return (
      <div className="p-8 bg-red-950/40 border border-red-900/50 rounded-2xl text-center shadow-xl shadow-black/40 backdrop-blur-md max-w-xl w-full mx-auto">
        <div className="text-red-500 mb-5">
          <svg className="w-14 h-14 mx-auto drop-shadow-md" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        </div>
        <h3 className="text-xl font-semibold text-red-300 mb-3 tracking-wide">Processing Failed</h3>
        <p className="text-red-200/70 text-sm leading-relaxed">{error || "An unknown error occurred during processing."}</p>
      </div>
    );
  }

  const currentStageIndex = STAGES.findIndex(s => s.id === status);
  // Fallback to 0 if unknown status
  const activeIndex = currentStageIndex >= 0 ? currentStageIndex : 0;

  return (
    <div className="p-10 bg-slate-900/60 backdrop-blur-sm border border-indigo-500/20 rounded-2xl flex flex-col items-center shadow-[0_8px_30px_rgb(79,70,229,0.05)] max-w-4xl w-full mx-auto">
      <h3 className="text-sm font-medium text-gray-400 uppercase tracking-widest mb-10">Processing Video Pipeline</h3>
      
      {/* Horizontal Stepper */}
      <div className="w-full flex justify-between items-center relative px-4">
        {/* Connecting line background */}
        <div className="absolute top-1/2 left-8 right-8 h-0.5 bg-slate-800 -z-10 -translate-y-1/2"></div>
        {/* Connecting line active progress */}
        <div 
          className="absolute top-1/2 left-8 h-0.5 bg-indigo-500 -z-10 -translate-y-1/2 transition-all duration-700 ease-in-out"
          style={{ width: `calc(${(activeIndex / (STAGES.length - 1)) * 100}% - 4rem)` }}
        ></div>

        {STAGES.map((stage, idx) => {
          const isCompleted = idx < activeIndex;
          const isActive = idx === activeIndex;
          
          return (
            <div key={stage.id} className="flex flex-col items-center gap-3 relative z-10 w-24">
              <div 
                className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-500
                  ${isCompleted ? 'bg-gradient-to-tr from-indigo-600 to-violet-600 text-white shadow-[0_0_15px_rgba(99,102,241,0.5)]' : 
                    isActive ? 'bg-slate-900 border-2 border-indigo-400 text-indigo-300 shadow-[0_0_20px_rgba(99,102,241,0.6)] animate-pulse' : 
                    'bg-slate-800 border border-slate-700 text-gray-500'}
                `}
              >
                {isCompleted ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" /></svg>
                ) : (
                  <span className="text-xs font-semibold">{idx + 1}</span>
                )}
              </div>
              <span className={`text-[10px] uppercase tracking-widest text-center whitespace-nowrap transition-colors duration-300
                ${isCompleted || isActive ? 'text-gray-200' : 'text-gray-600'}
              `}>
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>
      <p className="text-gray-500 text-xs font-mono mt-12 bg-slate-950/50 px-4 py-2 rounded-lg border border-indigo-500/10">
        Job ID: {jobId}
      </p>
    </div>
  );
}

function VideoWorkspace({ jobId }: { jobId: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const handleSendQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/query/${jobId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: userMessage.content }),
      });
      if (!res.ok) throw new Error("Query failed");
      const data = await res.json();

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.answer,
        mode: data.mode,
        sources: data.sources,
        fallback_used: data.fallback_used,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      console.error(err);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "Sorry, I encountered an error while trying to communicate with the server.",
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExplainScreen = async () => {
    const video = videoRef.current;
    if (!video) return;

    // Create an offscreen canvas to capture the current frame
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    
    // Draw current video frame to canvas
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    // Convert canvas to Blob
    canvas.toBlob(async (blob) => {
      if (!blob) return;

      const timestamp = formatTime(video.currentTime);
      const userMessage: Message = {
        id: Date.now().toString(),
        role: "user",
        content: `Explain what's on screen at ${timestamp}`,
      };
      
      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);

      const formData = new FormData();
      formData.append("file", blob, "frame.jpg");
      
      try {
        const res = await fetch(`${API_BASE}/explain-screen`, {
          method: "POST",
          body: formData
        });
        if (!res.ok) throw new Error("Explanation failed");
        const data = await res.json();

        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: data.answer,
          mode: "visual",
        };
        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        console.error(err);
        const errorMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: "Sorry, I encountered an error while trying to explain the screen.",
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
      }
    }, "image/jpeg", 0.9);
  };

  const handleSeek = (timeInSeconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = timeInSeconds;
      videoRef.current.play();
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_1fr] xl:grid-cols-[1.5fr_1fr] gap-6 lg:gap-8 h-[75vh] min-h-[600px]">
      
      {/* Video Side */}
      <div className="flex flex-col bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-indigo-500/20 shadow-[0_8px_30px_rgb(79,70,229,0.05)]">
        {/* We use an aspect-video container so the video doesn't have overflow-hidden clipping its native controls */}
        <div className="flex-1 p-4 flex flex-col justify-center">
          <div className="w-full aspect-video bg-black rounded-xl overflow-hidden relative shadow-inner">
            <video 
              ref={videoRef}
              src={`${API_BASE}/media/${jobId}`} 
              controls 
              crossOrigin="anonymous"
              className="w-full h-full object-contain block"
            />
          </div>
        </div>
        
        <div className="p-5 border-t border-indigo-500/10 flex justify-between items-center bg-slate-950/30 rounded-b-2xl">
          <span className="text-xs text-gray-500 font-mono tracking-wider uppercase">Job ID: {jobId.split('-')[0]}</span>
          
          <button 
            onClick={handleExplainScreen}
            className="px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white rounded-lg text-sm font-medium transition-all duration-150 shadow-[0_0_15px_rgba(99,102,241,0.2)] hover:shadow-[0_0_20px_rgba(99,102,241,0.5)] active:scale-95 flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
            Explain What's On Screen
          </button>
        </div>
      </div>

      {/* Chat Side */}
      <div className="flex flex-col h-full bg-slate-900/60 backdrop-blur-sm rounded-2xl border border-indigo-500/20 shadow-[0_8px_30px_rgb(79,70,229,0.05)] overflow-hidden">
        <div className="px-6 py-4 bg-slate-950/40 border-b border-indigo-500/10 flex items-center justify-between z-10">
          <h3 className="text-xs uppercase tracking-widest font-medium text-gray-400">Video Chat</h3>
          <span className="flex items-center gap-2 text-xs font-medium text-emerald-400 bg-emerald-400/10 px-3 py-1.5 rounded-md border border-emerald-400/20 shadow-[0_0_10px_rgba(52,211,153,0.1)]">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            Ready
          </span>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8 scroll-smooth relative">
          {messages.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-gray-500 gap-4">
              <div className="w-16 h-16 rounded-full bg-slate-800/50 flex items-center justify-center border border-indigo-500/10 shadow-inner">
                <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
              </div>
              <p className="text-sm font-light">Ask a question about the video contents...</p>
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"} relative z-10 items-end`}>
              {/* Avatar */}
              <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center shadow-md ${
                msg.role === "user" 
                  ? "bg-gradient-to-tr from-violet-500 to-fuchsia-500" 
                  : "bg-gradient-to-tr from-indigo-500 to-cyan-500"
              }`}>
                {msg.role === "user" ? (
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                ) : (
                  <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                )}
              </div>
              
              <div className={`max-w-[80%] rounded-2xl px-5 py-4 shadow-lg ${
                msg.role === "user" 
                  ? "bg-slate-800 border border-white/5 text-white rounded-br-sm" 
                  : "bg-slate-900/80 backdrop-blur-md border border-indigo-500/20 text-gray-200 rounded-bl-sm"
              }`}>
                {/* Mode Badges */}
                {msg.role === "assistant" && (msg.mode === "general_knowledge" || msg.fallback_used) && (
                  <div className="flex items-center gap-2 text-amber-300 text-[11px] uppercase tracking-wider font-semibold mb-3 bg-amber-400/10 w-fit px-3 py-1.5 rounded-md border border-amber-400/20">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                    General Knowledge
                  </div>
                )}
                
                {msg.role === "assistant" && msg.mode === "visual" && (
                  <div className="flex items-center gap-2 text-fuchsia-300 text-[11px] uppercase tracking-wider font-semibold mb-3 bg-fuchsia-500/10 w-fit px-3 py-1.5 rounded-md border border-fuchsia-500/20 shadow-[0_0_10px_rgba(217,70,239,0.1)]">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" /></svg>
                    Screen Explanation
                  </div>
                )}

                <div className="text-[15px] leading-relaxed font-light whitespace-normal">
                  {msg.role === "user" ? (
                    msg.content
                  ) : (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h1: ({node, ...props}) => <h1 className="text-xl font-bold mt-4 mb-2" {...props} />,
                        h2: ({node, ...props}) => <h2 className="text-lg font-bold mt-4 mb-2 text-indigo-300" {...props} />,
                        h3: ({node, ...props}) => <h3 className="text-md font-bold mt-3 mb-2" {...props} />,
                        p: ({node, ...props}) => <p className="mb-3 last:mb-0" {...props} />,
                        ul: ({node, ...props}) => <ul className="list-disc pl-5 mb-3 space-y-1" {...props} />,
                        ol: ({node, ...props}) => <ol className="list-decimal pl-5 mb-3 space-y-1" {...props} />,
                        strong: ({node, ...props}) => <strong className="font-semibold text-indigo-200" {...props} />,
                        code: ({node, inline, ...props}: any) => 
                          inline ? (
                            <code className="bg-slate-800/80 px-1.5 py-0.5 rounded text-indigo-300 font-mono text-[13px]" {...props} />
                          ) : (
                            <pre className="bg-slate-900/80 p-3 rounded-lg overflow-x-auto mb-3 border border-white/10"><code className="text-indigo-300 font-mono text-[13px]" {...props} /></pre>
                          ),
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  )}
                </div>

                {/* Sources */}
                {msg.role === "assistant" && msg.mode === "grounded" && msg.sources && msg.sources.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-indigo-500/10 flex flex-wrap gap-2 items-center">
                    <span className="text-[10px] uppercase tracking-widest text-gray-500 mr-1">Sources:</span>
                    {msg.sources.map((src, i) => (
                      <button 
                        key={i}
                        onClick={() => handleSeek(src.start_time)}
                        className="text-xs bg-slate-950/50 hover:bg-indigo-900/40 border border-indigo-500/20 px-3 py-1.5 rounded-md text-indigo-300 transition-all flex items-center gap-1.5 hover:border-indigo-500/50 hover:scale-105 hover:brightness-110 active:scale-95 cursor-pointer"
                        title={src.text}
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        {formatTime(src.start_time)}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start relative z-10 pl-11">
              <div className="bg-slate-800/80 backdrop-blur-sm border border-indigo-500/10 rounded-2xl rounded-bl-sm px-5 py-4 flex gap-1.5 items-center shadow-lg">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }}></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} className="h-1" />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-slate-950/60 border-t border-indigo-500/10 backdrop-blur-md z-10">
          <form onSubmit={handleSendQuery} className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading}
              placeholder="Ask about the video..."
              className="w-full bg-slate-900 border border-indigo-500/20 rounded-xl py-4 pl-5 pr-14 text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all disabled:opacity-50 shadow-inner"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="absolute right-2.5 p-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 disabled:opacity-50 disabled:pointer-events-none text-white rounded-lg transition-all duration-150 shadow-[0_0_10px_rgba(99,102,241,0.3)] hover:shadow-[0_0_15px_rgba(99,102,241,0.5)] active:scale-95"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" /></svg>
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [isProcessed, setIsProcessed] = useState(false);

  const handleNewVideo = () => {
    // If we've started processing or finished, confirm before resetting
    if (jobId || isProcessed) {
      if (!confirm("Start a new video? Current chat and processing will be cleared.")) {
        return;
      }
    }
    setJobId(null);
    setIsProcessed(false);
  };

  return (
    <div className="relative min-h-screen bg-[#09090b] text-gray-100 font-sans pt-20 pb-12 px-6 md:px-8 lg:px-12 overflow-hidden selection:bg-indigo-500/30 selection:text-white">
      
      {/* Slim Top Bar */}
      <header className="fixed top-0 left-0 right-0 h-16 bg-[#09090b]/80 backdrop-blur-md border-b border-indigo-500/20 z-50 flex items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 rounded bg-gradient-to-tr from-indigo-500 to-violet-500 shadow-[0_0_10px_rgba(99,102,241,0.4)] flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
          </div>
          <span className="font-semibold text-gray-200 tracking-wide text-sm uppercase">Video Understanding</span>
        </div>
        
        {/* New Video Button */}
        {(jobId || isProcessed) && (
          <button 
            onClick={handleNewVideo}
            className="flex items-center gap-2 text-xs font-medium text-gray-400 hover:text-white bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg transition-colors border border-white/10"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
            New Video
          </button>
        )}
      </header>

      {/* Ambient background glows */}
      <div className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] bg-indigo-600/10 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[50vw] h-[50vw] bg-violet-600/10 rounded-full blur-[120px] pointer-events-none"></div>

      <div className="relative max-w-7xl mx-auto h-full flex flex-col z-10">
        <header className="mb-14 text-center mt-6">
          <h2 className="text-5xl lg:text-6xl font-extrabold tracking-tight text-white inline-block relative">
            Video Understanding
            <div className="absolute -bottom-2 left-0 right-0 h-1 bg-gradient-to-r from-indigo-500 to-violet-500 rounded-full"></div>
          </h2>
          <p className="text-gray-400 mt-6 text-lg max-w-2xl mx-auto font-light leading-relaxed">
            Upload or paste a link to a video, and chat with its contents using Retrieval-Augmented Generation.
          </p>
        </header>

        <main className="flex-1 flex flex-col">
          {!jobId && (
            <div className="w-full mt-4 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <IngestZone onIngestComplete={setJobId} />
            </div>
          )}

          {jobId && !isProcessed && (
            <div className="w-full mt-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
              <ProcessingStatus 
                jobId={jobId} 
                onComplete={() => setIsProcessed(true)} 
              />
            </div>
          )}

          {jobId && isProcessed && (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
              <VideoWorkspace jobId={jobId} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
