"use client";

import { useState, useRef, useCallback } from "react";

const THEMES = [
  "Cyberpunk",
  "Fantasy",
  "Anime",
  "Professional",
  "Artistic",
  "Vintage",
  "Sci-Fi",
  "Watercolor",
];

type JobStatus = "idle" | "uploading" | "queued" | "processing" | "done" | "failed";

interface JobResult {
  job_id: string;
  status: JobStatus;
  url?: string;
  error?: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [theme, setTheme] = useState(THEMES[0]);
  const [outfit, setOutfit] = useState("");
  const [status, setStatus] = useState<JobStatus>("idle");
  const [jobResult, setJobResult] = useState<JobResult | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const handleFile = (f: File) => {
    setFile(f);
    const reader = new FileReader();
    reader.onloadend = () => setPreview(reader.result as string);
    reader.readAsDataURL(f);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith("image/")) handleFile(f);
  }, []);

  const connectWebSocket = (jobId: string) => {
    const ws = new WebSocket(`${WS_URL}/ws/jobs/${jobId}`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      const data: JobResult = JSON.parse(e.data);
      setStatus(data.status);
      setJobResult(data);
      if (data.status === "done" || data.status === "failed") {
        ws.close();
      }
    };

    ws.onerror = () => {
      setStatus("failed");
      setJobResult((prev) => ({
        ...(prev ?? { job_id: "" }),
        status: "failed",
        error: "WebSocket connection failed. Check the API server.",
      }));
    };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setStatus("uploading");
    setJobResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("theme", theme);
    formData.append("outfit", outfit || "casual");

    try {
      const res = await fetch(`${API_URL}/jobs`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
      const data = await res.json();
      setStatus("queued");
      setJobResult({ job_id: data.job_id, status: "queued" });
      connectWebSocket(data.job_id);
    } catch (err) {
      setStatus("failed");
      setJobResult({ job_id: "", status: "failed", error: String(err) });
    }
  };

  const reset = () => {
    wsRef.current?.close();
    setFile(null);
    setPreview(null);
    setStatus("idle");
    setJobResult(null);
  };

  const statusConfig: Record<JobStatus, { label: string; color: string }> = {
    idle: { label: "", color: "" },
    uploading: { label: "Uploading photo...", color: "text-blue-400" },
    queued: { label: "Job queued — waiting for a worker...", color: "text-yellow-400" },
    processing: {
      label: "Claude AI is analyzing your portrait and generating your avatar...",
      color: "text-purple-400",
    },
    done: { label: "Your avatar is ready!", color: "text-green-400" },
    failed: { label: "Generation failed", color: "text-red-400" },
  };

  const isGenerating =
    status === "uploading" || status === "queued" || status === "processing";

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-3xl mx-auto px-4 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-purple-400 via-pink-400 to-purple-400 bg-clip-text text-transparent mb-3">
            Avatar AI
          </h1>
          <p className="text-gray-400 text-lg">
            Upload your portrait · Pick a style · Get your AI avatar
          </p>
          <p className="text-gray-600 text-sm mt-1">
            Powered by Claude AI + Stability AI · Stored on AWS S3
          </p>
        </div>

        {/* Upload + Config Form */}
        {!isGenerating && status !== "done" && status !== "failed" && (
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Drop Zone */}
            <div
              className={`border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all select-none ${
                isDragging
                  ? "border-purple-400 bg-purple-950/20"
                  : "border-gray-700 hover:border-gray-500 hover:bg-gray-900/40"
              }`}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />

              {preview ? (
                <div className="flex flex-col items-center gap-3">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={preview}
                    alt="Portrait preview"
                    className="h-44 w-44 rounded-full object-cover border-4 border-purple-500 shadow-lg shadow-purple-900/40"
                  />
                  <p className="text-sm text-gray-400 font-medium">{file?.name}</p>
                  <p className="text-xs text-gray-600">Click to change photo</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4 text-gray-400 py-4">
                  <svg
                    className="w-16 h-16 text-gray-600"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1}
                      d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                  <div>
                    <p className="text-lg font-medium text-gray-300">
                      Drop your portrait here
                    </p>
                    <p className="text-sm mt-1">or click to browse — JPG, PNG, WebP</p>
                  </div>
                </div>
              )}
            </div>

            {/* Theme Selector */}
            <div>
              <label className="block text-sm font-semibold text-gray-300 mb-3">
                Style Theme
              </label>
              <div className="grid grid-cols-4 gap-2">
                {THEMES.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setTheme(t)}
                    className={`py-2.5 px-3 rounded-xl text-sm font-medium transition-all ${
                      theme === t
                        ? "bg-purple-600 text-white shadow-lg shadow-purple-900/40"
                        : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
                    }`}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>

            {/* Outfit Input */}
            <div>
              <label className="block text-sm font-semibold text-gray-300 mb-2">
                Outfit / Clothing Style
              </label>
              <input
                type="text"
                value={outfit}
                onChange={(e) => setOutfit(e.target.value)}
                placeholder="e.g. leather jacket, business suit, medieval armor..."
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-colors"
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={!file}
              className="w-full py-4 bg-gradient-to-r from-purple-600 to-pink-600 rounded-xl font-semibold text-lg disabled:opacity-40 disabled:cursor-not-allowed hover:from-purple-500 hover:to-pink-500 transition-all shadow-lg shadow-purple-900/30"
            >
              Generate Avatar
            </button>
          </form>
        )}

        {/* Progress Panel */}
        {isGenerating && (
          <div className="bg-gray-900 border border-gray-800 rounded-2xl p-10 text-center space-y-6">
            <div className="flex justify-center">
              <div className="w-14 h-14 border-4 border-purple-600 border-t-transparent rounded-full animate-spin" />
            </div>
            <p className={`text-lg font-medium ${statusConfig[status].color}`}>
              {statusConfig[status].label}
            </p>
            {jobResult?.job_id && (
              <p className="text-xs text-gray-600 font-mono">
                Job ID: {jobResult.job_id}
              </p>
            )}
          </div>
        )}

        {/* Result */}
        {status === "done" && jobResult?.url && (
          <div className="space-y-6 text-center">
            <p className="text-green-400 font-semibold text-lg">
              {statusConfig.done.label}
            </p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={jobResult.url}
              alt="Generated Avatar"
              className="mx-auto rounded-2xl shadow-2xl shadow-purple-900/50 max-w-sm w-full border border-gray-800"
            />
            <div className="flex gap-3 justify-center">
              <a
                href={jobResult.url}
                download="my-avatar.png"
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 rounded-xl font-medium transition-all"
              >
                Download Avatar
              </a>
              <button
                onClick={reset}
                className="px-6 py-3 bg-gray-800 hover:bg-gray-700 rounded-xl font-medium transition-colors"
              >
                Create Another
              </button>
            </div>
          </div>
        )}

        {/* Error */}
        {status === "failed" && (
          <div className="bg-gray-900 border border-red-900/50 rounded-2xl p-8 text-center space-y-4">
            <p className="text-red-400 font-semibold text-lg">Generation failed</p>
            {jobResult?.error && (
              <p className="text-sm text-gray-400 bg-gray-800 rounded-lg p-3 font-mono text-left">
                {jobResult.error}
              </p>
            )}
            <button
              onClick={reset}
              className="px-8 py-3 bg-gray-800 hover:bg-gray-700 rounded-xl font-medium transition-colors"
            >
              Try Again
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
