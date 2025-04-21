# Codebase Snapshot

Source Directory: `lesson`

## codebase.md

```markdown

```

## extract.py

```python
import os
import argparse


def extract_codebase(md_file, output_dir="extracted_codebase", encoding="utf-8"):
    """Extracts a codebase from a Markdown file."""

    if not os.path.isfile(md_file):
        raise ValueError(f"The provided path '{md_file}' is not a file.")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(md_file, "r", encoding=encoding) as f:
        lines = f.readlines()

    filepath = None
    in_code_block = False
    code_lines = []

    for line in lines:
        if line.startswith("## "):
            # Process previous code block (if any)
            if filepath and code_lines:
                write_code_to_file(output_dir, filepath, code_lines, encoding)
                code_lines = []  # Reset for the next file

            filepath = line[3:].strip()  # Extract filepath
            in_code_block = False  # Reset code block flag

        elif line.startswith("```"):
            if in_code_block:
                # End of code block
                in_code_block = False
                write_code_to_file(output_dir, filepath, code_lines, encoding)
                code_lines = []  # clear the code lines

            else:
                # Start of code block
                in_code_block = True
        elif in_code_block:
            code_lines.append(line)


    # Handle any remaining code block at the end of the file
    if filepath and code_lines:
        write_code_to_file(output_dir, filepath, code_lines, encoding)


