import os
import pathlib
import json
from typing import List, Optional, Union # Keep Union for Pydantic validation step if needed elsewhere
from pydantic import BaseModel, Field, ValidationError # Keep for validation AFTER response
import google.generativeai as genai

# Try importing the specific File type, fallback to Any
try:
    from google.generativeai.types import File as GeminiFile, GenerationConfig
except ImportError:
    print("Warning: Could not import specific 'File' type from google.generativeai.types.")
    GeminiFile = type("GeminiFile", (), {}) # Create a dummy type to avoid errors if import fails


# --- 1. Pydantic Models (Used for VALIDATING the response, not defining the request schema) ---
# These remain the same as they define our application's desired structure.

class StepModel(BaseModel):
    stepNumber: int
    title: str
    descriptionHtml: str

class VisualAidModel(BaseModel):
    # Make imageUrl optional in Pydantic model validation
    imageUrl: Optional[str] = Field(None) # Or just Optional[str] = None

class LessonDataModel(BaseModel):
    questionId: str
    questionText: str
    subject: str
    topic: str
    coreConceptHtml: str
    steps: List[StepModel]
    # Make visualAid optional in Pydantic model validation
    visualAid: Optional[VisualAidModel] = Field(None)
    hints: List[str]

class LessonResponse(BaseModel):
    lessonData: LessonDataModel

# --- 2. Manual Schema Definition (Dictionary Format for Gemini API) ---
# This explicitly defines the structure Gemini should follow.

# Corresponds to StepModel
step_schema = {
    "type": "OBJECT",
    "properties": {
        "stepNumber": {"type": "INTEGER"},
        "title": {"type": "STRING"},
        "descriptionHtml": {"type": "STRING"}
    },
    "required": ["stepNumber", "title", "descriptionHtml"]
}

# Corresponds to VisualAidModel
visual_aid_schema = {
    "type": "OBJECT",
    "properties": {
        # NOTE: imageUrl is the ONLY field here and it's OPTIONAL
        # We mark it nullable in the API schema.
        "imageUrl": {"type": "STRING", "nullable": True}
    },
    # Since imageUrl is optional, there are no 'required' fields within visualAid itself.
    # The 'visualAid' object itself is optional within LessonDataModel below.
}

# Corresponds to LessonDataModel
lesson_data_schema = {
    "type": "OBJECT",
    "properties": {
        "questionId": {"type": "STRING"},
        "questionText": {"type": "STRING"},
        "subject": {"type": "STRING"},
        "topic": {"type": "STRING"},
        "coreConceptHtml": {"type": "STRING"},
        "steps": {
            "type": "ARRAY",
            "items": step_schema # Use the nested step schema definition
        },
        # Define visualAid here, marking the OBJECT itself as nullable
        "visualAid": {
            "type": "OBJECT",    # Must specify type OBJECT here
            "nullable": True,   # Mark the object itself as optional/nullable
            "properties": visual_aid_schema["properties"] # Reference its properties
            # No 'required' needed here as imageUrl inside is optional
        },
        "hints": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        }
    },
    "required": [ # List required fields for the LessonData object
        "questionId",
        "questionText",
        "subject",
        "topic",
        "coreConceptHtml",
        "steps",
        "hints"
        # 'visualAid' is NOT required here because the object itself is optional.
    ]
}

# Corresponds to the top-level LessonResponse structure
# This is the final schema dictionary passed to the API.
MANUAL_LESSON_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "lessonData": lesson_data_schema # Reference the nested lesson data schema
    },
    "required": ["lessonData"] # The top-level 'lessonData' key is required.
}


# --- 3. Helper Functions ---

def upload_pdf_to_gemini(pdf_path: str, display_name: str) -> Optional[GeminiFile]:
    """Uploads a PDF file (from path) to the Gemini File API."""
    print(f"Uploading file '{pdf_path}' (display name: '{display_name}') to Gemini File API...")
    try:
        if not pathlib.Path(pdf_path).is_file():
             print(f"--- Error: File not found at path: {pdf_path} ---")
             return None
        uploaded_file = genai.upload_file(
            path=pdf_path,
            display_name=display_name,
            mime_type="application/pdf"
        )
        print(f"Successfully uploaded: {uploaded_file.name} ({uploaded_file.display_name})")
        return uploaded_file
    except Exception as e:
        print(f"--- Error uploading file '{display_name}': {e} ---")
        return None

