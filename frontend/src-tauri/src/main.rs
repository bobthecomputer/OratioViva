#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::{
    env,
    ffi::OsStr,
    fs::{self, File, OpenOptions},
    io::{BufRead, BufReader, Write},
    net::TcpListener,
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{Arc, Mutex},
    thread,
    time::Duration,
};

use chrono::Local;

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

use tauri::{AppHandle, Manager, RunEvent, State};

const DEFAULT_BACKEND_PORT: u16 = 8000;
const MAIN_VENV_NAME: &str = ".venv";
const DIA2_VENV_NAME: &str = ".venv_dia2";

#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

#[tauri::command]
fn get_api_base(state: State<BackendState>) -> String {
    let port = *state.port.lock().unwrap_or_else(|e| e.into_inner());
    let port = if port == 0 {
        DEFAULT_BACKEND_PORT
    } else {
        port
    };
    format!("http://127.0.0.1:{port}")
}

#[tauri::command]
fn open_devtools(app: AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.open_devtools();
        Ok(())
    } else {
        Err("Main window not found".to_string())
    }
}

#[tauri::command]
fn write_crash_report(app: AppHandle, report: String) -> Result<(), String> {
    let data_dir = get_app_data_dir(&app).ok_or("No app data dir")?;
    let logs_dir = data_dir.join("logs");
    fs::create_dir_all(&logs_dir).map_err(|e| format!("Failed to create logs dir: {e}"))?;
    let log_path = logs_dir.join("oratioviva-crash.log");
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("Failed to open crash log: {e}"))?;
    let ts = Local::now().format("%Y-%m-%d %H:%M:%S");
    let line = format!("[{ts}] {report}\n");
    file.write_all(line.as_bytes())
        .map_err(|e| format!("Failed to write crash log: {e}"))?;
    Ok(())
}

#[tauri::command]
fn log_frontend(app: AppHandle, message: String) -> Result<(), String> {
    let data_dir = get_app_data_dir(&app).ok_or("No app data dir")?;
    let logs_dir = data_dir.join("logs");
    fs::create_dir_all(&logs_dir).map_err(|e| format!("Failed to create logs dir: {e}"))?;
    let log_path = logs_dir.join("oratioviva-frontend.log");
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("Failed to open frontend log: {e}"))?;
    let ts = Local::now().format("%Y-%m-%d %H:%M:%S");
    let line = format!("[{ts}] {message}\n");
    file.write_all(line.as_bytes())
        .map_err(|e| format!("Failed to write frontend log: {e}"))?;
    Ok(())
}

#[derive(Default)]
struct BackendState {
    port: Mutex<u16>,
}

fn is_port_in_use(port: u16) -> bool {
    std::net::TcpStream::connect(("127.0.0.1", port)).is_ok()
}

fn find_available_port(preferred: u16) -> u16 {
    if preferred != 0 {
        if let Ok(listener) = TcpListener::bind(("127.0.0.1", preferred)) {
            drop(listener);
            return preferred;
        }
    }
    TcpListener::bind(("127.0.0.1", 0))
        .and_then(|listener| listener.local_addr().map(|addr| addr.port()))
        .unwrap_or(DEFAULT_BACKEND_PORT)
}

fn find_system_python() -> Option<PathBuf> {
    let found = which::which("python")
        .or_else(|_| which::which("python3"))
        .or_else(|_| which::which("py"))
        .ok();
    found.or_else(find_python_in_known_locations)
}

fn find_python_in_known_locations() -> Option<PathBuf> {
    let mut roots: Vec<PathBuf> = Vec::new();
    if let Ok(local_app_data) = env::var("LOCALAPPDATA") {
        let base = PathBuf::from(local_app_data);
        roots.push(base.join("Programs").join("Python"));
        let win_apps = base.join("Microsoft").join("WindowsApps");
        let win_python = win_apps.join("python.exe");
        if win_python.exists() {
            return Some(win_python);
        }
    }
    if let Ok(program_files) = env::var("ProgramFiles") {
        roots.push(PathBuf::from(program_files));
    }
    if let Ok(program_files_x86) = env::var("ProgramFiles(x86)") {
        roots.push(PathBuf::from(program_files_x86));
    }

    for root in roots {
        if let Some(found) = find_python_in_dir(&root) {
            return Some(found);
        }
    }
    None
}