def write_code_to_file(output_dir, filepath, code_lines, encoding):
    """Writes the extracted code lines to a file."""

    full_path = os.path.join(output_dir, filepath)
    dir_name = os.path.dirname(full_path)

    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

    try:
        with open(full_path, "w", encoding=encoding) as outfile:
            outfile.writelines(code_lines)
        print(f"Created: {full_path}")
    except Exception as e:
        print(f"Error writing to {full_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Extract a codebase from a Markdown file.")
    parser.add_argument("md_file", help="The path to the Markdown file.")
    parser.add_argument("-o", "--output", default="extracted_codebase", help="The output directory.")
    parser.add_argument("-e", "--encoding", default="utf-8", help="Character encoding for writing files.")
    args = parser.parse_args()

    try:
        extract_codebase(args.md_file, args.output, args.encoding)
        print(f"Codebase extracted to: {args.output}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()


```

## gemini_utils.py

```python
# -*- coding: utf-8 -*-
import os
import pathlib
import json
from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ValidationError
import google.generativeai as genai

# Attempt to import File type hint, fallback to Any
try:
    from google.generativeai.types import File as GeminiFile, GenerationConfig
except ImportError:
    print("Warning: Could not import specific 'File' type from google.generativeai.types.")
    GeminiFile = type("GeminiFile", (), {}) # Dummy type

# Import Pydantic models
from models import LessonResponse, QuestionListResponse, ExtractedQuestionItem

# --- Manual Schemas for Gemini API ---

# --- Schema for Question Extraction ---
extracted_question_item_schema = {
    "type": "OBJECT",
    "properties": {
        "questionId": {"type": "STRING", "description": "A unique identifier you assign to this question (e.g., 'q1', 'q2a')."},
        "questionText": {"type": "STRING", "description": "The full text of the extracted question."}
    },
    "required": ["questionId", "questionText"]
}

question_list_response_schema = {
    "type": "OBJECT",
    "properties": {
        "pdfFileId": {"type": "STRING", "description": "The unique name/ID of the PDF file provided in the input."},
        "questions": {
            "type": "ARRAY",
            "items": extracted_question_item_schema,
            "description": "An array of all questions identified in the document."
        }
    },
    "required": ["pdfFileId", "questions"]
}


# --- Schema for Lesson Generation (Copied from previous working version) ---
step_schema = {
    "type": "OBJECT", "properties": {"stepNumber": {"type": "INTEGER"}, "title": {"type": "STRING"}, "descriptionHtml": {"type": "STRING"}}, "required": ["stepNumber", "title", "descriptionHtml"]
}
visual_aid_schema_props = { "imageUrl": {"type": "STRING", "nullable": True} } # Properties only
lesson_data_schema = {
    "type": "OBJECT",
    "properties": {
        "questionId": {"type": "STRING"}, "questionText": {"type": "STRING"}, "subject": {"type": "STRING"}, "topic": {"type": "STRING"}, "coreConceptHtml": {"type": "STRING"},
        "steps": {"type": "ARRAY", "items": step_schema},
        "visualAid": { "type": "OBJECT", "nullable": True, "properties": { "imageUrl": {"type": "STRING", "nullable": True }, "isPresent": {"type": "BOOLEAN"} } }, # Added isPresent
        "hints": {"type": "ARRAY", "items": {"type": "STRING"}}
    },
    "required": ["questionId", "questionText", "subject", "topic", "coreConceptHtml", "steps", "hints"] # visualAid not required here
}
MANUAL_LESSON_RESPONSE_SCHEMA = {
    "type": "OBJECT", "properties": {"lessonData": lesson_data_schema }, "required": ["lessonData"]
}
# Modify visualAid schema to include isPresent
visual_aid_schema_props_lesson = {
    "imageUrl": {"type": "STRING", "nullable": True },
    "isPresent": {"type": "BOOLEAN"}
}
lesson_data_schema["properties"]["visualAid"]["properties"] = visual_aid_schema_props_lesson
lesson_data_schema["required"].append("visualAid") # Make the object required, but its content optional via nullable/isPresent


# --- Helper Functions ---

def upload_pdf_to_gemini(pdf_path: str, display_name: str) -> Optional[GeminiFile]:
    """Uploads a PDF file (from path) to the Gemini File API."""
    print(f"Uploading file '{pdf_path}' (display name: '{display_name}') to Gemini File API...")
    try:
        if not pathlib.Path(pdf_path).is_file():
             print(f"--- Error: File not found at path: {pdf_path} ---")
             return None
        # Use a descriptive display name if possible
        safe_display_name = display_name or pathlib.Path(pdf_path).name
        uploaded_file = genai.upload_file(
            path=pdf_path,
            display_name=safe_display_name,
            mime_type="application/pdf"
        )
        print(f"Successfully uploaded: {uploaded_file.name} ({uploaded_file.display_name})")
        return uploaded_file
    except Exception as e:
        print(f"--- Error uploading file '{display_name}': {e} ---")
        return None

def extract_questions_from_pdf(
    uploaded_file: GeminiFile,
    model_name: str = "gemini-1.5-flash-latest" # Use a capable model
) -> Optional[QuestionListResponse]:
    """
    Asks Gemini to extract all questions from the PDF and return a structured list.
    """
    print(f"Extracting questions from '{uploaded_file.display_name}' using {model_name}...")
    response_text = None
    try:
        prompt = (
            f"Analyze the provided PDF document '{uploaded_file.display_name}'. "
            "Identify and extract all distinct questions presented in the document. "
            "For each question, assign a unique string ID (e.g., 'q1', 'q2a', 'q3') and extract its full text. "
            f"Return the results as a JSON object conforming to the specified schema. Include the provided PDF file ID '{uploaded_file.name}' in the 'pdfFileId' field."
        )

        generation_config = GenerationConfig(
            response_mime_type='application/json',
            response_schema=question_list_response_schema # Use the manual dictionary schema
        )

        model = genai.GenerativeModel(model_name)
        # Only need the file for question extraction
        contents = [uploaded_file] # If prompt is needed, add it here

        print("Sending request to Gemini API for question extraction...")
        # Add the prompt *after* the file for this task
        response = model.generate_content(
            contents=[uploaded_file, prompt], # File first, then prompt describing the task
            generation_config=generation_config,
            # request_options={"timeout": 600} # Potentially long task
        )

        print("API response received for extraction. Validating structure using Pydantic...")
        response_text = response.text
        validated_response = QuestionListResponse.model_validate_json(response_text)
        # Add the file ID manually if the AI didn't include it (as a fallback)
        if not validated_response.pdfFileId:
             validated_response.pdfFileId = uploaded_file.name
        print(f"Successfully extracted {len(validated_response.questions)} questions.")
        return validated_response

    except ValidationError as e:
        print("--- Pydantic Validation Error during Question Extraction ---")
        print(e.json(indent=2))
        print("--- Raw JSON that failed validation ---")
        print(response_text)
        return None
    except Exception as e:
        print(f"--- An error occurred during question extraction: {type(e).__name__}: {e} ---")
        if response_text: print(f"--- Raw Response Text: {response_text} ---")
        return None

def generate_structured_lesson(
    # uploaded_file: GeminiFile, # Keep this signature if needed elsewhere
    pdf_file_id: str, # Now accept the ID (name)
    selected_question_id: str,
    selected_question_text: Optional[str], # Optional text for better context
    model_name: str = "gemini-1.5-flash-latest"
) -> Optional[LessonResponse]:
    """
    Generates structured lesson JSON for a SPECIFIC question, referencing
    an already uploaded PDF via its File API ID (name).
    """
    print(f"Generating lesson for Q ID '{selected_question_id}' from file '{pdf_file_id}' using {model_name}...")
    response_text = None
    try:
        # Re-construct the File object reference using the name/ID
        # This assumes the file still exists in the File API storage (within 48h usually)
        file_ref = genai.get_file(name=pdf_file_id)
        if not file_ref:
             print(f"--- Error: Could not retrieve file reference for ID: {pdf_file_id} ---")
             return None
        print(f"Retrieved file reference: {file_ref.name} ({file_ref.display_name})")

        # Construct the prompt for generating the lesson for the SPECIFIC question
        question_context = f"question ID '{selected_question_id}'"
        if selected_question_text:
            question_context += f" with text starting: '{selected_question_text[:100]}...'" # Use text snippet for context

        prompt = (
            f"You are an expert tutor AI. Referencing the provided PDF document '{file_ref.display_name}' (ID: {file_ref.name}), "
            f"focus *only* on the question identified by {question_context}. "
            "Generate a detailed, step-by-step educational lesson explaining how to understand and solve that specific question. "
            "Your response MUST strictly adhere to the provided JSON schema. "
            "Use the provided '{selected_question_id}' as the 'questionId' in your response. "
            "Extract the full question text accurately into 'questionText'. "
            "Determine the 'subject' and 'topic' for this question. "
            "Write a clear explanation for 'coreConceptHtml' using HTML tags like <p>, <ul>, <li>, <code>, <strong>. "
            "Provide detailed steps in the 'steps' array, using 'stepNumber', 'title', and 'descriptionHtml' (also allowing HTML). "
            "Identify if a relevant graph or image is directly associated with *this specific question* in the PDF and set 'visualAid.isPresent' to true or false. If true, include the 'visualAid' object with 'imageUrl' set to null. If false, omit 'visualAid' or set it to null. " # Clarify optionality
            "Include helpful 'hints' as a list of strings (can contain simple HTML like <strong>)."
        )

        generation_config = GenerationConfig(
            response_mime_type='application/json',
            response_schema=MANUAL_LESSON_RESPONSE_SCHEMA # Use the manual dictionary schema
        )

        model = genai.GenerativeModel(model_name)
        contents = [file_ref, prompt] # File ref first, then prompt

        print("Sending request to Gemini API for specific lesson generation...")
        response = model.generate_content(
            contents=contents,
            generation_config=generation_config,
            # request_options={"timeout": 600}
        )

        print("API response received for lesson generation. Validating structure using Pydantic...")
        response_text = response.text
        validated_lesson = LessonResponse.model_validate_json(response_text)
        print("Successfully parsed and validated lesson response against Pydantic model.")
        return validated_lesson

    except ValidationError as e:
        print("--- Pydantic Validation Error during Lesson Generation ---")
        print(e.json(indent=2))
        print("--- Raw JSON that failed validation ---")
        print(response_text)
        return None
    except Exception as e:
        print(f"--- An error occurred during specific lesson generation: {type(e).__name__}: {e} ---")
        # Handle specific errors like file not found (genai.exceptions.NotFound) if needed
        if "not found" in str(e).lower() and pdf_file_id in str(e).lower():
            print(f"--- Error: Could not find file {pdf_file_id} in File API. It might have expired (>48h). ---")
        if response_text: print(f"--- Raw Response Text: {response_text} ---")
        return None

# delete_uploaded_file remains the same
def delete_uploaded_file(file_name: Optional[str]): # Accept name directly
    """ Deletes the file from the Gemini File API using its name/ID. """
    if not file_name:
        print("Invalid or missing file name provided for deletion.")
        return

    print(f"Attempting to delete file: {file_name}...")
    try:
        genai.delete_file(file_name)
        print(f"File {file_name} deleted successfully.")
    except Exception as e:
        # Log error but don't stop execution, cleanup is best-effort
        print(f"--- Warning: Failed to delete uploaded file {file_name}: {e} ---")


```

## main.py

```python
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


```

## models.py

```python
# -*- coding: utf-8 -*-
from typing import List, Optional, Union
from pydantic import BaseModel, Field

# --- Models for Lesson Generation Output ---

class StepModel(BaseModel):
    """Represents a single step in the lesson's step-by-step guide."""
    stepNumber: int = Field(..., description="The sequential number of the step.")
    title: str = Field(..., description="The concise title displayed in the header of the step.")
    descriptionHtml: str = Field(..., description="Detailed HTML content for the step's explanation.")

class VisualAidModel(BaseModel):
    """Contains information about any visual aid (image/graph)."""
    imageUrl: Optional[str] = Field(None, description="Placeholder; currently expected to be null.")
    isPresent: bool = Field(False, description="Indicates if a relevant visual was identified.")

class LessonDataModel(BaseModel):
    """Represents the detailed data structure for a single lesson."""
    questionId: str = Field(..., description="Identifier for the specific question being explained.")
    questionText: str = Field(..., description="The exact text of the question being explained.")
    subject: str = Field(..., description="Inferred subject area.")
    topic: str = Field(..., description="Inferred specific topic.")
    coreConceptHtml: str = Field(..., description="HTML content for the core concept.")
    steps: List[StepModel] = Field(..., description="Ordered list of steps to solve.")
    visualAid: Optional[VisualAidModel] = Field(None, description="Optional visual aid info.")
    hints: List[str] = Field(..., description="List of helpful hints.")

class LessonResponse(BaseModel):
    """Overall response structure for a generated lesson."""
    lessonData: LessonDataModel

# --- Models for Question Extraction Output ---

class ExtractedQuestionItem(BaseModel):
    """Represents a single question identified in the PDF."""
    # Use a generic ID first, AI might struggle with exact numbering reliably
    # Could refine prompt later to improve ID extraction
    questionId: str = Field(..., description="An identifier for the question (e.g., 'q1', 'q2a', or simply index).")
    questionText: str = Field(..., description="The extracted text of the question.")

class QuestionListResponse(BaseModel):
    """Response structure containing the list of extracted questions."""
    # Include the File API name/ID so frontend can reference it later
    pdfFileId: str = Field(..., description="The internal identifier (name) of the uploaded PDF file in the File API.")
    questions: List[ExtractedQuestionItem] = Field(..., description="List of questions extracted from the PDF.")

# --- Model for Specific Lesson Request ---

class GenerateLessonRequest(BaseModel):
    """Data sent from frontend to request a specific lesson."""
    pdfFileId: str = Field(..., description="The identifier (name) of the uploaded file from the extraction step.")
    selectedQuestionId: str = Field(..., description="The 'questionId' of the question selected by the user from the extracted list.")
    # Optionally include questionText too, might help AI focus
    selectedQuestionText: Optional[str] = Field(None, description="The text of the selected question (optional, for context).")


# --- Standard Error Model ---
class ErrorResponse(BaseModel):
    """Standard error response structure."""
    detail: str


```

## project.md

```markdown


## templates/index.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LessonGenie - AI Exam Tutor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #f9fafb; }
        .premium-card { background-color: white; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; }
        /* Drop zone styles */
        .file-drop-zone { border: 2px dashed #d1d5db; background-color: #f9fafb; transition: background-color 0.2s ease-in-out, border-color 0.2s ease-in-out; }
        .file-drop-zone:hover { background-color: #f3f4f6; border-color: #6366f1; }
        .file-drop-zone.dragover { background-color: #e0e7ff; border-color: #4f46e5; border-style: solid; }
        /* Skeleton styles */
        .skeleton { background-color: #e5e7eb; border-radius: 4px; animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }
        .skeleton-line { height: 0.75rem; margin-bottom: 0.5rem; }
        .skeleton-line-short { width: 60%; }
        .skeleton-line-long { width: 90%; }
        .skeleton-block { height: 8rem; }
        .skeleton-title { height: 1.5rem; width: 60%; margin-bottom: 1rem; }
        .skeleton-text-short { height: 0.75rem; width: 80%; margin-bottom: 0.5rem; }
        .skeleton-text-long { height: 0.75rem; width: 95%; margin-bottom: 0.5rem; }
        .skeleton-avatar { width: 2.5rem; height: 2.5rem; border-radius: 9999px; }
        /* Question List Skeleton Item */
        .skeleton-list-item { border: 1px solid #e5e7eb; padding: 1rem; border-radius: 0.375rem; display: flex; align-items: center; margin-bottom: 1rem; }
        .skeleton-list-icon { width: 1.5rem; height: 1.5rem; background-color: #d1d5db; border-radius: 4px; margin-left: auto; /* Push icon to the right */ }


        /* Basic hidden utility */
        .hidden { display: none; }
        /* Prose fixes */
        .prose code::before, .prose code::after { content: "" !important; }
        .prose code { background-color: #eef2ff; color: #4338ca; padding: 0.1em 0.4em; border-radius: 4px; font-size: 0.9em; }
        /* Timeline styles */
         .timeline-item::before { content: ''; position: absolute; left: 19px; top: 40px; bottom: 0; width: 2px; background-color: #e5e7eb; z-index: 0; }
         .timeline-item:last-child::before { display: none; }
         .timeline-icon { z-index: 1; }
         .timeline-step-header { background-color: #e0e7ff; border-left: 3px solid #4f46e5; padding: 8px 16px; margin-left: -16px; margin-right: -16px; border-radius: 4px 4px 0 0; }
         .timeline-step-content { padding: 16px; background-color: white; border-radius: 0 0 4px 4px; border: 1px solid #e5e7eb; border-top: none; margin-left: -16px; margin-right: -16px; margin-top: -1px; }
         .step-appear { opacity: 0; transform: translateY(10px); animation: stepFadeIn 0.5s ease-out forwards; }
         @keyframes stepFadeIn { to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="text-gray-800">
    <div class="min-h-screen flex flex-col">
        <header class="bg-white shadow-sm sticky top-0 z-20 border-b border-gray-200">
             <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
                 <h1 class="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">LessonGenie</h1>
             </div>
        </header>

        <main class="flex-grow w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-12">

             <!-- === Upload Section === -->
             <div id="upload-section" class="premium-card p-8 md:p-10 mb-10">
                 <h2 class="text-3xl font-bold mb-2 text-gray-800">1. Upload Your Exam</h2>
                 <p class="text-lg text-gray-500 mb-8">Drop your exam PDF below or click to select a file.</p>

                 <form id="lesson-form">
                     <div id="upload-drop-zone" class="file-drop-zone rounded-xl p-10 md:p-16 text-center cursor-pointer mb-6">
                         <input type="file" id="pdf-file" name="pdf_file" accept="application/pdf" required class="hidden">
                         <svg class="mx-auto h-16 w-16 text-gray-400 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 16.5V9.75m0 0l3 3m-3-3l-3 3M6.75 19.5a4.5 4.5 0 01-1.41-8.775 5.25 5.25 0 0110.233-2.33 3 3 0 013.758 3.848A3.752 3.752 0 0118 19.5H6.75z" /></svg>
                         <p id="drop-zone-text" class="text-lg font-semibold text-gray-700 mb-1">Drag & drop PDF here</p>
                         <p class="text-sm text-gray-500 mb-4">or click to select file</p>
                         <p id="selected-file-name" class="text-sm text-indigo-700 font-medium mt-2"></p>
                     </div>

                     <button type="submit" id="generate-button"
                             class="w-full inline-flex justify-center items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition duration-150 disabled:opacity-50 disabled:cursor-not-allowed">
                         <svg id="button-loading-spinner" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white hidden" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"> <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle> <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path> </svg>
                         <span id="button-text">Extract Questions</span>
                     </button>
                 </form>
                 <div id="upload-error-message" class="mt-4 p-4 bg-red-100 border border-red-300 text-red-700 rounded-md text-sm hidden"></div>
             </div>

             <!-- === Question List Section (Initially Hidden) === -->
             <div id="question-list-section" class="premium-card p-8 md:p-10 mb-10 hidden">
                 <button onclick="resetUI()" class="mb-6 inline-flex items-center text-sm font-semibold text-indigo-600 hover:text-indigo-800 transition duration-150">
                     <svg class="w-5 h-5 mr-1.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
                     Upload Different PDF
                 </button>
                 <h2 class="text-3xl font-bold mb-2 text-gray-800">2. Select a Question</h2>
                 <p class="text-lg text-gray-500 mb-8">We're extracting the questions from your PDF. Click one below when they appear.</p>

                 <!-- Question List Skeleton Loader -->
                 <div id="question-list-skeleton" class="space-y-4">
                     <div class="skeleton-list-item">
                         <div class="flex-1 space-y-2 pr-4">
                             <div class="skeleton skeleton-line skeleton-line-short bg-indigo-200 h-4"></div>
                             <div class="skeleton skeleton-line skeleton-line-long h-3"></div>
                         </div>
                         <div class="skeleton skeleton-list-icon"></div>
                     </div>
                     <div class="skeleton-list-item">
                          <div class="flex-1 space-y-2 pr-4">
                             <div class="skeleton skeleton-line skeleton-line-short bg-indigo-200 h-4"></div>
                             <div class="skeleton skeleton-line skeleton-line-long h-3"></div>
                         </div>
                         <div class="skeleton skeleton-list-icon"></div>
                     </div>
                     <div class="skeleton-list-item">
                          <div class="flex-1 space-y-2 pr-4">
                             <div class="skeleton skeleton-line skeleton-line-short bg-indigo-200 h-4"></div>
                             <div class="skeleton skeleton-line skeleton-line-long h-3"></div>
                         </div>
                         <div class="skeleton skeleton-list-icon"></div>
                     </div>
                 </div>

                 <!-- Actual Question List (Initially Hidden by Skeleton) -->
                 <ul id="extracted-questions" class="space-y-4 hidden">
                     <!-- Populated by JS -->
                 </ul>
                 <div id="question-list-error-message" class="mt-6 p-4 bg-red-100 border border-red-300 text-red-700 rounded-md text-sm hidden"></div>
             </div>

             <!-- === Lesson Display Section (Initially Hidden) === -->
             <div id="lesson-section" class="hidden">
                <!-- Back Buttons -->
                 <button id="back-to-questions-button" onclick="showQuestionList(); hideLesson();" class="mb-6 inline-flex items-center text-sm font-semibold text-indigo-600 hover:text-indigo-800 transition duration-150">
                     <svg class="w-5 h-5 mr-1.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
                    Back to Question List
                </button>
                 <button id="back-to-upload-button" onclick="resetUI()" class="mb-6 ml-4 inline-flex items-center text-sm font-semibold text-gray-600 hover:text-gray-800 transition duration-150">
                     <svg class="w-5 h-5 mr-1.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3" /></svg>
                    Start Over (New PDF)
                </button>

                <!-- Lesson Content Card -->
                 <div class="premium-card">
                     <!-- Header Section (Includes Skeleton) -->
                     <div id="lesson-header-skeleton" class="bg-gradient-to-r from-indigo-200 to-purple-200 p-6 md:p-8 rounded-t-xl skeleton hidden">
                         <div class="skeleton skeleton-title bg-indigo-300 mb-3"></div>
                         <div class="skeleton skeleton-line bg-indigo-100 w-1/3"></div>
                     </div>
                     <div id="lesson-header-content" class="bg-gradient-to-r from-indigo-600 to-purple-600 p-6 md:p-8 rounded-t-xl hidden">
                         <h2 id="lesson-title" class="text-3xl md:text-4xl font-bold text-white mb-2 leading-tight"></h2>
                         <p id="lesson-subheader" class="text-indigo-100 text-sm font-medium"></p>
                     </div>

                     <!-- Body Section (Includes Skeleton & Content Area) -->
                     <div class="p-6 md:p-8">
                         <!-- Lesson Skeleton Loader -->
                         <div id="lesson-skeleton-loader" class="hidden">
                            <!-- Skeleton structure copied from previous response -->
                            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-12">
                                 <div class="lg:col-span-2 space-y-10">
                                     <div> <div class="skeleton skeleton-line w-1/4 mb-4 h-5 bg-gray-300"></div> <div class="skeleton skeleton-text-long h-3"></div> <div class="skeleton skeleton-text-long h-3"></div> <div class="skeleton skeleton-text-short h-3"></div> </div>
                                     <div> <div class="skeleton skeleton-line w-1/3 mb-6 h-5 bg-gray-300"></div> <div class="flex items-start space-x-4 mb-6"> <div class="skeleton skeleton-avatar bg-indigo-200"></div> <div class="flex-1 space-y-2"> <div class="skeleton skeleton-line w-1/2 h-4"></div> <div class="skeleton skeleton-text-long h-3"></div> <div class="skeleton skeleton-text-short h-3"></div> </div> </div> <div class="flex items-start space-x-4 mb-6"> <div class="skeleton skeleton-avatar bg-indigo-200"></div> <div class="flex-1 space-y-2"> <div class="skeleton skeleton-line w-1/2 h-4"></div> <div class="skeleton skeleton-text-long h-3"></div> </div> </div> </div>
                                </div>
                                <div class="lg:col-span-1 space-y-8">
                                     <div> <div class="skeleton skeleton-line w-1/2 mb-3 h-4 bg-gray-300"></div> <div class="skeleton skeleton-block aspect-video"></div> </div>
                                      <div> <div class="skeleton skeleton-line w-1/2 mb-3 h-4 bg-gray-300"></div> <div class="skeleton skeleton-text-short h-3"></div> <div class="skeleton skeleton-text-short h-3"></div> </div>
                                </div>
                             </div>
                         </div>

                         <!-- Actual Lesson Content -->
                         <div id="lesson-content-area" class="hidden">
                            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-12">
                                <div class="lg:col-span-2 space-y-10">
                                    <div> <h3 class="text-xl font-semibold mb-4 flex items-center text-gray-700"><svg class="w-6 h-6 mr-2 text-blue-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" /></svg>Understanding the Concept</h3> <div id="lesson-concept" class="prose prose-indigo max-w-none prose-sm md:prose-base mt-2"></div> </div>
                                    <div> <h3 class="text-xl font-semibold mb-6 flex items-center text-gray-700"><svg class="w-6 h-6 mr-2 text-green-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>Step-by-Step Solution</h3> <div id="lesson-steps-timeline" class="space-y-6 relative"></div> </div>
                                </div>
                                <div class="lg:col-span-1 space-y-8">
                                    <div id="lesson-image-container" class="hidden"> <h4 class="text-lg font-semibold mb-3 text-gray-700">Visual Aid</h4> <div id="lesson-image-placeholder" class="bg-gray-100 aspect-video w-full rounded-lg flex flex-col items-center justify-center text-gray-400 border border-gray-200 shadow-inner p-4 text-center"> <svg class="w-10 h-10 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z" /></svg> <span class="text-sm">A relevant visual was identified.</span> <span class="text-xs mt-1">(Rendering not implemented)</span> </div> </div>
                                    <div id="lesson-hints-container" class="hidden"> <div class="bg-yellow-50 border border-yellow-200 p-5 rounded-lg shadow-sm"> <h4 class="text-lg font-semibold mb-3 flex items-center text-yellow-900"><svg class="w-5 h-5 mr-2 text-yellow-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.355a11.998 11.998 0 01-4.5 0m-7.5-11.978a12.049 12.049 0 014.5 0m-4.5 0a12.048 12.048 0 00-1.605 5.493a1.5 1.5 0 001.605 1.5H6a1.5 1.5 0 001.605-1.5c-.168-1.988-.747-3.829-1.605-5.493M18 12a12.048 12.048 0 01-1.605 5.493A1.5 1.5 0 0118 19.5h.008a1.5 1.5 0 011.605-1.5c.858 1.664 1.437 3.505 1.605 5.493m0-11.978a12.049 12.049 0 00-4.5 0m4.5 0a12.048 12.048 0 011.605 5.493a1.5 1.5 0 01-1.605 1.5H18a1.5 1.5 0 01-1.605-1.5c.168-1.988.747-3.829 1.605-5.493" /></svg>Key Hints & Reminders</h4> <ul id="lesson-hints" class="prose prose-sm prose-yellow max-w-none text-yellow-800 ml-1 space-y-1 list-disc list-inside"></ul> </div> </div>
                                </div>
                            </div>
                         </div>
                         <div id="lesson-error-message" class="mt-6 p-4 bg-red-100 border border-red-300 text-red-700 rounded-md text-sm hidden"></div>
                     </div>
                 </div>
             </div>

        </main>

        <footer class="text-center p-5 text-xs text-gray-500 mt-auto border-t border-gray-200 bg-white">
            LessonGenie &copy; 2024 - AI Exam Tutor
        </footer>
    </div>

    <script src="https://cdn.tailwindcss.com?plugins=typography"></script>
    <script src="/static/js/script.js"></script>
</body>
</html>
```


## static/js/script.js

```javascript
// --- Get references to key HTML elements ---
const lessonForm = document.getElementById('lesson-form');
const pdfFileInput = document.getElementById('pdf-file');
const uploadDropZone = document.getElementById('upload-drop-zone');
const dropZoneText = document.getElementById('drop-zone-text');
const selectedFileNameEl = document.getElementById('selected-file-name');
const generateButton = document.getElementById('generate-button'); // Initial button
const buttonText = document.getElementById('button-text');
const loadingSpinner = document.getElementById('button-loading-spinner');
const uploadErrorMessageDiv = document.getElementById('upload-error-message');
const uploadSection = document.getElementById('upload-section');

// Question List Section elements
const questionListSection = document.getElementById('question-list-section');
const questionListSkeleton = document.getElementById('question-list-skeleton'); // Skeleton div for list
const extractedQuestionsListEl = document.getElementById('extracted-questions'); // Actual list ul
const questionListErrorMessageDiv = document.getElementById('question-list-error-message');

// Lesson Display Section elements
const lessonSection = document.getElementById('lesson-section');
const lessonSkeletonLoader = document.getElementById('lesson-skeleton-loader');
const lessonHeaderSkeleton = document.getElementById('lesson-header-skeleton');
const lessonHeaderContent = document.getElementById('lesson-header-content');
const lessonContentArea = document.getElementById('lesson-content-area');
const lessonTitleEl = document.getElementById('lesson-title');
const lessonSubheaderEl = document.getElementById('lesson-subheader');
const lessonConceptEl = document.getElementById('lesson-concept');
const lessonStepsTimelineEl = document.getElementById('lesson-steps-timeline');
const lessonImageContainerEl = document.getElementById('lesson-image-container');
const lessonHintsContainerEl = document.getElementById('lesson-hints-container');
const lessonHintsEl = document.getElementById('lesson-hints');
const lessonErrorMessageDiv = document.getElementById('lesson-error-message');
const backToQuestionsButton = document.getElementById('back-to-questions-button');
const backToUploadButton = document.getElementById('back-to-upload-button');

// Global state
let currentPdfFileId = null;
let currentExtractedQuestions = [];

// --- Event Listeners ---

if (uploadDropZone) {
    uploadDropZone.addEventListener('click', () => pdfFileInput?.click()); // Use optional chaining

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadDropZone.addEventListener(eventName, preventDefaults, false);
    });
    uploadDropZone.addEventListener('dragenter', handleDragEnter, false);
    uploadDropZone.addEventListener('dragover', handleDragEnter, false); // Treat over same as enter
    uploadDropZone.addEventListener('dragleave', handleDragLeave, false);
    uploadDropZone.addEventListener('drop', handleDrop, false);
}

if (pdfFileInput) {
    pdfFileInput.addEventListener('change', handleFileSelect);
}

if (lessonForm) {
    lessonForm.addEventListener('submit', handleExtractQuestionsSubmit);
}

// --- Event Handler Functions ---

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleDragEnter() {
    if (uploadDropZone) uploadDropZone.classList.add('dragover');
}

function handleDragLeave() {
    if (uploadDropZone) uploadDropZone.classList.remove('dragover');
}

function handleDrop(e) {
    handleDragLeave(); // Remove dragover style
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
        handleFiles(files);
    }
}

function handleFileSelect(event) {
    const files = event.target.files;
    handleFiles(files);
}

function handleFiles(files) {
     if (files.length > 0) {
        const file = files[0];
        if (file.type === "application/pdf") {
             // Check if pdfFileInput exists before trying to assign
             if (pdfFileInput instanceof HTMLInputElement) {
                  // Create a new FileList - necessary for programmatic assignment
                 const dataTransfer = new DataTransfer();
                 dataTransfer.items.add(file);
                 pdfFileInput.files = dataTransfer.files;
             }
             if (selectedFileNameEl) selectedFileNameEl.textContent = `Selected: ${file.name}`;
             hideError("upload");
         } else {
             showError("Please select or drop a PDF file only.", "upload");
             if (pdfFileInput) pdfFileInput.value = ''; // Clear the input
             if (selectedFileNameEl) selectedFileNameEl.textContent = '';
         }
     } else if (selectedFileNameEl) {
        selectedFileNameEl.textContent = '';
     }
}


async function handleExtractQuestionsSubmit(event) {
    event.preventDefault();
    const pdfFile = pdfFileInput?.files[0]; // Use optional chaining

    if (!pdfFile) {
        showError("Please select or drop a PDF file.", "upload");
        return;
    }

    setLoadingState(true, 'Extracting Questions...');
    hideError("upload");
    hideError("question-list");
    hideError("lesson");
    hideLesson(); // Ensure lesson is hidden
    hideUploadForm(); // Hide upload form immediately
    showQuestionList(); // Show the question list section immediately
    showQuestionListSkeleton(); // Show the skeleton for the list

    const formData = new FormData();
    formData.append('pdf_file', pdfFile);

    try {
        const response = await fetch('/extract-questions', { method: 'POST', body: formData });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || `HTTP error! Status: ${response.status}`);
        if (!result.pdfFileId || !result.questions) throw new Error("Invalid data received.");

        console.log("Extracted questions data:", result);
        currentPdfFileId = result.pdfFileId;
        currentExtractedQuestions = result.questions;
        hideQuestionListSkeleton(); // Hide skeleton
        displayQuestionList(result.questions); // Display actual list
        // No need to call showQuestionList() again, it's already visible

    } catch (error) {
        console.error('Error extracting questions:', error);
        hideQuestionListSkeleton(); // Hide skeleton on error
        showError(`Extraction failed: ${error.message}`, "question-list"); // Show error in question list area
    } finally {
        // Button might not be visible anymore, but doesn't hurt to reset
        setLoadingState(false, 'Extract Questions');
    }
}

async function handleQuestionSelection(event) {
    const listItem = event.currentTarget;
    const selectedQuestionId = listItem.dataset.questionId;
    const selectedQuestionText = listItem.dataset.questionText;

    if (!currentPdfFileId || !selectedQuestionId) {
        showError("Missing PDF/Question ID. Please retry.", "lesson"); // Show error in lesson area
        return;
    }

    console.log(`Requesting lesson for Q ID: ${selectedQuestionId} from PDF: ${currentPdfFileId}`);
    hideQuestionList(); // Hide the list view
    showLesson();       // Show the lesson view container
    showSkeletonLoader(); // Show lesson skeleton immediately
    hideError("lesson");  // Hide previous lesson errors


    try {
        const response = await fetch('/generate-specific-lesson', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pdfFileId: currentPdfFileId,
                selectedQuestionId: selectedQuestionId,
                selectedQuestionText: selectedQuestionText
            }),
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || `HTTP error! Status: ${response.status}`);

        console.log("Received specific lesson data:", result);
        displayLesson(result);
        showActualLessonContent(); // Hide skeleton, show content

    } catch (error) {
        console.error('Error generating specific lesson:', error);
        hideSkeletonLoader(); // Hide skeleton
        showError(`Failed to generate lesson: ${error.message}`, "lesson"); // Show error in lesson area
        clearLessonContent(); // Clear any partial content if error occurred
    }
}

// --- Display & Skeleton Functions ---

function displayQuestionList(questions) {
    if (!extractedQuestionsListEl) return;
    extractedQuestionsListEl.innerHTML = ''; // Clear skeleton or old list
    extractedQuestionsListEl.classList.remove('hidden'); // Make sure actual list UL is visible

    if (!questions || questions.length === 0) {
        extractedQuestionsListEl.innerHTML = `<li class="text-gray-500 italic p-4">No questions found in this PDF.</li>`;
        return;
    }

    questions.forEach((q, index) => {
        const li = document.createElement('li');
        const qId = q.questionId || `item-${index}`;
        const qText = q.questionText || "Question text missing";
        li.className = 'border border-gray-200 p-4 rounded-md hover:bg-indigo-50 cursor-pointer transition duration-150 flex justify-between items-center';
        li.innerHTML = `
            <div class="flex-grow mr-4 overflow-hidden">
                <span class="font-semibold text-indigo-700 block text-sm truncate">Detected Question (ID: ${qId})</span>
                <span class="text-gray-800 block mt-1 text-sm">${qText.substring(0, 120)}...</span>
            </div>
            <svg class="w-6 h-6 text-indigo-500 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
        `;
        li.dataset.questionId = qId;
        li.dataset.questionText = qText;
        li.addEventListener('click', handleQuestionSelection);
        extractedQuestionsListEl.appendChild(li);
    });
}

function showQuestionListSkeleton() {
    if (questionListSkeleton) questionListSkeleton.classList.remove('hidden');
    if (extractedQuestionsListEl) extractedQuestionsListEl.classList.add('hidden'); // Hide actual list UL
}

function hideQuestionListSkeleton() {
    if (questionListSkeleton) questionListSkeleton.classList.add('hidden');
}

function displayLesson(lessonResponse) {
    const lessonData = lessonResponse.lessonData;
    if (!lessonData) {
        showError("Received invalid lesson data.", "lesson");
        return;
    }
    // Populate Header
    if(lessonTitleEl) lessonTitleEl.textContent = `Lesson for: ${lessonData.questionText}`;
    if(lessonSubheaderEl) lessonSubheaderEl.textContent = `Subject: ${lessonData.subject} | Topic: ${lessonData.topic} | Q-ID: ${lessonData.questionId}`;
    // Populate Body
    if(lessonConceptEl) lessonConceptEl.innerHTML = lessonData.coreConceptHtml;
    if(lessonStepsTimelineEl) lessonStepsTimelineEl.innerHTML = '';
    let stepDelay = 0;
    const delayIncrement = 0.1;
    lessonData.steps.forEach(step => {
        const stepElement = createTimelineStepElement(step.stepNumber, step.title, step.descriptionHtml, stepDelay);
        if(lessonStepsTimelineEl) lessonStepsTimelineEl.appendChild(stepElement);
        stepDelay += delayIncrement;
    });
    if(lessonImageContainerEl){
        lessonImageContainerEl.classList.toggle('hidden', !(lessonData.visualAid && lessonData.visualAid.isPresent));
    }
    if(lessonHintsEl) lessonHintsEl.innerHTML = '';
    if(lessonHintsContainerEl) lessonHintsContainerEl.classList.add('hidden');
    if (lessonData.hints && lessonData.hints.length > 0) {
        if(lessonHintsContainerEl) lessonHintsContainerEl.classList.remove('hidden');
        lessonData.hints.forEach(hint => {
            const li = document.createElement('li');
            li.innerHTML = hint;
           if(lessonHintsEl) lessonHintsEl.appendChild(li);
        });
    }
}

function createTimelineStepElement(stepNumber, title, descriptionHtml, delay) {
    // Same as before
    const stepElement = document.createElement('div');
    stepElement.className = 'timeline-item relative pl-12 pb-6 step-appear';
    stepElement.style.animationDelay = `${delay}s`;
    const iconSVG = `<div class="timeline-icon absolute left-0 top-0 flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md"><span class="text-white font-bold text-sm">${stepNumber}</span></div>`;
    stepElement.innerHTML = `
        ${iconSVG}
        <div class="ml-3">
             <div class="timeline-step-header mb-0"> <h4 class="text-lg font-semibold text-indigo-800">${title}</h4> </div>
             <div class="timeline-step-content prose prose-sm max-w-none text-gray-600 leading-relaxed"> ${descriptionHtml} </div>
        </div>`;
    return stepElement;
}


// --- UI Visibility & State ---

function setLoadingState(isLoading, text = 'Generate Lesson') {
    if(!generateButton || !buttonText || !loadingSpinner) return;
    generateButton.disabled = isLoading;
    buttonText.textContent = text;
    loadingSpinner.classList.toggle('hidden', !isLoading);
}

function showError(message, type = "upload") {
    const errorDivId = `${type}-error-message`;
    const errorDiv = document.getElementById(errorDivId);
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    } else {
        console.error(`Error div with ID '${errorDivId}' not found!`);
        alert(`Error: ${message}`);
    }
}

function hideError(type = "upload") {
     const errorDivId = `${type}-error-message`;
     const errorDiv = document.getElementById(errorDivId);
     if(errorDiv) {
        errorDiv.classList.add('hidden');
        errorDiv.textContent = '';
     }
}

function showQuestionList() {
    if (questionListSection) {
        questionListSection.classList.remove('hidden');
        questionListSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function hideQuestionList() {
    if (questionListSection) questionListSection.classList.add('hidden');
    hideQuestionListSkeleton(); // Also hide skeleton when hiding the section
    // Don't clear the actual list (extractedQuestionsListEl) here
}

function showLesson() {
    if(lessonSection) {
         lessonSection.classList.remove('hidden');
         // Optional: Scroll only when actual content is shown?
         // lessonSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function hideLesson() {
     if(lessonSection) lessonSection.classList.add('hidden');
     clearLessonContent();
     hideSkeletonLoader();
}

function clearLessonContent() {
     if(lessonHeaderContent) lessonHeaderContent.classList.add('hidden');
     if(lessonContentArea) lessonContentArea.classList.add('hidden');
     if(lessonTitleEl) lessonTitleEl.textContent = '';
     if(lessonSubheaderEl) lessonSubheaderEl.textContent = '';
     if(lessonConceptEl) lessonConceptEl.innerHTML = '';
     if(lessonStepsTimelineEl) lessonStepsTimelineEl.innerHTML = '';
     if(lessonHintsEl) lessonHintsEl.innerHTML = '';
     if(lessonImageContainerEl) lessonImageContainerEl.classList.add('hidden');
     if(lessonHintsContainerEl) lessonHintsContainerEl.classList.add('hidden');
}

function showSkeletonLoader() {
    if (lessonSkeletonLoader) lessonSkeletonLoader.classList.remove('hidden');
    if (lessonHeaderSkeleton) lessonHeaderSkeleton.classList.remove('hidden');
    if (lessonContentArea) lessonContentArea.classList.add('hidden');
    if (lessonHeaderContent) lessonHeaderContent.classList.add('hidden');
}

function hideSkeletonLoader() {
    if (lessonSkeletonLoader) lessonSkeletonLoader.classList.add('hidden');
    if (lessonHeaderSkeleton) lessonHeaderSkeleton.classList.add('hidden');
}

function showActualLessonContent() {
    hideSkeletonLoader();
    if (lessonContentArea) lessonContentArea.classList.remove('hidden');
    if (lessonHeaderContent) lessonHeaderContent.classList.remove('hidden');
    // Scroll into view when actual content is ready
    if(lessonSection) lessonSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function showUploadForm() {
    if(uploadSection) uploadSection.classList.remove('hidden');
}

function hideUploadForm() {
     if(uploadSection) uploadSection.classList.add('hidden');
}

function resetUI() {
    hideLesson();
    hideQuestionList(); // Hides section and skeleton
    if (extractedQuestionsListEl) extractedQuestionsListEl.innerHTML = ''; // Clear list content
    hideError("upload");
    hideError("question-list");
    hideError("lesson");
    if (lessonForm) lessonForm.reset();
    if (selectedFileNameEl) selectedFileNameEl.textContent = '';
    showUploadForm();
    currentPdfFileId = null;
    currentExtractedQuestions = [];
    // Reset button text to initial state
    setLoadingState(false, 'Extract Questions');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- Initial UI State ---
function initializeUI() {
    console.log("Initializing UI...");
    resetUI();
}

initializeUI();

```
```

## requirements.txt

```
google-generativeai
pydantic
fastapi
uvicorn[standard]
python-dotenv
python-multipart
aiofiles # Often needed by FastAPI for async file operations
jinja2 # For HTML templating with FastAPI

```

## snapshot.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Standalone Codebase Snapshot Tool (Concise Commands)

This script provides two main functions, runnable from the command line:
1.  fm <folder>: Creates a single Markdown file snapshot from a source code folder.
2.  mf <markdown_file>: Recreates a folder structure from a Markdown snapshot file.

Usage:
  # Create snapshot FROM 'my_project_folder' TO 'snapshot.md' (Folder -> Markdown)
  python this_script.py fm ./my_project_folder -o snapshot.md

  # Create snapshot with additional ignore patterns
  python this_script.py fm ./proj -o out.md --ignore "*.log" --ignore "temp/"

  # Recreate folder structure FROM 'snapshot.md' TO 'recreated_project' (Markdown -> Folder)
  python this_script.py mf snapshot.md -o ./recreated_project
"""

import os
import mimetypes
import fnmatch
import platform
import argparse
import sys

# --- Configuration ---
ENCODING = 'utf-8'

# --- Default Ignore Patterns ---
DEFAULT_IGNORE_PATTERNS = [
    '.git', '.gitignore', '.gitattributes', '.svn', '.hg', 'node_modules',
    'bower_components', 'venv', '.venv', 'env', '.env', '.env.*', '*.pyc',
    '__pycache__', 'build', 'dist', 'target', '*.o', '*.so', '*.dll', '*.exe',
    '*.class', '*.jar', '*.war', '*.log', '*.tmp', '*.swp', '*.swo', '.DS_Store',
    'Thumbs.db', '.vscode', '.idea', '*.sublime-project', '*.sublime-workspace',
    '*.zip', '*.tar', '*.gz', '*.rar', 'credentials.*', 'config.local.*',
    'settings.local.py',
]

# --- Core Helper Functions (No Changes Here) ---

def is_ignored(relative_path, ignore_patterns):
    normalized_path = relative_path.replace("\\", "/")
    basename = os.path.basename(normalized_path)
    is_case_sensitive_fs = platform.system() != "Windows"
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(basename, pattern) or \
           (not is_case_sensitive_fs and fnmatch.fnmatch(basename.lower(), pattern.lower())):
            return True
        if fnmatch.fnmatch(normalized_path, pattern) or \
           (not is_case_sensitive_fs and fnmatch.fnmatch(normalized_path.lower(), pattern.lower())):
            return True
    return False

def guess_language(filepath):
    mimetypes.init()
    mime_type, _ = mimetypes.guess_type(filepath)
    if mime_type:
        lang_map_mime = {
            "text/x-python": "python", "application/x-python-code": "python",
            "text/javascript": "javascript", "application/javascript": "javascript",
            "text/html": "html", "text/css": "css", "application/json": "json",
            "application/xml": "xml", "text/xml": "xml",
            "text/x-java-source": "java", "text/x-java": "java",
            "text/x-csrc": "c", "text/x-c": "c", "text/x-c++src": "cpp", "text/x-c++": "cpp",
            "application/x-sh": "bash", "text/x-shellscript": "bash",
            "text/markdown": "markdown", "text/x-yaml": "yaml", "application/x-yaml": "yaml",
            "text/plain": ""
        }
        if mime_type in lang_map_mime: return lang_map_mime[mime_type]
        if mime_type.startswith("text/"): return ""
    _, ext = os.path.splitext(filepath.lower())
    lang_map_ext = {
        ".py": "python", ".pyw": "python", ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
        ".html": "html", ".htm": "html", ".css": "css", ".java": "java", ".cpp": "cpp", ".cxx": "cpp",
        ".cc": "cpp", ".hpp": "cpp", ".hxx": "cpp", ".c": "c", ".h": "c", ".cs": "csharp", ".php": "php",
        ".rb": "ruby", ".go": "go", ".rs": "rust", ".ts": "typescript", ".tsx": "typescript",
        ".json": "json", ".xml": "xml", ".yaml": "yaml", ".yml": "yaml", ".sh": "bash", ".bash": "bash",
        ".sql": "sql", ".md": "markdown", ".markdown": "markdown", ".txt": ""
    }
    return lang_map_ext.get(ext, "")

def write_code_to_file(output_dir, relative_filepath, code_lines, encoding=ENCODING):
    safe_relative_path = os.path.normpath(relative_filepath).replace("\\", "/")
    if safe_relative_path.startswith("..") or os.path.isabs(safe_relative_path):
        print(f"[WRITE] [WARN] Skipping potentially unsafe path: {relative_filepath}")
        return False
    abs_output_dir = os.path.abspath(output_dir)
    full_path = os.path.join(abs_output_dir, safe_relative_path)
    abs_full_path = os.path.abspath(full_path)
    if not abs_full_path.startswith(abs_output_dir + os.path.sep) and abs_full_path != abs_output_dir:
        print(f"[WRITE] [ERROR] Security Error: Attempted write outside target directory: {relative_filepath} -> {abs_full_path}")
        return False
    dir_name = os.path.dirname(full_path)
    try:
        if dir_name: os.makedirs(dir_name, exist_ok=True)
        if os.path.isdir(full_path):
             print(f"[WRITE] [ERROR] Cannot write file. Path exists and is a directory: {full_path}")
             return False
        with open(full_path, "w", encoding=encoding) as outfile:
            outfile.writelines(code_lines)
        return True
    except OSError as e:
        print(f"[WRITE] [ERROR] OS Error writing file {full_path}: {e}")
        return False
    except Exception as e:
        print(f"[WRITE] [ERROR] General Error writing file {full_path}: {e}")
        return False

# --- Main Logic Functions (No Changes Here) ---

def create_codebase_snapshot(root_dir, output_file, encoding=ENCODING, base_ignore_patterns=DEFAULT_IGNORE_PATTERNS, user_ignore_patterns=[]):
    processed_files_count = 0
    ignored_items_count = 0
    errors = []
    all_ignore_patterns = list(set(base_ignore_patterns + user_ignore_patterns))
    abs_root = os.path.abspath(root_dir)
    if not os.path.isdir(abs_root):
        print(f"[ERROR] Source directory not found or not a directory: {abs_root}", file=sys.stderr)
        return False, 0, 0, ["Source directory not found."]

    print("-" * 60)
    print(f"Starting snapshot creation (Folder -> Markdown):")
    print(f"  Source: {abs_root}")
    print(f"  Output: {output_file}")
    print(f"  Ignoring: {all_ignore_patterns}")
    print("-" * 60)
    try:
        with open(output_file, "w", encoding=encoding) as md_file:
            md_file.write("# Codebase Snapshot\n\n")
            md_file.write(f"Source Directory: `{os.path.basename(abs_root)}`\n\n")
            for dirpath, dirnames, filenames in os.walk(abs_root, topdown=True):
                dirs_to_remove = set()
                for d in dirnames:
                    rel_dir_path = os.path.relpath(os.path.join(dirpath, d), abs_root)
                    if is_ignored(rel_dir_path, all_ignore_patterns): dirs_to_remove.add(d)
                if dirs_to_remove:
                    ignored_items_count += len(dirs_to_remove)
                    dirnames[:] = [d for d in dirnames if d not in dirs_to_remove]
                filenames.sort()
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    relative_filepath = os.path.relpath(filepath, abs_root).replace("\\", "/")
                    if is_ignored(relative_filepath, all_ignore_patterns):
                        ignored_items_count += 1; continue
                    processed_files_count += 1
                    print(f"[PROCESS] Adding: {relative_filepath}")
                    md_file.write(f"## {relative_filepath}\n\n")
                    try:
                        try:
                             with open(filepath, "r", encoding=encoding) as f_content: content = f_content.read()
                             language = guess_language(filepath)
                             md_file.write(f"```{language}\n{content}\n```\n\n")
                        except UnicodeDecodeError:
                             md_file.write("```\n**Note:** File appears to be binary or uses an incompatible encoding.\nContent not displayed.\n```\n\n")
                             print(f"[WARN] Binary or non-{encoding} file skipped content: {relative_filepath}")
                        except Exception as read_err:
                             errors.append(f"Error reading file '{relative_filepath}': {read_err}")
                             md_file.write(f"```\n**Error reading file:** {read_err}\n```\n\n")
                             print(f"[ERROR] Could not read file: {relative_filepath} - {read_err}")
                    except Exception as e:
                        errors.append(f"Error processing file '{relative_filepath}': {e}")
                        md_file.write(f"```\n**Error processing file:** {e}\n```\n\n")
                        print(f"[ERROR] Processing failed for: {relative_filepath} - {e}")
    except IOError as e:
        print(f"[ERROR] Failed to write snapshot file '{output_file}': {e}", file=sys.stderr)
        return False, processed_files_count, ignored_items_count, [f"IOError writing snapshot: {e}"]
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred during snapshot generation: {e}", file=sys.stderr)
        return False, processed_files_count, ignored_items_count, [f"Unexpected error: {e}"]
    print("-" * 60)
    print(f"Snapshot creation finished.")
    print(f"  Processed: {processed_files_count} files")
    print(f"  Ignored:   {ignored_items_count} items")
    if errors: print(f"  Errors:    {len(errors)}"); [print(f"    - {err}") for err in errors]
    print("-" * 60)
    return True, processed_files_count, ignored_items_count, errors

def extract_codebase(md_file, output_dir, encoding=ENCODING):
    created_files_count = 0; errors = []; file_write_attempts = 0
    abs_output_dir = os.path.abspath(output_dir)
    if not os.path.isfile(md_file):
        print(f"[ERROR] Snapshot file not found: {md_file}", file=sys.stderr)
        return False, 0, ["Snapshot file not found."]
    print("-" * 60); print(f"Starting codebase extraction (Markdown -> Folder):"); print(f"  Snapshot: {md_file}"); print(f"  Output Directory: {abs_output_dir}"); print("-" * 60)
    try:
        os.makedirs(abs_output_dir, exist_ok=True); print(f"[INFO] Ensured output directory exists: {abs_output_dir}")
    except OSError as e: print(f"[ERROR] Failed to create output directory '{abs_output_dir}': {e}", file=sys.stderr); return False, 0, [f"Failed to create output directory: {e}"]
    try:
        with open(md_file, "r", encoding=encoding) as f: lines = f.readlines()
    except Exception as e: print(f"[ERROR] Failed to read snapshot file '{md_file}': {e}", file=sys.stderr); return False, 0, [f"Failed to read snapshot file: {e}"]
    relative_filepath = None; in_code_block = False; code_lines = []; skip_block_content = False
    for line_num, line in enumerate(lines, 1):
        line_stripped = line.strip()
        if line_stripped.startswith("## "):
            if relative_filepath and code_lines and not skip_block_content:
                file_write_attempts += 1
                if write_code_to_file(abs_output_dir, relative_filepath, code_lines, encoding): created_files_count += 1
                else: errors.append(f"Failed write: {relative_filepath} (ended near line {line_num})")
            code_lines = []; relative_filepath = None; in_code_block = False; skip_block_content = False
            new_relative_filepath = line[3:].strip().strip('/').strip('\\')
            if not new_relative_filepath: errors.append(f"Warning: Found '##' header without a filepath on line {line_num}. Skipping.")
            else: relative_filepath = new_relative_filepath
        elif line_stripped.startswith("```"):
            if in_code_block:
                in_code_block = False
                if relative_filepath and code_lines and not skip_block_content:
                     file_write_attempts += 1
                     if write_code_to_file(abs_output_dir, relative_filepath, code_lines, encoding): created_files_count += 1
                     else: errors.append(f"Failed write: {relative_filepath} (block ended line {line_num})")
                elif skip_block_content: pass
                elif relative_filepath and not code_lines:
                    file_write_attempts += 1; print(f"[WARN] Empty code block for {relative_filepath} on line {line_num}. Creating empty file.")
                    if write_code_to_file(abs_output_dir, relative_filepath, [], encoding): created_files_count += 1
                    else: errors.append(f"Failed write (empty): {relative_filepath}")
                elif not relative_filepath and code_lines: errors.append(f"Warning: Code block found ending on line {line_num} without a preceding '## filepath' header. Content ignored.")
                code_lines = []; skip_block_content = False
            else: in_code_block = True; code_lines = []; skip_block_content = False
        elif in_code_block:
            if line_stripped.startswith("**Note:") or line_stripped.startswith("**Error reading file:") or line_stripped.startswith("**Binary File:"):
                 skip_block_content = True; print(f"[INFO] Skipping content block for {relative_filepath} due to marker: {line_stripped[:30]}...")
            if not skip_block_content: code_lines.append(line)
    if relative_filepath and code_lines and not skip_block_content:
        file_write_attempts += 1
        if write_code_to_file(abs_output_dir, relative_filepath, code_lines, encoding): created_files_count += 1
        else: errors.append(f"Failed write (end of file): {relative_filepath}")
    elif relative_filepath and skip_block_content: pass
    print("-" * 60); print(f"Codebase extraction finished."); print(f"  Attempted writes: {file_write_attempts}"); print(f"  Successfully created: {created_files_count} files")
    if errors: print(f"  Errors/Warnings: {len(errors)}"); [print(f"    - {err}") for err in errors]
    print("-" * 60)
    return True, created_files_count, errors


# --- Command Line Interface (Modified for Positional Args) ---
def main():
    parser = argparse.ArgumentParser(
        description="Standalone Codebase Snapshot Tool. Use 'fm <folder>' or 'mf <markdown_file>'.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  python %(prog)s fm ./my_project -o project_snapshot.md
  python %(prog)s mf project_snapshot.md -o ./recreated_project"""
    )

    subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands: fm, mf')

    # --- Sub-parser for fm (Folder to Markdown) ---
    parser_fm = subparsers.add_parser('fm', help='Create Markdown from Folder.')
    # Positional argument for input directory
    parser_fm.add_argument('input_directory', help='Path to the source code directory.')
    # Optional argument for output file
    parser_fm.add_argument('--output', '-o', required=True, dest='output_markdown', help='Path for the output Markdown snapshot file.')
    # Optional ignore patterns (remains the same)
    parser_fm.add_argument('--ignore', action='append', default=[], help='Additional ignore patterns (glob style). Can be used multiple times.')

    # --- Sub-parser for mf (Markdown to Folder) ---
    parser_mf = subparsers.add_parser('mf', help='Create Folder from Markdown.')
    # Positional argument for input markdown file
    parser_mf.add_argument('input_markdown', help='Path to the input Markdown snapshot file.')
    # Optional argument for output directory
    parser_mf.add_argument('--output', '-o', required=True, dest='output_directory', help='Path to the directory where the codebase will be recreated.')

    args = parser.parse_args()

    # --- Execute selected command ---
    if args.command == 'fm':
        print(f"Running: Folder to Markdown (fm)")
        success, processed, ignored, errors = create_codebase_snapshot(
            root_dir=args.input_directory,       # Use positional arg
            output_file=args.output_markdown,    # Use '-o' arg (renamed via dest)
            encoding=ENCODING,
            base_ignore_patterns=DEFAULT_IGNORE_PATTERNS,
            user_ignore_patterns=args.ignore
        )
        if success:
            print(f"\nSuccess! Snapshot created at: {args.output_markdown}")
            print(f"Processed {processed} files, ignored {ignored} items.")
            if errors: print(f"Completed with {len(errors)} errors/warnings during file processing.")
            sys.exit(0)
        else:
            print(f"\nFailed to create snapshot.", file=sys.stderr)
            sys.exit(1)

    elif args.command == 'mf':
        print(f"Running: Markdown to Folder (mf)")
        success, created_count, errors = extract_codebase(
            md_file=args.input_markdown,       # Use positional arg
            output_dir=args.output_directory,  # Use '-o' arg (renamed via dest)
            encoding=ENCODING
        )
        if success:
             print(f"\nSuccess! Codebase extracted to: {args.output_directory}")
             print(f"Created {created_count} files.")
             if errors: print(f"Completed with {len(errors)} errors/warnings during file writing.")
             sys.exit(0)
        else:
            print(f"\nFailed to extract codebase.", file=sys.stderr)
            sys.exit(1)

# --- Main Execution Guard ---
if __name__ == '__main__':
    main()
```

## static/css/style.css

```css
/* Add any custom CSS overrides or styles not easily achievable with Tailwind */
body {
    /* Example: Ensure smooth scrolling if needed */
    /* scroll-behavior: smooth; */
}

/* Fix for potential prose-code spacing issue in some Tailwind versions */
.prose code::before,
.prose code::after {
    content: "" !important;
}

```

## static/js/script.js

```javascript
// --- Get references to key HTML elements ---
const lessonForm = document.getElementById('lesson-form');
const pdfFileInput = document.getElementById('pdf-file');
const uploadDropZone = document.getElementById('upload-drop-zone');
const dropZoneText = document.getElementById('drop-zone-text');
const selectedFileNameEl = document.getElementById('selected-file-name');
const generateButton = document.getElementById('generate-button'); // Initial button
const buttonText = document.getElementById('button-text');
const loadingSpinner = document.getElementById('button-loading-spinner');
const uploadErrorMessageDiv = document.getElementById('upload-error-message');
const uploadSection = document.getElementById('upload-section');

// Question List Section elements
const questionListSection = document.getElementById('question-list-section');
const questionListSkeleton = document.getElementById('question-list-skeleton'); // Skeleton div for list
const extractedQuestionsListEl = document.getElementById('extracted-questions'); // Actual list ul
const questionListErrorMessageDiv = document.getElementById('question-list-error-message');

// Lesson Display Section elements
const lessonSection = document.getElementById('lesson-section');
const lessonSkeletonLoader = document.getElementById('lesson-skeleton-loader');
const lessonHeaderSkeleton = document.getElementById('lesson-header-skeleton');
const lessonHeaderContent = document.getElementById('lesson-header-content');
const lessonContentArea = document.getElementById('lesson-content-area');
const lessonTitleEl = document.getElementById('lesson-title');
const lessonSubheaderEl = document.getElementById('lesson-subheader');
const lessonConceptEl = document.getElementById('lesson-concept');
const lessonStepsTimelineEl = document.getElementById('lesson-steps-timeline');
const lessonImageContainerEl = document.getElementById('lesson-image-container');
const lessonHintsContainerEl = document.getElementById('lesson-hints-container');
const lessonHintsEl = document.getElementById('lesson-hints');
const lessonErrorMessageDiv = document.getElementById('lesson-error-message');
const backToQuestionsButton = document.getElementById('back-to-questions-button');
const backToUploadButton = document.getElementById('back-to-upload-button');

// Global state
let currentPdfFileId = null;
let currentExtractedQuestions = [];

// --- Event Listeners ---

if (uploadDropZone) {
    uploadDropZone.addEventListener('click', () => pdfFileInput?.click()); // Use optional chaining

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadDropZone.addEventListener(eventName, preventDefaults, false);
    });
    uploadDropZone.addEventListener('dragenter', handleDragEnter, false);
    uploadDropZone.addEventListener('dragover', handleDragEnter, false); // Treat over same as enter
    uploadDropZone.addEventListener('dragleave', handleDragLeave, false);
    uploadDropZone.addEventListener('drop', handleDrop, false);
}

if (pdfFileInput) {
    pdfFileInput.addEventListener('change', handleFileSelect);
}

if (lessonForm) {
    lessonForm.addEventListener('submit', handleExtractQuestionsSubmit);
}

// --- Event Handler Functions ---

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleDragEnter() {
    if (uploadDropZone) uploadDropZone.classList.add('dragover');
}

function handleDragLeave() {
    if (uploadDropZone) uploadDropZone.classList.remove('dragover');
}

function handleDrop(e) {
    handleDragLeave(); // Remove dragover style
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
        handleFiles(files);
    }
}

function handleFileSelect(event) {
    const files = event.target.files;
    handleFiles(files);
}

function handleFiles(files) {
     if (files.length > 0) {
        const file = files[0];
        if (file.type === "application/pdf") {
             // Check if pdfFileInput exists before trying to assign
             if (pdfFileInput instanceof HTMLInputElement) {
                  // Create a new FileList - necessary for programmatic assignment
                 const dataTransfer = new DataTransfer();
                 dataTransfer.items.add(file);
                 pdfFileInput.files = dataTransfer.files;
             }
             if (selectedFileNameEl) selectedFileNameEl.textContent = `Selected: ${file.name}`;
             hideError("upload");
         } else {
             showError("Please select or drop a PDF file only.", "upload");
             if (pdfFileInput) pdfFileInput.value = ''; // Clear the input
             if (selectedFileNameEl) selectedFileNameEl.textContent = '';
         }
     } else if (selectedFileNameEl) {
        selectedFileNameEl.textContent = '';
     }
}


async function handleExtractQuestionsSubmit(event) {
    event.preventDefault();
    const pdfFile = pdfFileInput?.files[0]; // Use optional chaining

    if (!pdfFile) {
        showError("Please select or drop a PDF file.", "upload");
        return;
    }

    setLoadingState(true, 'Extracting Questions...');
    hideError("upload");
    hideError("question-list");
    hideError("lesson");
    hideLesson(); // Ensure lesson is hidden
    hideUploadForm(); // Hide upload form immediately
    showQuestionList(); // Show the question list section immediately
    showQuestionListSkeleton(); // Show the skeleton for the list

    const formData = new FormData();
    formData.append('pdf_file', pdfFile);

    try {
        const response = await fetch('/extract-questions', { method: 'POST', body: formData });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || `HTTP error! Status: ${response.status}`);
        if (!result.pdfFileId || !result.questions) throw new Error("Invalid data received.");

        console.log("Extracted questions data:", result);
        currentPdfFileId = result.pdfFileId;
        currentExtractedQuestions = result.questions;
        hideQuestionListSkeleton(); // Hide skeleton
        displayQuestionList(result.questions); // Display actual list
        // No need to call showQuestionList() again, it's already visible

    } catch (error) {
        console.error('Error extracting questions:', error);
        hideQuestionListSkeleton(); // Hide skeleton on error
        showError(`Extraction failed: ${error.message}`, "question-list"); // Show error in question list area
    } finally {
        // Button might not be visible anymore, but doesn't hurt to reset
        setLoadingState(false, 'Extract Questions');
    }
}

async function handleQuestionSelection(event) {
    const listItem = event.currentTarget;
    const selectedQuestionId = listItem.dataset.questionId;
    const selectedQuestionText = listItem.dataset.questionText;

    if (!currentPdfFileId || !selectedQuestionId) {
        showError("Missing PDF/Question ID. Please retry.", "lesson"); // Show error in lesson area
        return;
    }

    console.log(`Requesting lesson for Q ID: ${selectedQuestionId} from PDF: ${currentPdfFileId}`);
    hideQuestionList(); // Hide the list view
    showLesson();       // Show the lesson view container
    showSkeletonLoader(); // Show lesson skeleton immediately
    hideError("lesson");  // Hide previous lesson errors


    try {
        const response = await fetch('/generate-specific-lesson', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pdfFileId: currentPdfFileId,
                selectedQuestionId: selectedQuestionId,
                selectedQuestionText: selectedQuestionText
            }),
        });

        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || `HTTP error! Status: ${response.status}`);

        console.log("Received specific lesson data:", result);
        displayLesson(result);
        showActualLessonContent(); // Hide skeleton, show content

    } catch (error) {
        console.error('Error generating specific lesson:', error);
        hideSkeletonLoader(); // Hide skeleton
        showError(`Failed to generate lesson: ${error.message}`, "lesson"); // Show error in lesson area
        clearLessonContent(); // Clear any partial content if error occurred
    }
}

// --- Display & Skeleton Functions ---

function displayQuestionList(questions) {
    if (!extractedQuestionsListEl) return;
    extractedQuestionsListEl.innerHTML = ''; // Clear skeleton or old list
    extractedQuestionsListEl.classList.remove('hidden'); // Make sure actual list UL is visible

    if (!questions || questions.length === 0) {
        extractedQuestionsListEl.innerHTML = `<li class="text-gray-500 italic p-4">No questions found in this PDF.</li>`;
        return;
    }

    questions.forEach((q, index) => {
        const li = document.createElement('li');
        const qId = q.questionId || `item-${index}`;
        const qText = q.questionText || "Question text missing";
        li.className = 'border border-gray-200 p-4 rounded-md hover:bg-indigo-50 cursor-pointer transition duration-150 flex justify-between items-center';
        li.innerHTML = `
            <div class="flex-grow mr-4 overflow-hidden">
                <span class="font-semibold text-indigo-700 block text-sm truncate">Detected Question (ID: ${qId})</span>
                <span class="text-gray-800 block mt-1 text-sm">${qText.substring(0, 120)}...</span>
            </div>
            <svg class="w-6 h-6 text-indigo-500 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
        `;
        li.dataset.questionId = qId;
        li.dataset.questionText = qText;
        li.addEventListener('click', handleQuestionSelection);
        extractedQuestionsListEl.appendChild(li);
    });
}

function showQuestionListSkeleton() {
    if (questionListSkeleton) questionListSkeleton.classList.remove('hidden');
    if (extractedQuestionsListEl) extractedQuestionsListEl.classList.add('hidden'); // Hide actual list UL
}

function hideQuestionListSkeleton() {
    if (questionListSkeleton) questionListSkeleton.classList.add('hidden');
}

function displayLesson(lessonResponse) {
    const lessonData = lessonResponse.lessonData;
    if (!lessonData) {
        showError("Received invalid lesson data.", "lesson");
        return;
    }
    // Populate Header
    if(lessonTitleEl) lessonTitleEl.textContent = `Lesson for: ${lessonData.questionText}`;
    if(lessonSubheaderEl) lessonSubheaderEl.textContent = `Subject: ${lessonData.subject} | Topic: ${lessonData.topic} | Q-ID: ${lessonData.questionId}`;
    // Populate Body
    if(lessonConceptEl) lessonConceptEl.innerHTML = lessonData.coreConceptHtml;
    if(lessonStepsTimelineEl) lessonStepsTimelineEl.innerHTML = '';
    let stepDelay = 0;
    const delayIncrement = 0.1;
    lessonData.steps.forEach(step => {
        const stepElement = createTimelineStepElement(step.stepNumber, step.title, step.descriptionHtml, stepDelay);
        if(lessonStepsTimelineEl) lessonStepsTimelineEl.appendChild(stepElement);
        stepDelay += delayIncrement;
    });
    if(lessonImageContainerEl){
        lessonImageContainerEl.classList.toggle('hidden', !(lessonData.visualAid && lessonData.visualAid.isPresent));
    }
    if(lessonHintsEl) lessonHintsEl.innerHTML = '';
    if(lessonHintsContainerEl) lessonHintsContainerEl.classList.add('hidden');
    if (lessonData.hints && lessonData.hints.length > 0) {
        if(lessonHintsContainerEl) lessonHintsContainerEl.classList.remove('hidden');
        lessonData.hints.forEach(hint => {
            const li = document.createElement('li');
            li.innerHTML = hint;
           if(lessonHintsEl) lessonHintsEl.appendChild(li);
        });
    }
}

function createTimelineStepElement(stepNumber, title, descriptionHtml, delay) {
    // Same as before
    const stepElement = document.createElement('div');
    stepElement.className = 'timeline-item relative pl-12 pb-6 step-appear';
    stepElement.style.animationDelay = `${delay}s`;
    const iconSVG = `<div class="timeline-icon absolute left-0 top-0 flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md"><span class="text-white font-bold text-sm">${stepNumber}</span></div>`;
    stepElement.innerHTML = `
        ${iconSVG}
        <div class="ml-3">
             <div class="timeline-step-header mb-0"> <h4 class="text-lg font-semibold text-indigo-800">${title}</h4> </div>
             <div class="timeline-step-content prose prose-sm max-w-none text-gray-600 leading-relaxed"> ${descriptionHtml} </div>
        </div>`;
    return stepElement;
}


// --- UI Visibility & State ---

function setLoadingState(isLoading, text = 'Generate Lesson') {
    if(!generateButton || !buttonText || !loadingSpinner) return;
    generateButton.disabled = isLoading;
    buttonText.textContent = text;
    loadingSpinner.classList.toggle('hidden', !isLoading);
}

function showError(message, type = "upload") {
    const errorDivId = `${type}-error-message`;
    const errorDiv = document.getElementById(errorDivId);
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    } else {
        console.error(`Error div with ID '${errorDivId}' not found!`);
        alert(`Error: ${message}`);
    }
}