def generate_structured_lesson(
    uploaded_file: GeminiFile,
    question_description: str,
    model_name: str = "gemini-1.5-flash-latest"
) -> Optional[LessonResponse]:
    """
    Generates structured lesson JSON using Gemini API based on an uploaded PDF,
    a question description, and a MANUAL dictionary schema.
    Validates the response using Pydantic models AFTER receiving it.
    """
    print(f"Generating lesson for '{question_description}' using {model_name}...")
    if not uploaded_file or not hasattr(uploaded_file, 'display_name'):
         print("--- Error: Invalid or incomplete uploaded file object provided. ---")
         return None

    response_text = None # Initialize in case API call fails before response is assigned

    try:
        # Construct the prompt, ensuring instructions match the manual schema expectations
        prompt = (
            f"You are an expert tutor AI. Analyze the provided PDF document named '{uploaded_file.display_name}'. "
            f"Within that document, locate the question best described as: '{question_description}'. "
            "Once located, generate a detailed, step-by-step educational lesson explaining how to understand and solve that specific question. "
            "Your response MUST strictly adhere to the provided JSON schema. "
            "Extract the question text accurately into 'questionText'. "
            "The 'questionId' field should be the number/label (like '3', '4.1', '6b') extracted from the document as a STRING. " # Emphasize string
            "Determine the 'subject' and 'topic'. "
            "Write a clear explanation for 'coreConceptHtml' using HTML tags like <p>, <ul>, <li>, <code>, <strong>. "
            "Provide detailed steps in the 'steps' array, using 'stepNumber', 'title', and 'descriptionHtml' (also allowing HTML). "
            "If there is NO relevant graph or image directly associated with *this specific question* in the PDF, OMIT the 'visualAid' object entirely or set it to null. If there IS a visual aid, include the 'visualAid' object and set its 'imageUrl' field to null (as we are not extracting URLs). " # Clarify handling of optional object
            "Include helpful 'hints' as a list of strings (can contain simple HTML like <strong>)."
        )

        # Configure for JSON output using the MANUAL dictionary schema
        generation_config = GenerationConfig(
            response_mime_type='application/json',
            response_schema=MANUAL_LESSON_RESPONSE_SCHEMA # Use the dictionary schema
            # temperature=0.7 # Optional: Adjust creativity/determinism
        )

        model = genai.GenerativeModel(model_name)
        contents = [uploaded_file, prompt]

        print("Sending request to Gemini API with manual dictionary schema...")
        response = model.generate_content(
            contents=contents,
            generation_config=generation_config,
            # request_options={"timeout": 600}
        )

        # --- Process and Validate the Response using Pydantic ---
        print("API response received. Validating structure using Pydantic...")
        response_text = response.text # Store text for potential error reporting

        # Use Pydantic to parse and validate the JSON response against the Pydantic models
        # This confirms Gemini produced JSON matching *our application's expectation*
        validated_lesson = LessonResponse.model_validate_json(response_text) # Pydantic V2+ method

        print("Successfully parsed and validated response against Pydantic model.")
        return validated_lesson

    except ValidationError as e:
        print("--- Pydantic Validation Error ---")
        print("Gemini produced JSON, but it didn't match the Pydantic model structure.")
        print(e.json(indent=2))
        print("--- Raw JSON that failed validation ---")
        print(response_text) # Print the text that failed validation
        return None
    except json.JSONDecodeError:
        print("--- JSON Decode Error ---")
        print("The API response was not valid JSON, despite requesting it.")
        print("Response Text:", response_text)
        return None
    except Exception as e:
        # Handle other potential errors (API errors, network issues, etc.)
        print(f"--- An error occurred during Gemini lesson generation: {type(e).__name__}: {e} ---")
        # Check if the error message indicates a schema issue from the API side
        if "schema" in str(e).lower() or "field" in str(e).lower():
             print("This might indicate an issue with how the API interprets the provided dictionary schema.")
        # Print raw text if available
        if response_text:
             print("--- Raw Response Text at time of error ---")
             print(response_text)
        return None

# delete_uploaded_file remains the same as the previous correct version
def delete_uploaded_file(file_object: Optional[GeminiFile]):
    """ Deletes the file from the Gemini File API. """
    if not file_object or not hasattr(file_object, 'name') or not file_object.name:
        print("Invalid or missing file object provided for deletion.")
        return

    file_name = file_object.name
    print(f"Attempting to delete file: {file_name}...")
    try:
        genai.delete_file(file_name)
        print(f"File {file_name} deleted successfully.")
    except Exception as e:
        print(f"--- Warning: Failed to delete uploaded file {file_name}: {e} ---")