fn find_python_in_dir(root: &Path) -> Option<PathBuf> {
    if !root.exists() {
        return None;
    }
    let entries = fs::read_dir(root).ok()?;
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_lowercase();
        if !name.starts_with("python") {
            continue;
        }
        let candidate = path.join("python.exe");
        if candidate.exists() {
            return Some(candidate);
        }
    }
    None
}

fn write_bootstrap_log(log_path: Option<&Path>, message: &str) {
    if let Some(path) = log_path {
        if let Some(parent) = path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Ok(mut file) = fs::OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(
                file,
                "[{}] {}",
                chrono::Local::now().format("%Y-%m-%d %H:%M:%S"),
                message
            );
        }
    }
}

#[cfg(target_os = "windows")]
fn kill_existing_backend_processes() {
    use std::process::Command;

    println!("Checking for existing backend processes...");
    let output = Command::new("powershell")
        .args(&["-Command", r#"Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*backend/server.py*' } | Select-Object -ExpandProperty Id"#])
        .creation_flags(CREATE_NO_WINDOW)
        .output()
        .ok();

    if let Some(output) = output {
        if output.status.success() {
            let stdout = String::from_utf8_lossy(&output.stdout);
            for line in stdout.lines() {
                if let Ok(pid) = line.trim().parse::<u32>() {
                    println!("Found existing backend process PID: {}", pid);
                    let _ = Command::new("powershell")
                        .args(&["-Command", &format!("Stop-Process -Id {} -Force", pid)])
                        .creation_flags(CREATE_NO_WINDOW)
                        .output();
                    println!("Killed backend process PID: {}", pid);
                }
            }
        }
    }
}

#[cfg(not(target_os = "windows"))]
fn kill_existing_backend_processes() {
    use std::process::Command;

    println!("Checking for existing backend processes...");
    let output = Command::new("sh")
        .args(&["-c", "pgrep -f 'backend/server.py' | xargs -r echo"])
        .output()
        .ok();

    if let Some(output) = output {
        if output.status.success() {
            let stdout = String::from_utf8_lossy(&output.stdout);
            for line in stdout.lines() {
                if let Ok(pid) = line.trim().parse::<u32>() {
                    println!("Found existing backend process PID: {}", pid);
                    let _ = Command::new("kill")
                        .args(&["-9", &pid.to_string()])
                        .output();
                    println!("Killed backend process PID: {}", pid);
                }
            }
        }
    }
}

fn find_embedded_python(venv_path: &Path) -> Option<PathBuf> {
    let python_path = if cfg!(target_os = "windows") {
        venv_path.join("Scripts").join("python.exe")
    } else {
        venv_path.join("bin").join("python")
    };
    if python_path.exists() {
        Some(python_path)
    } else {
        None
    }
}

fn get_app_data_dir(app: &AppHandle) -> Option<PathBuf> {
    app.path().app_data_dir().ok()
}

fn get_venv_path(app_data: &Path, venv_name: &str) -> PathBuf {
    app_data.join(venv_name)
}

fn venv_is_broken(venv_path: &Path) -> bool {
    let pyvenv_cfg = venv_path.join("pyvenv.cfg");
    let python_exe = venv_python_exe(venv_path);
    !python_exe.exists() || !pyvenv_cfg.exists()
}

fn verify_venv_works(python: &Path) -> bool {
    let mut cmd = Command::new(python);
    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.args(&[
        "-c",
        "import fastapi; import uvicorn; import huggingface_hub; import certifi; import os; c=certifi.where(); assert c and os.path.isfile(c), f'Certifi broken: {c}'; print('OK')",
    ])
    .stdout(Stdio::piped())
    .stderr(Stdio::piped());

    match cmd.output() {
        Ok(output) => {
            if !output.status.success() {
                if let Some(stderr) = String::from_utf8_lossy(&output.stderr).lines().next() {
                    eprintln!("Venv verification failed: {}", stderr);
                }
            }
            output.status.success()
        }
        Err(e) => {
            eprintln!("Venv verification error: {}", e);
            false
        }
    }
}

fn verify_dia2_venv(python: &Path) -> bool {
    let mut cmd = Command::new(python);
    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.args(&[
        "-c",
        "import torch; import transformers; import safetensors; import sphn; print('OK')",
    ])
    .stdout(Stdio::piped())
    .stderr(Stdio::piped());

    match cmd.output() {
        Ok(output) => {
            if !output.status.success() {
                if let Some(stderr) = String::from_utf8_lossy(&output.stderr).lines().next() {
                    eprintln!("Dia2 venv verification failed: {}", stderr);
                }
            }
            output.status.success()
        }
        Err(e) => {
            eprintln!("Dia2 venv verification error: {}", e);
            false
        }
    }
}

fn install_requirements(
    python: &Path,
    requirements: &Path,
    log_path: Option<&Path>,
) -> std::io::Result<bool> {
    println!("Installing requirements from {:?}", requirements);

    let mut cmd = Command::new(python);
    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.args(&["-m", "pip", "install", "--upgrade", "pip", "--no-cache-dir"]);
    if !run_command_with_output(&mut cmd, log_path)? {
        eprintln!("Warning: Failed to upgrade pip");
    }

    let mut cmd = Command::new(python);
    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.args(&[
        "-m",
        "pip",
        "install",
        "--force-reinstall",
        "--no-cache-dir",
        "certifi",
    ]);
    if !run_command_with_output(&mut cmd, log_path)? {
        eprintln!("Warning: Failed to reinstall certifi");
    }

    let mut cmd = Command::new(python);
    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.args(&["-m", "pip", "install", "-r", requirements.to_str().unwrap()]);
    run_command_with_output(&mut cmd, log_path)
}

fn get_requirements_path(backend_root: &Path) -> PathBuf {
    backend_root.join("requirements.txt")
}

fn venv_python_exe(venv_path: &Path) -> PathBuf {
    if cfg!(target_os = "windows") {
        venv_path.join("Scripts").join("python.exe")
    } else {
        venv_path.join("bin").join("python")
    }
}

fn run_command_with_output(cmd: &mut Command, log_path: Option<&Path>) -> std::io::Result<bool> {
    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let mut child = cmd.stdout(Stdio::piped()).stderr(Stdio::piped()).spawn()?;

    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();

    let log_path_buf = log_path.map(|path| path.to_path_buf());
    let log_path_stdout = log_path_buf.clone();
    let log_path_stderr = log_path_buf.clone();

    let stdout_thread = thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            if let Ok(line) = line {
                println!("[pip] {}", line);
                if let Some(path) = log_path_stdout.as_deref() {
                    write_bootstrap_log(Some(path), &format!("[pip] {}", line));
                }
            }
        }
    });

    let stderr_thread = thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            if let Ok(line) = line {
                eprintln!("[pip error] {}", line);
                if let Some(path) = log_path_stderr.as_deref() {
                    write_bootstrap_log(Some(path), &format!("[pip error] {}", line));
                }
            }
        }
    });

    let status = child.wait()?;
    let _ = stdout_thread.join();
    let _ = stderr_thread.join();

    Ok(status.success())
}

