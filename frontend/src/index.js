import React from "react";
import ReactDOM from "react-dom/client";
import "@/index.css";
import App from "@/App";

// Suprime el error benigno "ResizeObserver loop ..." que dispara el overlay de
// desarrollo de webpack (no ocurre en producción). No afecta la funcionalidad.
const isResizeObserverError = (msg) =>
  typeof msg === "string" && msg.includes("ResizeObserver loop");

window.addEventListener("error", (e) => {
  if (isResizeObserverError(e.message)) {
    e.stopImmediatePropagation();
    e.preventDefault();
    const overlay = document.getElementById("webpack-dev-server-client-overlay");
    if (overlay) overlay.style.display = "none";
  }
});

window.addEventListener("unhandledrejection", (e) => {
  if (isResizeObserverError(e?.reason?.message)) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
