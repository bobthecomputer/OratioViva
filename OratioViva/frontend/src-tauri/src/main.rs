#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    env,
    fs,
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{Arc, Mutex},
};

use anyhow::{Context, Result};
use tauri::{AppHandle, Manager, RunEvent};
use which::which;

const DEFAULT_PORT: u16 = 1421;

fn find_backend_script(app: &AppHandle) -> Option<PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(cwd) = env::current_dir() {
        candidates.push(cwd.join("backend").join("server.py"));
        candidates.push(cwd.join("..").join("backend").join("server.py"));
    }

    if let Some(res_dir) = app.path_resolver().resource_dir() {
        candidates.push(res_dir.join("backend").join("server.py"));
    }

    candidates.into_iter().find(|p| p.exists())
}

fn find_project_root(script: &Path) -> Option<PathBuf> {
    script.parent().and_then(Path::parent).map(Path::to_path_buf)
}

fn find_python(root: &Path) -> Result<PathBuf> {
    let candidates = [
        root.join(".venv").join("Scripts").join("python.exe"),
        root.join(".venv").join("bin").join("python"),
    ];
    for cand in candidates {
        if cand.exists() {
            return Ok(cand);
        }
    }

    which("python")
        .or_else(|_| which("python3"))
        .context("Python introuvable (ni .venv ni PATH)")
}

fn spawn_backend(app: &AppHandle) -> Result<Child> {
    let script = find_backend_script(app).context("backend/server.py introuvable")?;
    let project_root = find_project_root(&script).context("Impossible de determiner la racine du projet")?;
    let python = find_python(&project_root)?;

    let port = env::var("ORATIO_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(DEFAULT_PORT);
    let host = env::var("ORATIO_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());

    let data_dir = app
        .path_resolver()
        .app_data_dir()
        .unwrap_or_else(|| project_root.join("data"));
    fs::create_dir_all(&data_dir)?;

    println!(
        "[oratioviva-tauri] lancement backend: {} {}:{} (cwd: {})",
        python.display(),
        host,
        port,
        project_root.display()
    );

    let mut cmd = Command::new(python);
    cmd.arg(&script)
        .arg("--host")
        .arg(&host)
        .arg("--port")
        .arg(port.to_string())
        .current_dir(&project_root)
        .env("ORATIO_DATA_DIR", &data_dir)
        .env("ORATIO_HOST", &host)
        .env("ORATIO_PORT", port.to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    let child = cmd.spawn().context("Echec du demarrage du backend")?;
    Ok(child)
}

fn main() {
    let backend_proc: Arc<Mutex<Option<Child>>> = Arc::new(Mutex::new(None));
    let backend_proc_run = backend_proc.clone();

    tauri::Builder::default()
        .setup(move |app| {
            match spawn_backend(app) {
                Ok(child) => {
                    *backend_proc.lock().unwrap() = Some(child);
                }
                Err(err) => {
                    eprintln!("[oratioviva-tauri] backend non demarre: {err:?}");
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("Erreur au demarrage de Tauri")
        .run(move |_app_handle, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                if let Some(mut child) = backend_proc_run.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        });
}