fn create_venv(python_path: &Path, venv_path: &Path) -> std::io::Result<()> {
    println!("Creating virtual environment at {:?}", venv_path);

    let mut cmd = Command::new(python_path);
    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let is_py_launcher = python_path
        .file_stem()
        .map(|name| name == OsStr::new("py"))
        .unwrap_or(false);
    if is_py_launcher {
        cmd.arg("-3");
    }
    cmd.args(&[
        "-m",
        "venv",
        "--clear",
        "--upgrade-deps",
        venv_path.to_str().unwrap(),
    ])
    .stdout(Stdio::null())
    .stderr(Stdio::null());

    let status = cmd.status()?;

    if !status.success() {
        return Err(std::io::Error::new(
            std::io::ErrorKind::Other,
            "Failed to create virtual environment",
        ));
    }

    Ok(())
}

fn try_create_venv_atomic(python_path: &Path, venv_path: &Path) -> std::io::Result<PathBuf> {
    if venv_path.exists() {
        let py_exe = venv_python_exe(venv_path);
        if py_exe.exists() {
            println!("Existing venv found at {:?}, verifying...", venv_path);
            if verify_venv_works(&py_exe) {
                return Ok(venv_path.to_path_buf());
            }
            println!("Existing venv is broken, recreating...");
        }

        let backup_path = venv_path.with_extension(".bak");
        if let Err(e) = fs::rename(venv_path, &backup_path) {
            println!("Cannot rename venv for backup: {}, trying delete", e);
            if let Err(e2) = fs::remove_dir_all(venv_path) {
                println!("Cannot remove broken venv: {}, trying new venv name", e2);
                let mut counter = 2;
                loop {
                    let new_name = format!(".venv_{}", counter);
                    let new_path = venv_path.parent().unwrap_or(Path::new(".")).join(&new_name);
                    if !new_path.exists() {
                        create_venv(python_path, &new_path)?;
                        return Ok(new_path);
                    }
                    counter += 1;
                    if counter > 100 {
                        return Err(std::io::Error::new(
                            std::io::ErrorKind::Other,
                            "Too many venv attempts",
                        ));
                    }
                }
            }
        }

        if let Err(e) = create_venv(python_path, venv_path) {
            println!(
                "Failed to create venv at {:?}, restoring backup: {}",
                venv_path, e
            );
            let _ = fs::remove_dir_all(venv_path);
            let _ = fs::rename(&backup_path, venv_path);
            return Err(e);
        }

        let _ = fs::remove_dir_all(backup_path);
        Ok(venv_path.to_path_buf())
    } else {
        create_venv(python_path, venv_path)?;
        Ok(venv_path.to_path_buf())
    }
}