function hideError(type = "upload") {
     const errorDivId = `${type}-error-message`;
     const errorDiv = document.getElementById(errorDivId);
     if(errorDiv) {
        errorDiv.classList.add('hidden');
        errorDiv.textContent = '';
     }
}

function showQuestionList() {
    if (questionListSection) {
        questionListSection.classList.remove('hidden');
        questionListSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function hideQuestionList() {
    if (questionListSection) questionListSection.classList.add('hidden');
    hideQuestionListSkeleton(); // Also hide skeleton when hiding the section
    // Don't clear the actual list (extractedQuestionsListEl) here
}

function showLesson() {
    if(lessonSection) {
         lessonSection.classList.remove('hidden');
         // Optional: Scroll only when actual content is shown?
         // lessonSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function hideLesson() {
     if(lessonSection) lessonSection.classList.add('hidden');
     clearLessonContent();
     hideSkeletonLoader();
}

function clearLessonContent() {
     if(lessonHeaderContent) lessonHeaderContent.classList.add('hidden');
     if(lessonContentArea) lessonContentArea.classList.add('hidden');
     if(lessonTitleEl) lessonTitleEl.textContent = '';
     if(lessonSubheaderEl) lessonSubheaderEl.textContent = '';
     if(lessonConceptEl) lessonConceptEl.innerHTML = '';
     if(lessonStepsTimelineEl) lessonStepsTimelineEl.innerHTML = '';
     if(lessonHintsEl) lessonHintsEl.innerHTML = '';
     if(lessonImageContainerEl) lessonImageContainerEl.classList.add('hidden');
     if(lessonHintsContainerEl) lessonHintsContainerEl.classList.add('hidden');
}

function showSkeletonLoader() {
    if (lessonSkeletonLoader) lessonSkeletonLoader.classList.remove('hidden');
    if (lessonHeaderSkeleton) lessonHeaderSkeleton.classList.remove('hidden');
    if (lessonContentArea) lessonContentArea.classList.add('hidden');
    if (lessonHeaderContent) lessonHeaderContent.classList.add('hidden');
}

function hideSkeletonLoader() {
    if (lessonSkeletonLoader) lessonSkeletonLoader.classList.add('hidden');
    if (lessonHeaderSkeleton) lessonHeaderSkeleton.classList.add('hidden');
}

function showActualLessonContent() {
    hideSkeletonLoader();
    if (lessonContentArea) lessonContentArea.classList.remove('hidden');
    if (lessonHeaderContent) lessonHeaderContent.classList.remove('hidden');
    // Scroll into view when actual content is ready
    if(lessonSection) lessonSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function showUploadForm() {
    if(uploadSection) uploadSection.classList.remove('hidden');
}

function hideUploadForm() {
     if(uploadSection) uploadSection.classList.add('hidden');
}

function resetUI() {
    hideLesson();
    hideQuestionList(); // Hides section and skeleton
    if (extractedQuestionsListEl) extractedQuestionsListEl.innerHTML = ''; // Clear list content
    hideError("upload");
    hideError("question-list");
    hideError("lesson");
    if (lessonForm) lessonForm.reset();
    if (selectedFileNameEl) selectedFileNameEl.textContent = '';
    showUploadForm();
    currentPdfFileId = null;
    currentExtractedQuestions = [];
    // Reset button text to initial state
    setLoadingState(false, 'Extract Questions');
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- Initial UI State ---
function initializeUI() {
    console.log("Initializing UI...");
    resetUI();
}

initializeUI();


```

## templates/index.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LessonGenie - AI Exam Tutor</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="/static/css/style.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; background-color: #f9fafb; }
        .premium-card { background-color: white; border-radius: 12px; box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05), 0 4px 6px -2px rgba(0, 0, 0, 0.05); border: 1px solid #e5e7eb; }
        /* Drop zone styles */
        .file-drop-zone { border: 2px dashed #d1d5db; background-color: #f9fafb; transition: background-color 0.2s ease-in-out, border-color 0.2s ease-in-out; }
        .file-drop-zone:hover { background-color: #f3f4f6; border-color: #6366f1; }
        .file-drop-zone.dragover { background-color: #e0e7ff; border-color: #4f46e5; border-style: solid; }
        /* Skeleton styles */
        .skeleton { background-color: #e5e7eb; border-radius: 4px; animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: .5; } }
        .skeleton-line { height: 0.75rem; margin-bottom: 0.5rem; }
        .skeleton-line-short { width: 60%; }
        .skeleton-line-long { width: 90%; }
        .skeleton-block { height: 8rem; }
        .skeleton-title { height: 1.5rem; width: 60%; margin-bottom: 1rem; }
        .skeleton-text-short { height: 0.75rem; width: 80%; margin-bottom: 0.5rem; }
        .skeleton-text-long { height: 0.75rem; width: 95%; margin-bottom: 0.5rem; }
        .skeleton-avatar { width: 2.5rem; height: 2.5rem; border-radius: 9999px; }
        .skeleton-list-item { border: 1px solid #e5e7eb; padding: 1rem; border-radius: 0.375rem; display: flex; align-items: center; margin-bottom: 1rem; }
        .skeleton-list-icon { width: 1.5rem; height: 1.5rem; background-color: #d1d5db; border-radius: 4px; margin-left: auto; }

        /* Basic hidden utility */
        .hidden { display: none; }
        /* Prose fixes */
        .prose code::before, .prose code::after { content: "" !important; }
        .prose code { background-color: #eef2ff; color: #4338ca; padding: 0.1em 0.4em; border-radius: 4px; font-size: 0.9em; }
        /* Timeline styles */
         .timeline-item::before { content: ''; position: absolute; left: 19px; top: 40px; bottom: 0; width: 2px; background-color: #e5e7eb; z-index: 0; }
         .timeline-item:last-child::before { display: none; }
         .timeline-icon { z-index: 1; }
         .timeline-step-header { background-color: #e0e7ff; border-left: 3px solid #4f46e5; padding: 8px 16px; margin-left: -16px; margin-right: -16px; border-radius: 4px 4px 0 0; }
         .timeline-step-content { padding: 16px; background-color: white; border-radius: 0 0 4px 4px; border: 1px solid #e5e7eb; border-top: none; margin-left: -16px; margin-right: -16px; margin-top: -1px; }
         .step-appear { opacity: 0; transform: translateY(10px); animation: stepFadeIn 0.5s ease-out forwards; }
         @keyframes stepFadeIn { to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="text-gray-800">
    <div class="min-h-screen flex flex-col">
        <header class="bg-white shadow-sm sticky top-0 z-20 border-b border-gray-200">
             <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
                 <h1 class="text-3xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-purple-600">LessonGenie</h1>
             </div>
        </header>

        <main class="flex-grow w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 md:py-12">

             <!-- === Upload Section === -->
             <div id="upload-section" class="premium-card p-8 md:p-10 mb-10">
                 <h2 class="text-3xl font-bold mb-2 text-gray-800">1. Upload Your Exam</h2>
                 <p class="text-lg text-gray-500 mb-8">Drop your exam PDF below or click to select a file.</p>

                 <form id="lesson-form">
                     <div id="upload-drop-zone" class="file-drop-zone rounded-xl p-10 md:p-16 text-center cursor-pointer mb-6">
                         <input type="file" id="pdf-file" name="pdf_file" accept="application/pdf" required class="hidden">
                         <!-- Heroicon: cloud-arrow-up -->
                         <svg class="mx-auto h-16 w-16 text-gray-400 mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                           <path stroke-linecap="round" stroke-linejoin="round" d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5a4.5 4.5 0 0 1-1.41-8.775 5.25 5.25 0 0 1 10.233-2.33 3 3 0 0 1 3.758 3.848A3.752 3.752 0 0 1 18 19.5H6.75Z" />
                         </svg>
                         <p id="drop-zone-text" class="text-lg font-semibold text-gray-700 mb-1">Drag & drop PDF here</p>
                         <p class="text-sm text-gray-500 mb-4">or click to select file</p>
                         <p id="selected-file-name" class="text-sm text-indigo-700 font-medium mt-2"></p>
                     </div>

                     <button type="submit" id="generate-button"
                             class="w-full inline-flex justify-center items-center px-6 py-3 border border-transparent text-base font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition duration-150 disabled:opacity-50 disabled:cursor-not-allowed">
                         <!-- Loading Spinner SVG (remains the same) -->
                         <svg id="button-loading-spinner" class="animate-spin -ml-1 mr-3 h-5 w-5 text-white hidden" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"> <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle> <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path> </svg>
                         <span id="button-text">Extract Questions</span>
                     </button>
                 </form>
                 <div id="upload-error-message" class="mt-4 p-4 bg-red-100 border border-red-300 text-red-700 rounded-md text-sm hidden"></div>
             </div>

             <!-- === Question List Section (Initially Hidden) === -->
             <div id="question-list-section" class="premium-card p-8 md:p-10 mb-10 hidden">
                 <button onclick="resetUI()" class="mb-6 inline-flex items-center text-sm font-semibold text-indigo-600 hover:text-indigo-800 transition duration-150">
                      <!-- Heroicon: arrow-uturn-left -->
                      <svg class="w-5 h-5 mr-1.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M9 15 3 9m0 0 6-6M3 9h12a6 6 0 0 1 0 12h-3" />
                      </svg>
                     Upload Different PDF
                 </button>
                 <h2 class="text-3xl font-bold mb-2 text-gray-800">2. Select a Question</h2>
                 <p class="text-lg text-gray-500 mb-8">We're extracting the questions from your PDF. Click one below when they appear.</p>

                 <!-- Question List Skeleton Loader -->
                 <div id="question-list-skeleton" class="space-y-4">
                     <!-- Skeleton Item Structure (Remains the same) -->
                     <div class="skeleton-list-item"> <div class="flex-1 space-y-2 pr-4"> <div class="skeleton skeleton-line skeleton-line-short bg-indigo-200 h-4"></div> <div class="skeleton skeleton-line skeleton-line-long h-3"></div> </div> <div class="skeleton skeleton-list-icon"></div> </div>
                     <div class="skeleton-list-item"> <div class="flex-1 space-y-2 pr-4"> <div class="skeleton skeleton-line skeleton-line-short bg-indigo-200 h-4"></div> <div class="skeleton skeleton-line skeleton-line-long h-3"></div> </div> <div class="skeleton skeleton-list-icon"></div> </div>
                     <div class="skeleton-list-item"> <div class="flex-1 space-y-2 pr-4"> <div class="skeleton skeleton-line skeleton-line-short bg-indigo-200 h-4"></div> <div class="skeleton skeleton-line skeleton-line-long h-3"></div> </div> <div class="skeleton skeleton-list-icon"></div> </div>
                 </div>

                 <!-- Actual Question List (Populated by JS) -->
                 <ul id="extracted-questions" class="space-y-4 hidden"> </ul>
                 <div id="question-list-error-message" class="mt-6 p-4 bg-red-100 border border-red-300 text-red-700 rounded-md text-sm hidden"></div>
             </div>

             <!-- === Lesson Display Section (Initially Hidden) === -->
             <div id="lesson-section" class="hidden">
                <!-- Back Buttons -->
                 <button id="back-to-questions-button" onclick="showQuestionList(); hideLesson();" class="mb-6 inline-flex items-center text-sm font-semibold text-indigo-600 hover:text-indigo-800 transition duration-150">
                     <!-- Heroicon: arrow-left -->
                     <svg class="w-5 h-5 mr-1.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" /> </svg>
                    Back to Question List
                </button>
                 <button id="back-to-upload-button" onclick="resetUI()" class="mb-6 ml-4 inline-flex items-center text-sm font-semibold text-gray-600 hover:text-gray-800 transition duration-150">
                     <!-- Heroicon: arrow-uturn-left -->
                     <svg class="w-5 h-5 mr-1.5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" d="M9 15 3 9m0 0 6-6M3 9h12a6 6 0 0 1 0 12h-3" /> </svg>
                    Start Over (New PDF)
                </button>

                <!-- Lesson Content Card -->
                 <div class="premium-card">
                     <!-- Header Section -->
                     <div id="lesson-header-skeleton" class="bg-gradient-to-r from-indigo-200 to-purple-200 p-6 md:p-8 rounded-t-xl skeleton hidden"> <div class="skeleton skeleton-title bg-indigo-300 mb-3"></div> <div class="skeleton skeleton-line bg-indigo-100 w-1/3"></div> </div>
                     <div id="lesson-header-content" class="bg-gradient-to-r from-indigo-600 to-purple-600 p-6 md:p-8 rounded-t-xl hidden"> <h2 id="lesson-title" class="text-3xl md:text-4xl font-bold text-white mb-2 leading-tight"></h2> <p id="lesson-subheader" class="text-indigo-100 text-sm font-medium"></p> </div>

                     <!-- Body Section -->
                     <div class="p-6 md:p-8">
                         <!-- Lesson Skeleton Loader -->
                         <div id="lesson-skeleton-loader" class="hidden"> <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-12"> <div class="lg:col-span-2 space-y-10"> <div> <div class="skeleton skeleton-line w-1/4 mb-4 h-5 bg-gray-300"></div> <div class="skeleton skeleton-text-long h-3"></div> <div class="skeleton skeleton-text-long h-3"></div> <div class="skeleton skeleton-text-short h-3"></div> </div> <div> <div class="skeleton skeleton-line w-1/3 mb-6 h-5 bg-gray-300"></div> <div class="flex items-start space-x-4 mb-6"> <div class="skeleton skeleton-avatar bg-indigo-200"></div> <div class="flex-1 space-y-2"> <div class="skeleton skeleton-line w-1/2 h-4"></div> <div class="skeleton skeleton-text-long h-3"></div> <div class="skeleton skeleton-text-short h-3"></div> </div> </div> <div class="flex items-start space-x-4 mb-6"> <div class="skeleton skeleton-avatar bg-indigo-200"></div> <div class="flex-1 space-y-2"> <div class="skeleton skeleton-line w-1/2 h-4"></div> <div class="skeleton skeleton-text-long h-3"></div> </div> </div> </div> </div> <div class="lg:col-span-1 space-y-8"> <div> <div class="skeleton skeleton-line w-1/2 mb-3 h-4 bg-gray-300"></div> <div class="skeleton skeleton-block aspect-video"></div> </div> <div> <div class="skeleton skeleton-line w-1/2 mb-3 h-4 bg-gray-300"></div> <div class="skeleton skeleton-text-short h-3"></div> <div class="skeleton skeleton-text-short h-3"></div> </div> </div> </div> </div>

                         <!-- Actual Lesson Content -->
                         <div id="lesson-content-area" class="hidden">
                            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8 lg:gap-12">
                                <div class="lg:col-span-2 space-y-10">
                                     <!-- Concept Section -->
                                    <div> <h3 class="text-xl font-semibold mb-4 flex items-center text-gray-700">
                                        <!-- Heroicon: academic-cap -->
                                        <svg class="w-6 h-6 mr-2 text-blue-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.627 48.627 0 0 1 12 20.904a48.627 48.627 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.57 50.57 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" /> </svg>
                                        Understanding the Concept</h3> <div id="lesson-concept" class="prose prose-indigo max-w-none prose-sm md:prose-base mt-2"></div>
                                    </div>
                                     <!-- Steps Section -->
                                    <div> <h3 class="text-xl font-semibold mb-6 flex items-center text-gray-700">
                                        <!-- Heroicon: list-bullet -->
                                        <svg class="w-6 h-6 mr-2 text-green-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 6.75h12M8.25 12h12M8.25 17.25h12M3.75 6.75h.007v.008H3.75V6.75Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0ZM3.75 12h.007v.008H3.75V12Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Zm-.375 5.25h.007v.008H3.75v-.008Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" /> </svg>
                                        Step-by-Step Solution</h3> <div id="lesson-steps-timeline" class="space-y-6 relative"></div>
                                    </div>
                                </div>
                                 <!-- Right Column -->
                                <div class="lg:col-span-1 space-y-8">
                                    <!-- Visual Aid Section -->
                                    <div id="lesson-image-container" class="hidden"> <h4 class="text-lg font-semibold mb-3 text-gray-700">Visual Aid</h4> <div id="lesson-image-placeholder" class="bg-gray-100 aspect-video w-full rounded-lg flex flex-col items-center justify-center text-gray-400 border border-gray-200 shadow-inner p-4 text-center">
                                         <!-- Heroicon: photo -->
                                         <svg class="w-10 h-10 mb-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 0 0 1.5-1.5V6a1.5 1.5 0 0 0-1.5-1.5H3.75A1.5 1.5 0 0 0 2.25 6v12a1.5 1.5 0 0 0 1.5 1.5Zm10.5-11.25h.008v.008h-.008V8.25Zm.375 0a.375.375 0 1 1-.75 0 .375.375 0 0 1 .75 0Z" /> </svg>
                                         <span class="text-sm">A relevant visual was identified.</span> <span class="text-xs mt-1">(Rendering not implemented)</span> </div>
                                    </div>
                                     <!-- Hints Section -->
                                    <div id="lesson-hints-container" class="hidden"> <div class="bg-yellow-50 border border-yellow-200 p-5 rounded-lg shadow-sm"> <h4 class="text-lg font-semibold mb-3 flex items-center text-yellow-900">
                                        <!-- Heroicon: light-bulb -->
                                        <svg class="w-5 h-5 mr-2 text-yellow-600 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189a6.01 6.01 0 0 1-1.5-.189m3.75 7.478a12.06 12.06 0 0 1-4.5 0m3.75 2.355a11.998 11.998 0 0 1-4.5 0m-7.5-11.978a12.049 12.049 0 0 1 4.5 0m-4.5 0a12.048 12.048 0 0 0-1.605 5.493a1.5 1.5 0 0 0 1.605 1.5H6a1.5 1.5 0 0 0 1.605-1.5c-.168-1.988-.747-3.829-1.605-5.493M18 12a12.048 12.048 0 0 1-1.605 5.493A1.5 1.5 0 0 1 18 19.5h.008a1.5 1.5 0 0 1 1.605-1.5c.858 1.664 1.437 3.505 1.605 5.493m0-11.978a12.049 12.049 0 0 0-4.5 0m4.5 0a12.048 12.048 0 0 1 1.605 5.493a1.5 1.5 0 0 1-1.605 1.5H18a1.5 1.5 0 0 1-1.605-1.5c.168-1.988.747-3.829 1.605-5.493" /> </svg>
                                        Key Hints & Reminders</h4> <ul id="lesson-hints" class="prose prose-sm prose-yellow max-w-none text-yellow-800 ml-1 space-y-1 list-disc list-inside"></ul> </div>
                                    </div>
                                </div>
                            </div>
                         </div>
                         <div id="lesson-error-message" class="mt-6 p-4 bg-red-100 border border-red-300 text-red-700 rounded-md text-sm hidden"></div>
                     </div>
                 </div>
             </div>

        </main>

        <footer class="text-center p-5 text-xs text-gray-500 mt-auto border-t border-gray-200 bg-white">
            LessonGenie © 2024 - AI Exam Tutor
        </footer>
    </div>

    <script src="https://cdn.tailwindcss.com?plugins=typography"></script>
    <script src="/static/js/script.js"></script>
</body>
</html>
```

## templates/landing.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LessonGenie - Your AI Exam Paper Tutor</title>
    <!-- Tailwind CSS via CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Google Fonts (Inter) -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        /* Base styles */
        body { font-family: 'Inter', sans-serif; scroll-behavior: smooth; }
        /* Custom gradient or theme colors if needed */
        .gradient-text { background: linear-gradient(to right, #4f46e5, #7c3aed); -webkit-background-clip: text; background-clip: text; color: transparent; }
        /* Button styles (consistent with app) */
        .premium-button { display: inline-block; padding: 10px 24px; border-radius: 8px; font-weight: 600; text-align: center; transition: all 0.2s ease-in-out; box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px 0 rgba(0,0,0,0.06); }
        .premium-button-primary { background-color: #4f46e5; color: white; border: 1px solid transparent;}
        .premium-button-primary:hover { background-color: #4338ca; transform: translateY(-1px); box-shadow: 0 4px 8px 0 rgba(0,0,0,0.15), 0 2px 4px 0 rgba(0,0,0,0.1); }
        .premium-button-secondary { background-color: white; color: #4f46e5; border: 1px solid #e0e7ff; }
        .premium-button-secondary:hover { background-color: #f9fafb; }
        /* Simple animation */
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        .fade-in-up { animation: fadeInUp 0.6s ease-out forwards; }
        /* Add delay classes if needed: .animation-delay-200 { animation-delay: 0.2s; } etc. */
         /* Added some basic icon sizing consistency */
        .feature-icon svg { width: 2rem; height: 2rem; } /* w-8 h-8 */
        .logo-icon svg { width: 2rem; height: 2rem; } /* w-8 h-8 */

    </style>
</head>
<body class="bg-white text-gray-800 antialiased">

    <!-- Header -->
    <header class="sticky top-0 z-30 bg-white/80 backdrop-blur-md shadow-sm border-b border-gray-200">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div class="flex justify-between items-center py-4">
                <!-- Logo/Brand Name -->
                <div class="flex justify-start items-center lg:w-0 lg:flex-1">
                    <a href="#" class="flex items-center space-x-2">
                        <!-- Heroicon: academic-cap (as logo placeholder) -->
                         <span class="logo-icon text-indigo-600">
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-8 h-8">
                              <path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.627 48.627 0 0 1 12 20.904a48.627 48.627 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.57 50.57 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" />
                            </svg>
                         </span>
                        <span class="text-2xl font-extrabold gradient-text">LessonGenie</span>
                    </a>
                </div>
                <!-- Navigation / CTA -->
                <div class="flex items-center justify-end md:flex-1 lg:w-0">
                    <!-- Link to your actual app -->
                    <!-- *** FIXED BUTTON *** -->
                    <a href="/" class="premium-button premium-button-primary">
                        Launch App
                    </a>
                </div>
            </div>
        </div>
    </header>

    <main>
        <!-- Hero Section -->
        <section class="relative py-20 md:py-32 bg-gradient-to-b from-indigo-50 to-white overflow-hidden">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
                <div class="fade-in-up">
                    <h1 class="text-4xl md:text-5xl lg:text-6xl font-extrabold text-gray-900 tracking-tight mb-4">
                        Stop Dreading Exams.<br> <span class="gradient-text">Master Them with AI.</span>
                    </h1>
                    <p class="mt-3 max-w-md mx-auto text-base text-gray-500 sm:text-lg md:mt-5 md:text-xl md:max-w-3xl mb-10">
                        LessonGenie transforms your past exam papers into clear, interactive lessons. Understand concepts, identify weak spots, and ace your tests – effortlessly.
                    </p>
                    <div class="mt-5 max-w-md mx-auto sm:flex sm:justify-center md:mt-8">
                        <div class="rounded-md shadow">
                             <!-- *** FIXED BUTTON *** -->
                            <a href="/" class="w-full premium-button premium-button-primary text-base px-8 py-3">
                                Try LessonGenie Now
                            </a>
                        </div>
                        <!-- Optional secondary button -->
                        <!-- <div class="mt-3 rounded-md shadow sm:mt-0 sm:ml-3"> <a href="#features" class="w-full premium-button premium-button-secondary text-base px-8 py-3"> Learn More </a> </div> -->
                    </div>
                </div>
                 <div class="mt-16 fade-in-up" style="animation-delay: 0.2s;">
                    <div class="relative mx-auto w-full max-w-3xl h-64 bg-gray-200 rounded-lg shadow-lg flex items-center justify-center text-gray-400 border border-gray-300">
                         <!-- Placeholder Icon -->
                         <svg class="w-16 h-16" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></path></svg>
                         <span class="ml-2">App Preview Placeholder</span>
                    </div>
                </div>
            </div>
        </section>

        <!-- Features Section -->
        <section id="features" class="py-16 md:py-24 bg-white">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="text-center mb-16">
                    <h2 class="text-base text-indigo-600 font-semibold tracking-wide uppercase">Features</h2>
                    <p class="mt-2 text-3xl lg:text-4xl font-extrabold text-gray-900 tracking-tight">
                        Everything You Need to Succeed
                    </p>
                </div>

                <div class="grid grid-cols-1 gap-12 md:grid-cols-2 lg:grid-cols-3">
                    <!-- Feature 1: PDF Upload -->
                    <div class="text-center fade-in-up">
                        <div class="feature-icon flex items-center justify-center h-16 w-16 rounded-full bg-indigo-100 text-indigo-600 mx-auto mb-5">
                             <!-- Heroicon: document-arrow-up -->
                             <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m.75 12 3 3m0 0 3-3m-3 3v-6m-1.5-9H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" /> </svg>
                        </div>
                        <h3 class="text-xl font-semibold text-gray-900 mb-2">Smart PDF Upload</h3>
                        <p class="text-base text-gray-500">Simply upload your past exam paper (PDF). LessonGenie automatically extracts questions, images, and graphs.</p>
                    </div>

                    <!-- Feature 2: AI Explanations -->
                    <div class="text-center fade-in-up" style="animation-delay: 0.1s;">
                        <div class="feature-icon flex items-center justify-center h-16 w-16 rounded-full bg-indigo-100 text-indigo-600 mx-auto mb-5">
                            <!-- Heroicon: chat-bubble-left-right -->
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3.1-3.102a1.125 1.125 0 0 0-.794-.332C8.35 16.425 6.75 15.17 6.75 13.5v-4.286c0-.97.616-1.813 1.5-2.097m6.75 0a48.667 48.667 0 0 0-7.5 0m7.5 0a48.667 48.667 0 0 1-7.5 0M12 12.75h.008v.008H12v-.008Z" /> </svg>
                         </div>
                        <h3 class="text-xl font-semibold text-gray-900 mb-2">Clear AI Explanations</h3>
                        <p class="text-base text-gray-500">Ask for help on any question. Get instant, easy-to-understand explanations generated by our advanced AI tutor.</p>
                    </div>

                    <!-- Feature 3: Interactive Lessons -->
                    <div class="text-center fade-in-up" style="animation-delay: 0.2s;">
                         <div class="feature-icon flex items-center justify-center h-16 w-16 rounded-full bg-indigo-100 text-indigo-600 mx-auto mb-5">
                            <!-- Heroicon: academic-cap -->
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"> <path stroke-linecap="round" stroke-linejoin="round" d="M4.26 10.147a60.438 60.438 0 0 0-.491 6.347A48.627 48.627 0 0 1 12 20.904a48.627 48.627 0 0 1 8.232-4.41 60.46 60.46 0 0 0-.491-6.347m-15.482 0a50.57 50.57 0 0 0-2.658-.813A59.906 59.906 0 0 1 12 3.493a59.903 59.903 0 0 1 10.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.697 50.697 0 0 1 12 13.489a50.702 50.702 0 0 1 7.74-3.342M6.75 15a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm0 0v-3.675A55.378 55.378 0 0 1 12 8.443m-7.007 11.55A5.981 5.981 0 0 0 6.75 15.75v-1.5" /> </svg>
                        </div>
                        <h3 class="text-xl font-semibold text-gray-900 mb-2">Interactive Step-by-Step</h3>
                        <p class="text-base text-gray-500">Follow structured, visual lessons presented in a clear timeline format. Understand the 'why' behind each step.</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- How It Works Section -->
        <section class="py-16 md:py-24 bg-gray-50">
             <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
                 <div class="text-center mb-16">
                     <h2 class="text-base text-indigo-600 font-semibold tracking-wide uppercase">How It Works</h2>
                     <p class="mt-2 text-3xl lg:text-4xl font-extrabold text-gray-900 tracking-tight">
                         Get Help in 3 Simple Steps
                     </p>
                 </div>
                 <div class="flex flex-col md:flex-row justify-center items-start space-y-8 md:space-y-0 md:space-x-12 lg:space-x-16">
                     <!-- Step 1 -->
                     <div class="text-center flex-1 fade-in-up">
                          <div class="flex items-center justify-center h-12 w-12 rounded-full bg-indigo-600 text-white font-bold text-xl mx-auto mb-4">1</div>
                          <h3 class="text-lg font-semibold text-gray-900 mb-2">Upload PDF</h3>
                          <p class="text-base text-gray-500">Drag & drop or select your exam paper file.</p>
                     </div>
                      <!-- Step 2 -->
                     <div class="text-center flex-1 fade-in-up" style="animation-delay: 0.15s;">
                          <div class="flex items-center justify-center h-12 w-12 rounded-full bg-indigo-600 text-white font-bold text-xl mx-auto mb-4">2</div>
                          <h3 class="text-lg font-semibold text-gray-900 mb-2">Select Question</h3>
                          <p class="text-base text-gray-500">Choose the question you're stuck on from the extracted list.</p>
                     </div>
                      <!-- Step 3 -->
                     <div class="text-center flex-1 fade-in-up" style="animation-delay: 0.3s;">
                          <div class="flex items-center justify-center h-12 w-12 rounded-full bg-indigo-600 text-white font-bold text-xl mx-auto mb-4">3</div>
                          <h3 class="text-lg font-semibold text-gray-900 mb-2">Learn & Master</h3>
                          <p class="text-base text-gray-500">Receive an instant, interactive lesson explaining the concept and solution.</p>
                     </div>
                 </div>
             </div>
        </section>

         <!-- Call to Action Section -->
         <section class="bg-white py-20">
            <div class="max-w-4xl mx-auto text-center px-4 sm:px-6 lg:px-8">
                 <h2 class="text-3xl font-extrabold text-gray-900 sm:text-4xl">
                    Ready to Transform Your Study Sessions?
                 </h2>
                 <p class="mt-4 text-lg leading-6 text-gray-500">
                    Stop guessing and start understanding. Upload your first exam paper today!
                 </p>
                 <div class="mt-8 flex justify-center">
                     <div class="inline-flex rounded-md shadow">
                        <!-- *** FIXED BUTTON *** -->
                        <a href="/" class="premium-button premium-button-primary text-base px-8 py-3">
                             Get Started for Free
                         </a>
                     </div>
                 </div>
            </div>
         </section>

    </main>

    <!-- Footer -->
    <footer class="bg-gray-100 border-t border-gray-200">
        <div class="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8 text-center">
             <p class="text-base text-gray-500">
                © 2024 LessonGenie. All rights reserved.
             </p>
            <!-- Optional links -->
             <!-- <div class="mt-4 space-x-6"> <a href="#" class="text-sm text-gray-500 hover:text-gray-900">Privacy Policy</a> <a href="#" class="text-sm text-gray-500 hover:text-gray-900">Terms of Service</a> </div> -->
        </div>
    </footer>

</body>
</html>
```

