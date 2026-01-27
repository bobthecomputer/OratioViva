import React from "react";
import { createRoot } from "react-dom/client";
import { invoke, isTauri } from "@tauri-apps/api/core";
import App from "./App";
import "./styles.css";
import { I18nProvider } from "./i18n";

function logFrontend(message) {
  if (typeof window === "undefined") return;
  const payload = typeof message === "string" ? message : JSON.stringify(message);
  try {
    if (window.__TAURI__?.invoke) {
      window.__TAURI__.invoke("log_frontend", { message: payload });
    } else if (isTauri()) {
      invoke("log_frontend", { message: payload });
    }
  } catch {}
}

const DEVTOOLS_PASSWORD = "5122";

function writeCrashReport(report) {
  if (typeof window === "undefined") return;
  const payload = typeof report === "string" ? report : JSON.stringify(report);
  try {
    if (window.__TAURI__?.invoke) {
      window.__TAURI__.invoke("write_crash_report", { report: payload });
    } else if (isTauri()) {
      invoke("write_crash_report", { report: payload });
    }
  } catch {}
}

function requestDevtools(reason) {
  if (typeof window === "undefined") return;
  if (reason === "manual") {
    const input = window.prompt("DevTools password:");
    if (input !== DEVTOOLS_PASSWORD) return;
  }
  try {
    if (window.__TAURI__?.invoke) {
      window.__TAURI__.invoke("open_devtools");
    } else if (isTauri()) {
      invoke("open_devtools");
    }
  } catch {}
}

if (typeof window !== "undefined") {
  window.addEventListener("keydown", (event) => {
    if (event.ctrlKey && event.shiftKey && event.code === "KeyD") {
      event.preventDefault();
      requestDevtools("manual");
    }
  });

  window.addEventListener("error", (event) => {
    const location = `${event.filename || ""}:${event.lineno || 0}:${event.colno || 0}`;
    logFrontend(`[error] ${event.message} ${location}`);
    writeCrashReport(
      `[error] ${event.message} ${location} UA=${navigator.userAgent} URL=${window.location.href}`,
    );
    requestDevtools("error");
    if (event.error?.stack) {
      logFrontend(event.error.stack);
      writeCrashReport(event.error.stack);
    }
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    const message = reason?.message || String(reason);
    logFrontend(`[unhandledrejection] ${message}`);
    writeCrashReport(
      `[unhandledrejection] ${message} UA=${navigator.userAgent} URL=${window.location.href}`,
    );
    requestDevtools("error");
    if (reason?.stack) {
      logFrontend(reason.stack);
      writeCrashReport(reason.stack);
    }
  });

  const originalError = console.error;
  console.error = (...args) => {
    logFrontend(`[console.error] ${args.map(String).join(" ")}`);
    originalError(...args);
  };
}

const root = createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <I18nProvider defaultLang="en">
      <App />
    </I18nProvider>
  </React.StrictMode>,
);