fn ensure_venv(
    app_data: &Path,
    _backend_root: &Path,
    venv_name: &str,
    requirements_path: &Path,
    log_path: Option<&Path>,
) -> Option<PathBuf> {
    let venv_path = get_venv_path(app_data, venv_name);
    let requirements = requirements_path.to_path_buf();

    if !requirements.exists() {
        eprintln!("Requirements file not found: {:?}", requirements);
        return None;
    }

    let python = find_system_python().or_else(|| find_embedded_python(&venv_path))?;

    println!("Ensuring venv {} at {:?}", venv_name, venv_path);

    match try_create_venv_atomic(&python, &venv_path) {
        Ok(actual_venv_path) => {
            let venv_python = venv_python_exe(&actual_venv_path);
            if !venv_python.exists() {
                eprintln!("Python not found in venv: {:?}", venv_python);
                return None;
            }

            if verify_venv_works(&venv_python) {
                println!("Venv {} verified successfully", venv_name);
                return Some(venv_python);
            }

            println!(
                "Venv verification failed, reinstalling dependencies in {}...",
                venv_name
            );
            match install_requirements(&venv_python, &requirements, log_path) {
                Ok(true) => {}
                Ok(false) => {
                    eprintln!("Failed to install requirements in {}", venv_name);
                    return None;
                }
                Err(e) => {
                    eprintln!("Failed to install requirements in {}: {}", venv_name, e);
                    return None;
                }
            }

            if verify_venv_works(&venv_python) {
                println!("Venv {} verified after reinstall", venv_name);
                Some(venv_python)
            } else {
                eprintln!("Venv {} still broken after reinstall", venv_name);
                None
            }
        }
        Err(e) => {
            eprintln!("Failed to create/verify {}: {}", venv_name, e);
            None
        }
    }
}

