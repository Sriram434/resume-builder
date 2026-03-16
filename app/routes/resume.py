from fastapi import APIRouter, UploadFile, File, HTTPException
# from app.services.extractor import extract_resume_data

router = APIRouter()

@router.get("/upload")
async def upload_resume():
    return {"Hello": "World"}