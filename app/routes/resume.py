from fastapi import APIRouter, File, UploadFile

from app.services.extractor import extract_resume_data

router = APIRouter()


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    resume_data = await extract_resume_data(file)
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "page_count": resume_data["page_count"],
        "skills": resume_data["skills"],
        "text": resume_data["text"],
    }