fn ensure_backend_venv(app: &AppHandle, log_path: Option<&Path>) -> Option<PathBuf> {
    let backend_root = find_backend_root(app)?;
    let app_data = get_app_data_dir(app)?;
    let requirements = get_requirements_path(&backend_root);
    ensure_venv(&app_data, &backend_root, MAIN_VENV_NAME, &requirements, log_path)
}

fn ensure_dia2_venv(app: &AppHandle, log_path: Option<&Path>) -> Option<PathBuf> {
    let backend_root = find_backend_root(app)?;
    let app_data = get_app_data_dir(app)?;
    let requirements_dia2 = backend_root.join("requirements_dia2.txt");
    let requirements_default = get_requirements_path(&backend_root);
    let requirements = if requirements_dia2.exists() {
        &requirements_dia2
    } else {
        &requirements_default
    };
    let python = ensure_venv(&app_data, &backend_root, DIA2_VENV_NAME, requirements, log_path)?;

    // If Dia2 deps are missing (older installs), force-install the Dia2 requirements.
    if !verify_dia2_venv(&python) {
        println!("Dia2 deps missing, installing requirements...");
        match install_requirements(&python, requirements, log_path) {
            Ok(true) => {}
            Ok(false) => {
                eprintln!("Failed to install Dia2 requirements");
                return None;
            }
            Err(e) => {
                eprintln!("Failed to install Dia2 requirements: {}", e);
                return None;
            }
        }
        if !verify_dia2_venv(&python) {
            eprintln!("Dia2 venv still missing required packages after install");
            return None;
        }
    }

    Some(python)
}

fn find_backend_root(app: &AppHandle) -> Option<PathBuf> {
    if let Ok(resource_dir) = app.path().resource_dir() {
        println!("[find_backend_root] resource_dir: {:?}", resource_dir);

        let candidates = [
            resource_dir.join("backend"),
            resource_dir.join("resources").join("backend"),
            resource_dir.join("_up_").join("_up_").join("backend"),
        ];
        for candidate in &candidates {
            println!("[find_backend_root] Checking candidate: {:?}", candidate);
            println!("[find_backend_root] server.py exists: {}", candidate.join("server.py").exists());
            println!("[find_backend_root] certs exists: {}", candidate.join("certs").join("cacert.pem").exists());
            if candidate.join("server.py").exists() {
                println!("[find_backend_root] Found backend at: {:?}", candidate);
                return Some(candidate.clone());
            }
        }

        if let Ok(entries) = fs::read_dir(&resource_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                let candidate = path.join("backend");
                println!("[find_backend_root] Scanning dir: {:?}, checking: {:?}", path, candidate);
                println!("[find_backend_root] server.py exists: {}", candidate.join("server.py").exists());
                if candidate.join("server.py").exists() {
                    println!("[find_backend_root] Found backend at: {:?}", candidate);
                    return Some(candidate);
                }
                let nested = path.join("_up_").join("backend");
                if nested.join("server.py").exists() {
                    println!("[find_backend_root] Found backend at (nested): {:?}", nested);
                    return Some(nested);
                }
            }
        }
    }

    let dev = PathBuf::from("C:/Users/paul/OratioViva/backend");
    if dev.join("server.py").exists() {
        println!("[find_backend_root] Using development backend: {:?}", dev);
        return Some(dev);
    }

    println!("[find_backend_root] Backend NOT found!");
    None
}

