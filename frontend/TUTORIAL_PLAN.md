# OratioViva Enhanced Tutorial & Features Implementation Plan

## Part 1: Complete UI Element Inventory for Tour

### 1. Toolbar Elements
- `.toolbar` - Main toolbar container
- `.toolbar-icon` - App icon
- `.toolbar-title` - App name
- `.toolbar-actions` - Action buttons container
- Backend restart button (ghost with ↻)
- Backend status badge (`.badge.badge-ok` / `.badge.badge-warn`)
- Model status badge
- Diagnostics button
- Cleanup button
- Settings button
- Language selector (`.lang-select`)

### 2. Hero Section (`.hero`)
- Title area with eyebrow, headline, lede
- Logo area with pill showing available models

### 3. Main Grid (`.grid`)
#### Left Card - Form (`.card .form`)
- **Text Editor Section**
  - Label (`.label`)
  - Text actions: Copy (`.ghost.small`), Clear (`.ghost.small`)
  - Character count (`.char-count`)
  - Textarea (`.input.textarea`)
  
- **Estimator Panel** (`.estimator-panel`)
  - Estimated audio duration
  - Estimated generation time
  - Average realtime factor

- **Synthesis Progress** (`.synthesis-progress`)
  - Progress bar (`.progress-container`)
  - Voice indicator (`.synthesis-voice`)

- **Retry Button** (`.retry-container .retry-btn`)

- **Voice Browser Section** (`.voice-browser-section`)
  - Voice view chip showing mode (Model/Language)
  - Voice browser container (`.voice-browser`)
  - Model grid (`.voice-model-grid`) with cards (`.voice-model-card`)
    - Model header with download button
    - Voice wheel (`.voice-wheel`) with center label
    - Voice items (`.voice-wheel-item`)
  - Language grid (`.voice-language-grid`)
  - Missing models section (`.voice-missing-models`)

- **Speed Control**
  - Label with current speed value
  - Range input

- **Quality Mode** (`.segmented`)
  - Fast / Balanced / Quality buttons (`.segmented-btn`)

- **Tone Preset** (`.field`)
  - Dropdown select with preset list
  - Manage presets button (`.ghost.small`)

- **Voice Direction Preset** (`.field`)
  - Dropdown select

- **Style Input** (`.field`)
  - Text input for style prompt

- **Voice Prompt Section** (`.field`)
  - Textarea for voice prompt
  - Auto-punctuate checkbox

- **Voice Reference** (`.field`)
  - Input for file path/URL
  - Clear button

- **Generate Button** (`.form-actions .button`)
- **Long Text Button** (when text > threshold)

#### Right Card - History (`.card.history`)
- Header with title and actions
- Refresh button
- Export ZIP button
- Delete selected button
- History list (`.history-list`)
  - Items (`.history-item`)
    - Checkbox for selection
    - Tags for model and voice
    - Delete button
    - Text preview
    - Date
    - Audio player and download link

### 4. Jobs Queue Section (`.card.jobs`)
- Header with title
- Jobs count badge
- Refresh button
- Delete selected button
- Jobs list
  - Job items with status tags
  - Retry button for failed jobs
  - Remove button

### 5. Analytics Section (`.card.analytics`)
- Header with refresh button
- Cards for: Runtime, Activity, Estimator

### 6. Modal Panels
- **Models Panel** (`.modal-content.models-panel`)
  - Model grid with cards
  - Download buttons
  - Progress indicators
  
- **Settings Panel** (`.settings-panel`)
  - Voice browse mode (segmented)
  - Performance profile select
  - Reading speed slider
  - Open models button
  - Telemetry toggle
  - HF token input
  
- **Long Audio Modal**
  - Chunk size slider
  - Sequential/Parallel mode selectors
  
- **Presets Panel** (`.presets-panel`)
  - Tabs for Tones, Prompts, Music, SFX
  - Preset list with edit/delete actions
  - Add form
  
- **Diagnostics Panel** (`.diagnostics-panel`)
  - Backend info
  - Storage info
  - Settings info
  - Models info
  - Error log
  
