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
  is_error?: boolean;
  retry_content?: string;
  verification?: {
    verified: boolean | null;
    confidence: string | null;
    note: string;
  };
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
    <div className="w-full max-w-3xl mx-auto flex flex-col bg-white border-2 border-black shadow-[4px_4px_0px_0px_#000000] rounded-xl overflow-hidden transition-all duration-300">
      
      {/* Tabs */}
      <div className="flex border-b-2 border-black bg-transparent">
        <button 
          onClick={() => { setTab("file"); setError(null); }}
          className={`flex-1 py-4 text-sm font-bold uppercase tracking-widest transition-colors ${tab === "file" ? "text-black border-b-4 border-black bg-white" : "text-black/60 hover:text-black hover:bg-white/50"}`}
        >
          Upload File
        </button>
        <button 
          onClick={() => { setTab("url"); setError(null); }}
          className={`flex-1 py-4 text-sm font-bold uppercase tracking-widest transition-colors ${tab === "url" ? "text-black border-b-4 border-black bg-white" : "text-black/60 hover:text-black hover:bg-white/50"}`}
        >
          Paste URL
        </button>
      </div>

      <div className="p-10 md:p-14">
        {tab === "file" ? (
          <div 
            className="flex flex-col items-center justify-center py-12 px-6 border-4 border-dashed border-black rounded-xl bg-transparent hover:bg-white shadow-[4px_4px_0px_0px_#000000] transition-all duration-300 cursor-pointer group hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-[2px_2px_0px_0px_#000000]"
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
            <div className={`text-black mb-6 transition-transform duration-300 ${isSubmitting ? 'animate-pulse' : 'group-hover:scale-110'}`}>
              <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <h3 className="text-xl font-display font-extrabold text-black mb-2 tracking-tight uppercase">
              {isSubmitting ? "Uploading video..." : "Click or drag video"}
            </h3>
            <p className="text-black/70 text-sm font-mono font-bold">
              Supports .mp4, .mov, .mkv, .webm
            </p>
          </div>
        ) : (
          <form onSubmit={handleUrlSubmit} className="flex flex-col gap-6">
            <div>
              <label htmlFor="url-input" className="block text-xs font-bold uppercase tracking-widest text-black mb-3">
                YouTube or Video URL
              </label>
              <input
                id="url-input"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                disabled={isSubmitting}
                className="w-full bg-white border-2 border-black shadow-[3px_3px_0px_0px_#000000] rounded-md py-4 px-5 text-black font-mono placeholder-[#121212]/40 focus:outline-none focus:translate-x-[2px] focus:translate-y-[2px] focus:shadow-[1px_1px_0px_0px_#000000] transition-all"
              />
            </div>
            <button
              type="submit"
              disabled={isSubmitting || !url.trim()}
              className="w-full py-4 bg-[#FF4D00] disabled:bg-gray-300 disabled:text-gray-500 disabled:border-black text-white font-display font-extrabold uppercase tracking-widest rounded-full border-2 border-black shadow-[3px_3px_0px_0px_#000000] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none disabled:shadow-none disabled:translate-x-0 disabled:translate-y-0 transition-all duration-150"
            >
              {isSubmitting ? "Downloading..." : "Ingest Video"}
            </button>
          </form>
        )}

        {error && (
          <div className="mt-6 p-4 bg-white border-2 border-black shadow-[3px_3px_0px_0px_#000000] rounded-md text-black font-mono font-bold text-sm animate-in fade-in slide-in-from-bottom-2">
            ERROR: {error}
          </div>
        )}
      </div>
    </div>
  );
}