fn start_backend(app: &AppHandle, python_path: &Path, port: u16) -> Option<std::process::Child> {
    if is_port_in_use(port) {
        eprintln!("Port {} is already in use", port);
        return None;
    }

    let backend_root = find_backend_root(app)?;
    let server = backend_root.join("server.py");
    if !server.exists() {
        eprintln!("Server file not found: {:?}", server);
        return None;
    }

    let data_dir = get_app_data_dir(app)?;
    let models_dir = data_dir.join("models");
    let outputs_dir = data_dir.join("outputs");
    let logs_dir = data_dir.join("logs");

    // Dia2 runs in its own venv. Backend needs to know where that interpreter is.
    let dia2_venv_dir = get_venv_path(&data_dir, DIA2_VENV_NAME);
    let dia2_python = venv_python_exe(&dia2_venv_dir);

    for dir in [&models_dir, &outputs_dir, &logs_dir] {
        if let Err(e) = fs::create_dir_all(dir) {
            eprintln!("Failed to create directory {:?}: {}", dir, e);
        }
    }

    let log_path = logs_dir.join("oratioviva-backend.log");
    let log_file = File::create(&log_path).ok();

    // Find the bundled certificates path
    let bundled_cert_path = backend_root.join("certs").join("cacert.pem");
    println!("Checking for bundled cert at: {:?}", bundled_cert_path);
    println!("Bundled cert exists: {}", bundled_cert_path.exists());

    let mut cmd = Command::new(python_path);
    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.arg(&server)
        .arg("--host")
        .arg("127.0.0.1")
        .arg("--port")
        .arg(port.to_string())
        .current_dir(&backend_root)
        .env("ORATIO_DATA_DIR", &data_dir)
        .env("ORATIO_MODELS_DIR", &models_dir)
        .env("ORATIO_OUTPUTS_DIR", &outputs_dir)
        .env("ORATIO_LOG_DIR", &logs_dir)
        .env("ORATIO_DIA2_PYTHON", &dia2_python)
        .env("ORATIO_PORT", port.to_string())
        .env("TAURI_RESOURCE_DIR", &backend_root)
        .stdin(Stdio::null());

    // Only set ORATIO_CA_BUNDLE if bundled certificate exists
    if bundled_cert_path.exists() {
        let cert_path_str = bundled_cert_path.to_string_lossy().to_string();
        println!("Setting ORATIO_CA_BUNDLE to: {}", cert_path_str);
        cmd.env("ORATIO_CA_BUNDLE", cert_path_str);
    } else {
        println!("NOT setting ORATIO_CA_BUNDLE - bundled cert not found");
    }

    if let Some(file) = log_file {
        let err_file = file.try_clone().ok();
        cmd.stdout(Stdio::from(file));
        if let Some(err_file) = err_file {
            cmd.stderr(Stdio::from(err_file));
        }
    }

    println!("Starting backend with Python: {:?}", python_path);
    println!("Backend root: {:?}", backend_root);
    println!("Models dir: {:?}", models_dir);

    match cmd.spawn() {
        Ok(child) => {
            println!("Backend started successfully");
            Some(child)
        }
        Err(e) => {
            eprintln!("Failed to start backend: {}", e);
            None
        }
    }
}

fn wait_for_backend(port: u16, max_attempts: u32) -> bool {
    for i in 0..max_attempts {
        if is_port_in_use(port) {
            println!("Backend is ready after {} attempts", i + 1);
            return true;
        }
        std::thread::sleep(Duration::from_millis(500));
    }
    eprintln!("Backend failed to start after {} attempts", max_attempts);
    false
}

#[tauri::command]
async fn restart_backend(app: AppHandle, state: State<'_, BackendState>) -> Result<(), String> {
    let app_data_root = get_app_data_dir(&app).ok_or("No app data dir")?;
    let bootstrap_log = app_data_root.join("logs").join("oratioviva-bootstrap.log");

    write_bootstrap_log(Some(&bootstrap_log), "Restarting backend via user request...");

    kill_existing_backend_processes();
    write_bootstrap_log(Some(&bootstrap_log), "Killed existing backend processes");

    let venv_path = get_venv_path(&app_data_root, MAIN_VENV_NAME);
    let venv_python = venv_python_exe(&venv_path);

    if !venv_python.exists() {
        return Err("Venv Python not found".to_string());
    }

    let port = {
        let state_port = *state.port.lock().map_err(|e| e.to_string())?;
        if state_port == 0 {
            DEFAULT_BACKEND_PORT
        } else {
            state_port
        }
    };

    if is_port_in_use(port) {
        write_bootstrap_log(Some(&bootstrap_log), &format!("Port {} still in use, waiting...", port));
        tokio::time::sleep(tokio::time::Duration::from_millis(1000)).await;
    }

    write_bootstrap_log(Some(&bootstrap_log), &format!("Starting new backend on port {}...", port));

    let new_child = start_backend(&app, &venv_python, port);

    if new_child.is_none() {
        return Err("Failed to start backend".to_string());
    }

    let port_clone = port;
    let bootstrap_log_clone = bootstrap_log.clone();
    tokio::spawn(async move {
        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
        if !wait_for_backend(port_clone, 30) {
            write_bootstrap_log(Some(&bootstrap_log_clone), &format!("Backend restart may have failed on port {}", port_clone));
        } else {
            write_bootstrap_log(Some(&bootstrap_log_clone), &format!("Backend restarted successfully on port {}", port_clone));
        }
    });

    Ok(())
}