- **Cleanup Panel** (`.cleanup-panel`)
  - Options checkboxes
  - Cleanup button

### 7. First-Run Guide (`.first-run-guide`)
- Icon display
- Progress dots
- Title and content
- Skip / Next / Get Started buttons

---

## Part 2: Enhanced First-Run Content

### English Strings
```json
{
  "firstRun": {
    "welcomeTitle": "Welcome to OratioViva",
    "welcomeContent": "Transform text into natural-sounding speech with just a few clicks. This guide will walk you through everything you need to know.",
    "setupTitle": "Quick Setup",
    "setupContent": "Before you begin, make sure you have models downloaded. Go to Settings → Models to download voices like Dia2, Parler-TTS, or Bark.",
    "voiceBrowserTitle": "Choosing Your Voice",
    "voiceBrowserContent": "Browse voices by model or language using the toggle. Click the download button on any model to unlock its voices, then select a voice from the wheel.",
    "textInputTitle": "Enter Your Text",
    "textInputContent": "Paste articles, books, or any text into the editor. The estimator panel shows how long your audio will be.",
    "customizationTitle": "Fine-Tune Your Audio",
    "customizationContent": "Adjust speed with the slider. Choose a tone preset (Neutral, Expressive, Calm, etc.) and a voice direction. Add a style prompt or voice reference for more control.",
    "generationTitle": "Generate Audio",
    "customizationContent": "Click Generate to create your audio. For long texts, use the Long Text button to process in chunks. Progress shows in real-time.",
    "historyQueueTitle": "History & Queue",
    "historyQueueContent": "Your generated audio appears in History. Failed or pending jobs show in the Queue. Click any item to play, download, or delete it.",
    "exportsSettingsTitle": "Exports & Settings",
    "exportsSettingsContent": "Export multiple files as ZIP, or access Settings to adjust performance, models, and telemetry. Use the toolbar buttons for diagnostics and cleanup.",
    "readyTitle": "You're All Set!",
    "readyContent": "You now know everything OratioViva can do. Paste your text, choose a voice, and click Generate. Happy listening!",
    "skip": "Skip",
    "next": "Next",
    "back": "Back",
    "getStarted": "Get Started",
    "takeTour": "Take the Full Tour"
  }
}
```

### French Strings
```json
{
  "firstRun": {
    "welcomeTitle": "Bienvenue sur OratioViva",
    "welcomeContent": "Transformez du texte en parole naturelle en quelques clics. Ce guide vous montrera tout ce dont vous avez besoin.",
    "setupTitle": "Configuration Rapide",
    "setupContent": "Avant de commencer, assurez-vous d'avoir téléchargé des modèles. Allez dans Paramètres → Modèles pour télécharger des voix comme Dia2, Parler-TTS ou Bark.",
    "voiceBrowserTitle": "Choisir Votre Voix",
    "voiceBrowserContent": "Parcourez les voix par modèle ou langue. Cliquez sur le bouton de téléchargement d'un modèle pour débloquer ses voix, puis sélectionnez une voix.",
    "textInputTitle": "Entrez Votre Texte",
    "textInputContent": "Collez des articles, livres ou tout texte dans l'éditeur. Le panneau d'estimation montre la durée de votre audio.",
    "customizationTitle": "Personnalisez Votre Audio",
    "customizationContent": "Ajustez la vitesse. Choisissez un preset de ton (Neutre, Expressif, Calme, etc.) et une direction vocale. Ajoutez un prompt de style ou une référence vocale.",
    "generationTitle": "Générer l'Audio",
    "customizationContent": "Cliquez sur Générer pour créer votre audio. Pour les longs textes, utilisez le bouton Long Texte pour traiter par morceaux.",
    "historyQueueTitle": "Historique & File",
    "customizationContent": "Votre audio généré apparaît dans l'Histoire. Les jobs échoués ou en attente sont dans la File. Cliquez pour écouter, télécharger ou supprimer.",
    "exportsSettingsTitle": "Exportations & Paramètres",
    "exportsSettingsContent": "Exportez plusieurs fichiers en ZIP, ou accédez aux Paramètres pour ajuster les performances, modèles et télémétrie.",
    "readyTitle": "Vous Êtes Prêt!",
    "readyContent": "Vous connaissez tout ce qu'OratioViva peut faire. Collez votre texte, choisissez une voix et cliquez sur Générer. Bonne écoute!",
    "skip": "Passer",
    "next": "Suivant",
    "back": "Retour",
    "getStarted": "Commencer",
    "takeTour": "Faire le Tour Complet"
  }
}
```

