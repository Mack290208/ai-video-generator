from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Any
from pathlib import Path
import os
import uuid
import json
import uvicorn
from dotenv import load_dotenv

from storyboard_pipeline import run_pipeline
from services.tts_service import TTSConfig
from services.manim_service import list_templates, dump_template_catalog
from llm_storyboard_service import generate_storyboard_with_llm, TEMPLATE_CATALOG, _get_llm_caller
from llm_codegen_service import generate_manim_code, execute_manim_code
from llm_chat_service import chat_with_ai, generate_storyboard_from_chat

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)
OUTPUT_DIR = BASE_DIR / "outputs"
AUDIO_DIR = OUTPUT_DIR / "audio"
SUBTITLE_DIR = OUTPUT_DIR / "subtitles"
VIDEO_DIR = OUTPUT_DIR / "video"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="ML Teaching Video Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateVideoRequest(BaseModel):
    video_task: str | None = None
    request_id: str | None = None
    topic: str | None = None
    title: str | None = None
    global_style: dict[str, Any] | None = None
    segments: list[dict[str, Any]] = Field(default_factory=list)


@app.get("/")
def root():
    return {
        "ok": True,
        "service": "ml_teaching_video_generator",
        "version": "v3-pipeline"
    }


@app.get("/health")
def health():
    cfg = TTSConfig.from_env()
    return {
        "status": "ok",
        "tts_provider": cfg.provider,
        "tts_base_url": cfg.base_url,
    }


@app.get("/templates")
def get_templates():
    """返回所有可用 Manim 模板。"""
    catalog = dump_template_catalog()
    return {"templates": catalog.get("templates", [])}


@app.post("/generate-video")
@app.post("/tts/pipeline")
def generate_video(payload: GenerateVideoRequest):
    """完整的视频生成流程：TTS + WhisperX对齐 + Manim + 合成"""
    # 解析请求
    if payload.video_task:
        try:
            task = json.loads(payload.video_task)
            if not isinstance(task, dict):
                raise HTTPException(status_code=400, detail="video_task 必须是 JSON object")
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"video_task 不是合法 JSON: {e}")
    else:
        task = {
            "video_title": payload.title or "未命名视频",
            "segments": payload.segments,
        }

    segments = task.get("segments", [])
    if not segments:
        raise HTTPException(status_code=400, detail="segments 不能为空")

    task_id = task.get("request_id") or payload.request_id or str(uuid.uuid4())

    # 调用完整 pipeline
    result = run_pipeline(storyboard=task, task_id=task_id, use_whisper=True)

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return result


class ChatRequest(BaseModel):
    message: str
    history: list[dict[str, str]] = Field(default_factory=list)
    provider: str | None = None  # 可选: "mimo", "deepseek", "openai"


@app.post("/chat/generate-storyboard")
def chat_generate_storyboard(payload: ChatRequest):
    """AI 对话 - 支持聊天讨论和 storyboard 生成"""
    if not payload.message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    # 调用聊天服务
    result = chat_with_ai(
        message=payload.message,
        history=payload.history,
        provider=payload.provider
    )
    
    # 如果需要生成 storyboard
    if result.get("should_generate") and result.get("topic"):
        topic = result["topic"]
        storyboard = generate_storyboard_from_chat(
            topic=topic,
            history=payload.history,
            provider=payload.provider
        )
        
        if storyboard.get("error"):
            return {
                "ok": False,
                "message": result["response"] + f"\n\n生成 storyboard 时出错：{storyboard['error']}",
                "should_generate": True,
                "topic": topic
            }
        
        return {
            "ok": True,
            "storyboard": storyboard,
            "message": result["response"] + f"\n\n已为「{storyboard.get('video_title', topic)}」生成 storyboard，共 {len(storyboard.get('segments', []))} 个段落",
            "should_generate": True,
            "topic": topic
        }
    
    # 普通对话
    return {
        "ok": True,
        "message": result["response"],
        "should_generate": False,
        "topic": None
    }


@app.get("/llm/providers")
def get_llm_providers():
    """返回可用的 LLM 提供商列表"""
    providers = []
    if os.getenv("MIMO_API_KEY") and os.getenv("MIMO_API_KEY") != "your_mimo_api_key_here":
        providers.append({"id": "mimo", "name": "MiMo (小米大模型)", "model": os.getenv("MIMO_MODEL", "mimo-v2-pro")})
    if os.getenv("DEEPSEEK_API_KEY") and os.getenv("DEEPSEEK_API_KEY") != "your_deepseek_api_key_here":
        providers.append({"id": "deepseek", "name": "DeepSeek", "model": "deepseek-chat"})
    if os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY"):
        providers.append({"id": "openai", "name": "OpenAI 兼容", "model": os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3")})
    return {"providers": providers}


@app.get("/templates/catalog")
def get_template_catalog():
    """返回模板目录（供 LLM 参考）"""
    return TEMPLATE_CATALOG


class CodeGenRequest(BaseModel):
    title: str
    requirements: str
    provider: str | None = None


@app.post("/codegen/generate")
def codegen_generate(payload: CodeGenRequest):
    """方案C: LLM 生成 Manim 代码"""
    from llm_storyboard_service import _get_llm_caller
    
    llm_func = _get_llm_caller(payload.provider)
    
    result = generate_manim_code(
        title=payload.title,
        requirements=payload.requirements,
        llm_func=llm_func
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return {
        "ok": True,
        "code": result["code"],
        "message": "代码生成成功"
    }


@app.post("/codegen/render")
def codegen_render(payload: CodeGenRequest):
    """方案C: LLM 生成代码并渲染视频"""
    from llm_storyboard_service import _get_llm_caller
    
    llm_func = _get_llm_caller(payload.provider)
    
    # 生成代码
    code_result = generate_manim_code(
        title=payload.title,
        requirements=payload.requirements,
        llm_func=llm_func
    )
    
    if not code_result["success"]:
        raise HTTPException(status_code=500, detail=code_result["error"])
    
    # 渲染视频
    render_result = execute_manim_code(
        code=code_result["code"],
        quality="medium"
    )
    
    if not render_result["success"]:
        raise HTTPException(status_code=500, detail=render_result["error"])
    
    # 返回视频路径
    video_path = Path(render_result["video_path"])
    video_filename = video_path.name
    
    return {
        "ok": True,
        "code": code_result["code"],
        "video_filename": video_filename,
        "message": "代码生成并渲染成功"
    }


# 静态文件
FRONTEND_DIR = BASE_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