fn main() {
    let backend_child: Arc<Mutex<Option<std::process::Child>>> = Arc::new(Mutex::new(None));
    let backend_child_run = backend_child.clone();

    tauri::Builder::default()
        .manage(BackendState {
            port: Mutex::new(DEFAULT_BACKEND_PORT),
        })
        .setup(move |app| {
            let app_handle = app.handle().clone();
            let backend_child_setup = backend_child.clone();
            thread::spawn(move || {
                let app_data_root = get_app_data_dir(&app_handle);
                let bootstrap_log = app_data_root
                    .as_ref()
                    .map(|path| path.join("logs").join("oratioviva-bootstrap.log"));

                println!("OratioViva starting...");
                write_bootstrap_log(bootstrap_log.as_deref(), "OratioViva bootstrap starting...");

                kill_existing_backend_processes();
                write_bootstrap_log(
                    bootstrap_log.as_deref(),
                    "Checked for existing backend processes",
                );

                let backend_root = find_backend_root(&app_handle);
                if backend_root.is_none() {
                    eprintln!("ERROR: Could not find backend directory");
                    write_bootstrap_log(
                        bootstrap_log.as_deref(),
                        "ERROR: Could not find backend directory",
                    );
                    return;
                }
                println!("Found backend at: {:?}", backend_root.as_ref().unwrap());
                write_bootstrap_log(
                    bootstrap_log.as_deref(),
                    &format!("Backend root: {:?}", backend_root.as_ref().unwrap()),
                );

                let app_data = app_data_root;
                if app_data.is_none() {
                    eprintln!("ERROR: Could not get app data directory");
                    write_bootstrap_log(
                        bootstrap_log.as_deref(),
                        "ERROR: Could not get app data directory",
                    );
                    return;
                }
                println!("App data directory: {:?}", app_data.as_ref().unwrap());
                write_bootstrap_log(
                    bootstrap_log.as_deref(),
                    &format!("App data directory: {:?}", app_data.as_ref().unwrap()),
                );
                let venv_log = app_data
                    .as_ref()
                    .map(|path| path.join("logs").join("oratioviva-venv.log"));

                let system_python = find_system_python();
                write_bootstrap_log(
                    bootstrap_log.as_deref(),
                    &format!("System python: {:?}", system_python),
                );
                let venv_path = get_venv_path(app_data.as_ref().unwrap(), MAIN_VENV_NAME);
                write_bootstrap_log(
                    bootstrap_log.as_deref(),
                    &format!("Expected venv path: {:?}", venv_path),
                );

                println!("Setting up main Python environment...");
                write_bootstrap_log(
                    bootstrap_log.as_deref(),
                    "Setting up main Python environment...",
                );
                let python_path = ensure_backend_venv(&app_handle, venv_log.as_deref());
                if python_path.is_none() {
                    eprintln!("ERROR: Failed to setup main venv");
                    write_bootstrap_log(
                        bootstrap_log.as_deref(),
                        "ERROR: Failed to setup main venv",
                    );
                    return;
                }
                println!("Main venv Python: {:?}", python_path.as_ref().unwrap());
                write_bootstrap_log(
                    bootstrap_log.as_deref(),
                    &format!("Main venv Python: {:?}", python_path.as_ref().unwrap()),
                );

                let app_handle_dia2 = app_handle.clone();
                let bootstrap_log_dia2 = bootstrap_log.clone();
                let venv_log_dia2 = venv_log.clone();
                thread::spawn(move || {
                    println!("Setting up Dia2 Python environment...");
                    write_bootstrap_log(
                        bootstrap_log_dia2.as_deref(),
                        "Setting up Dia2 Python environment...",
                    );
                    let dia2_python = ensure_dia2_venv(&app_handle_dia2, venv_log_dia2.as_deref());
                    if dia2_python.is_none() {
                        eprintln!("Warning: Failed to setup Dia2 venv (may not be needed yet)");
                        write_bootstrap_log(
                            bootstrap_log_dia2.as_deref(),
                            "Warning: Failed to setup Dia2 venv (may not be needed yet)",
                        );
                    } else {
                        println!("Dia2 venv ready");
                        write_bootstrap_log(bootstrap_log_dia2.as_deref(), "Dia2 venv ready");
                    }
                });

                let mut port = find_available_port(DEFAULT_BACKEND_PORT);
                {
                    let _state = app_handle.state::<BackendState>();
                    *_state.port.lock().unwrap() = port;
                }

                println!("Starting backend server on port {}...", port);
                write_bootstrap_log(
                    bootstrap_log.as_deref(),
                    &format!("Starting backend server on port {}...", port),
                );
                let python_for_backend = python_path.unwrap().clone();
                let child = start_backend(&app_handle, &python_for_backend, port);
                let child_running = child.is_some();
                *backend_child_setup.lock().unwrap() = child;

                if child_running {
                    println!("Waiting for backend to be ready...");
                    write_bootstrap_log(
                        bootstrap_log.as_deref(),
                        "Waiting for backend to be ready...",
                    );
                    if !wait_for_backend(port, 60) {
                        eprintln!("Backend failed on port {}, retrying...", port);
                        write_bootstrap_log(
                            bootstrap_log.as_deref(),
                            &format!("Backend failed on port {}, retrying...", port),
                        );
                        if let Some(mut previous) = backend_child_setup.lock().unwrap().take() {
                            let _ = previous.kill();
                        }
                        port = find_available_port(0);
                        {
                            let state = app_handle.state::<BackendState>();
                            *state.port.lock().unwrap() = port;
                        }
                        println!("Retrying backend on port {}...", port);
                        write_bootstrap_log(
                            bootstrap_log.as_deref(),
                            &format!("Retrying backend on port {}...", port),
                        );
                        let child = start_backend(&app_handle, &python_for_backend, port);
                        let child_running = child.is_some();
                        *backend_child_setup.lock().unwrap() = child;
                        if child_running {
                            if wait_for_backend(port, 60) {
                                println!("Backend is ready on port {}!", port);
                                write_bootstrap_log(
                                    bootstrap_log.as_deref(),
                                    &format!("Backend is ready on port {}!", port),
                                );
                            } else {
                                eprintln!("Warning: Backend may not be ready");
                                write_bootstrap_log(
                                    bootstrap_log.as_deref(),
                                    "Warning: Backend may not be ready",
                                );
                            }
                        }
                    } else {
                        println!("Backend is ready! Opening main window...");
                        write_bootstrap_log(bootstrap_log.as_deref(), "Backend is ready!");
                    }
                } else {
                    write_bootstrap_log(
                        bootstrap_log.as_deref(),
                        "ERROR: Failed to start backend process",
                    );
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_api_base,
            restart_backend,
            log_frontend,
            open_devtools,
            write_crash_report
        ])
        .build(tauri::generate_context!())
        .expect("Failed to start OratioViva")
        .run(move |_app_handle, event| {
            if matches!(event, RunEvent::ExitRequested { .. } | RunEvent::Exit) {
                println!("Shutting down...");
                if let Some(mut child) = backend_child_run.lock().unwrap().take() {
                    let _ = child.kill();
                }
                kill_existing_backend_processes();
            }
        });
}
