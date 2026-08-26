import os
import sys
import json
import asyncio
import hashlib
import shutil
import re
import zipfile
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8905282088:AAF5Py6J4vl_k4Jp7q6QAr2Qh-NqxLZM6aA"
ADMIN_ID = "8905282088"
DATA_FILE = "users.json"

# ==================== DATABASE ====================
def load_db():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_db(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

def register_user(user):
    data = load_db()
    uid = str(user.id)
    if uid not in data:
        data[uid] = {
            "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
            "username": f"@{user.username}" if user.username else "no_username",
            "dumps": 0
        }
        save_db(data)
    return data

# ==================== RUNNER SCRIPT TEMPLATE ====================
RUNNER_CODE = """
import sys, os, builtins, hashlib, traceback, types, re, datetime, threading, io

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception: pass

DUMP_DIR = sys.argv[2]
TARGET_FILE = sys.argv[1]
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

_real_exec    = builtins.exec
_real_eval    = builtins.eval
_real_compile = builtins.compile
_real_makedirs = os.makedirs

def _mock_makedirs(name, mode=0o777, exist_ok=False):
    if "/storage/emulated/0" in name:
        name = name.replace("/storage/emulated/0", os.getcwd())
    return _real_makedirs(name, mode, exist_ok)
os.makedirs = _mock_makedirs
os.makedirs(DUMP_DIR, exist_ok=True)

class _HookedDatetime(datetime.datetime):
    @classmethod
    def now(cls, tz=None): return datetime.datetime(2024, 1, 1)
    @classmethod
    def utcnow(cls): return datetime.datetime(2024, 1, 1)
datetime.datetime = _HookedDatetime

_layer_count      = 0
_final_code       = None
_captured_hashes  = set()
_inside_hook      = False
_last_compile_src = None
_stop_requested   = False
_TARGET_SIZE      = os.path.getsize(TARGET_FILE)

class StopDecoding(Exception): pass

sys.gettrace   = lambda: None
sys.getprofile = lambda: None
_real_settrace   = sys.settrace
_real_setprofile = sys.setprofile
sys.settrace   = lambda *a, **k: None
sys.setprofile = lambda *a, **k: None

try:
    import gc as _gc
    _real_gc_get = _gc.get_objects
    def _safe_gc_get():
        _bad = ('Tracer','Debugger','Coverage','Profile','BdbQuit','Pdb')
        return [o for o in _real_gc_get() if type(o).__name__ not in _bad]
    _gc.get_objects = _safe_gc_get
except: pass

for _evar in ['PYTHONDEBUG','PYTHONINSPECT','PYTHONTRACEMALLOC','PYTHONBREAKPOINT',
               'PYDEVD_USE_FRAME_EVAL','PYCHARM_HOSTED','_PYCHARM_HOSTED']:
    os.environ.pop(_evar, None)
os.environ['TERM'] = 'dumb'

_real_open = builtins.open
def _hooked_open(file, mode='r', *args, **kwargs):
    try:
        file_str = str(file)
        if TARGET_FILE in file_str and 'r' in str(mode):
            fh = _real_open(file, mode, *args, **kwargs)
            return fh
    except: pass
    return _real_open(file, mode, *args, **kwargs)
builtins.open = _hooked_open

builtins.input = lambda *a, **k: ""

import time as _time
_real_time = _time.time
_time.time = lambda: _real_time()

try:
    import socket as _socket
    _real_getaddrinfo = _socket.getaddrinfo
    def _mocked_getaddrinfo(host, port, *a, **k):
        blocked = ['worldtimeapi.org','api.ipify.org','checkip.amazonaws.com','ipinfo.io']
        if any(b in str(host) for b in blocked):
            return [(_socket.AF_INET, _socket.SOCK_STREAM, 0, '', ('127.0.0.1', port or 80))]
        return _real_getaddrinfo(host, port, *a, **k)
    _socket.getaddrinfo = _mocked_getaddrinfo
except: pass

import threading as _threading
_real_enumerate = _threading.enumerate
def _safe_enumerate():
    _bad_names = ('pydevd','debugger','tracer','profiler')
    return [t for t in _real_enumerate() if not any(b in t.name.lower() for b in _bad_names)]
_threading.enumerate = _safe_enumerate

import platform as _platform
_platform.node = lambda: 'DESKTOP-USER'

_real_getframe = sys._getframe
def _safe_getframe(depth=0):
    f = _real_getframe(depth + 1)
    return f
sys._getframe = _safe_getframe

print("[BYPASS] Universal bypass suite installed.", flush=True)

def _is_noise(code_str):
    if not code_str: return True
    noise_markers = [
        "/python3.", "/lib/python", "<frozen importlib", "__create_fn__",
        "__dataclass_type__", "__dataclass_HAS_DEFAULT_FACTORY__",
        "__dataclasses_recursive_repr", "_dflt_repr", "_type_repr",
        "Base16, Base32, Base64", "RFC 3548", "Generalized interface for other encodings",
        "already_repring", "_compat.repr_context", "_cached_setattr_get",
        "attr_dict[", "_tuple_new(_cls"
    ]
    lower = code_str[:5000].lower()
    if any(marker.lower() in lower for marker in noise_markers): return True
    if "def __init__(self," in code_str and "return (__init__," in code_str: return True
    dunder_count = code_str.count("def __")
    if dunder_count >= 3 and len(code_str) < 5000 and "import " not in code_str: return True
    return False

def _should_auto_stop(code_str):
    if len(code_str) < 2000: return False
    if _TARGET_SIZE > 0 and len(code_str) >= _TARGET_SIZE * 0.8: return False
    clean_markers = ["import ", "def ", "class ", "print(", "if __name__", "from "]
    obf_markers   = [
        "exec(", "eval(", "marshal.loads", "base64.b64decode",
        "getattr(builtins", "zlib.decompress",
        "__import__(",
        "os._exit",
        ".b64decode(",
        "bytes(["
    ]
    clean_count = sum(1 for m in clean_markers if m in code_str)
    obf_count   = sum(1 for m in obf_markers   if m in code_str)
    has_main = "if __name__ == '__main__':" in code_str or 'if __name__ == "__main__":' in code_str
    # Strong: has main block + clean markers + no obfuscation
    if has_main and clean_count >= 2 and obf_count == 0: return True
    # Good: enough clean markers without obfuscation (even without main)
    if clean_count >= 3 and obf_count == 0: return True
    # Moderate: has functions/classes + documentation + no obfuscation
    func_count = len(re.findall(r'^def \\w+\\(', code_str, re.MULTILINE))
    class_count = len(re.findall(r'^class \\w+', code_str, re.MULTILINE))
    has_docstrings = '\\"\\"\\"' in code_str or "'''" in code_str
    if (func_count >= 3 or class_count >= 1) and has_docstrings and obf_count == 0: return True
    return False

def _save_layer(code_str, layer_num, source_label="exec"):
    global _captured_hashes, _final_code, _stop_requested
    if _is_noise(code_str): return

    size_kb = len(code_str) / 1024
    if 1.0 <= size_kb <= 3.0: return

    if _final_code and len(_final_code) > 10240 and len(code_str) < 5120: return

    if len(code_str.strip()) < 800: return

    code_hash = hashlib.md5(code_str.encode('utf-8', errors='replace')).hexdigest()
    if code_hash in _captured_hashes: return
    _captured_hashes.add(code_hash)

    dump_path = os.path.join(DUMP_DIR, f"layer_{layer_num}.py")
    with open(dump_path, "w", encoding="utf-8", errors="replace") as f:
        f.write(code_str)

    with open(os.path.join(DUMP_DIR, "final_decoded.py"), "w", encoding="utf-8", errors="replace") as f:
        f.write(code_str)

    _final_code = code_str

    if _should_auto_stop(code_str):
        raise StopDecoding("Final layer found")

def _get_real_globals_locals(globals_, locals_):
    if globals_ is not None: return globals_, locals_
    try:
        frame = sys._getframe(1)
        while frame:
            co_file = frame.f_code.co_filename or ""
            if SCRIPT_DIR not in co_file:
                return frame.f_globals, frame.f_locals
            frame = frame.f_back
    except Exception: pass
    return globals_, locals_

def _hooked_exec(code, globals_=None, locals_=None):
    global _layer_count, _inside_hook, _last_compile_src, _stop_requested
    if _stop_requested: raise StopDecoding("Stop requested")
    if _inside_hook: return _real_exec(code, globals_, locals_)
    real_g, real_l = _get_real_globals_locals(globals_, locals_)
    code_str = None
    try:
        if isinstance(code, str): code_str = code
        elif isinstance(code, bytes):
            try: code_str = code.decode("utf-8")
            except: code_str = code.decode("latin-1")
        elif isinstance(code, types.CodeType):
            if _last_compile_src and len(_last_compile_src) > 30:
                code_str = _last_compile_src
                _last_compile_src = None
        if code_str and len(code_str.strip()) > 30 and not _is_noise(code_str):
            _layer_count += 1
            _inside_hook = True
            try:
                before = _final_code
                _save_layer(code_str, _layer_count, "exec")
                if _final_code != before:
                    print(f"[LAYER {_layer_count}] exec: {len(code_str)} bytes", flush=True)
            finally: _inside_hook = False
        else:
            if code_str:
                reason = "noise" if _is_noise(code_str) else f"too small ({len(code_str)}b)" if len(code_str.strip()) <= 30 else "size filter"
                print(f"[SKIP] {len(code_str)} bytes — {reason}", flush=True)
    except StopDecoding: raise
    except Exception as e: print(f"[HOOK-ERR] {e}", flush=True)
    return _real_exec(code, real_g, real_l)

def _hooked_eval(code, *args, **kwargs):
    global _inside_hook, _layer_count
    if _inside_hook: return _real_eval(code, *args, **kwargs)
    _inside_hook = True
    try:
        code_str = code if isinstance(code, str) else None
        if code_str and len(code_str.strip()) > 200:
            _layer_count += 1
            _save_layer(code_str, _layer_count, "eval")
            print(f"[LAYER {_layer_count}] eval: {len(code_str)} bytes", flush=True)
    except StopDecoding: raise
    except: pass
    finally: _inside_hook = False
    return _real_eval(code, *args, **kwargs)

def _hooked_compile(source, filename, mode, flags=0, dont_inherit=False, optimize=-1):
    global _last_compile_src, _inside_hook
    if _inside_hook: return _real_compile(source, filename, mode, flags, dont_inherit, optimize)
    _inside_hook = True
    try:
        src_str = source if isinstance(source, str) else source.decode("utf-8", errors="replace") if isinstance(source, bytes) else repr(source)
        if src_str and len(src_str.strip()) > 30: _last_compile_src = src_str
    except: pass
    finally: _inside_hook = False
    return _real_compile(source, filename, mode, flags, dont_inherit, optimize)

def _hooked_exit(*args, **kwargs): pass

builtins.exec    = _hooked_exec
builtins.eval    = _hooked_eval
builtins.compile = _hooked_compile
builtins.exit    = _hooked_exit
sys.exit         = _hooked_exit
if isinstance(__builtins__, dict):
    __builtins__['exec'] = _hooked_exec; __builtins__['eval'] = _hooked_eval
    __builtins__['compile'] = _hooked_compile; __builtins__['exit'] = _hooked_exit
elif hasattr(__builtins__, '__dict__'):
    __builtins__.__dict__['exec'] = _hooked_exec; __builtins__.__dict__['eval'] = _hooked_eval
    __builtins__.__dict__['compile'] = _hooked_compile; __builtins__.__dict__['exit'] = _hooked_exit

os._exit = lambda *a, **k: None
try: os.abort = lambda: None
except: pass

sys.argv = [TARGET_FILE]
sys.path.insert(0, os.path.dirname(os.path.abspath(TARGET_FILE)))

print(f"[START] Target: {TARGET_FILE} ({os.path.getsize(TARGET_FILE)} bytes)", flush=True)

def _force_stop_timeout():
    global _stop_requested
    _stop_requested = True
    print("[TIMEOUT] 30s reached — force stop.", flush=True)

_timer = threading.Timer(30.0, _force_stop_timeout)
_timer.daemon = True
_timer.start()

try:
    with open(TARGET_FILE, "r", encoding="utf-8", errors="ignore") as f:
        code = f.read()
    ns = {"__name__": "__main__", "__builtins__": __builtins__, "__file__": TARGET_FILE}
    _real_exec(code, ns)
except StopDecoding:
    print("[STOP] StopDecoding raised — final layer saved.", flush=True)
except Exception as e:
    print(f"[CRASH] {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
finally:
    _timer.cancel()
    print(f"[DONE] Total layers captured: {_layer_count}", flush=True)
    import os as _os
    final = _os.path.join(DUMP_DIR, 'final_decoded.py')
    if _os.path.exists(final):
        print(f"[FINAL] final_decoded.py = {_os.path.getsize(final)} bytes", flush=True)
    else:
        print("[FINAL] No final_decoded.py written!", flush=True)
"""

# ==================== LOCAL HEURISTIC ====================
def local_pick_best(dump_dir):
    """
    Pick best file from dumps using a multi-signal scoring system:
    1. Has 'import' statements at top
    2. Has 'if __name__ == "__main__":' at end (bonus, not required)
    3. Has function/class definitions
    4. Has docstrings/comments
    5. Penalize obfuscation signals and huge lines
    Returns (filename, content) or (None, None)
    """
    candidates = []
    for fname in os.listdir(dump_dir):
        fpath = os.path.join(dump_dir, fname)
        if not os.path.isfile(fpath): continue
        if not fname.endswith(".py"): continue
        if os.path.getsize(fpath) < 800: continue

        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        lines = content.splitlines()
        score = 0

        # --- Check 1: imports at top (first 30 lines) ---
        top_lines = lines[:30]
        import_count = sum(
            1 for l in top_lines
            if re.match(r'^\s*(import |from \w)', l)
        )
        score += import_count * 10

        # --- Check 2: if __name__ at bottom (bonus, not required) ---
        bottom_lines = "\n".join(lines[-40:])
        has_main = (
            'if __name__ == "__main__":' in bottom_lines or
            "if __name__ == '__main__':" in bottom_lines
        )
        if has_main:
            score += 50

        # --- Check 3: function definitions ---
        func_count = sum(1 for l in lines if re.match(r'^def \w+\(', l))
        score += min(func_count, 10) * 5  # cap at 10 funcs for scoring

        # --- Check 4: class definitions ---
        class_count = sum(1 for l in lines if re.match(r'^class \w+', l))
        score += class_count * 15

        # --- Check 5: docstrings/comments (sign of real code) ---
        docstring_count = content.count('"""') // 2 + content.count("'''") // 2
        comment_lines = sum(1 for l in lines if re.match(r'^\s*#', l))
        score += min(docstring_count, 5) * 5
        score += min(comment_lines, 10) * 2

        # --- Check 6: penalize obfuscation signals ---
        obf_signals = [
            "__import__(", ".b64decode(", "bytes([",
            "zlib.decompress", "marshal.loads",
            "getattr(builtins", "os._exit"
        ]
        obf_count = sum(1 for s in obf_signals if s in content)
        score -= obf_count * 20

        # --- Check 7: penalize huge single lines (base64 blobs) ---
        max_line_len = max((len(l) for l in lines), default=0)
        if max_line_len > 5000:
            score -= 40

        candidates.append((fname, score, content))
        print(f"[SCORE] {fname}: score={score}, imports={import_count}, main={has_main}, "
              f"funcs={func_count}, classes={class_count}, obf={obf_count}")

    if not candidates:
        return None, None

    candidates.sort(key=lambda x: x[1], reverse=True)
    best_fname, best_score, best_content = candidates[0]

    print(f"[BEST] {best_fname} with score {best_score}")
    return best_fname, best_content

def is_real_code_local(content):
    """
    Final validation — checks if code looks like real human-readable Python.
    Returns True if looks like real decoded code.

    Does NOT require if __name__ == '__main__': — many real scripts don't have it.
    Uses multiple signals: imports, functions, classes, docstrings, comments,
    readable structure, and absence of obfuscation markers.
    """
    lines = content.splitlines()

    # --- Imports in top 30 lines ---
    top_lines = lines[:30]
    import_count = sum(
        1 for l in top_lines
        if re.match(r'^\s*(import |from \w)', l)
    )

    # --- if __name__ block (optional bonus, not required) ---
    bottom_lines = "\n".join(lines[-40:])
    has_main = (
        'if __name__ == "__main__":' in bottom_lines or
        "if __name__ == '__main__':" in bottom_lines
    )

    # --- Function definitions ---
    func_count = sum(1 for l in lines if re.match(r'^def \w+\(', l))

    # --- Class definitions ---
    class_count = sum(1 for l in lines if re.match(r'^class \w+', l))

    # --- Docstrings (triple-quote blocks) ---
    docstring_count = content.count('"""') // 2 + content.count("'''") // 2

    # --- Comments (# lines) ---
    comment_lines = sum(1 for l in lines if re.match(r'^\s*#', l))

    # --- Obfuscation signals ---
    obf_signals = [
        "__import__(", ".b64decode(", "bytes([",
        "zlib.decompress", "marshal.loads",
        "getattr(builtins", "os._exit"
    ]
    obf_count = sum(1 for s in obf_signals if s in content)

    # --- Long lines (base64 blobs) ---
    max_line_len = max((len(l) for l in lines), default=0)

    # --- Meaningful code indicators ---
    has_meaningful_defs = func_count >= 2 or class_count >= 1
    has_documentation = docstring_count >= 1 or comment_lines >= 3
    has_readable_structure = has_meaningful_defs and has_documentation

    print(f"[VALIDATE] imports={import_count}, main={has_main}, funcs={func_count}, "
          f"classes={class_count}, docstrings={docstring_count}, comments={comment_lines}, "
          f"obf={obf_count}, max_line={max_line_len}")

    # --- Hard rejection: clearly obfuscated ---
    if obf_count >= 2: return False
    if max_line_len > 5000: return False

    # --- Strong pass: has main block + imports ---
    if import_count >= 1 and has_main: return True

    # --- Strong pass: many imports (even without main) ---
    if import_count >= 3: return True

    # --- Good pass: has functions/classes + documentation + no obfuscation ---
    if has_readable_structure and obf_count == 0:
        return True

    # --- Moderate pass: has some imports + some functions, no obfuscation ---
    if import_count >= 1 and func_count >= 1 and obf_count == 0 and max_line_len <= 2000:
        return True

    # --- Pass: has classes or many functions with documentation ---
    if (class_count >= 1 or func_count >= 3) and has_documentation and obf_count == 0:
        return True

    return False

# ==================== ACTIVE USERS TRACKING ====================
processing_users = set()  # Users currently being processed

# ==================== ANIMATION ====================
async def animate_message(msg):
    texts = [
        "⚙️ <i>Bypassing obfuscation layers.</i>",
        "⚙️ <i>Bypassing obfuscation layers..</i>",
        "⚙️ <i>Bypassing obfuscation layers...</i>",
        "🔓 <i>Extracting hidden source code.</i>",
        "🔓 <i>Extracting hidden source code..</i>",
        "🔓 <i>Extracting hidden source code...</i>",
        "🧠 <i>Analyzing decoded layers.</i>",
        "🧠 <i>Analyzing decoded layers..</i>",
        "🧠 <i>Analyzing decoded layers...</i>"
    ]
    i = 0
    try:
        while True:
            try:
                await msg.edit_text(texts[i % len(texts)], parse_mode="HTML")
            except:
                pass
            i += 1
            await asyncio.sleep(0.6)
    except asyncio.CancelledError:
        pass

# ==================== ADMIN PANEL ====================
def get_admin_page(page, db):
    users = list(db.values())
    users.sort(key=lambda x: x.get('dumps', 0), reverse=True)

    chunks = [users[i:i+10] for i in range(0, len(users), 10)]
    if not chunks:
        return "<i>No users found.</i>", None

    if page >= len(chunks): page = len(chunks) - 1
    if page < 0: page = 0

    text = f"🛠 <b>Admin Panel - Leaderboard (Page {page+1}/{len(chunks)})</b>\n\n"
    for u in chunks[page]:
        name = u.get("username")
        if name == "no_username" or not name:
            name = u.get("name", "Unknown")
        text += f"👤 {name} - <b>{u.get('dumps', 0)} decodes</b>\n"

    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_page_{page-1}"))
    if page < len(chunks) - 1:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_page_{page+1}"))

    markup = InlineKeyboardMarkup([buttons]) if buttons else None
    return text, markup

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("Not authorized!", show_alert=True)
        return

    await query.answer()
    data = query.data

    if data.startswith("admin_page_"):
        page = int(data.split("_")[2])
        db = load_db()
        text, markup = get_admin_page(page, db)
        await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")

# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("🚀 Decode File"), KeyboardButton("📊 Stats")],
        [KeyboardButton("🛠 Admin Panel"), KeyboardButton("📢 Broadcast")]
    ], resize_keyboard=True)

    welcome_text = (
        "👋 <b>Welcome to Python Decoder Bot!</b>\n\n"
        "<i>Click '🚀 Decode File' to start decoding obfuscated Python scripts.</i>\n\n"
        "📦 <b>You will receive:</b>\n"
        "• <i>Best decoded file (auto-detected)</i>\n"
        "• <i>ZIP of all captured layers</i>\n"
        "• <i>Raw error/log output</i>"
    )
    await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode="HTML")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    register_user(update.effective_user)
    db = load_db()

    if text == "🚀 Decode File":
        context.user_data["waiting_for_file"] = True
        await update.message.reply_text("📁 <i>Please send the .py file you want to decode.</i>", parse_mode="HTML")

    elif text == "📊 Stats":
        uid = str(user_id)
        user_dumps = db.get(uid, {}).get("dumps", 0)
        total_dumps = sum(u.get("dumps", 0) for u in db.values())
        total_users = len(db)

        stats_text = (
            "📊 <b>Bot Statistics</b>\n\n"
            f"👤 <i>Your Total Decodes:</i> <b>{user_dumps}</b>\n\n"
            f"🌍 <i>Global Total Decodes:</i> <b>{total_dumps}</b>\n"
            f"👥 <i>Total Users:</i> <b>{total_users}</b>"
        )
        await update.message.reply_text(stats_text, parse_mode="HTML")

    elif text == "🛠 Admin Panel":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ <i>You are not authorized!</i>", parse_mode="HTML")
            return

        text_msg, markup = get_admin_page(0, db)
        await update.message.reply_text(text_msg, reply_markup=markup, parse_mode="HTML")

    elif text == "📢 Broadcast":
        if user_id != ADMIN_ID:
            await update.message.reply_text("❌ <i>You are not authorized!</i>", parse_mode="HTML")
            return

        context.user_data["waiting_for_broadcast"] = True
        await update.message.reply_text(
            "📢 <b>Broadcast Message</b>\n\n"
            "<i>Send or forward the message you want to broadcast to all users.\n"
            "The message will be copied (without forward origin tag) to everyone.</i>\n\n"
            "⚠️ <i>Send /cancel to abort.</i>",
            parse_mode="HTML"
        )

    elif context.user_data.get("waiting_for_broadcast"):
        if user_id != ADMIN_ID:
            context.user_data["waiting_for_broadcast"] = False
            return

        context.user_data["waiting_for_broadcast"] = False
        users = list(load_db().keys())
        total = len(users)
        success = 0
        failed = 0

        progress_msg = await update.message.reply_text(
            f"📤 <i>Broadcasting to {total} users...</i>",
            parse_mode="HTML"
        )

        for uid in users:
            try:
                await context.bot.copy_message(
                    chat_id=int(uid),
                    from_chat_id=update.message.chat_id,
                    message_id=update.message.message_id
                )
                success += 1
            except Exception as e:
                failed += 1
                print(f"[BROADCAST] Failed for {uid}: {e}")

        await progress_msg.edit_text(
            f"✅ <b>Broadcast Complete!</b>\n\n"
            f"📨 <i>Sent:</i> <b>{success}</b>\n"
            f"❌ <i>Failed:</i> <b>{failed}</b>\n"
            f"👥 <i>Total:</i> <b>{total}</b>",
            parse_mode="HTML"
        )

