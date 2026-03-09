"""Page routes"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.repositories.users import UserRepository
from app.repositories.conversations import ConversationRepository
from app.repositories.resumes import ResumeRepository
import json

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    """Main page"""
    from jinja2 import FileSystemLoader, Environment
    import os
    
    # Initialize user and conversation
    user = UserRepository.get_or_create_demo_user(db)
    conversations = ConversationRepository.get_user_conversations(db, user.id)
    resumes = ResumeRepository.get_user_resumes(db, user.id)
    
    # Get latest conversation or create new
    if conversations:
        latest_conv = conversations[0]
    else:
        latest_conv = ConversationRepository.create_conversation(db, user.id)
    
    messages = ConversationRepository.get_conversation_messages(db, latest_conv.id)
    
    # Format for template
    messages_data = [{"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in messages]
    
    resumes_data = []
    for r in resumes:
        resumes_data.append({
            "id": r.id,
            "title": r.title,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        })
    
    context = {
        "user_id": user.id,
        "conversation_id": latest_conv.id,
        "messages": messages_data,
        "resumes": resumes_data,
        "candidate_profile": None,
        "vacancy_profile": None,
        "strategy_brief": None,
    }
    
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("index.html")
    
    return template.render(context)
