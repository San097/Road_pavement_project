from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import json
import os
import re
import secrets
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
import uuid
import smtplib
from email.mime.text import MIMEText

import cv2
import numpy as np
import pandas as pd

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "road_pavement_project", "ESC 12 Pavement Dataset.csv")
ENV_PATH = os.path.join(BASE_DIR, ".env")
DATA_DIR = BASE_DIR
UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
AUTH_STORE_PATH = os.path.join(DATA_DIR, "auth_store.json")
LEGACY_DATABASE_PATHS = []
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_ORIGINS", os.getenv("FRONTEND_ORIGIN", "")).split(",")
    if origin.strip()
]

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
PASSWORD_RESET_MINUTES = 30
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

PLACEHOLDER_ENV_PREFIXES = ("your-", "your_", "replace-", "replace_", "changeme")


def env_value_is_placeholder(value):
    normalized = (value or "").strip().strip('"').strip("'").lower()
    if not normalized:
        return True
    return normalized.startswith(PLACEHOLDER_ENV_PREFIXES)

def load_dotenv_file(path):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            current = os.environ.get(key)
            if key and (current is None or env_value_is_placeholder(current)):
                os.environ[key] = value


load_dotenv_file(ENV_PATH)


def refresh_storage_paths():
    global DATA_DIR, UPLOAD_FOLDER, AUTH_STORE_PATH, LEGACY_DATABASE_PATHS
    DATA_DIR = os.path.abspath(os.getenv("DATA_DIR", BASE_DIR))
    UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
    AUTH_STORE_PATH = os.path.join(DATA_DIR, "auth_store.json")
    LEGACY_DATABASE_PATHS = [
        os.path.join(DATA_DIR, "database.db"),
        os.path.join(BASE_DIR, "database.db"),
    ]


refresh_storage_paths()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "road_pavement_project", "templates"),
    static_folder=os.path.join(BASE_DIR, "road_pavement_project", "static"),
)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "road_project")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv(
    "SESSION_COOKIE_SAMESITE",
    "None" if FRONTEND_ORIGINS else "Lax",
)
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


@app.after_request
def add_frontend_cors_headers(response):
    origin = (request.headers.get("Origin") or "").rstrip("/")
    if origin and origin in FRONTEND_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Vary"] = "Origin"
    return response


try:
    predictions_df = pd.read_csv(CSV_PATH)
except Exception:
    predictions_df = None


def allowed_image_file(filename):
    if not filename or "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def load_image_from_bytes(image_bytes):
    image_array = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
    if image is None:
        return None

    height, width = image.shape[:2]
    max_side = max(height, width)
    if max_side > 1280:
        scale = 1280 / max_side
        image = cv2.resize(
            image,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    return image


def clamp(value, low, high):
    return max(low, min(high, value))


def analyze_uploaded_road_image(image):
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)

    saturation = hsv[:, :, 1]
    brightness = hsv[:, :, 2]
    lower_start = int(height * 0.35)

    road_mask = (
        (saturation < 95)
        & (brightness > 28)
        & (brightness < 220)
    )
    surface_mask = (saturation < 120) & (brightness < 235)
    lower_road_ratio = float(road_mask[lower_start:, :].mean()) if lower_start < height else float(road_mask.mean())
    overall_road_ratio = float(road_mask.mean())

    edges = cv2.Canny(gray, 60, 150)
    edge_density = float(edges.mean() / 255.0)
    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 17))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
    blackhat_strength = float(blackhat.mean() / 255.0)
    crack_ratio = float(((blackhat > 18) & surface_mask).mean())

    dark_ratio = float(((gray < 78) & surface_mask).mean())
    lower_dark_ratio = float(((gray[lower_start:, :] < 78) & surface_mask[lower_start:, :]).mean()) if lower_start < height else dark_ratio
    texture_score = float(gray.std() / 64.0)

    skin_mask = (
        (ycrcb[:, :, 1] >= 135)
        & (ycrcb[:, :, 1] <= 180)
        & (ycrcb[:, :, 2] >= 85)
        & (ycrcb[:, :, 2] <= 135)
        & (ycrcb[:, :, 0] > 70)
    )
    skin_ratio = float(skin_mask.mean())

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype("float32")
    rg = np.abs(rgb[:, :, 0] - rgb[:, :, 1])
    yb = np.abs(0.5 * (rgb[:, :, 0] + rgb[:, :, 1]) - rgb[:, :, 2])
    colorfulness = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))
    normalized_colorfulness = min(1.0, colorfulness / 120.0)

    road_scene_score = clamp(
        (lower_road_ratio * 60.0)
        + (overall_road_ratio * 25.0)
        + ((1.0 - normalized_colorfulness) * 10.0)
        + min(10.0, blur_score / 18.0),
        0.0,
        100.0,
    )
    distress_score = clamp(
        (crack_ratio * 1200.0)
        + (dark_ratio * 280.0)
        + (lower_dark_ratio * 320.0)
        + (edge_density * 180.0)
        + (blackhat_strength * 120.0)
        + (texture_score * 10.0),
        0.0,
        100.0,
    )

    return {
        "height": height,
        "width": width,
        "road_scene_score": round(road_scene_score, 2),
        "distress_score": round(distress_score, 2),
        "road_ratio": round(overall_road_ratio, 4),
        "lower_road_ratio": round(lower_road_ratio, 4),
        "edge_density": round(edge_density, 4),
        "crack_ratio": round(crack_ratio, 4),
        "dark_ratio": round(dark_ratio, 4),
        "lower_dark_ratio": round(lower_dark_ratio, 4),
        "blackhat_strength": round(blackhat_strength, 4),
        "texture_score": round(texture_score, 4),
        "blur_score": round(blur_score, 2),
        "skin_ratio": round(skin_ratio, 4),
        "colorfulness": round(colorfulness, 2),
        "normalized_colorfulness": round(normalized_colorfulness, 4),
    }


