/**
 * OratioViva Tutorial Audio Player
 * 
 * This component provides an audio tutorial that users can listen to
 * to learn how to use OratioViva. Uses a pre-generated audio file.
 */

import { useState, useEffect, useRef } from "react";
import { useTranslation } from "./i18n";

const TUTORIAL_SECTIONS = [
  { id: "intro", title: "Introduction", content: "Welcome to OratioViva, your powerful text-to-speech companion. This tutorial will guide you through everything you need to know.", duration: 30 },
  { id: "setup", title: "Quick Setup", content: "Before you begin generating audio, let's make sure you're set up correctly. Download TTS models from Settings.", duration: 45 },
  { id: "voices", title: "Choosing Your Voice", content: "Explore the voice browser organized by model or language. Download models to unlock their voices.", duration: 60 },
  { id: "text", title: "Entering Your Text", content: "Paste any text you want to convert into audio. The editor supports articles, books, scripts.", duration: 30 },
  { id: "customize", title: "Customizing Your Audio", content: "Use the speed slider, quality mode, tone presets, and voice direction prompts to customize your audio.", duration: 75 },
  { id: "generate", title: "Generating Audio", content: "Click Generate to create your audio. Use Long Text button for texts over 4000 characters.", duration: 45 },
  { id: "history", title: "History and Queue", content: "The History panel shows all your generated audio files. Export multiple items as ZIP.", duration: 30 },
  { id: "export", title: "Export and Settings", content: "Export as ZIP, CSV, or JSON manifest. Adjust performance, voice browsing, and telemetry in Settings.", duration: 45 },
  { id: "help", title: "Getting Help", content: "Click Help for guided tour or keyboard shortcuts. Control Enter generates, Escape clears.", duration: 15 },
  { id: "conclusion", title: "Conclusion", content: "That's everything you need to know. Paste text, choose a voice, and click Generate. Happy listening!", duration: 15 },
];

