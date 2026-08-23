import os
import datetime
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(DATABASE_DIR, "joyst_corp.db")
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    DATABASE_FILE = "/tmp/joyst_corp.db"

# Cloud Database URL (Supabase PostgreSQL / Cloud SQL)
DATABASE_URL = os.environ.get("DATABASE_URL")

engine = None
if DATABASE_URL:
    try:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_recycle=300
        )
    except Exception as e:
        print(f"[JOYST DATABASE] Cloud Database Notice: {e}")
        engine = None

if engine is None:
    engine = create_engine(
        f"sqlite:///{DATABASE_FILE}",
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Developer(Base):
    __tablename__ = "developers"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(120), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    owner_id = Column(String(32), unique=True, index=True, nullable=False)
    api_key = Column(String(64), unique=True, index=True, nullable=True)
    plan = Column(String(20), default="Free") # Free, Developer, Enterprise
    discord_id = Column(String(50), unique=True, index=True, nullable=True)
    max_apps = Column(Integer, default=3)
    max_users_per_app = Column(Integer, default=1000)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    applications = relationship("Application", back_populates="developer", cascade="all, delete-orphan")
    resellers = relationship("Reseller", back_populates="developer", cascade="all, delete-orphan")

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    developer_id = Column(Integer, ForeignKey("developers.id"), nullable=False)
    name = Column(String(100), index=True, nullable=False)
    owner_id = Column(String(32), index=True, nullable=False)
    secret = Column(String(64), unique=True, index=True, nullable=False)
    version = Column(String(20), default="1.0")
    status = Column(String(20), default="enabled") # enabled, disabled, maintenance, paused
    custom_status = Column(String(50), default="UNDETECTED") # UNDETECTED, ONLINE, UPDATING, MAINTENANCE, OFFLINE
    hwid_lock_enabled = Column(Boolean, default=True)
    allow_user_hwid_reset = Column(Boolean, default=False)
    vpn_block_enabled = Column(Boolean, default=False)
    hash_check_enabled = Column(Boolean, default=False)
    app_hash = Column(String(64), default="")
    session_timeout_minutes = Column(Integer, default=60)
    download_link = Column(String(500), default="")
    custom_message = Column(String(500), default="")
    # Custom Response Messages Hub (100% Configurable from Dashboard)
    login_success_message = Column(String(500), default="Welcome back! Logged in successfully.")
    login_failed_message = Column(String(500), default="Invalid username or password.")
    user_not_found_message = Column(String(500), default="Username does not exist.")
    hwid_mismatch_message = Column(String(500), default="HWID Mismatch! Your account is locked to another computer.")
    maintenance_message = Column(String(500), default="Application is under maintenance. Please check back soon.")
    expired_sub_message = Column(String(500), default="Your subscription has expired! Please renew.")
    banned_user_message = Column(String(500), default="Account is banned!")
    brute_force_ban_message = Column(String(500), default="Too many invalid attempts! Your PC hardware and IP are permanently banned.")
    blacklist_message = Column(String(500), default="Access Denied! Your IP or Machine HWID has been blacklisted.")
    invalid_license_message = Column(String(500), default="Invalid license key.")
    used_license_message = Column(String(500), default="This license key is already used.")
    paused_license_message = Column(String(500), default="This license key is paused by administrator.")
    revoked_license_message = Column(String(500), default="This license key has been revoked.")
    register_success_message = Column(String(500), default="Account created successfully! You are now logged in.")
    license_login_success_message = Column(String(500), default="License authenticated successfully!")
    hash_mismatch_message = Column(String(500), default="Executable integrity verification failed! Modified or cracked binary detected.")
    version_mismatch_message = Column(String(500), default="Update required! Please download the latest version.")
    vpn_blocked_message = Column(String(500), default="VPN or Proxy connections are strictly prohibited.")

    webhook_url = Column(String(500), default="")
    webhook_bot_name = Column(String(100), default="JOYST AUTH SHIELD")
    webhook_avatar_url = Column(String(500), default="https://joystauth.cc/static/img/joyst_logo.png")
    webhook_on_login = Column(Boolean, default=True)
    webhook_on_register = Column(Boolean, default=True)
    webhook_on_hwid_reset = Column(Boolean, default=True)
    webhook_on_failed = Column(Boolean, default=True)
    webhook_on_key_gen = Column(Boolean, default=True)
    webhook_on_ban = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    developer = relationship("Developer", back_populates="applications")
    users = relationship("User", back_populates="app", cascade="all, delete-orphan")
    licenses = relationship("License", back_populates="app", cascade="all, delete-orphan")
    variables = relationship("AppVariable", back_populates="app", cascade="all, delete-orphan")
    files = relationship("AppFile", back_populates="app", cascade="all, delete-orphan")
    logs = relationship("AuditLog", back_populates="app", cascade="all, delete-orphan")
    tiers = relationship("SubscriptionTier", back_populates="app", cascade="all, delete-orphan")
    blacklists = relationship("Blacklist", back_populates="app", cascade="all, delete-orphan")
    notifications = relationship("AppNotification", back_populates="app", cascade="all, delete-orphan")

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    username = Column(String(100), index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    hwid = Column(String(255), nullable=True, index=True)
    hwid_lock_override = Column(Boolean, default=None)
    last_ip = Column(String(45), default="")
    registered_ip = Column(String(45), default="")
    subscription_tier = Column(String(50), default="default")
    level = Column(Integer, default=1)
    expires_at = Column(DateTime, nullable=True)
    is_banned = Column(Boolean, default=False)
    ban_reason = Column(String(255), default="")
    key_used = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, default=datetime.datetime.utcnow)

    app = relationship("Application", back_populates="users")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

class License(Base):
    __tablename__ = "licenses"
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    license_key = Column(String(100), unique=True, index=True, nullable=False)
    duration_days = Column(Integer, default=30)
    level = Column(String(50), default="default")
    level_rank = Column(Integer, default=1)
    status = Column(String(20), default="unused")
    used_by_username = Column(String(100), default="")
    used_at = Column(DateTime, nullable=True)
    created_by_reseller = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(String(255), default="")

    app = relationship("Application", back_populates="licenses")

class SubscriptionTier(Base):
    __tablename__ = "subscription_tiers"
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    name = Column(String(50), nullable=False)
    level_rank = Column(Integer, default=1)
    description = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    app = relationship("Application", back_populates="tiers")

class AppVariable(Base):
    __tablename__ = "app_variables"
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    name = Column(String(100), index=True, nullable=False)
    value = Column(Text, nullable=False)
    is_encrypted = Column(Boolean, default=True)
    is_user_writable = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    app = relationship("Application", back_populates="variables")

class AppFile(Base):
    __tablename__ = "app_files"
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    file_id = Column(String(100), unique=True, index=True, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, default=0)
    file_url = Column(String(500), default="")
    file_path = Column(String(500), nullable=True)
    file_hash = Column(String(64), default="")
    auth_required = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    app = relationship("Application", back_populates="files")

class Blacklist(Base):
    __tablename__ = "blacklists"
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    type = Column(String(20), nullable=False)
    data = Column(String(255), nullable=False)
    reason = Column(String(255), default="Blacklisted by Admin")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    app = relationship("Application", back_populates="blacklists")

class AppNotification(Base):
    __tablename__ = "app_notifications"
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    title = Column(String(150), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(20), default="info") # info, success, warning, danger
    is_active = Column(Boolean, default=True)
    show_on_login = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    app = relationship("Application", back_populates="notifications")

class Reseller(Base):
    __tablename__ = "resellers"
    id = Column(Integer, primary_key=True, index=True)
    developer_id = Column(Integer, ForeignKey("developers.id"), nullable=False)
    username = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    balance = Column(Integer, default=100)
    allowed_apps = Column(String(255), default="all")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    developer = relationship("Developer", back_populates="resellers")

class PlanKey(Base):
    __tablename__ = "plan_keys"
    id = Column(Integer, primary_key=True, index=True)
    key_code = Column(String(100), unique=True, index=True, nullable=False)
    target_plan = Column(String(20), nullable=False) # Developer, Enterprise
    is_used = Column(Boolean, default=False)
    used_by_username = Column(String(100), default="")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_token = Column(String(100), unique=True, index=True, nullable=False)
    app_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    hwid = Column(String(255), nullable=True)
    ip_address = Column(String(45), default="")
    encryption_key = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_valid = Column(Boolean, default=True)

    user = relationship("User", back_populates="sessions")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("applications.id"), nullable=True)
    username = Column(String(100), default="")
    action = Column(String(50), nullable=False)
    ip_address = Column(String(45), default="")
    hwid = Column(String(255), default="")
    details = Column(String(500), default="")
    status = Column(String(20), default="INFO")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    app = relationship("Application", back_populates="logs")

