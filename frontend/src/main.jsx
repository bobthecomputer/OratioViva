import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./styles.css";
import { I18nProvider } from "./i18n";

const root = createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <I18nProvider defaultLang="en">
      <App />
    </I18nProvider>
  </React.StrictMode>,
);
