import os
import pathlib
import tempfile # For creating temporary files/directories
import shutil   # For removing temporary directories
from typing import Optional, Union # Keep Union for response_model
import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import google.generativeai as genai

# Try importing the specific File type, fallback handled in gemini_utils
try:
    from google.generativeai.types import File as GeminiFile
except ImportError:
    GeminiFile = None # Let gemini_utils handle the 'Any' type

# Import utility functions and models
import gemini_utils
from models import LessonResponse, ErrorResponse

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

# Define a temporary directory base (optional, but good practice)
TEMP_DIR_BASE = "temp_uploads"
pathlib.Path(TEMP_DIR_BASE).mkdir(exist_ok=True)


# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serves the main HTML page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate-lesson", response_model=Union[LessonResponse, ErrorResponse])
async def generate_lesson_endpoint(
    request: Request,
    pdf_file: UploadFile = File(..., description="The PDF exam paper to analyze."),
    question_description: str = Form(..., description="A description of the question to explain (e.g., 'Question 3a').")
):
    """
    API endpoint to upload a PDF, generate a structured lesson for a specific
    question using Gemini, and return the lesson JSON.
    """
    print(f"\nReceived request to generate lesson for: '{question_description}'")
    uploaded_gemini_file_obj: Optional[GeminiFile] = None
    temp_dir_path: Optional[str] = None # Keep track of temp directory

    try:
        # --- Step 1: Save Uploaded File Temporarily ---
        pdf_content = await pdf_file.read()
        if not pdf_content:
            raise HTTPException(status_code=400, detail="PDF file is empty.")

        # Create a unique temporary directory for this request
        temp_dir_path = tempfile.mkdtemp(dir=TEMP_DIR_BASE)
        # Create the full path for the temporary file
        temp_pdf_path = os.path.join(temp_dir_path, pdf_file.filename or "temp_upload.pdf")

        print(f"Saving uploaded file temporarily to: {temp_pdf_path}")
        with open(temp_pdf_path, "wb") as temp_pdf:
            temp_pdf.write(pdf_content)

        # --- Step 2: Upload the *Temporary File* to Gemini ---
        display_name = pdf_file.filename or "uploaded_exam.pdf"
        uploaded_gemini_file_obj = gemini_utils.upload_pdf_to_gemini(
            pdf_path=temp_pdf_path, # Pass the path to the temporary file
            display_name=display_name
        )
        if not uploaded_gemini_file_obj:
            raise HTTPException(status_code=500, detail="Failed to upload PDF to Gemini File API.")

        # --- Step 3: Generate Lesson using Gemini ---
        lesson_response_model = gemini_utils.generate_structured_lesson(
            uploaded_file=uploaded_gemini_file_obj,
            question_description=question_description,
            model_name="gemini-1.5-flash-latest"
        )

        if not lesson_response_model:
            raise HTTPException(status_code=500, detail="Failed to generate or validate lesson content from Gemini.")

        # --- Step 4: Return Successful Response ---
        print("Successfully generated and validated lesson. Returning to client.")
        return lesson_response_model

    except HTTPException as http_exc:
        raise http_exc # Let FastAPI handle known HTTP errors
    except Exception as e:
        print(f"--- Unexpected Error in /generate-lesson endpoint: {e} ---")
        # import traceback # Uncomment for detailed debugging
        # traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(detail="An unexpected server error occurred.").model_dump()
        )

    finally:
        # --- Step 5: Cleanup ---
        print("--- Endpoint finished, initiating cleanup ---")
        # Delete file from Gemini servers
        if uploaded_gemini_file_obj:
             gemini_utils.delete_uploaded_file(uploaded_gemini_file_obj)
        # Delete the local temporary directory and its contents
        if temp_dir_path and os.path.exists(temp_dir_path):
            try:
                print(f"Removing temporary directory: {temp_dir_path}")
                shutil.rmtree(temp_dir_path)
                print("Temporary directory removed.")
            except Exception as cleanup_error:
                print(f"--- Warning: Failed to remove temporary directory {temp_dir_path}: {cleanup_error} ---")


# --- Run the App (for local development) ---
if __name__ == "__main__":
    print("Starting LessonGenie FastAPI server...")
    # Ensure necessary directories exist
    pathlib.Path(TEMP_DIR_BASE).mkdir(exist_ok=True)
    pathlib.Path("lesson_outputs").mkdir(exist_ok=True) # If you use save_lesson_to_json

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