def validate_road_damage_image(metrics):
    if metrics["skin_ratio"] > 0.22 and metrics["lower_road_ratio"] < 0.22:
        return "Only broken road images are allowed. Selfies, faces, and people photos cannot be analyzed."
    if metrics["lower_road_ratio"] < 0.16 or metrics["road_scene_score"] < 22 or metrics["normalized_colorfulness"] > 0.72:
        return "Upload a clear road surface image only. Random photos, indoor scenes, and unrelated images are not supported."
    if metrics["blur_score"] < 35:
        return "The image is too blurry. Capture the broken road surface again with a steadier camera."
    if metrics["distress_score"] < 14 and metrics["crack_ratio"] < 0.01 and metrics["dark_ratio"] < 0.015:
        return "The image looks unrelated to broken pavement, or the damage is not visible enough. Upload a closer road crack or pothole image."
    return None


def find_closest_dataset_row(target_pci, target_iri, target_rutting):
    if predictions_df is None or predictions_df.empty:
        return None

    ranked = predictions_df.copy()
    ranked["match_score"] = (
        ((ranked["PCI"] - target_pci).abs() / 100.0)
        + ((ranked["IRI"] - target_iri).abs() / 6.0)
        + ((ranked["Rutting"] - target_rutting).abs() / 40.0)
    )
    return ranked.nsmallest(1, "match_score").iloc[0]


def build_prediction_from_image(metrics):
    distress_score = metrics["distress_score"]
    pci = clamp(
        98.0
        - (distress_score * 0.76)
        - (metrics["dark_ratio"] * 120.0)
        - (metrics["crack_ratio"] * 1200.0)
        + (metrics["road_scene_score"] * 0.03),
        12.0,
        96.0,
    )
    iri = clamp(
        0.6 + (distress_score / 28.0) + (metrics["edge_density"] * 5.5),
        0.5,
        5.8,
    )
    rutting = clamp(
        4.5 + (distress_score * 0.22) + (metrics["lower_dark_ratio"] * 80.0),
        3.0,
        35.0,
    )

    road_condition = get_road_condition_from_pci(pci)
    severity = get_crack_severity(iri, rutting)

    if severity == "Critical":
        maintenance = "Immediate Repair"
        priority = "Critical"
        window = "within 24 to 48 hours"
    elif severity == "High":
        maintenance = "Repair Required"
        priority = "High"
        window = "within 3 to 7 days"
    elif severity == "Medium":
        maintenance = "Preventive Repair"
        priority = "Medium"
        window = "during the next maintenance cycle"
    else:
        maintenance = "Routine Maintenance"
        priority = "Low"
        window = "through routine inspection scheduling"

    confidence = round(
        clamp(
            68.0
            + (metrics["road_scene_score"] * 0.16)
            + min(10.0, metrics["blur_score"] / 25.0)
            - (metrics["normalized_colorfulness"] * 7.0),
            72.0,
            98.5,
        ),
        2,
    )

    matched_row = find_closest_dataset_row(pci, iri, rutting)
    if matched_row is not None:
        segment_id = matched_row.get("Segment ID", "Estimated Segment")
        road_type = matched_row.get("Road Type", "Estimated Road")
    else:
        segment_id = "Estimated Segment"
        road_type = "Estimated Road"

    indicators = []
    if metrics["crack_ratio"] >= 0.015:
        indicators.append("visible crack patterns")
    if metrics["dark_ratio"] >= 0.03:
        indicators.append("dark pothole-like zones")
    if metrics["edge_density"] >= 0.055:
        indicators.append("rough surface texture")
    if not indicators:
        indicators.append("localized pavement distress")

    summary = (
        f"The uploaded image passed road-only validation and shows {', '.join(indicators)}. "
        f"Estimated pavement condition is {road_condition} with {severity.lower()} severity. "
        f"Recommended action is {maintenance.lower()} {window}."
    )

    repair_summary = "\n".join(
        [
            f"ROAD-ONLY CHECK: Passed ({metrics['road_scene_score']}/100)",
            f"DAMAGE SCORE: {metrics['distress_score']}/100",
            f"VISIBLE INDICATORS: {', '.join(indicators).upper()}",
            f"PCI ESTIMATE: {pci:.2f}",
            f"IRI ESTIMATE: {iri:.2f}",
            f"RUTTING ESTIMATE: {rutting:.2f} mm",
            f"RECOMMENDED ACTION: {maintenance.upper()}",
            f"REPAIR WINDOW: {window.upper()}",
            f"CONDITION: {road_condition.upper()}",
        ]
    )

    return {
        "condition": road_condition,
        "severity": severity,
        "maintenance": maintenance,
        "priority": priority,
        "confidence": confidence,
        "detail": repair_summary,
        "summary": summary,
        "segment_id": segment_id,
        "road_type": road_type,
        "damage_score": round(metrics["distress_score"], 2),
    }


