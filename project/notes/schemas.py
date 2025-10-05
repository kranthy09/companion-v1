"""
companion/project/notes/schemas.py

Updated Notes schemas with AI fields
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict
from datetime import datetime


# Request Schemas
class NoteCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    content_type: str = Field(default="text", pattern="^(text|markdown|html)$")
    tags: Optional[List[str]] = Field(default_factory=list)

    @field_validator("title", "content")
    @classmethod
    def strip_whitespace(cls, v):
        return v.strip() if v else v


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    content_type: Optional[str] = Field(None, pattern="^(text|markdown|html)$")
    tags: Optional[List[str]] = None

    @field_validator("title", "content")
    @classmethod
    def strip_whitespace(cls, v):
        return v.strip() if v else v


# Response Schemas
class NoteBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    content: str
    content_type: str
    tags: Optional[List[str]]
    words_count: int
    created_at: datetime
    updated_at: datetime


class NoteResponse(BaseModel):
    success: bool
    data: NoteBase
    message: str


class NoteStatsBase(BaseModel):
    total_notes: int
    total_words: int
    content_types: dict
    unique_tags: List[str]
    tags_count: int


class NoteStatsResponse(BaseModel):
    success: bool = True
    data: NoteStatsBase
    message: Optional[str] = None


class NotesListResponse(BaseModel):
    success: bool = True
    data: List[NoteBase]
    total_count: int
    page: int = 1
    page_size: int = 20
    message: Optional[str] = None


class NoteDeleteResponse(BaseModel):
    success: bool = True
    message: str = "Note deleted successfully"


# Error Response
class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


# Filter/Query Schemas
class NoteQueryParams(BaseModel):
    search: Optional[str] = None
    tags: Optional[List[str]] = None
    content_type: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    sort_by: str = Field(
        default="created_at", pattern="^(created_at|updated_at|title)$"
    )
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class EnhancedNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    version_number: int
    created_at: datetime


class QuestionBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    answer: Optional[str]
    created_at: datetime


class QuestionCreate(BaseModel):
    note_id: int
    question_text: str


class QuizQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    options: List[str]


class QuizResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    questions: List[QuizQuestionResponse]
    created_at: datetime


class QuizAnswerSubmit(BaseModel):
    quiz_id: int
    answers: Dict[int, str]  # question_id: selected_answer


class QuizResultDetail(BaseModel):
    is_correct: bool
    explanation: Optional[str] = None


class QuizSubmitResponse(BaseModel):
    quiz_id: int
    correct_count: int
    total_count: int
    results: Dict[int, QuizResultDetail]


class QuizResultItem(BaseModel):
    question_id: int
    is_correct: bool


class QuizResultResponse(BaseModel):
    correct_count: int
    total_count: int
    results: List[QuizResultItem]


class QuizQuestionData(BaseModel):
    question_id: int
    question: str
    options: Dict[str, str]  # {"A": "opt", "B": "opt", ...}


class QuizGenerateResponse(BaseModel):
    task_id: str


class QuizGenerationResult(BaseModel):
    quiz_id: int
    questions: List[QuizQuestionData]
    total: int


class QuizQuestionWithSubmission(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_text: str
    options: List[str]
    user_answer: Optional[str] = None
    is_correct: Optional[bool] = None


class QuizWithSubmission(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    questions: List[QuizQuestionWithSubmission]
    submission: Optional[Dict] = None  # {score, total, submitted_at}


class NoteSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    created_at: datetime


class NoteMetaResponse(BaseModel):
    enhanced_count: int
    quiz_count: int
    question_count: int
    summary_count: int
