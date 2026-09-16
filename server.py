import os
import sys
import subprocess

# --- অটো-ডিপেনডেন্সি ইনস্টলার ---
REQUIRED_PACKAGES = {
    "fastapi": "fastapi==0.110.0",
    "uvicorn": "uvicorn==0.28.0",
    "telegram": "python-telegram-bot==20.8",
    "psutil": "psutil==5.9.8",
    "aiofiles": "aiofiles==23.2.1",
    "pydantic": "pydantic==2.6.4",
    "multipart": "python-multipart==0.0.9"
}

for module_name, pip_name in REQUIRED_PACKAGES.items():
    try:
        mod_to_check = "multipart" if module_name == "multipart" else module_name
        __import__(mod_to_check)
    except ImportError:
        print(f"📦 Missing package '{module_name}' detected. Installing automatically...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

# --- মূল সার্ভার কোড ---
import shutil
import zipfile
import asyncio
import logging
import time
import ast
import psutil
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
import uvicorn

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("RahulBotServer")

BOT_TOKEN = os.getenv("BOT_TOKEN", "8902207256:AAG7amU9d5HHg5LTyG7ztL2sDDbImpRU4UM")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8902207256"))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "10000"))

BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"
PROJECTS_DIR.mkdir(exist_ok=True)

projects: Dict[str, dict] = {}

class ProjectManager:
    @staticmethod
    def list_projects() -> List[dict]:
        projs = []
        for pid, data in projects.items():
            projs.append({
                "id": pid,
                "name": data["name"],
                "type": data["type"],
                "status": data["status"],
                "pid": data.get("pid"),
                "error": data.get("error")
            })
        return projs

    @staticmethod
    def get_project(pid: str) -> Optional[dict]:
        return projects.get(pid)

    @staticmethod
    def validate_code(file_path: Path) -> tuple[bool, str]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            ast.parse(code)
            return True, "Syntax check passed"
        except SyntaxError as e:
            return False, f"SyntaxError at line {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def start_project(pid: str):
        proj = projects.get(pid)
        if not proj:
            return

        proj["status"] = "🟡 STARTING"
        proj["logs"].append(f"[{datetime.now().strftime('%H:%M:%S' )}] Starting project...")

        work_dir = Path(proj["path"])
        entry_file = work_dir / proj["entry"]

        # যদি কেউ ভুলবশত সার্ভার ফাইলটিই সাব প্রজেক্ট হিসেবে স্টার্ট করতে চায়, পোর্ট কনফ্লিক্ট এড়াতে পোর্ট ফ্রি এনভায়রনমেন্ট দেওয়া হবে
        env = os.environ.copy()
        if entry_file.name == "server.py":
            env["PORT"] = "0"  # সাব-সার্ভার হিসেবে ফিক্সড পোর্টের ঝামেলা এড়াতে

        valid, msg = ProjectManager.validate_code(entry_file)
        if not valid:
            proj["status"] = "❌ ERROR"
            proj["error"] = msg
            proj["logs"].append(f"[{datetime.now().strftime('%H:%M:%S' )}] ❌ {msg}")
            return

        req_file = work_dir / "requirements.txt"
        if req_file.exists():
            proj["status"] = "🟠 INSTALLING"
            proj["logs"].append(f"[{datetime.now().strftime('%H:%M:%S' )}] Installing dependencies from requirements.txt...")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--target", str(work_dir / "venv_libs")],
                    cwd=str(work_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=120,
                    check=True
                )
            except Exception as e:
                proj["status"] = "❌ ERROR"
                proj["error"] = f"Dependency installation failed: {e}"
                proj["logs"].append(f"[{datetime.now().strftime('%H:%M:%S' )}] ❌ {proj['error']}")
                return

        env.pop("BOT_TOKEN", None)
        env.pop("ADMIN_ID", None)
        if work_dir.joinpath("venv_libs").exists():
            env["PYTHONPATH"] = str(work_dir / "venv_libs")

        try:
            process = subprocess.Popen(
                [sys.executable, str(entry_file)],
                cwd=str(work_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env
            )
            proj["process"] = process
            proj["pid"] = process.pid
            proj["status"] = "🟢 RUNNING"
            proj["error"] = None
            proj["logs"].append(f"[{datetime.now().strftime('%H:%M:%S' )}] 🚀 Started successfully (PID: {process.pid})")

            def monitor():
                while process.poll() is None:
                    line = process.stdout.readline()
                    if line:
                        proj["logs"].append(f"[{datetime.now().strftime('%H:%M:%S' )}] {line.strip()}")
                        if len(proj["logs"]) > 500:
                            proj["logs"].pop(0)
                    time.sleep(0.1)
                
                retcode = process.poll()
                if retcode == 0:
                    proj["status"] = "⚪ STOPPED"
                else:
                    proj["status"] = "🔴 CRASHED"
                proj["logs"].append(f"[{datetime.now().strftime('%H:%M:%S' )}] Process exited with code {retcode}")

            import threading
            threading.Thread(target=monitor, daemon=True).start()

        except Exception as e:
            proj["status"] = "❌ ERROR"
            proj["error"] = str(e)
            proj["logs"].append(f"[{datetime.now().strftime('%H:%M:%S' )}] ❌ Startup failed: {e}")

    @staticmethod
    def stop_project(pid: str):
        proj = projects.get(pid)
        if not proj or not proj.get("process"):
            if proj:
                proj["status"] = "⚪ STOPPED"
            return
        
        proc: subprocess.Popen = proj["process"]
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        except Exception:
            pass
        
        proj["process"] = None
        proj["pid"] = None
        proj["status"] = "⚪ STOPPED"
        proj["logs"].append(f"[{datetime.now().strftime('%H:%M:%S' )}] ⏹ Project stopped.")

    @staticmethod
    def restart_project(pid: str):
        ProjectManager.stop_project(pid)
        time.sleep(1)
        ProjectManager.start_project(pid)

    @staticmethod
    def delete_project(pid: str):
        ProjectManager.stop_project(pid)
        proj = projects.get(pid)
        if proj:
            shutil.rmtree(proj["path"], ignore_errors=True)
            del projects[pid]

app = FastAPI(title="Rahul Bot Server")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return DASHBOARD_HTML

@app.get("/api/status")
async def api_status():
    running = sum(1 for p in projects.values() if p["status"] == "🟢 RUNNING")
    stopped = sum(1 for p in projects.values() if p["status"] == "⚪ STOPPED")
    failed = sum(1 for p in projects.values() if p["status"] in ["🔴 CRASHED", "❌ ERROR"])
    
    try:
        cpu = f"{psutil.cpu_percent(interval=None)}%"
        ram = f"{psutil.virtual_memory().used // (1024 * 1024)} MB"
        disk = f"{psutil.disk_usage('/').used // (1024 * 1024 * 1024)} GB"
    except Exception:
        cpu = ram = disk = "Unavailable"

    return {
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
        "running": running,
        "stopped": stopped,
        "failed": failed,
        "projects": ProjectManager.list_projects()
    }

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    pid = f"RB-{int(time.time())}"
    proj_dir = PROJECTS_DIR / pid
    proj_dir.mkdir(exist_ok=True)

    file_path = proj_dir / filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    entry_file = filename
    proj_type = "Python"

    if filename.endswith(".zip"):
        proj_type = "ZIP Project"
        try:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(proj_dir)
            file_path.unlink()
            candidates = ["bot.py", "main.py", "app.py", "run.py"]
            found = [c for c in candidates if (proj_dir / c).exists()]
            entry_file = found[0] if found else list(proj_dir.glob("*.py"))[0].name
        except Exception as e:
            shutil.rmtree(proj_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Invalid ZIP archive: {e}")

    projects[pid] = {
        "id": pid,
        "name": filename,
        "type": proj_type,
        "path": str(proj_dir),
        "entry": entry_file,
        "status": "⚪ STOPPED",
        "pid": None,
        "error": None,
        "process": None,
        "logs": [f"[{datetime.now().strftime('%H:%M:%S' )}] Project uploaded successfully."]
    }

    return {"status": "success", "project_id": pid, "filename": filename}

@app.post("/api/project/{pid}/{action}")
async def project_action(pid: str, action: str, background_tasks: BackgroundTasks):
    proj = ProjectManager.get_project(pid)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")

    if action == "start":
        background_tasks.add_task(ProjectManager.start_project, pid)
        return {"status": "success", "message": "Starting project..."}
    elif action == "stop":
        ProjectManager.stop_project(pid)
        return {"status": "success", "message": "Project stopped."}
    elif action == "restart":
        background_tasks.add_task(ProjectManager.restart_project, pid)
        return {"status": "success", "message": "Restarting project..."}
    elif action == "delete":
        ProjectManager.delete_project(pid)
        return {"status": "success", "message": "Project deleted."}
    else:
        raise HTTPException(status_code=400, detail="Unknown action")

# Telegram Handlers
async def tg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Unauthorized access.")
        return

    keyboard = [
        [KeyboardButton("🚀 MY PROJECTS"), KeyboardButton("📁 UPLOAD PROJECT")],
        [KeyboardButton("🖥 SERVER STATUS"), KeyboardButton("🆘 SERVICE CENTER")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("╔══════════════════════════════════╗\n          RAHUL BOT SERVER          \n╚══════════════════════════════════╝\nWelcome to your premium bot hosting server.", reply_markup=reply_markup)

async def tg_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and update.effective_user.id != ADMIN_ID:
        return

    text = update.message.text
    if text == "🚀 MY PROJECTS":
        projs = ProjectManager.list_projects()
        if not projs:
            await update.message.reply_text("No projects found.")
            return
        
        for p in projs:
            kb = [
                [InlineKeyboardButton("▶ Start", callback_data=f"start_{p['id']}"),
                 InlineKeyboardButton("⏹ Stop", callback_data=f"stop_{p['id']}"),
                 InlineKeyboardButton("🔄 Restart", callback_data=f"restart_{p['id']}")],
                [InlineKeyboardButton("📜 Logs", callback_data=f"logs_{p['id']}"),
                 InlineKeyboardButton("🗑 Delete", callback_data=f"delete_{p['id']}")]
            ]
            await update.message.reply_text(f"🤖 **{p['name']}**\nType: {p['type']}\nStatus: {p['status']}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    elif text == "📁 UPLOAD PROJECT":
        await update.message.reply_text("Please send your `.py` file or `.zip` project archive directly in this chat.")

    elif text == "🖥 SERVER STATUS":
        try:
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().used // (1024 * 1024)
            disk = psutil.disk_usage('/').used // (1024 * 1024 * 1024)
        except Exception:
            cpu = ram = disk = "Unavailable"

        running = sum(1 for p in projects.values() if p["status"] == "🟢 RUNNING")
        stopped = sum(1 for p in projects.values() if p["status"] == "⚪ STOPPED")
        
        msg = f"🖥 **SERVER STATUS**\n🟢 API SERVER: ONLINE\nCPU: {cpu}%\nRAM: {ram} MB\nDisk: {disk} GB\nRUNNING: {running}\nSTOPPED: {stopped}"
        await update.message.reply_text(msg, parse_mode="Markdown")

    elif text == "🆘 SERVICE CENTER":
        await update.message.reply_text("Rahul Bot Server is operating normally.")

async def tg_document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID and update.effective_user.id != ADMIN_ID:
        return

    doc = update.message.document
    filename = doc.file_name
    if not filename or not (filename.endswith(".py") or filename.endswith(".zip")):
        await update.message.reply_text("❌ Only .py or .zip files are supported.")
        return

    file = await context.bot.get_file(doc.file_id)
    pid = f"RB-{int(time.time())}"
    proj_dir = PROJECTS_DIR / pid
    proj_dir.mkdir(exist_ok=True)

    file_path = proj_dir / filename
    await file.download_to_drive(custom_path=str(file_path))

    entry_file = filename
    proj_type = "Python"

    if filename.endswith(".zip"):
        proj_type = "ZIP Project"
        try:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                zip_ref.extractall(proj_dir)
            file_path.unlink()
            candidates = ["bot.py", "main.py", "app.py", "run.py"]
            found = [c for c in candidates if (proj_dir / c).exists()]
            entry_file = found[0] if found else list(proj_dir.glob("*.py"))[0].name
        except Exception as e:
            shutil.rmtree(proj_dir, ignore_errors=True)
            await update.message.reply_text(f"❌ Failed to extract ZIP: {e}")
            return

    projects[pid] = {
        "id": pid,
        "name": filename,
        "type": proj_type,
        "path": str(proj_dir),
        "entry": entry_file,
        "status": "⚪ STOPPED",
        "pid": None,
        "error": None,
        "process": None,
        "logs": [f"[{datetime.now().strftime('%H:%M:%S' )}] Project uploaded via Telegram."]
    }

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("▶ Start Now", callback_data=f"start_{pid}")]])
    await update.message.reply_text(f"📦 **File Uploaded Successfully!**\nName: {filename}\nProject ID: {pid}", reply_markup=kb, parse_mode="Markdown")

async def tg_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    action, pid = data.split("_", 1)

    proj = ProjectManager.get_project(pid)
    if not proj:
        await query.edit_message_text("❌ Project no longer exists.")
        return

    if action == "start":
        ProjectManager.start_project(pid)
        await query.edit_message_text(f"🚀 Started project: {proj['name']}\nStatus: {proj['status']}")
    elif action == "stop":
        ProjectManager.stop_project(pid)
        await query.edit_message_text(f"⏹ Stopped project: {proj['name']}\nStatus: {proj['status']}")
    elif action == "restart":
        ProjectManager.restart_project(pid)
        await query.edit_message_text(f"🔄 Restarted project: {proj['name']}")
    elif action == "logs":
        logs_text = "\n".join(proj["logs"][-10:])
        await query.message.reply_text(f"📜 **Logs for {proj['name']}**:\n```\n{logs_text}\n```", parse_mode="Markdown")
    elif action == "delete":
        ProjectManager.delete_project(pid)
        await query.edit_message_text(f"🗑 Project {proj['name']} deleted.")

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rahul Bot Server</title>
    <style>
        :root { background-color: #0f172a; color: #f8fafc; font-family: system-ui, -apple-system, sans-serif; }
        body { margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { width: 100%; max-width: 900px; }
        header { text-align: center; border-bottom: 2px solid #334155; padding-bottom: 15px; margin-bottom: 20px; }
        h1 { margin: 0; font-size: 1.8rem; letter-spacing: 1px; color: #38bdf8; }
        .card { background: #1e293b; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .stat-box { background: #0f172a; padding: 15px; border-radius: 8px; border: 1px solid #334155; }
        .btn { background: #0284c7; color: white; border: none; padding: 10px 15px; border-radius: 6px; cursor: pointer; font-weight: bold; transition: background 0.2s; }
        .btn:hover { background: #0369a1; }
        .btn-danger { background: #dc2626; }
        .btn-danger:hover { background: #b91c1c; }
        .project-card { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 15px; margin-bottom: 10px; display: flex; flex-direction: column; gap: 10px; }
        .project-actions { display: flex; gap: 8px; flex-wrap: wrap; }
        input[type="file"] { display: none; }
        .upload-label { display: inline-block; background: #10b981; color: white; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; }
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>╔══════════════════════════════════╗<br>RAHUL BOT SERVER<br>╚══════════════════════════════════╝</h1>
        <p style="color: #34d399; margin: 5px 0;">🟢 SERVER ONLINE</p>
    </header>

    <div class="card">
        <h3>Server Metrics</h3>
        <div class="grid" id="metrics">
            <div class="stat-box">CPU: <span id="cpu">...</span></div>
            <div class="stat-box">RAM: <span id="ram">...</span></div>
            <div class="stat-box">Disk: <span id="disk">...</span></div>
            <div class="stat-box">Running: <span id="running">0</span></div>
            <div class="stat-box">Stopped: <span id="stopped">0</span></div>
            <div class="stat-box">Failed: <span id="failed">0</span></div>
        </div>
    </div>

    <div class="card">
        <h3>Upload Project</h3>
        <label class="upload-label">
            📁 Choose Python File or ZIP
            <input type="file" id="fileInput" accept=".py,.zip" onchange="uploadFile()">
        </label>
        <p id="uploadStatus" style="margin-top: 10px; font-size: 0.9rem; color: #94a3b8;"></p>
    </div>

    <div class="card">
        <h3>My Projects</h3>
        <div id="projectsList">Loading projects...</div>
    </div>
</div>

<script>
async function fetchStatus() {
    try {
        let res = await fetch('/api/status');
        let data = await res.json();
        document.getElementById('cpu').innerText = data.cpu;
        document.getElementById('ram').innerText = data.ram;
        document.getElementById('disk').innerText = data.disk;
        document.getElementById('running').innerText = data.running;
        document.getElementById('stopped').innerText = data.stopped;
        document.getElementById('failed').innerText = data.failed;

        let listHtml = '';
        if (data.projects.length === 0) {
            listHtml = '<p style="color: #94a3b8;">No projects deployed yet.</p>';
        } else {
            data.projects.forEach(p => {
                listHtml += `
                    <div class="project-card">
                        <div><strong>🤖 ${p.name}</strong> (${p.type}) - Status: <strong>${p.status}</strong></div>
                        ${p.error ? `<div style="color: #f87171; font-size: 0.85rem;">Error: ${p.error}</div>` : ''}
                        <div class="project-actions">
                            <button class="btn" onclick="projAction('${p.id}', 'start')">▶ Start</button>
                            <button class="btn" onclick="projAction('${p.id}', 'stop')">⏹ Stop</button>
                            <button class="btn" onclick="projAction('${p.id}', 'restart')">🔄 Restart</button>
                            <button class="btn btn-danger" onclick="projAction('${p.id}', 'delete')">🗑 Delete</button>
                        </div>
                    </div>
                `;
            });
        }
        document.getElementById('projectsList').innerHTML = listHtml;
    } catch (e) {
        console.error(e);
    }
}

async function uploadFile() {
    let input = document.getElementById('fileInput');
    if (input.files.length === 0) return;
    let file = input.files[0];
    let formData = new FormData();
    formData.append('file', file);

    document.getElementById('uploadStatus').innerText = `Uploading ${file.name}...`;
    let res = await fetch('/api/upload', { method: 'POST', body: formData });
    let result = await res.json();
    if (res.ok) {
        document.getElementById('uploadStatus').innerText = `✅ Uploaded successfully! ID: ${result.project_id}`;
        fetchStatus();
    } else {
        document.getElementById('uploadStatus').innerText = `❌ Error: ${result.detail}`;
    }
}

async function projAction(pid, action) {
    await fetch(`/api/project/${pid}/${action}`, { method: 'POST' });
    fetchStatus();
}

setInterval(fetchStatus, 3000);
fetchStatus();
</script>
</body>
</html>
"""

telegram_app = None

@app.on_event("startup")
async def startup_event():
    global telegram_app
    if not BOT_TOKEN:
        logger.error("❌ CRITICAL ERROR: BOT_TOKEN environment variable is missing!")
        return

    try:
        telegram_app = Application.builder().token(BOT_TOKEN).build()
        telegram_app.add_handler(CommandHandler("start", tg_start))
        telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tg_message_handler))
        telegram_app.add_handler(MessageHandler(filters.Document.ALL, tg_document_handler))
        telegram_app.add_handler(CallbackQueryHandler(tg_callback_handler))

        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling(drop_pending_updates=True)
        logger.info("🚀 Telegram Bot started successfully via FastAPI Startup event.")
    except Exception as e:
        logger.error(f"⚠️ Telegram Bot failed to start: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    global telegram_app
    if telegram_app:
        try:
            await telegram_app.updater.stop()
            await telegram_app.stop()
            await telegram_app.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    if not BOT_TOKEN:
        logger.error("❌ CRITICAL ERROR: BOT_TOKEN environment variable is missing!")
        sys.exit(1)

    logger.info(f"🌐 Starting FastAPI Web Dashboard on http://{HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
