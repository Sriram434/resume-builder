from __future__ import annotations

import json
import os
from io import BytesIO

import httpx
import pdfplumber
from fastapi import HTTPException, UploadFile


GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _read_resume_text(file_bytes: bytes, filename: str | None) -> tuple[str, int]:
    if filename and filename.lower().endswith(".txt"):
        return file_bytes.decode("utf-8").strip(), 1

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        pages: list[str] = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages).strip(), len(pdf.pages)


async def _get_skills_from_groq(resume_text: str) -> dict[str, list[str]]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is missing.")

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract the candidate's technical skills from the resume and group related skills "
                    "into logical categories. Respond with valid JSON only in this exact outer shape: "
                    '{"categories":{"Frontend":["React","Angular"],"Backend":["FastAPI","Node.js"]}}. '
                    "Rules: use concise, meaningful category names based only on the resume; category keys "
                    "can vary; put each skill in the single most appropriate category; use skill names as "
                    "written in the resume when possible; do not invent skills; return "
                    '{"categories":{}} when no technical skills are found; do not include any other keys.'
                ),
            },
            {"role": "user", "content": resume_text[:12000]},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Groq request failed.") from exc

    try:
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        categories = data["categories"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Invalid response from Groq.") from exc

    if not isinstance(categories, dict):
        raise HTTPException(status_code=502, detail="Invalid response from Groq.")

    cleaned_categories: dict[str, list[str]] = {}

    for category, skills in categories.items():
        if not isinstance(category, str) or not category.strip():
            continue
        if not isinstance(skills, list):
            continue

        cleaned_categories[category.strip()] = list(
            dict.fromkeys(
                skill.strip()
                for skill in skills
                if isinstance(skill, str) and skill.strip()
            )
        )

    return cleaned_categories

async def extract_resume_data(file: UploadFile) -> dict[str, str | int | dict[str, list[str]]]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing.")

    if not file.filename.lower().endswith((".pdf", ".txt")):
        raise HTTPException(status_code=400, detail="Upload a PDF or TXT file.")

    file_bytes = await file.read()
    await file.close()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        text, page_count = _read_resume_text(file_bytes, file.filename)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="TXT file must be UTF-8.") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read the resume file.") from exc

    if not text:
        raise HTTPException(status_code=400, detail="No readable text found in the resume.")

    skill_categories = await _get_skills_from_groq(text)

    return {
        "page_count": page_count,
        "skill_categories": skill_categories,
    }
