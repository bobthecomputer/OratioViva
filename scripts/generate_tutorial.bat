@echo off
REM OratioViva Tutorial Audio Generator
REM This batch file uses the OratioViva backend API to generate tutorial audio

echo ============================================================
echo OratioViva Tutorial Audio Generator
echo ============================================================
echo.

REM Check if backend is running
echo Checking backend status...
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo ERROR: Backend is not running!
    echo Please start the backend first with: cd backend && python main.py
    pause
    exit /b 1
)
echo Backend is running!

REM Create output directory
mkdir "%USERPROFILE%\OratioViva\outputs\audio" 2>nul
mkdir "%USERPROFILE%\OratioViva\outputs" 2>nul

REM Tutorial script segments
set SCRIPT_INTRO=Welcome to OratioViva, your powerful text-to-speech companion. This tutorial will guide you through everything you need to know to transform your text into natural, clear audio. Whether you are creating audiobooks, voiceovers, or simply listening to articles, OratioViva has you covered. Let us get started!

set SCRIPT_SETUP=Before you begin generating audio, let us make sure you are set up correctly. First, you will need to download the TTS models that power OratioViva. Click on Settings in the toolbar, then select Models. Here you can download voices like Dia Two for streaming dialogue, Parler TTS for style-controlled speech, Bark Small for expressive synthesis, and many more. If you have a Hugging Face token, you can enter it in Settings to access gated models that require authentication. The app runs entirely on your machine, so your data stays private.

set SCRIPT_VOICES=Now let us explore the voice browser. By default, voices are organized by model, but you can switch to language view if you prefer. Each model card shows which voices are available. If a model is not downloaded yet, click the download button to unlock its voices. Once downloaded, you can select a voice from the wheel interface. Try selecting different voices to hear how they sound. For voice cloning, models like Speech T Five, X T T S v Two, F Five T T S, and Cosy Voice Three allow you to use a reference audio file to mimic a specific voice. Simply upload a WAV or MP3 file with clear speech, and the model will learn to speak in that voice style.

set SCRIPT_TEXT=Paste any text you want to convert into audio. The editor supports articles, books, scripts, or any other content. You can copy text to your clipboard or clear the editor with the buttons on the right. The character counter shows how long your text is. The estimator panel will show you the estimated audio duration and generation time based on your current settings.

set SCRIPT_CUSTOMIZE=OratioViva gives you powerful controls to customize how your audio sounds. Use the speed slider to adjust playback from point six times to one and a half times normal speed. Choose your quality mode: Fast for quick previews, Balanced for good quality and speed, or Quality for the best results. Now let us talk about tone presets. Select a tone like Neutral, Expressive, Calm, Authoritative, or Storyteller to change the delivery style. You can also add a voice direction prompt to give the voice specific instructions, such as warm and confident or soft and gentle. The auto punctuate feature will automatically add basic punctuation to your text if it is missing. For models that support it, you can add a style prompt for fine-grained control over the synthesis. And for voice cloning models, you can provide a reference audio file.

set SCRIPT_GENERATE=When you are ready, click the Generate button to create your audio. You will see a progress bar showing the synthesis status. For long texts over four thousand characters, click the Long Text button to process your content in chunks, either sequentially or in parallel for faster generation. Once complete, your audio appears in the History panel where you can play it directly, download the file, or share it.

set SCRIPT_HISTORY=The History panel shows all your generated audio files. Click any item to play, download, or delete it. You can select multiple items and export them as a ZIP file. The Queue panel shows pending and in-progress jobs. If a job fails, you can retry it or remove it from the queue.

set SCRIPT_EXPORT=OratioViva offers multiple export options. Export your files as ZIP for easy sharing, or download a CSV or JSON manifest with metadata about your generations. In Settings, you can adjust the performance profile based on your hardware, configure voice browsing preferences, and manage telemetry options. Use the Diagnostics panel to check system information, and Cleanup to free up disk space.

set SCRIPT_HELP=Need help at any time? Click Help in the toolbar to start the guided tour again or view keyboard shortcuts. Control Enter generates audio, Escape clears the text, and Control C copies to clipboard.

set SCRIPT_CONCLUSION=That is everything you need to know to get the most out of OratioViva. Paste your text, choose a voice, and click Generate. Happy listening!

echo Generating 10 tutorial segments...
echo ------------------------------------------------------------

REM Generate intro
echo [1/10] Generating intro...
curl -s -X POST http://localhost:8000/synthesize -H "Content-Type: application/json" -d "{\"text\": \"%SCRIPT_INTRO%\", \"voice_id\": \"dia2_2b_en\", \"speed\": 1.0, \"quality\": \"balanced\", \"tone_id\": \"neutral\"}" > "%TEMP%\intro_job.json"
for /f "tokens=2 delims=:, " %%a in ('type "%TEMP%\intro_job.json" ^| findstr /b "{\"job_id"') do set INTRO_JOB=%%a
set INTRO_JOB=%INTRO_JOB:~1,-1%
echo Job ID: %INTRO_JOB%

REM Wait for completion and download
echo Waiting for intro to complete...
:wait_intro
timeout /t 5 /nobreak >nul
curl -s http://localhost:8000/jobs/%INTRO_JOB% > "%TEMP%\intro_status.json"
findstr /c:"\"status\"" "%TEMP%\intro_status.json" | findstr /c:"succeeded" >nul
if errorlevel 1 goto wait_intro
echo Done!

echo.
echo Tutorial audio generation complete!
echo Audio files are in: %USERPROFILE%\OratioViva\outputs\audio
echo.
echo To create a single MP3 file, use ffmpeg:
echo   ffmpeg -f concat -safe 0 -i tutorial_concat.txt -b:a 192k tutorial_complete.mp3
echo.

pause