---

## Part 3: Guided Tour Component (Coach Marks)

The guided tour will be a step-by-step overlay that:
1. Highlights each UI element with a spotlight effect
2. Shows a tooltip explaining the element
3. Allows navigation (Next/Back/Skip)
4. Can be restarted from Help menu
5. Persists progress in localStorage

### Tour Steps Order:
1. Toolbar (backend restart, status badges, diagnostics, cleanup, settings, language)
2. Hero section (title, models pill)
3. Text editor (input, copy, clear, char count)
4. Estimator panel
5. Voice browser (model/language toggle, download buttons, voice wheel)
6. Speed control
7. Quality mode
8. Tone preset dropdown
9. Voice direction preset
10. Style input
11. Voice prompt + auto-punctuate
12. Voice reference
13. Generate button
14. History section (refresh, export, delete, audio player)
15. Jobs queue
16. Analytics
17. Settings button (via toolbar)
18. Models button (via settings)
19. Summary

---

## Part 4: Help Menu

Add a Help menu item in toolbar with:
- **Start Tour** - Opens guided tour
- **Keyboard Shortcuts** - Shows modal with:
  - Ctrl/Cmd + Enter = Generate
  - Escape = Clear text
- **What's New** - Opens changelog/release notes

---

## Part 5: Batch/Chain Generation

### Frontend UI
- Add "Chain Generation" button in form actions
- Opens modal with:
  - List of text entries (add/remove)
  - Per-entry settings (voice, tone, etc.) or inherit from main
  - Progress indicator (x/y completed)
  - Pause/Cancel controls
  - Notifications on completion

### Backend API
- `POST /synthesize/chain` - Accepts array of synthesis requests
- Returns `chain_id` and job list
- Processes sequentially with automatic chaining
- Status endpoint returns chain progress

---

## Part 6: Notifications System

### Toast Notifications
- Success: "Audio generated successfully"
- Error: "Generation failed: [reason]"
- Warning: "Voice model missing - download now?"
- Info: "Downloading model: Dia2 (45%)"

### OS Notifications (Tauri)
- Toggle in Settings (default: off)
- Triggered on job completion
- Shows: "OratioViva: Audio ready - [voice]"

---

## Part 7: Enhanced Export Options

Current: ZIP export of WAV files

New options:
1. **Export ZIP** - Existing functionality
2. **Export CSV** - Manifest with columns: job_id, text_preview, voice, model, created_at, duration, file_path
3. **Export JSON** - Full metadata + settings used
4. **Export Individual** - Download specific files
5. **MP3 Conversion** - Optional ffmpeg-based conversion (toggle in export dialog)

Backend endpoints:
- `POST /export/csv` - Returns CSV file
- `POST /export/manifest` - Returns JSON metadata
- `POST /export/mp3` - Converts WAV to MP3 on demand

---

## Part 8: QA Checklist Updates

Add to `QA_CHECKLIST.md`:
- [ ] First-run guide displays correctly
- [ ] All tour steps are clear and accurate
- [ ] Tour can be restarted from Help menu
- [ ] Keyboard shortcuts work as documented
- [ ] Batch/chain generation works
- [ ] Notifications appear and dismiss correctly
- [ ] OS notifications work (if enabled)
- [ ] Export CSV/JSON/MP3 options work
- [ ] No warning messages shown to user (converted to guidance)
- [ ] All buttons have clear tooltips/labels

---

## Part 9: Documentation Updates

Update `frontend/README.md`:
- Add "Guided Tour" section explaining how to use
- Document keyboard shortcuts
- Explain batch/chain generation
- List export options
- Describe notification system

