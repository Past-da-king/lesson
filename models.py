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