def now_utc():
    return datetime.utcnow()


def fmt_dt(value):
    return value.strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(text):
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def normalize_email(email):
    return email.strip().lower()


def is_valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def password_is_strong(password):
    return bool(
        len(password) >= 8
        and re.search(r"[A-Z]", password)
        and re.search(r"[a-z]", password)
        and re.search(r"\d", password)
    )


def username_is_valid(username):
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", username))


def google_oauth_ready():
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    return (
        bool(client_id)
        and bool(client_secret)
        and not client_id.startswith("your-google-client-id")
        and not client_secret.startswith("your-google-client-secret")
    )


def default_auth_store():
    return {
        "users": [],
        "password_reset_tokens": [],
        "auth_logs": [],
        "meta": {"migrated_from_legacy_db": False},
    }


os.makedirs(DATA_DIR, exist_ok=True)

if not DATABASE_URL and not os.path.exists(AUTH_STORE_PATH):
    with open(AUTH_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(default_auth_store(), f)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

if not os.path.exists(CSV_PATH):
    print("Dataset not found - running in demo mode")


def auth_database_enabled():
    return DATABASE_URL.startswith(("postgresql://", "postgres://"))


def get_db_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")
    if psycopg2 is None:
        raise RuntimeError("psycopg2-binary is required when DATABASE_URL is configured.")
    return psycopg2.connect(DATABASE_URL)


def init_postgres_auth_store():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    email VARCHAR(150) UNIQUE,
                    password_hash TEXT,
                    email_verified INTEGER DEFAULT 0,
                    provider VARCHAR(50) DEFAULT 'local',
                    role VARCHAR(50) DEFAULT 'user',
                    failed_attempts INTEGER DEFAULT 0,
                    locked_until VARCHAR(32)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    token TEXT UNIQUE NOT NULL,
                    expires_at VARCHAR(32),
                    used BOOLEAN DEFAULT FALSE
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS auth_logs (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(150),
                    provider VARCHAR(50),
                    ip_address TEXT,
                    user_agent TEXT,
                    event_type VARCHAR(100),
                    event_status VARCHAR(100),
                    created_at VARCHAR(32)
                )
                """
            )
            conn.commit()


def fetch_postgres_store():
    init_postgres_auth_store()
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users ORDER BY id")
            users = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT * FROM password_reset_tokens ORDER BY id")
            tokens = [dict(row) for row in cur.fetchall()]
            cur.execute("SELECT * FROM auth_logs ORDER BY id DESC LIMIT 500")
            logs = [dict(row) for row in reversed(cur.fetchall())]

    for user in users:
        user["email_verified"] = int(user.get("email_verified") or 0)
        user["failed_attempts"] = int(user.get("failed_attempts") or 0)
    return {
        "users": users,
        "password_reset_tokens": tokens,
        "auth_logs": logs,
        "meta": {"database": "postgresql"},
    }


def save_postgres_store(store):
    init_postgres_auth_store()
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for user in store.get("users", []):
                cur.execute(
                    """
                    INSERT INTO users (
                        id, username, email, password_hash, email_verified,
                        provider, role, failed_attempts, locked_until
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        username = EXCLUDED.username,
                        email = EXCLUDED.email,
                        password_hash = EXCLUDED.password_hash,
                        email_verified = EXCLUDED.email_verified,
                        provider = EXCLUDED.provider,
                        role = EXCLUDED.role,
                        failed_attempts = EXCLUDED.failed_attempts,
                        locked_until = EXCLUDED.locked_until
                    """,
                    (
                        user.get("id"),
                        user.get("username"),
                        user.get("email") or None,
                        user.get("password_hash") or "",
                        int(user.get("email_verified") or 0),
                        user.get("provider") or "local",
                        user.get("role") or "user",
                        int(user.get("failed_attempts") or 0),
                        user.get("locked_until"),
                    ),
                )

            for token in store.get("password_reset_tokens", []):
                cur.execute(
                    """
                    INSERT INTO password_reset_tokens (id, user_id, token, expires_at, used)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        user_id = EXCLUDED.user_id,
                        token = EXCLUDED.token,
                        expires_at = EXCLUDED.expires_at,
                        used = EXCLUDED.used
                    """,
                    (
                        token.get("id"),
                        token.get("user_id"),
                        token.get("token"),
                        token.get("expires_at"),
                        bool(token.get("used")),
                    ),
                )

            cur.execute("DELETE FROM auth_logs")
            for log in store.get("auth_logs", [])[-500:]:
                cur.execute(
                    """
                    INSERT INTO auth_logs (
                        username, provider, ip_address, user_agent,
                        event_type, event_status, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        log.get("username"),
                        log.get("provider"),
                        log.get("ip_address"),
                        log.get("user_agent"),
                        log.get("event_type"),
                        log.get("event_status"),
                        log.get("created_at"),
                    ),
                )
            cur.execute("SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM users")
            cur.execute(
                "SELECT setval(pg_get_serial_sequence('password_reset_tokens', 'id'), COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM password_reset_tokens"
            )
            conn.commit()


def load_auth_store():
    if auth_database_enabled():
        return fetch_postgres_store()
    if not os.path.exists(AUTH_STORE_PATH):
        init_auth_store()
    with open(AUTH_STORE_PATH, "r", encoding="utf-8") as auth_file:
        data = json.load(auth_file)
    data.setdefault("users", [])
    data.setdefault("password_reset_tokens", [])
    data.setdefault("auth_logs", [])
    data.setdefault("meta", {})
    return data


def save_auth_store(store):
    if auth_database_enabled():
        save_postgres_store(store)
        return
    with open(AUTH_STORE_PATH, "w", encoding="utf-8") as auth_file:
        json.dump(store, auth_file, indent=2)


def next_id(items):
    return max((item.get("id", 0) for item in items), default=0) + 1


def make_unique_username(users, desired_username, exclude_user_id=None):
    base = re.sub(r"[^a-zA-Z0-9_.-]+", "_", desired_username.strip().lower()).strip("._-")
    if not base:
        base = "user"
    base = base[:24]
    candidate = base
    suffix = 1
    while True:
        exists = False
        for user in users:
            if exclude_user_id is not None and user.get("id") == exclude_user_id:
                continue
            if user.get("username", "").lower() == candidate.lower():
                exists = True
                break
        if not exists:
            return candidate
        suffix += 1
        suffix_text = str(suffix)
        candidate = f"{base[:max(1, 24 - len(suffix_text))]}{suffix_text}"


def read_legacy_users(db_path):
    if not os.path.exists(db_path):
        return []
    try:
        uri = f"file:{db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        if not cur.fetchone():
            conn.close()
            return []
        cur.execute("PRAGMA table_info(users)")
        cols = {row[1] for row in cur.fetchall()}
        select_cols = ["id", "username"]
        for col in ("email", "password_hash", "password", "email_verified", "provider", "role", "failed_attempts", "locked_until"):
            if col in cols:
                select_cols.append(col)
        cur.execute(f"SELECT {', '.join(select_cols)} FROM users")
        rows = cur.fetchall()
        conn.close()
    except sqlite3.Error:
        return []

    users = []
    for row in rows:
        username = (row["username"] or "").strip()
        email = normalize_email(row["email"] or "") if "email" in row.keys() and row["email"] else ""
        password_hash = row["password_hash"] if "password_hash" in row.keys() and row["password_hash"] else ""
        if not password_hash and "password" in row.keys() and row["password"]:
            password_hash = generate_password_hash(row["password"])
        if not username and not email:
            continue
        users.append(
            {
                "id": row["id"] if "id" in row.keys() and row["id"] is not None else len(users) + 1,
                "username": username or (email.split("@", 1)[0] if email else "user"),
                "email": email,
                "password_hash": password_hash,
                "email_verified": int(row["email_verified"]) if "email_verified" in row.keys() and row["email_verified"] is not None else (1 if email else 0),
                "provider": row["provider"] if "provider" in row.keys() and row["provider"] else "local",
                "role": row["role"] if "role" in row.keys() and row["role"] else "user",
                "failed_attempts": int(row["failed_attempts"]) if "failed_attempts" in row.keys() and row["failed_attempts"] is not None else 0,
                "locked_until": row["locked_until"] if "locked_until" in row.keys() else None,
            }
        )
    return users


def merge_legacy_users(store, legacy_users):
    for legacy_user in legacy_users:
        email = legacy_user.get("email", "")
        username = legacy_user.get("username", "")
        existing = None
        for user in store["users"]:
            if email and user.get("email", "").lower() == email.lower():
                existing = user
                break
            if username and user.get("username", "").lower() == username.lower():
                existing = user
                break
        if existing:
            if not existing.get("password_hash") and legacy_user.get("password_hash"):
                existing["password_hash"] = legacy_user["password_hash"]
            if not existing.get("email") and email:
                existing["email"] = email
            continue

        legacy_user["id"] = next_id(store["users"])
        legacy_user["username"] = make_unique_username(store["users"], legacy_user["username"] or email.split("@", 1)[0] or "user")
        store["users"].append(legacy_user)


def init_auth_store():
    if auth_database_enabled():
        init_postgres_auth_store()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users")
                has_users = cur.fetchone()[0] > 0
        if has_users:
            return

        store = default_auth_store()
        if os.path.exists(AUTH_STORE_PATH):
            with open(AUTH_STORE_PATH, "r", encoding="utf-8") as auth_file:
                try:
                    store = json.load(auth_file)
                except json.JSONDecodeError:
                    store = default_auth_store()
            store.setdefault("users", [])
            store.setdefault("password_reset_tokens", [])
            store.setdefault("auth_logs", [])
            store.setdefault("meta", {})
        for db_path in LEGACY_DATABASE_PATHS:
            merge_legacy_users(store, read_legacy_users(db_path))
        store["meta"]["migrated_to_postgres"] = True
        save_postgres_store(store)
        return

    if os.path.exists(AUTH_STORE_PATH):
        return
    store = default_auth_store()
    for db_path in LEGACY_DATABASE_PATHS:
        merge_legacy_users(store, read_legacy_users(db_path))
    store["meta"]["migrated_from_legacy_db"] = bool(store["users"])
    save_auth_store(store)


def render_login(error=None, info=None):
    return render_template(
        "login.html",
        error=error,
        info=info,
        google_enabled=google_oauth_ready(),
    )


def render_register(error=None, info=None):
    return render_template(
        "register.html",
        error=error,
        info=info,
        google_enabled=google_oauth_ready(),
    )


def render_forgot_password(error=None, info=None):
    return render_template(
        "forgot_password.html",
        error=error,
        info=info,
    )


def render_reset_password(token, error=None, info=None):
    return render_template(
        "reset_password.html",
        token=token,
        error=error,
        info=info,
        google_enabled=google_oauth_ready(),
    )


def email_smtp_configured():
    return bool(
        (os.getenv("EMAIL_HOST") or "").strip()
        and (os.getenv("EMAIL_USER") or "").strip()
        and (os.getenv("EMAIL_PASS") or "").strip()
    )


def email_env_looks_like_placeholder():
    user = (os.getenv("EMAIL_USER") or "").strip().lower()
    pwd = (os.getenv("EMAIL_PASS") or "").strip().lower()
    if not user or not pwd:
        return False
    bad_users = ("your_email@gmail.com", "your_email@example.com", "changeme@example.com")
    bad_pwds = ("your_app_password", "password", "changeme")
    if user in bad_users or pwd in bad_pwds:
        return True
    if "your_" in user or "your_" in pwd:
        return True
    return False


def send_reset_email(to_email, reset_url):
    try:
        smtp_server = (os.getenv("EMAIL_HOST") or "").strip()
        smtp_port = int(os.getenv("EMAIL_PORT", "587"))
        sender_email = (os.getenv("EMAIL_USER") or "").strip()
        sender_password = (os.getenv("EMAIL_PASS") or "").strip()
        timeout = int(os.getenv("EMAIL_TIMEOUT", "30"))

        use_ssl_env = (os.getenv("EMAIL_USE_SSL") or "").strip().lower()
        use_ssl = use_ssl_env in ("1", "true", "yes") or (
            smtp_port == 465 and use_ssl_env not in ("0", "false", "no")
        )

        subject = "Password Reset Request"
        body = f"""
Hello,

Click the link below to reset your password:

{reset_url}

This link will expire in 30 minutes.

If you did not request this, ignore this email.
"""

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email

        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=timeout)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=timeout)
            server.starttls()

        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()

        return True
    except Exception as e:
        print("Email error:", repr(e))
        return False


