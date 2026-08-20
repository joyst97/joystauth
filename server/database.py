import os
import datetime
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

DATABASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_FILE = os.path.join(DATABASE_DIR, "joyst_corp.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATABASE_FILE}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
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
    status = Column(String(20), default="enabled") # enabled, disabled, maintenance
    hwid_lock_enabled = Column(Boolean, default=True)
    vpn_block_enabled = Column(Boolean, default=False)
    session_timeout_minutes = Column(Integer, default=60)
    download_link = Column(String(500), default="")
    custom_message = Column(String(500), default="")
    webhook_url = Column(String(500), default="")
    webhook_on_login = Column(Boolean, default=True)
    webhook_on_register = Column(Boolean, default=True)
    webhook_on_hwid_reset = Column(Boolean, default=True)
    webhook_on_failed = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    developer = relationship("Developer", back_populates="applications")
    users = relationship("User", back_populates="app", cascade="all, delete-orphan")
    licenses = relationship("License", back_populates="app", cascade="all, delete-orphan")
    variables = relationship("AppVariable", back_populates="app", cascade="all, delete-orphan")
    files = relationship("AppFile", back_populates="app", cascade="all, delete-orphan")
    logs = relationship("AuditLog", back_populates="app", cascade="all, delete-orphan")
    tiers = relationship("SubscriptionTier", back_populates="app", cascade="all, delete-orphan")
    blacklists = relationship("Blacklist", back_populates="app", cascade="all, delete-orphan")

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
    with engine.connect() as conn:
        def run_alter(stmt):
            try:
                conn.connection.cursor().execute(stmt)
            except Exception:
                pass
        
        run_alter("ALTER TABLE developers ADD COLUMN api_key VARCHAR(64)")
        run_alter("ALTER TABLE developers ADD COLUMN max_apps INTEGER DEFAULT 3")
        run_alter("ALTER TABLE developers ADD COLUMN max_users_per_app INTEGER DEFAULT 1000")
        run_alter("ALTER TABLE applications ADD COLUMN vpn_block_enabled BOOLEAN DEFAULT 0")
        run_alter("ALTER TABLE applications ADD COLUMN download_link VARCHAR(500) DEFAULT ''")
        run_alter("ALTER TABLE applications ADD COLUMN custom_message VARCHAR(500) DEFAULT ''")
        run_alter("ALTER TABLE applications ADD COLUMN webhook_on_login BOOLEAN DEFAULT 1")
        run_alter("ALTER TABLE applications ADD COLUMN webhook_on_register BOOLEAN DEFAULT 1")
        run_alter("ALTER TABLE applications ADD COLUMN webhook_on_hwid_reset BOOLEAN DEFAULT 1")
        run_alter("ALTER TABLE applications ADD COLUMN webhook_on_failed BOOLEAN DEFAULT 1")
        run_alter("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
        run_alter("ALTER TABLE licenses ADD COLUMN level_rank INTEGER DEFAULT 1")
        run_alter("ALTER TABLE licenses ADD COLUMN created_by_reseller VARCHAR(100) DEFAULT ''")
        run_alter("ALTER TABLE app_variables ADD COLUMN is_user_writable BOOLEAN DEFAULT 0")
        run_alter("ALTER TABLE app_files ADD COLUMN file_url VARCHAR(500) DEFAULT ''")
        run_alter("ALTER TABLE app_files ADD COLUMN auth_required BOOLEAN DEFAULT 1")
        run_alter("ALTER TABLE subscription_tiers ADD COLUMN description VARCHAR(255) DEFAULT ''")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
