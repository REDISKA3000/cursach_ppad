"""User repository"""
from sqlalchemy.orm import Session
from app.models import User
import logging

logger = logging.getLogger(__name__)

class UserRepository:
    @staticmethod
    def create_user(db: Session, username: str) -> User:
        """Create new user"""
        user = User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> User:
        """Get user by username"""
        return db.query(User).filter(User.username == username).first()
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """Get user by ID"""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_or_create_demo_user(db: Session) -> User:
        """Get or create demo user"""
        demo_user = UserRepository.get_user_by_username(db, "demo_user")
        if not demo_user:
            demo_user = UserRepository.create_user(db, "demo_user")
        return demo_user