def log_auth_event(username, provider, event_type, event_status):
    store = load_auth_store()
    store["auth_logs"].append(
        {
            "id": next_id(store["auth_logs"]),
            "username": username,
            "provider": provider,
            "ip_address": request.remote_addr,
            "user_agent": request.headers.get("User-Agent", "unknown"),
            "event_type": event_type,
            "event_status": event_status,
            "created_at": fmt_dt(now_utc()),
        }
    )
    store["auth_logs"] = store["auth_logs"][-500:]
    save_auth_store(store)


def find_user_by_login(store, identifier):
    lowered = identifier.strip().lower()
    for user in store["users"]:
        if user.get("username", "").lower() == lowered or user.get("email", "").lower() == lowered:
            return user
    return None


def find_user_by_email(store, email):
    lowered = email.strip().lower()
    for user in store["users"]:
        if user.get("email", "").lower() == lowered:
            return user
    return None


def find_user_by_id(store, user_id):
    for user in store["users"]:
        if user.get("id") == user_id:
            return user
    return None


def clear_lock_if_expired(user):
    locked_until = parse_dt(user.get("locked_until"))
    if locked_until and locked_until <= now_utc():
        user["failed_attempts"] = 0
        user["locked_until"] = None
        return True
    return False


def login_user(user, provider):
    session.clear()
    session.permanent = True
    session["user"] = user["username"]
    session["user_email"] = user.get("email")
    session["auth_provider"] = provider


