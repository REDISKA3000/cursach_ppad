"""User repository"""
from sqlalchemy.orm import Session
from app.models import User
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class UserRepository:
    @staticmethod
    def create_user(db: Session, username: str, email: str = None, password_hash: str = None) -> User:
        """Create new user"""
        user = User(username=username, email=email, password_hash=password_hash)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> User:
        """Get user by username"""
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> User:
        """Get user by normalized email"""
        return db.query(User).filter(User.email == email.lower().strip()).first()
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def create_registered_user(db: Session, email: str, password_hash: str) -> User:
        """Create an auth-enabled user."""
        normalized_email = email.lower().strip()
        return UserRepository.create_user(
            db,
            username=normalized_email,
            email=normalized_email,
            password_hash=password_hash,
        )

    @staticmethod
    def update_password(db: Session, user: User, password_hash: str) -> User:
        """Update password hash for an existing user."""
        user.password_hash = password_hash
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_or_create_demo_user(db: Session) -> User:
        """Get or create demo user"""
        demo_user = UserRepository.get_user_by_username(db, "demo_user")
        if not demo_user:
            demo_user = UserRepository.create_user(db, "demo_user")
        return demo_user