const STAGES = [
  { id: "queued", label: "Queued" },
  { id: "downloading", label: "Downloading" },
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
      <div className="p-8 bg-white border-4 border-black rounded-xl text-center shadow-[6px_6px_0px_0px_#000000] max-w-xl w-full mx-auto">
        <div className="text-black mb-5">
          <svg className="w-14 h-14 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        </div>
        <h3 className="text-xl font-display font-extrabold uppercase text-black mb-3 tracking-tight">Processing Failed</h3>
        <p className="text-black/80 font-mono font-bold text-sm leading-relaxed">{error || "An unknown error occurred during processing."}</p>
      </div>
    );
  }

  const currentStageIndex = STAGES.findIndex(s => s.id === status);
  // Fallback to 0 if unknown status
  const activeIndex = currentStageIndex >= 0 ? currentStageIndex : 0;

  return (
    <div className="p-10 bg-white border-2 border-black rounded-xl flex flex-col items-center shadow-[4px_4px_0px_0px_#000000] max-w-4xl w-full mx-auto">
      <h3 className="text-sm font-display font-extrabold text-black uppercase tracking-widest mb-10 border-b-2 border-black pb-1">Processing Pipeline</h3>
      
      {/* Horizontal Stepper */}
      <div className="w-full flex justify-between items-center relative px-4">
        {/* Connecting line background */}
        <div className="absolute top-1/2 left-8 right-8 h-1 bg-black/10 -z-10 -translate-y-1/2 rounded-full border-t border-dashed border-black/30"></div>
        {/* Connecting line active progress */}
        <div 
          className="absolute top-1/2 left-8 h-1 bg-black -z-10 -translate-y-1/2 transition-all duration-700 ease-in-out border-t-2 border-black"
          style={{ width: `calc(${(activeIndex / (STAGES.length - 1)) * 100}% - 4rem)` }}
        ></div>

        {STAGES.map((stage, idx) => {
          const isCompleted = idx < activeIndex;
          const isActive = idx === activeIndex;
          
          return (
                       <div key={stage.id} className="flex flex-col items-center gap-3 relative z-10 w-20 md:w-24">
              <div 
                className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-500 font-mono font-bold
                  ${isCompleted ? 'bg-black text-white border-2 border-black shadow-[2px_2px_0px_0px_#000000]' : 
                    isActive ? 'bg-white border-4 border-black text-black shadow-[4px_4px_0px_0px_#000000]' : 
                    'bg-white border-2 border-black/30 text-black/40'}
                `}
              >
                {isCompleted ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                ) : (
                  <span>{idx + 1}</span>
                )}
              </div>
                          <span className={`text-[10px] font-display font-extrabold uppercase tracking-widest text-center leading-tight transition-colors duration-300
                ${isCompleted || isActive ? 'text-black' : 'text-black/40'}
              `}>
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>
      <p className="text-black text-xs font-mono font-bold mt-12 bg-white px-4 py-2 rounded-md border-2 border-black shadow-[2px_2px_0px_0px_#000000]">
        JOB ID: {jobId}
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

  const handleSendQuery = async (e?: React.FormEvent, retryText?: string) => {
    if (e) e.preventDefault();
    const query = retryText || input;
    if (!query.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: query,
    };

    setMessages((prev) => [...prev, userMessage]);
    if (!retryText) setInput("");
    setIsLoading(true);

    try {
      let res;
      try {
        res = await fetch(`${API_BASE}/query/${jobId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: userMessage.content }),
        });
      } catch (networkErr) {
        throw new Error("Having trouble reaching the server — please check your connection and try again.");
      }

      if (!res.ok) {
        if (res.status === 429) {
          throw new Error("The AI service is experiencing high demand right now. Please wait a moment and try again.");
        } else if (res.status >= 500) {
          throw new Error("Something went wrong processing that question. Please try rephrasing or try again.");
        } else {
          // Check if body mentions rate limit/quota
          const text = await res.text().catch(() => "");
          if (text.toLowerCase().includes("quota") || text.toLowerCase().includes("rate limit")) {
             throw new Error("The AI service is experiencing high demand right now. Please wait a moment and try again.");
          }
          throw new Error("Sorry, I encountered an error while trying to communicate with the server.");
        }
      }
      
      const data = await res.json();

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: data.answer,
        mode: data.mode,
        sources: data.sources,
        fallback_used: data.fallback_used,
        verification: data.verification,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      console.error(err);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: err.message || "Sorry, I encountered an error while trying to communicate with the server.",
        is_error: true,
        retry_content: userMessage.content,
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
    <div className="bg-white border-2 border-black rounded-2xl shadow-[5px_5px_0px_0px_#000000] overflow-hidden flex flex-col h-[75vh] min-h-[600px]">
      {/* Browser Header Bar */}
      <div className="bg-white border-b-2 border-black px-4 py-3 flex items-center justify-between z-20">
        <div className="flex gap-2">
          <div className="w-3 h-3 rounded-full bg-red-500 border border-black"></div>
          <div className="w-3 h-3 rounded-full bg-yellow-400 border border-black"></div>
          <div className="w-3 h-3 rounded-full bg-green-500 border border-black"></div>
        </div>
        <div className="bg-gray-100 border-2 border-black rounded-full px-4 py-1 text-xs font-mono font-bold text-black flex items-center justify-center">
          video-rag.local
        </div>
        <div className="w-12"></div>
      </div>
      
      {/* Main Content Area */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 overflow-hidden">
      
      {/* Video Side (40% wide on large screens) */}
      <div className="lg:col-span-5 flex flex-col bg-white border-r-2 border-black">
        {/* We use an aspect-video container so the video doesn't have overflow-hidden clipping its native controls */}
        <div className="flex-1 p-4 flex flex-col justify-center">
          <div className="w-full aspect-video bg-black border-2 border-black rounded-md overflow-hidden relative shadow-[2px_2px_0px_0px_#000000]">
            <video 
              ref={videoRef}
              src={`${API_BASE}/media/${jobId}`} 
              controls 
              crossOrigin="anonymous"
              className="w-full h-full object-contain block"
            />
          </div>
        </div>
        
        <div className="p-5 border-t-2 border-black flex justify-between items-center bg-transparent rounded-b-xl">
          <span className="text-xs text-black font-mono tracking-wider font-display font-extrabold uppercase">JOB: {jobId.split('-')[0]}</span>
          
          <button 
            onClick={handleExplainScreen}
            className="px-4 py-2 bg-[#FF4D00] text-white border-2 border-black shadow-[3px_3px_0px_0px_#000000] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none rounded-full text-xs font-display font-extrabold uppercase transition-all duration-150 flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
            Explain Screen
          </button>
        </div>
      </div>

      {/* Chat Side (60% wide on large screens) */}
      <div className="lg:col-span-7 flex flex-col h-full bg-white overflow-hidden">
        <div className="px-6 py-4 bg-transparent border-b-2 border-black flex items-center justify-between z-10">
          <h3 className="text-sm uppercase tracking-widest font-display font-extrabold text-black">Video Chat</h3>
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto p-6 space-y-8 scroll-smooth relative bg-white border-b-2 border-black">
          {messages.length === 0 && (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-black gap-4">
              <div className="w-16 h-16 rounded-md bg-white border-2 border-black shadow-[4px_4px_0px_0px_#000000] flex items-center justify-center">
                <svg className="w-6 h-6 text-black" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
              </div>
              <p className="text-sm font-bold uppercase tracking-wider">Ask a question...</p>
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"} relative z-10 items-end group`}>
              {/* Avatar */}
              <div className={`w-10 h-10 rounded-md flex-shrink-0 flex items-center justify-center border-2 border-black shadow-[2px_2px_0px_0px_#000000] ${
                msg.role === "user" 
                  ? "bg-black text-white" 
                  : "bg-white text-black"
              }`}>
                {msg.role === "user" ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                )}
              </div>
              
              <div className={`max-w-[85%] rounded-md px-5 py-4 border-2 border-black relative ${
                msg.role === "user" 
                  ? "bg-black text-white shadow-[3px_3px_0px_0px_#666]" 
                  : msg.is_error
                    ? "bg-[#FFF8F5] text-black border-l-8 border-l-[#FF4D00] shadow-[3px_3px_0px_0px_#000000]"
                    : "bg-white text-black shadow-[3px_3px_0px_0px_#000000]"
              }`}>
                
                {/* Copy Button (Hide on errors) */}
                {!msg.is_error && (
                  <button
                    onClick={() => navigator.clipboard.writeText(msg.content)}
                    className={`absolute top-2 right-2 p-1.5 rounded-md opacity-0 group-hover:opacity-100 transition-opacity z-20 border-2 border-black shadow-[2px_2px_0px_0px_#000000] hover:translate-x-[1px] hover:translate-y-[1px] hover:shadow-[1px_1px_0px_0px_#000000] ${
                      msg.role === "user" ? "bg-white text-black" : "bg-white text-black"
                    }`}
                    title="Copy message"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                  </button>
                )}
                
                {/* Mode Badges */}
                {msg.role === "assistant" && (msg.mode === "general_knowledge" || msg.fallback_used) && (
                  <div className="flex items-center gap-2 text-black text-[10px] uppercase tracking-wider font-bold mb-4 bg-white w-fit px-3 py-1.5 rounded-sm border-2 border-black shadow-[2px_2px_0px_0px_#000000]">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                    Beyond This Video
                  </div>
                )}
                
                {msg.role === "assistant" && msg.mode === "visual" && (
                  <div className="flex items-center gap-2 text-black text-[10px] uppercase tracking-wider font-bold mb-4 bg-white w-fit px-3 py-1.5 rounded-sm border-2 border-black shadow-[2px_2px_0px_0px_#000000]">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" /></svg>
                    Screen Explanation
                  </div>
                )}

                <div className="text-[15px] leading-relaxed whitespace-normal font-medium">
                  {msg.role === "user" ? (
                    <div className="font-medium font-sans">{msg.content}</div>
                  ) : msg.is_error ? (
                    <div>
                      <div className="font-bold text-[#FF4D00] flex items-center gap-2 mb-2">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        System Notice
                      </div>
                      <p className="font-sans text-black/90 mb-4">{msg.content}</p>
                      {msg.retry_content && (
                        <button 
                          onClick={() => handleSendQuery(undefined, msg.retry_content)}
                          disabled={isLoading}
                          className="bg-white text-black border-2 border-black font-mono font-bold text-xs px-3 py-1.5 rounded-sm shadow-[2px_2px_0px_0px_#000000] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none hover:bg-black hover:text-white transition-all flex items-center gap-1.5"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                          Retry Request
                        </button>
                      )}
                    </div>
                  ) : (
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        h1: ({node, ...props}) => <h1 className="text-2xl font-display font-extrabold mt-6 mb-3 text-black uppercase tracking-tight border-b-2 border-black pb-1" {...props} />,
                        h2: ({node, ...props}) => <h2 className="text-xl font-display font-bold mt-5 mb-3 text-black uppercase tracking-tight" {...props} />,
                        h3: ({node, ...props}) => <h3 className="text-lg font-display font-bold mt-4 mb-2 text-black" {...props} />,
                        div: ({node, ...props}) => <div className="mb-4 last:mb-0" {...props} />,
                        p: ({node, ...props}) => <div className="mb-4 last:mb-0 text-black/90" {...props} />,
                        ul: ({node, ...props}) => <ul className="list-disc pl-6 mb-4 space-y-1 text-black/90 font-bold" {...props} />,
                        ol: ({node, ...props}) => <ol className="list-decimal pl-6 mb-4 space-y-1 text-black/90 font-bold" {...props} />,
                        strong: ({node, ...props}) => <strong className="font-display font-extrabold text-black" {...props} />,
                        code: ({node, inline, ...props}: any) => 
                          inline ? (
                            <code className="bg-[#E8E4D9] px-1.5 py-0.5 rounded-sm text-black font-mono text-[13px] border-2 border-black" {...props} />
                          ) : (
                            <pre className="bg-[#E8E4D9] p-4 rounded-md overflow-x-auto mb-4 border-2 border-black shadow-[3px_3px_0px_0px_#000000] [&::-webkit-scrollbar]:h-3 [&::-webkit-scrollbar-thumb]:bg-black [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-track]:border-t-2 [&::-webkit-scrollbar-track]:border-black"><code className="text-black font-mono font-bold text-[13px] block min-w-full" {...props} /></pre>
                          ),
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  )}
                </div>

                {/* Sources */}
                {msg.role === "assistant" && msg.mode === "grounded" && msg.sources && msg.sources.length > 0 && (
                  <div className="mt-5 pt-4 border-t-2 border-black flex flex-wrap gap-3 items-center">
                    <span className="text-xs font-display font-extrabold uppercase tracking-widest text-black mr-1">Sources:</span>
                    {msg.sources.map((src, i) => (
                      <button 
                        key={i}
                        onClick={() => handleSeek(src.start_time)}
                        className="bg-[#FF4D00] text-white border-2 border-black font-mono font-bold text-xs px-2.5 py-1 rounded-full shadow-[1.5px_1.5px_0px_0px_#000000] active:translate-x-[1.5px] active:translate-y-[1.5px] active:shadow-none hover:bg-black transition-all flex items-center gap-1.5 cursor-pointer"
                        title={src.text}
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        {formatTime(src.start_time)}
                      </button>
                    ))}
                    
                    {/* Verification Badge */}
                    {msg.verification && msg.verification.verified !== null && (
                      <div 
                        className={`ml-auto flex items-center gap-1.5 px-2 py-1 rounded-md border-2 border-black font-mono font-bold text-[10px] uppercase tracking-wider shadow-[2px_2px_0px_0px_#000000] cursor-default ${
                          msg.verification.verified && msg.verification.confidence === "high"
                            ? "bg-green-100 text-green-900"
                            : "bg-yellow-100 text-yellow-900"
                        }`}
                        title={msg.verification.note || undefined}
                      >
                        {msg.verification.verified && msg.verification.confidence === "high" ? (
                          <>
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
                            Verified
                          </>
                        ) : (
                          <>
                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                            Unverified — review sources
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex justify-start relative z-10 pl-14">
              <div className="bg-white border-2 border-black rounded-md px-5 py-4 flex gap-2 items-center shadow-[3px_3px_0px_0px_#000000]">
                <div className="w-2.5 h-2.5 bg-black animate-bounce" style={{ animationDelay: "0ms" }}></div>
                <div className="w-2.5 h-2.5 bg-black animate-bounce" style={{ animationDelay: "150ms" }}></div>
                <div className="w-2.5 h-2.5 bg-black animate-bounce" style={{ animationDelay: "300ms" }}></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} className="h-1" />
        </div>

        {/* Input Area */}
        <div className="p-5 bg-white z-10">
          <form onSubmit={handleSendQuery} className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading}
              placeholder="Ask a question..."
              className="w-full bg-white border-2 border-black rounded-full py-4 pl-5 pr-16 text-black font-medium font-sans placeholder-gray-500 focus:outline-none focus:translate-x-[2px] focus:translate-y-[2px] focus:shadow-[2px_2px_0px_0px_#000000] transition-all disabled:opacity-50 shadow-[4px_4px_0px_0px_#000000]"
            />
            <button
              type="submit"
              disabled={isLoading || !input.trim()}
              className="absolute right-2.5 p-2.5 bg-[#FF4D00] disabled:opacity-50 disabled:pointer-events-none text-white rounded-full border-2 border-black shadow-[3px_3px_0px_0px_#000000] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none transition-all"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14M12 5l7 7-7 7" /></svg>
            </button>
          </form>
        </div>
      </div>
    </div>
    </div>
  );
}

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [isProcessed, setIsProcessed] = useState(false);
  const [showSplash, setShowSplash] = useState(true);

  useEffect(() => {
    // Only show splash once per load
    const timer = setTimeout(() => setShowSplash(false), 2200);
    return () => clearTimeout(timer);
  }, []);

  const handleNewVideo = () => {
    if (jobId || isProcessed) {
      if (!confirm("Start a new video? Current chat and processing will be cleared.")) {
        return;
      }
    }
    setJobId(null);
    setIsProcessed(false);
  };

  if (showSplash) {
    return (
      <div className="fixed inset-0 z-[100] bg-[#FAF9F5] flex flex-col items-center justify-center">
        <style>{`
          @keyframes progress-fill {
            0% { width: 0%; }
            100% { width: 100%; }
          }
        `}</style>
        <div className="relative flex flex-col items-center">
          {/* Minimal Play/Camera SVG (Thick outline) */}
          <div className="w-20 h-20 bg-white border-4 border-black shadow-[6px_6px_0px_0px_#000000] flex items-center justify-center animate-bounce">
            <svg className="w-10 h-10 text-black" fill="currentColor" viewBox="0 0 24 24">
              <polygon points="8 5 19 12 8 19 8 5" />
            </svg>
          </div>
          {/* Sleek progress line */}
          <div className="mt-10 w-56 h-4 bg-white border-2 border-black shadow-[3px_3px_0px_0px_#000000] overflow-hidden">
            <div className="h-full bg-black" style={{ animation: 'progress-fill 2s cubic-bezier(0.4, 0, 0.2, 1) forwards' }}></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-transparent text-black font-sans pt-24 pb-12 px-6 md:px-8 lg:px-12 overflow-x-hidden selection:bg-black selection:text-white">
      
      {/* Clean Header Bar */}
      <header className="fixed top-0 left-0 right-0 h-20 bg-[#FAF9F5] border-b-2 border-black z-50 flex items-center justify-between px-8">
        <div className="flex items-center gap-4">
          <div className="w-10 h-10 bg-black flex items-center justify-center border-2 border-black shadow-[3px_3px_0px_0px_#666]">
            <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24"><polygon points="8 5 19 12 8 19 8 5" /></svg>
          </div>
          <span className="font-display font-extrabold text-black tracking-tighter text-2xl uppercase">Video Understanding</span>
        </div>
        
        {/* New Video Button */}
        {(jobId || isProcessed) && (
          <button 
            onClick={handleNewVideo}
            className="flex items-center gap-2 text-xs font-display font-black uppercase text-white bg-[#FF4D00] border-2 border-black rounded-full shadow-[3px_3px_0px_0px_#000000] active:translate-x-[2px] active:translate-y-[2px] active:shadow-none px-4 py-2 transition-all"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
            New Video
          </button>
        )}
      </header>

      <div className="relative max-w-7xl mx-auto h-full flex flex-col z-10">
        <header className="mb-16 text-center mt-4">
          <h2 className="text-5xl lg:text-7xl font-display font-black tracking-tighter text-black inline-block uppercase">
            Video Understanding
          </h2>
          <p className="text-black mt-6 text-lg max-w-2xl mx-auto font-bold font-mono bg-white border-2 border-black p-4 shadow-[4px_4px_0px_0px_#000000]">
            Upload or paste a link to a video, and chat with its contents using Retrieval-Augmented Generation.
          </p>
        </header>

        <main className="flex-1 flex flex-col">
          {!jobId && (
            <div className="w-full mt-4">
              <IngestZone onIngestComplete={setJobId} />
            </div>
          )}

          {jobId && !isProcessed && (
            <div className="w-full mt-8">
              <ProcessingStatus 
                jobId={jobId} 
                onComplete={() => setIsProcessed(true)} 
              />
            </div>
          )}

          {jobId && isProcessed && (
            <div className="w-full">
              <VideoWorkspace jobId={jobId} />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
