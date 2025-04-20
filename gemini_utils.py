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