async def _send_document_with_retry(update, file_path, filename, caption, retries=3, read_timeout=120, write_timeout=120, connect_timeout=30):
    """Send a document with retries and increased timeouts to handle large files."""
    last_err = None
    for attempt in range(retries):
        try:
            with open(file_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=filename,
                    caption=caption,
                    parse_mode="HTML",
                    read_timeout=read_timeout,
                    write_timeout=write_timeout,
                    connect_timeout=connect_timeout,
                )
            return True
        except Exception as e:
            last_err = e
            print(f"[SEND] Attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(3)
    print(f"[SEND] All {retries} attempts failed: {last_err}")
    return False

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    user_id = update.effective_user.id

    if not context.user_data.get("waiting_for_file"):
        await update.message.reply_text(
            "⚠️ <b>Action Required!</b>\n\n"
            "<i>Please click the '🚀 Decode File' button first before sending your file.</i>",
            parse_mode="HTML"
        )
        return

    context.user_data["waiting_for_file"] = False

    # Reject if user already has a file being processed
    if user_id in processing_users:
        await update.message.reply_text(
            "⏳ <b>Already Processing!</b>\n\n"
            "<i>Your previous file is still being decoded. Please wait for it to finish.</i>",
            parse_mode="HTML"
        )
        return

    processing_users.add(user_id)
    work_dir = None
    msg = None

    try:
        doc = update.message.document
        if not doc.file_name.endswith(".py"):
            await update.message.reply_text("❌ <i>Please send a valid Python (.py) file.</i>", parse_mode="HTML")
            return

        msg = await update.message.reply_text("⏳ <i>Initializing secure environment...</i>", parse_mode="HTML")

        file_id = doc.file_id
        new_file = await context.bot.get_file(file_id)

        task_id = update.message.message_id
        work_dir = f"task_{user_id}_{task_id}"
        os.makedirs(work_dir, exist_ok=True)

        original_name = doc.file_name
        target_path = os.path.join(work_dir, original_name)
        await new_file.download_to_drive(target_path)

        # @Py0bfuscatorBot restriction — admin bypass
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            top_lines = "".join(f.readline() for _ in range(50))
        if "Obfuscated By @Py0bfuscatorBot" in top_lines and user_id != ADMIN_ID:
            await msg.edit_text(
                "🚫 <b>Restricted File</b>\n\n"
                "<i>This file was obfuscated by <b>@Py0bfuscatorBot</b> and cannot be decoded.</i>",
                parse_mode="HTML"
            )
            return

        await msg.edit_text("🔍 <i>Scanning file for protections...</i>", parse_mode="HTML")

        dump_dir = os.path.join(work_dir, "dumps")
        os.makedirs(dump_dir, exist_ok=True)

        runner_path = os.path.join(work_dir, "runner.py")
        with open(runner_path, "w", encoding="utf-8") as f:
            f.write(RUNNER_CODE)

        anim_task = asyncio.create_task(animate_message(msg))

        stdout_raw = ""
        stderr_raw = ""

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "runner.py", original_name, "dumps",
                cwd=work_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_data, stderr_data = await asyncio.wait_for(proc.communicate(), timeout=35)
            stdout_raw = stdout_data.decode("utf-8", errors="replace")
            stderr_raw = stderr_data.decode("utf-8", errors="replace")

            if stdout_raw:
                print(f"\n===== RUNNER LOG [{original_name}] =====")
                print(stdout_raw)
                print("=" * 45)
            if stderr_raw:
                print(f"[RUNNER STDERR]\n{stderr_raw[:1000]}")

        except asyncio.TimeoutError:
            try: proc.kill()
            except: pass
            stdout_raw += "\n[BOT] Subprocess force-killed after 35s timeout."
            print(f"[BOT] Timeout for {original_name}")

        anim_task.cancel()
        try:
            await anim_task
        except asyncio.CancelledError:
            pass
        await msg.edit_text("📦 <i>Packaging all layers...</i>", parse_mode="HTML")

        # ---- Collect all dump files ----
        dump_files_list = []
        for fname in sorted(os.listdir(dump_dir)):
            fpath = os.path.join(dump_dir, fname)
            if os.path.isfile(fpath) and fname.endswith(".py"):
                dump_files_list.append(fname)

        # ---- Pick best file using local heuristic ----
        best_fname, best_content = local_pick_best(dump_dir)

        # ---- Build ZIP of ALL dumps ----
        zip_path = os.path.join(work_dir, f"AllLayers_{original_name.replace('.py','')}.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in dump_files_list:
                fpath = os.path.join(dump_dir, fname)
                zf.write(fpath, arcname=fname)

        # ---- Send raw log first ----
        log_combined = ""
        if stdout_raw:
            log_combined += "=== STDOUT ===\n" + stdout_raw
        if stderr_raw:
            log_combined += "\n=== STDERR ===\n" + stderr_raw

        if log_combined:
            if len(log_combined) > 3500:
                log_path = os.path.join(work_dir, "runner_log.txt")
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(log_combined)
                await _send_document_with_retry(
                    update, log_path, "runner_log.txt",
                    "📋 <b>Raw Runner Log</b>"
                )
            else:
                await update.message.reply_text(
                    f"📋 <b>Raw Runner Log:</b>\n<pre>{log_combined[:3500]}</pre>",
                    parse_mode="HTML"
                )

        # ---- Send ZIP of all layers ----
        if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
            zip_sent = await _send_document_with_retry(
                update, zip_path, os.path.basename(zip_path),
                f"📦 <b>All Captured Layers</b>\n<i>Total files: {len(dump_files_list)}</i>"
            )
            if not zip_sent:
                await update.message.reply_text(
                    "⚠️ <i>ZIP upload failed after retries. Try again or check server connection.</i>",
                    parse_mode="HTML"
                )
        else:
            await update.message.reply_text("⚠️ <i>No dump layers were captured.</i>", parse_mode="HTML")

        # ---- Send best decoded file ----
        if best_fname and best_content:
            is_real = is_real_code_local(best_content)
            final_path = os.path.join(dump_dir, best_fname)
            decoded_name = f"Decoded_{original_name}"

            if is_real:
                caption = (
                    "✅ <b>Best Decoded File</b>\n\n"
                    f"📄 <i>Selected: <b>{best_fname}</b></i>\n"
                    "<i>Detected as: Real human-readable code</i>"
                )
            else:
                caption = (
                    "⚠️ <b>Best Layer (May Still Be Obfuscated)</b>\n\n"
                    f"📄 <i>Selected: <b>{best_fname}</b></i>\n"
                    "<i>Could not fully confirm as real code.\n"
                    "Check the ZIP for other layers.</i>"
                )

            await _send_document_with_retry(
                update, final_path, decoded_name, caption
            )
        else:
            await update.message.reply_text(
                "❌ <i>No valid decoded file found in dumps.\n"
                "Check the ZIP for raw layers.</i>",
                parse_mode="HTML"
            )

        if msg:
            await msg.delete()

        # Update stats
        db = load_db()
        uid = str(user_id)
        if uid in db:
            db[uid]["dumps"] = db[uid].get("dumps", 0) + 1
            save_db(db)

    except Exception as e:
        print(f"[ERROR] handle_document user {user_id}: {e}")
        try:
            await update.message.reply_text(
                f"❌ <b>Unexpected Error</b>\n\n<pre>{str(e)[:500]}</pre>",
                parse_mode="HTML"
            )
        except: pass

    finally:
        # Always remove user from processing & cleanup folder
        processing_users.discard(user_id)
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)

# ==================== CANCEL COMMAND ====================
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("waiting_for_broadcast", None)
    context.user_data.pop("waiting_for_file", None)
    await update.message.reply_text("❌ <i>Action cancelled.</i>", parse_mode="HTML")

# ==================== MAIN ====================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).read_timeout(120).write_timeout(120).connect_timeout(30).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.FileExtension("py"), handle_document))
    app.add_handler(CallbackQueryHandler(admin_callback))

    print("Bot is running...")
    app.run_polling()