def init_db():
    Base.metadata.create_all(bind=engine)
    from sqlalchemy import text
    
    columns = [
        ("developers", "api_key", "VARCHAR(64)"),
        ("developers", "discord_id", "VARCHAR(50)"),
        ("developers", "max_apps", "INTEGER DEFAULT 3"),
        ("developers", "max_users_per_app", "INTEGER DEFAULT 1000"),
        ("applications", "custom_status", "VARCHAR(50) DEFAULT 'UNDETECTED'"),
        ("applications", "vpn_block_enabled", "BOOLEAN DEFAULT FALSE"),
        ("applications", "allow_user_hwid_reset", "BOOLEAN DEFAULT FALSE"),
        ("applications", "hash_check_enabled", "BOOLEAN DEFAULT FALSE"),
        ("applications", "app_hash", "VARCHAR(64) DEFAULT ''"),
        ("applications", "download_link", "VARCHAR(500) DEFAULT ''"),
        ("applications", "custom_message", "VARCHAR(500) DEFAULT ''"),
        ("applications", "login_success_message", "VARCHAR(500) DEFAULT 'Welcome back! Logged in successfully.'"),
        ("applications", "login_failed_message", "VARCHAR(500) DEFAULT 'Invalid username or password.'"),
        ("applications", "hwid_mismatch_message", "VARCHAR(500) DEFAULT 'HWID Mismatch! Your account is locked to another computer.'"),
        ("applications", "maintenance_message", "VARCHAR(500) DEFAULT 'Application is under maintenance. Please check back soon.'"),
        ("applications", "user_not_found_message", "VARCHAR(500) DEFAULT 'Username does not exist.'"),
        ("applications", "expired_sub_message", "VARCHAR(500) DEFAULT 'Your subscription has expired! Please renew.'"),
        ("applications", "banned_user_message", "VARCHAR(500) DEFAULT 'Account is banned!'"),
        ("applications", "brute_force_ban_message", "VARCHAR(500) DEFAULT 'Too many invalid attempts! Your PC hardware and IP are permanently banned.'"),
        ("applications", "blacklist_message", "VARCHAR(500) DEFAULT 'Access Denied! Your IP or Machine HWID has been blacklisted.'"),
        ("applications", "invalid_license_message", "VARCHAR(500) DEFAULT 'Invalid license key.'"),
        ("applications", "used_license_message", "VARCHAR(500) DEFAULT 'This license key is already used.'"),
        ("applications", "paused_license_message", "VARCHAR(500) DEFAULT 'This license key is paused by administrator.'"),
        ("applications", "revoked_license_message", "VARCHAR(500) DEFAULT 'This license key has been revoked.'"),
        ("applications", "register_success_message", "VARCHAR(500) DEFAULT 'Account created successfully! You are now logged in.'"),
        ("applications", "license_login_success_message", "VARCHAR(500) DEFAULT 'License authenticated successfully!'"),
        ("applications", "hash_mismatch_message", "VARCHAR(500) DEFAULT 'Executable integrity verification failed! Modified or cracked binary detected.'"),
        ("applications", "version_mismatch_message", "VARCHAR(500) DEFAULT 'Update required! Please download the latest version.'"),
        ("applications", "vpn_blocked_message", "VARCHAR(500) DEFAULT 'VPN or Proxy connections are strictly prohibited.'"),
        ("applications", "webhook_bot_name", "VARCHAR(100) DEFAULT 'JOYST AUTH SHIELD'"),
        ("applications", "webhook_avatar_url", "VARCHAR(500) DEFAULT 'https://joystauth.cc/static/img/joyst_logo.png'"),
        ("applications", "webhook_on_login", "BOOLEAN DEFAULT TRUE"),
        ("applications", "webhook_on_register", "BOOLEAN DEFAULT TRUE"),
        ("applications", "webhook_on_hwid_reset", "BOOLEAN DEFAULT TRUE"),
        ("applications", "webhook_on_failed", "BOOLEAN DEFAULT TRUE"),
        ("applications", "webhook_on_key_gen", "BOOLEAN DEFAULT TRUE"),
        ("applications", "webhook_on_ban", "BOOLEAN DEFAULT TRUE"),
        ("users", "level", "INTEGER DEFAULT 1"),
        ("licenses", "level_rank", "INTEGER DEFAULT 1"),
        ("licenses", "created_by_reseller", "VARCHAR(100) DEFAULT ''"),
        ("app_variables", "is_user_writable", "BOOLEAN DEFAULT FALSE"),
        ("app_files", "file_url", "VARCHAR(500) DEFAULT ''"),
        ("app_files", "auth_required", "BOOLEAN DEFAULT TRUE"),
        ("subscription_tiers", "description", "VARCHAR(255) DEFAULT ''")
    ]

    for table, col, col_def in columns:
        # 1. Try PostgreSQL IF NOT EXISTS syntax in isolated connection
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {col_def}"))
                conn.commit()
                continue
        except Exception:
            pass
            
        # 2. Fallback for SQLite in isolated connection
        try:
            with engine.connect() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))
                conn.commit()
        except Exception:
            pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