export function TutorialPlayer({ t, onClose }) {
  const [currentSection, setCurrentSection] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [error, setError] = useState(null);
  const audioRef = useRef(null);
  
  const section = TUTORIAL_SECTIONS[currentSection];
  const totalDuration = TUTORIAL_SECTIONS.reduce((sum, s) => sum + s.duration, 0);
  
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.src = "/audio/tutorial_complete.mp3";
    }
  }, []);
  
  function togglePlay() {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play().catch(e => {
          console.error("Playback error:", e);
          setError("Unable to play audio. Make sure the backend is running and audio file exists.");
        });
      }
      setIsPlaying(!isPlaying);
    }
  }
  
  function handleAudioEnded() {
    setIsPlaying(false);
  }
  
  function goToSection(index) {
    if (index >= 0 && index < TUTORIAL_SECTIONS.length) {
      setCurrentSection(index);
      setIsPlaying(false);
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
      }
    }
  }
  
  function playAll() {
    goToSection(0);
    setTimeout(() => {
      if (audioRef.current) {
        audioRef.current.play().catch(e => {
          setError("Unable to play audio. Make sure the backend is running.");
        });
      }
    }, 100);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content tutorial-player" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{t("tutorial.title", "Audio Tutorial")}</h2>
          <button className="ghost modal-close" onClick={onClose}>✕</button>
        </div>
        
        <div className="tutorial-content">
          <div className="tutorial-progress">
            <div 
              className="tutorial-progress-bar"
              style={{ width: `${((currentSection + 1) / TUTORIAL_SECTIONS.length) * 100}%` }}
            />
          </div>
          
          <div className="tutorial-current">
            <div className="tutorial-section-title">
              {currentSection + 1}. {section.title}
            </div>
            <div className="tutorial-section-content">
              {section.content}
            </div>
            <div className="tutorial-section-duration">
              ~{section.duration}s
            </div>
          </div>
          
          <div className="tutorial-player-controls">
            <audio
              ref={audioRef}
              onEnded={handleAudioEnded}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
            />
            
            <div className="tutorial-buttons">
              <button 
                className="ghost"
                onClick={() => goToSection(currentSection - 1)}
                disabled={currentSection === 0}
              >
                ⏮ Previous
              </button>
              
              <button 
                className="button"
                onClick={togglePlay}
              >
                {isPlaying ? "⏸ Pause" : "▶ Play"}
              </button>
              
              <button 
                className="ghost"
                onClick={() => goToSection(currentSection + 1)}
                disabled={currentSection === TUTORIAL_SECTIONS.length - 1}
              >
                Next ⏭
              </button>
            </div>
            
            <div className="tutorial-play-all">
              <button 
                className="button button-secondary"
                onClick={playAll}
              >
                ▶▶ Play Complete Tutorial
              </button>
            </div>
          </div>
          
          {error && (
            <div className="tutorial-error">
              <p>{error}</p>
              <button className="ghost" onClick={() => setError(null)}>Dismiss</button>
            </div>
          )}
          
          <div className="tutorial-sections-list">
            <h3>Tutorial Sections</h3>
            {TUTORIAL_SECTIONS.map((s, i) => (
              <div 
                key={s.id}
                className={`tutorial-section-item ${i === currentSection ? "active" : ""}`}
                onClick={() => goToSection(i)}
              >
                <span className="section-number">{i + 1}</span>
                <span className="section-title">{s.title}</span>
                <span className="section-duration">~{s.duration}s</span>
              </div>
            ))}
          </div>
          
          <div className="tutorial-summary">
            <span>{TUTORIAL_SECTIONS.length} sections</span>
            <span>Total: ~{totalDuration}s ({Math.ceil(totalDuration / 60)} min)</span>
          </div>
        </div>
        
        <div className="modal-footer">
          <button className="ghost" onClick={onClose}>
            {t("diagnostics.close", "Close")}
          </button>
        </div>
      </div>
      
      <style>{`
        .tutorial-player {
          max-width: 700px;
          max-height: 90vh;
          overflow-y: auto;
        }
        
        .tutorial-content {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }
        
        .tutorial-progress {
          height: 4px;
          background: var(--border);
          border-radius: 2px;
          overflow: hidden;
        }
        
        .tutorial-progress-bar {
          height: 100%;
          background: linear-gradient(90deg, var(--accent), var(--accent-strong));
          transition: width 0.3s ease;
        }
        
        .tutorial-current {
          padding: 20px;
          background: rgba(255, 255, 255, 0.03);
          border-radius: 12px;
          border: 1px solid var(--border);
        }
        
        .tutorial-section-title {
          font-size: 1.2rem;
          font-weight: 600;
          margin-bottom: 12px;
          color: var(--accent-strong);
        }
        
        .tutorial-section-content {
          line-height: 1.7;
          color: var(--text);
          margin-bottom: 12px;
        }
        
        .tutorial-section-duration {
          font-size: 0.85rem;
          color: var(--muted);
        }
        
        .tutorial-player-controls {
          display: flex;
          flex-direction: column;
          gap: 16px;
          align-items: center;
        }
        
        .tutorial-buttons {
          display: flex;
          gap: 12px;
          align-items: center;
        }
        
        .tutorial-play-all {
          margin-top: 8px;
        }
        
        .tutorial-error {
          padding: 16px;
          background: rgba(248, 113, 113, 0.1);
          border-radius: 12px;
          border: 1px solid rgba(248, 113, 113, 0.3);
          color: #f87171;
        }
        
        .tutorial-error button {
          margin-top: 8px;
        }
        
        .tutorial-sections-list {
          border-top: 1px solid var(--border);
          padding-top: 16px;
        }
        
        .tutorial-sections-list h3 {
          margin: 0 0 12px;
          font-size: 0.9rem;
          color: var(--text-secondary);
          text-transform: uppercase;
          letter-spacing: 0.02em;
        }
        
        .tutorial-section-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 14px;
          border-radius: 8px;
          cursor: pointer;
          transition: all 0.2s;
          border: 1px solid transparent;
        }
        
        .tutorial-section-item:hover {
          background: rgba(255, 255, 255, 0.03);
        }
        
        .tutorial-section-item.active {
          background: rgba(96, 165, 250, 0.1);
          border-color: rgba(96, 165, 250, 0.3);
        }
        
        .section-number {
          width: 28px;
          height: 28px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(96, 165, 250, 0.2);
          border-radius: 50%;
          font-size: 0.8rem;
          font-weight: 600;
          color: var(--accent-strong);
        }
        
        .section-title {
          flex: 1;
          font-weight: 500;
        }
        
        .section-duration {
          font-size: 0.8rem;
          color: var(--muted);
        }
        
        .tutorial-summary {
          display: flex;
          justify-content: space-between;
          font-size: 0.85rem;
          color: var(--text-secondary);
          padding-top: 12px;
          border-top: 1px solid var(--border);
        }
      `}</style>
    </div>
  );
}

export default TutorialPlayer;