def create_password_reset_token(store, user_id):
    for token in store["password_reset_tokens"]:
        if token.get("user_id") == user_id and not token.get("used"):
            token["used"] = True
    token_value = secrets.token_urlsafe(32)
    store["password_reset_tokens"].append(
        {
            "id": next_id(store["password_reset_tokens"]),
            "user_id": user_id,
            "token": token_value,
            "expires_at": fmt_dt(now_utc() + timedelta(minutes=PASSWORD_RESET_MINUTES)),
            "used": False,
        }
    )
    return token_value


def find_reset_token(store, token_value):
    for token in store["password_reset_tokens"]:
        if token.get("token") == token_value:
            return token
    return None


def get_road_condition_from_pci(pci):
    if pci >= 85:
        return "Excellent"
    if pci >= 70:
        return "Good"
    if pci >= 55:
        return "Fair"
    if pci >= 40:
        return "Poor"
    return "Very Poor"


def get_crack_severity(iri, rutting):
    avg_issue = (iri + rutting) / 2
    if avg_issue < 2:
        return "Low"
    if avg_issue < 3:
        return "Medium"
    if avg_issue < 4:
        return "High"
    return "Critical"


def get_repair_summary(row):
    pci = row.get("PCI", 50)
    iri = row.get("IRI", 2.0)
    rutting = row.get("Rutting", 15.0)
    summary = []
    if iri > 2.5:
        summary.append(f"CRACK REPAIR: IRI {iri:.2f}")
    if rutting > 18:
        summary.append(f"POTHOLE REPAIR: {rutting:.2f}mm")
    summary.append(f"CONDITION: {get_road_condition_from_pci(pci)}")
    return "\n".join(summary)


