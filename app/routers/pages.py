"""Page routes"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from jinja2 import Environment, FileSystemLoader
import os

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def index():
    """Main page"""
    template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("flow.html")
    return template.render()
