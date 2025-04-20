# -*- coding: utf-8 -*-
import os
import pathlib
import tempfile
import shutil
from typing import Optional, Union
import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request, Body # Import Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import google.generativeai as genai

# Import utility functions and models
import gemini_utils
# Import all necessary response models
from models import LessonResponse, ErrorResponse, QuestionListResponse, GenerateLessonRequest

# --- Configuration ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
    exit(1)

try:
    genai.configure(api_key=API_KEY)
    print("Gemini API Key configured successfully.")
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    exit(1)

# --- FastAPI App Setup ---
app = FastAPI(title="LessonGenie API")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
TEMP_DIR_BASE = "temp_uploads"
pathlib.Path(TEMP_DIR_BASE).mkdir(exist_ok=True)

# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/extract-questions", response_model=Union[QuestionListResponse, ErrorResponse])
async def extract_questions_endpoint(
    pdf_file: UploadFile = File(..., description="The PDF exam paper to analyze.")
):
    """
    Uploads a PDF, extracts questions using Gemini, returns the list of questions
    and the File API ID (name) of the uploaded PDF.
    Does NOT delete the PDF from File API yet.
    """
    print("\nReceived request to extract questions from PDF.")
    temp_dir_path: Optional[str] = None
    uploaded_gemini_file_obj = None # Keep track to potentially delete if extraction fails mid-way

    try:
        # --- Step 1: Save Uploaded File Temporarily ---
        pdf_content = await pdf_file.read()
        if not pdf_content:
            raise HTTPException(status_code=400, detail="PDF file is empty.")

        temp_dir_path = tempfile.mkdtemp(dir=TEMP_DIR_BASE)
        temp_pdf_path = os.path.join(temp_dir_path, pdf_file.filename or "temp_upload.pdf")

        print(f"Saving uploaded file temporarily to: {temp_pdf_path}")
        with open(temp_pdf_path, "wb") as temp_pdf:
            temp_pdf.write(pdf_content)

        # --- Step 2: Upload the Temporary File to Gemini ---
        display_name = pdf_file.filename or "uploaded_exam.pdf"
        uploaded_gemini_file_obj = gemini_utils.upload_pdf_to_gemini(
            pdf_path=temp_pdf_path,
            display_name=display_name
        )
        if not uploaded_gemini_file_obj:
            raise HTTPException(status_code=500, detail="Failed to upload PDF to Gemini File API.")

        # --- Step 3: Extract Questions using Gemini ---
        question_list_response = gemini_utils.extract_questions_from_pdf(
            uploaded_file=uploaded_gemini_file_obj,
            model_name="gemini-1.5-flash-latest" # Or pro if needed
        )

        if not question_list_response:
            # Extraction failed, delete the file we just uploaded
            if uploaded_gemini_file_obj:
                 gemini_utils.delete_uploaded_file(uploaded_gemini_file_obj.name)
            raise HTTPException(status_code=500, detail="Failed to extract questions from the PDF.")

        # --- Step 4: Return Successful Question List ---
        print("Successfully extracted questions. Returning list to client.")
        # We need pdfFileId in the response for the next step
        if not question_list_response.pdfFileId:
             question_list_response.pdfFileId = uploaded_gemini_file_obj.name # Ensure it's set

        return question_list_response # FastAPI handles serialization

    except HTTPException as http_exc:
        # If upload failed before gemini obj was created, we only clean up local temp
        if uploaded_gemini_file_obj: # Clean up Gemini file if upload succeeded but extraction failed
             gemini_utils.delete_uploaded_file(uploaded_gemini_file_obj.name)
        raise http_exc
    except Exception as e:
        print(f"--- Unexpected Error in /extract-questions endpoint: {e} ---")
        if uploaded_gemini_file_obj: # Clean up Gemini file on generic error too
             gemini_utils.delete_uploaded_file(uploaded_gemini_file_obj.name)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(detail="An unexpected server error occurred during question extraction.").model_dump()
        )
    finally:
        # --- Step 5: Cleanup Local Temporary File ---
        # Gemini file cleanup happens ONLY if extraction fails OR in the generate lesson endpoint
        if temp_dir_path and os.path.exists(temp_dir_path):
            try:
                print(f"Removing temporary directory: {temp_dir_path}")
                shutil.rmtree(temp_dir_path)
                print("Temporary directory removed.")
            except Exception as cleanup_error:
                print(f"--- Warning: Failed to remove temporary directory {temp_dir_path}: {cleanup_error} ---")


@app.post("/generate-specific-lesson", response_model=Union[LessonResponse, ErrorResponse])
async def generate_specific_lesson_endpoint(
    # Use Pydantic model for request body
    request_data: GenerateLessonRequest = Body(...)
):
    """
    Generates a detailed lesson for a specific question, referencing the
    PDF already uploaded via its File API ID (name).
    Deletes the PDF from File API after generating the lesson.
    """
    print(f"\nReceived request to generate lesson for Q_ID: '{request_data.selectedQuestionId}' from File ID: '{request_data.pdfFileId}'")
    pdf_file_id_to_delete = request_data.pdfFileId # Store ID for cleanup

    try:
        # --- Step 1: Generate Lesson using Gemini ---
        lesson_response_model = gemini_utils.generate_structured_lesson(
            pdf_file_id=request_data.pdfFileId,
            selected_question_id=request_data.selectedQuestionId,
            selected_question_text=request_data.selectedQuestionText, # Pass optional text
            model_name="gemini-1.5-flash-latest"
        )

        if not lesson_response_model:
            # Attempting generation failed (e.g., file expired, AI error)
            # We might still try to delete the file ID if it was invalid
            raise HTTPException(status_code=500, detail="Failed to generate or validate lesson content from Gemini.")

        # --- Step 2: Return Successful Response ---
        print("Successfully generated specific lesson. Returning to client.")
        return lesson_response_model

    except HTTPException as http_exc:
        # Don't try deleting file on HTTP error typically raised before generation attempt
        raise http_exc
    except Exception as e:
        print(f"--- Unexpected Error in /generate-specific-lesson endpoint: {e} ---")
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(detail="An unexpected server error occurred during lesson generation.").model_dump()
        )
    finally:
        # --- Step 3: Cleanup - Delete the referenced PDF from Gemini File API ---
        print("--- Specific Lesson Endpoint finished, initiating file cleanup ---")
        if pdf_file_id_to_delete:
             gemini_utils.delete_uploaded_file(pdf_file_id_to_delete)
        else:
             print("No PDF File ID was provided in the request for cleanup.")


# --- Run the App (for local development) ---
if __name__ == "__main__":
    print("Starting LessonGenie FastAPI server...")
    pathlib.Path(TEMP_DIR_BASE).mkdir(exist_ok=True)
    pathlib.Path("lesson_outputs").mkdir(exist_ok=True) # If using save function

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