def google_redirect_uri():
    override = (os.getenv("GOOGLE_REDIRECT_URI", "") or "").strip()
    if override:
        return override
    return url_for("google_callback", _external=True)


def exchange_google_code_for_tokens(code):
    payload = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "redirect_uri": google_redirect_uri(),
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        GOOGLE_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_google_userinfo(access_token):
    req = urllib.request.Request(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


@app.route("/")
def home():
    return redirect(url_for("login_page"))


@app.route("/healthz")
def healthz():
    return {"status": "ok"}, 200


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/login", methods=["GET"])
def login_page():
    return render_login(
        error=request.args.get("error"),
        info=request.args.get("info"),
    )


@app.route("/login", methods=["POST"])
def login():
    identifier = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not identifier or not password:
        return render_login(error="Username/email and password are required.")

    store = load_auth_store()
    user = find_user_by_login(store, identifier)
    if not user:
        log_auth_event(identifier, "local", "login", "failed")
        return render_login(error="Invalid username/email or password.")

    lock_cleared = clear_lock_if_expired(user)
    if lock_cleared:
        save_auth_store(store)

    locked_until = parse_dt(user.get("locked_until"))
    if locked_until and locked_until > now_utc():
        remaining_minutes = max(1, int((locked_until - now_utc()).total_seconds() // 60) + 1)
        log_auth_event(user["username"], user.get("provider", "local"), "login", "locked")
        return render_login(error=f"Account locked. Try again in about {remaining_minutes} minutes.")

    if not user.get("password_hash"):
        log_auth_event(user["username"], user.get("provider", "local"), "login", "failed")
        if user.get("provider") == "google":
            return render_login(error="This account uses Google sign-in. Continue with Google to access it.")
        return render_login(error="Password login is not available for this account.")

    if not check_password_hash(user["password_hash"], password):
        user["failed_attempts"] = int(user.get("failed_attempts", 0)) + 1
        if user["failed_attempts"] >= MAX_FAILED_LOGINS:
            user["locked_until"] = fmt_dt(now_utc() + timedelta(minutes=LOCKOUT_MINUTES))
        save_auth_store(store)
        log_auth_event(user["username"], user.get("provider", "local"), "login", "failed")
        if user["failed_attempts"] >= MAX_FAILED_LOGINS:
            return render_login(error="Too many failed login attempts. Your account is temporarily locked.")
        return render_login(error="Invalid username/email or password.")

    user["failed_attempts"] = 0
    user["locked_until"] = None
    save_auth_store(store)

    login_user(user, "local")
    log_auth_event(user["username"], user.get("provider", "local"), "login", "success")
    return redirect(url_for("dashboard"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_register()

    username = request.form.get("username", "").strip()
    email = normalize_email(request.form.get("email", ""))
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not username or not email or not password or not confirm_password:
        return render_register(error="Username, email, and password are required.")
    if not username_is_valid(username):
        return render_register(error="Username must be 3-30 characters and use letters, numbers, dots, underscores, or hyphens.")
    if not is_valid_email(email):
        return render_register(error="Enter a valid email address.")
    if password != confirm_password:
        return render_register(error="Passwords do not match.")
    if not password_is_strong(password):
        return render_register(error="Password must be at least 8 characters and include uppercase, lowercase, and a number.")

    store = load_auth_store()
    if find_user_by_login(store, username):
        return render_register(error="Username already exists.")
    if find_user_by_email(store, email):
        return render_register(error="An account with that email already exists.")

    store["users"].append(
        {
            "id": next_id(store["users"]),
            "username": make_unique_username(store["users"], username),
            "email": email,
            "password_hash": generate_password_hash(password),
            "email_verified": 1,
            "provider": "local",
            "role": "user",
            "failed_attempts": 0,
            "locked_until": None,
        }
    )
    save_auth_store(store)
    log_auth_event(username, "local", "register", "success")
    return redirect(url_for("login_page", info="Account created successfully. Please sign in."))


@app.route("/auth/google")
def google_login():
    if not google_oauth_ready():
        return redirect(url_for("login_page", error="Google sign-in is not configured yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET first."))

    state = secrets.token_urlsafe(24)
    session["google_oauth_state"] = state
    params = {
        "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return redirect(f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}")


@app.route("/auth/google/callback")
@app.route("/login/google/authorized")
def google_callback():
    if not google_oauth_ready():
        return redirect(url_for("login_page", error="Google sign-in is not configured yet."))

    returned_state = request.args.get("state", "")
    expected_state = session.pop("google_oauth_state", "")
    if not expected_state or returned_state != expected_state:
        return redirect(url_for("login_page", error="Google sign-in could not be verified. Please try again."))

    if request.args.get("error"):
        return redirect(url_for("login_page", error="Google sign-in was cancelled or denied."))

    code = request.args.get("code", "")
    if not code:
        return redirect(url_for("login_page", error="Google sign-in did not return an authorization code."))

    try:
        token_data = exchange_google_code_for_tokens(code)
        access_token = token_data.get("access_token", "")
        if not access_token:
            raise ValueError("Missing access token")
        profile = fetch_google_userinfo(access_token)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, json.JSONDecodeError):
        return redirect(url_for("login_page", error="Google sign-in failed while contacting Google. Please try again."))

    email = normalize_email(profile.get("email", ""))
    if not email:
        return redirect(url_for("login_page", error="Google did not provide an email address for this account."))

    preferred_name = profile.get("name") or profile.get("given_name") or email.split("@", 1)[0]
    store = load_auth_store()
    user = find_user_by_email(store, email)
    if user:
        user["email_verified"] = 1
        if user.get("provider") != "local":
            user["provider"] = "google"
    else:
        user = {
            "id": next_id(store["users"]),
            "username": make_unique_username(store["users"], preferred_name),
            "email": email,
            "password_hash": "",
            "email_verified": 1,
            "provider": "google",
            "role": "user",
            "failed_attempts": 0,
            "locked_until": None,
        }
        store["users"].append(user)
    save_auth_store(store)

    login_user(user, "google")
    log_auth_event(user["username"], "google", "login", "success")
    return redirect(url_for("dashboard", info="Signed in with Google successfully."))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_forgot_password(
            error=request.args.get("error"),
            info=request.args.get("info"),
        )

    identifier = request.form.get("identifier", "").strip()
    if not identifier:
        return render_forgot_password(error="Enter your username or email to continue.")

    store = load_auth_store()
    user = find_user_by_login(store, identifier)
    info = "If an account matches that username or email, password reset instructions have been sent where possible."

    if user:
        token_value = create_password_reset_token(store, user["id"])
        save_auth_store(store)
        reset_url = url_for("reset_password", token=token_value, _external=True)
        log_auth_event(user["username"], user.get("provider", "local"), "password_reset_requested", "success")

        if email_env_looks_like_placeholder():
            info = (
                "Email is still set to placeholder values in .env. Replace EMAIL_USER with your real "
                "address and EMAIL_PASS with a Gmail App Password (Google Account → Security → "
                "2-Step Verification → App passwords), then restart the app."
            )
        elif email_smtp_configured() and user.get("email"):
            email_sent = send_reset_email(user["email"], reset_url)
            if email_sent:
                info = f"A password reset link has been sent to {user['email']}."
            else:
                info = (
                    "We could not send the reset email. For Gmail use an App Password, not your normal "
                    "password; set EMAIL_HOST, EMAIL_PORT (587 or 465), EMAIL_USER, EMAIL_PASS. "
                    "Check the terminal for the detailed error."
                )
        elif not email_smtp_configured():
            info = (
                "Email delivery is not configured on this server, so a reset link could not be sent. "
                "Ask an administrator to configure SMTP (EMAIL_HOST, EMAIL_USER, EMAIL_PASS)."
            )
        else:
            info = (
                "This account has no email address on file, so a reset link could not be emailed. "
                "Contact support or sign in another way."
            )
    else:
        log_auth_event(identifier, "local", "password_reset_requested", "not_found")

    return render_forgot_password(info=info)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    store = load_auth_store()
    token_row = find_reset_token(store, token)

    if not token_row or token_row.get("used"):
        return redirect(url_for("forgot_password", error="That reset link is invalid or has already been used."))

    expires_at = parse_dt(token_row.get("expires_at"))
    if not expires_at or expires_at <= now_utc():
        token_row["used"] = True
        save_auth_store(store)
        return redirect(url_for("forgot_password", error="That reset link has expired. Request a new one."))

    if request.method == "GET":
        return render_reset_password(token)

    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if password != confirm_password:
        return render_reset_password(token, error="Passwords do not match.")
    if not password_is_strong(password):
        return render_reset_password(token, error="Password must be at least 8 characters and include uppercase, lowercase, and a number.")

    user = find_user_by_id(store, token_row["user_id"])
    if not user:
        token_row["used"] = True
        save_auth_store(store)
        return redirect(url_for("forgot_password", error="That account could not be found. Request a new link."))

    user["password_hash"] = generate_password_hash(password)
    user["failed_attempts"] = 0
    user["locked_until"] = None
    token_row["used"] = True
    save_auth_store(store)
    log_auth_event(user["username"], user.get("provider", "local"), "password_reset_completed", "success")
    return redirect(url_for("login_page", info="Password updated successfully. You can sign in now."))


@app.route("/dashboard")
def dashboard():
    if "user" in session:
        return render_template(
            "dashboard.html",
            info=request.args.get("info"),
            error=request.args.get("error"),
        )
    return redirect(url_for("login_page"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/history")
def history():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return render_template("history.html", history=session.get("history", []))


@app.route("/analysis/latest")
def analysis_latest():
    if "user" not in session:
        return redirect(url_for("login_page"))

    latest_prediction = session.get("latest_prediction")
    if not latest_prediction:
        return redirect(url_for("dashboard", info="No analysis found yet. Upload an image and run analysis first."))

    return render_template(
        "prediction.html",
        condition=latest_prediction.get("condition", "Unknown"),
        severity=latest_prediction.get("severity", "Unknown"),
        maintenance=latest_prediction.get("maintenance", "Unknown"),
        priority=latest_prediction.get("priority", "Unknown"),
        confidence=latest_prediction.get("confidence", 0),
        detail=latest_prediction.get("detail", "No analysis summary available."),
        summary=latest_prediction.get("summary", "No analysis summary available."),
        image_url=latest_prediction.get("image_url"),
        segment_id=latest_prediction.get("segment_id", "Unknown"),
        road_type=latest_prediction.get("road_type", "Unknown"),
        damage_score=latest_prediction.get("damage_score", 0),
        username=session.get("user", "User"),
    )


@app.route("/predict", methods=["POST"])
def predict():
    if "user" not in session:
        return redirect(url_for("login_page"))

    image = request.files.get("image")
    if image is None or not image.filename:
        return redirect(url_for("dashboard", error="Upload a broken road image before running prediction."))
    if not allowed_image_file(image.filename):
        return redirect(url_for("dashboard", error="Only JPG, JPEG, PNG, or WEBP road images are supported."))

    image_bytes = image.read()
    image.stream.seek(0)

    if not image_bytes:
        return redirect(url_for("dashboard", error="The uploaded file is empty. Please select a road image again."))
    if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
        return redirect(url_for("dashboard", error="The image is too large. Upload a road image smaller than 10 MB."))

    decoded_image = load_image_from_bytes(image_bytes)
    if decoded_image is None:
        return redirect(url_for("dashboard", error="The uploaded file could not be read as an image. Please try another road photo."))

    image_metrics = analyze_uploaded_road_image(decoded_image)
    validation_error = validate_road_damage_image(image_metrics)
    if validation_error:
        return redirect(url_for("dashboard", error=validation_error))

    filename = f"{uuid.uuid4()}_{secure_filename(image.filename)}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    with open(path, "wb") as saved_file:
        saved_file.write(image_bytes)
    image_url = url_for("uploaded_file", filename=filename)

    prediction = build_prediction_from_image(image_metrics)

    history_data = session.get("history", [])
    history_data.insert(
        0,
        {
            "timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "condition": prediction["condition"],
            "severity": prediction["severity"],
            "maintenance": prediction["maintenance"],
            "priority": prediction["priority"],
            "confidence": prediction["confidence"],
        },
    )
    session["history"] = history_data[:20]
    session["latest_prediction"] = {
        "condition": prediction["condition"],
        "severity": prediction["severity"],
        "maintenance": prediction["maintenance"],
        "priority": prediction["priority"],
        "confidence": prediction["confidence"],
        "detail": prediction["detail"],
        "summary": prediction["summary"],
        "image_url": image_url,
        "segment_id": prediction["segment_id"],
        "road_type": prediction["road_type"],
        "damage_score": prediction["damage_score"],
    }

    return render_template(
        "prediction.html",
        condition=prediction["condition"],
        severity=prediction["severity"],
        maintenance=prediction["maintenance"],
        priority=prediction["priority"],
        confidence=prediction["confidence"],
        detail=prediction["detail"],
        summary=prediction["summary"],
        image_url=image_url,
        segment_id=prediction["segment_id"],
        road_type=prediction["road_type"],
        damage_score=prediction["damage_score"],
        username=session.get("user", "User"),
    )


if __name__ == "__main__":
    host = (os.environ.get("HOST") or "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Flask app on {host}:{port}")
    app.run(host=host, port=port)
