// Get references to key HTML elements
const lessonForm = document.getElementById('lesson-form');
const pdfFileInput = document.getElementById('pdf-file');
// const questionDescriptionInput = document.getElementById('question-description'); // No longer needed here
const generateButton = document.getElementById('generate-button'); // This button now triggers EXTRACTION
const buttonText = document.getElementById('button-text');
const loadingSpinner = document.getElementById('button-loading-spinner');
// REMOVED: const errorMessageDiv = document.getElementById('error-message'); // This ID doesn't exist
const uploadSection = document.getElementById('upload-section');

// New section for displaying extracted questions
const questionListSection = document.getElementById('question-list-section');
const extractedQuestionsListEl = document.getElementById('extracted-questions');
const questionListLoadingEl = document.getElementById('question-list-loading'); // Ensure this ID exists if used

// Lesson display section
const lessonSection = document.getElementById('lesson-section');
const lessonTitleEl = document.getElementById('lesson-title');
const lessonSubheaderEl = document.getElementById('lesson-subheader');
const lessonConceptEl = document.getElementById('lesson-concept');
const lessonStepsTimelineEl = document.getElementById('lesson-steps-timeline');
const lessonImageContainerEl = document.getElementById('lesson-image-container');
const lessonHintsContainerEl = document.getElementById('lesson-hints-container');
const lessonHintsEl = document.getElementById('lesson-hints');
const backToUploadButton = document.getElementById('back-to-upload-button'); // Ensure this ID exists if used
const backToQuestionsButton = document.getElementById('back-to-questions-button'); // Ensure this ID exists

// Store the PDF File ID from the extraction step
let currentPdfFileId = null;

// --- Event Listener for Initial PDF Upload (Triggers Question Extraction) ---
lessonForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const pdfFile = pdfFileInput.files[0];

    if (!pdfFile) {
        showError("Please select a PDF file.", "upload-error"); // Specify which error div
        return;
    }

    // Pass button text to loading state function
    setLoadingState(true, 'Extracting Questions...');
    hideError("upload-error"); // Specify which error div to hide
    hideError("lesson-error");
    hideQuestionList();
    hideLesson();

    const formData = new FormData();
    formData.append('pdf_file', pdfFile);

    try {
        // --- Call the /extract-questions endpoint ---
        const response = await fetch('/extract-questions', {
            method: 'POST',
            body: formData,
        });

        const result = await response.json(); // Expects QuestionListResponse

        if (!response.ok) {
            throw new Error(result.detail || `HTTP error! status: ${response.status}`);
        }

        // --- Process Successful Extraction ---
        console.log("Extracted questions data:", result);
        if (!result.pdfFileId || !result.questions) {
            throw new Error("Invalid data received from server after extraction.");
        }
        currentPdfFileId = result.pdfFileId; // Store the File ID
        displayQuestionList(result.questions);
        showQuestionList();
        hideUploadForm(); // Hide upload form, show question list

    } catch (error) {
        console.error('Error extracting questions:', error);
        showError(`Failed to extract questions: ${error.message}`, "upload-error"); // Show in upload error div
    } finally {
        // Reset button text specifically for extraction
        setLoadingState(false, 'Extract Questions');
    }
});

// --- Function to Display Extracted Questions ---
function displayQuestionList(questions) {
    // Ensure the target element exists before modifying it
    if (!extractedQuestionsListEl) {
        console.error("Element with ID 'extracted-questions' not found.");
        showError("UI Error: Could not display questions.", "upload-error");
        return;
    }
    extractedQuestionsListEl.innerHTML = ''; // Clear previous list
    if (!questions || questions.length === 0) {
        const li = document.createElement('li');
        li.textContent = "No questions were extracted from this PDF, or the AI couldn't identify them.";
        li.className = "text-gray-500 italic p-4"; // Add some padding
        extractedQuestionsListEl.appendChild(li);
        return;
    }

    questions.forEach(q => {
        const li = document.createElement('li');
        // Make sure questionId and questionText exist
        const qId = q.questionId || `unknown-${Math.random().toString(16).slice(2)}`; // Fallback ID
        const qText = q.questionText || "Question text missing";

        li.className = 'border border-gray-200 p-4 rounded-md hover:bg-indigo-50 cursor-pointer transition duration-150 flex justify-between items-center';
        li.innerHTML = `
            <div class="flex-grow mr-4 overflow-hidden"> <!-- Added overflow-hidden -->
                <span class="font-semibold text-indigo-700 block text-sm truncate">Q-ID: ${qId}</span> <!-- Added truncate -->
                <span class="text-gray-800 block mt-1 text-sm">${qText.substring(0, 120)}...</span> <!-- Limit text length -->
            </div>
            <svg class="w-6 h-6 text-indigo-500 flex-shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" /></svg>
        `;
        li.dataset.questionId = qId;
        li.dataset.questionText = qText; // Store full text
        li.addEventListener('click', handleQuestionSelection);
        extractedQuestionsListEl.appendChild(li);
    });
}

// --- Event Handler for Clicking a Question in the List ---
async function handleQuestionSelection(event) {
    const listItem = event.currentTarget;
    const selectedQuestionId = listItem.dataset.questionId;
    const selectedQuestionText = listItem.dataset.questionText;

    if (!currentPdfFileId || !selectedQuestionId) {
        showError("Missing PDF reference or Question ID. Please try uploading again.", "lesson-error");
        return;
    }

    console.log(`Requesting lesson for Question ID: ${selectedQuestionId} from PDF: ${currentPdfFileId}`);
    showLoadingIndicator("lesson-loading");
    hideQuestionList();
    showLesson(); // Show the lesson container (with loading indicator inside)
    // Clear previous lesson content before loading new one
    clearLessonContent();
    hideError("lesson-error");


    try {
        // --- Call the /generate-specific-lesson endpoint ---
        const response = await fetch('/generate-specific-lesson', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                pdfFileId: currentPdfFileId,
                selectedQuestionId: selectedQuestionId,
                selectedQuestionText: selectedQuestionText
            }),
        });

        const result = await response.json(); // Expects LessonResponse

        if (!response.ok) {
            throw new Error(result.detail || `HTTP error! status: ${response.status}`);
        }

        // --- Process Successful Lesson Generation ---
        console.log("Received specific lesson data:", result);
        displayLesson(result); // Display the actual lesson content

    } catch (error) {
        console.error('Error generating specific lesson:', error);
        showError(`Failed to generate lesson for question ${selectedQuestionId}: ${error.message}`, "lesson-error");
        // Hide lesson area, show question list again on error? Or show error within lesson area?
        // Let's show the error within the lesson area for now.
        clearLessonContent(); // Clear partially loaded stuff if any
    } finally {
        hideLoadingIndicator("lesson-loading");
    }
}


// --- UI Visibility and State Functions ---

function setLoadingState(isLoading, text = 'Generate Lesson') {
    // Check if elements exist before manipulating them
    if(!generateButton || !buttonText || !loadingSpinner) return;

    if (isLoading) {
        generateButton.disabled = true;
        buttonText.textContent = text;
        loadingSpinner.classList.remove('hidden');
    } else {
        generateButton.disabled = false;
        buttonText.textContent = text; // Use passed text for reset state too
        loadingSpinner.classList.add('hidden');
    }
}

function showError(message, type = "upload") { // Default to upload error div
    const errorDivId = (type === "lesson") ? "lesson-error-message" : "upload-error-message";
    const errorDiv = document.getElementById(errorDivId);
    if(errorDiv) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    } else {
        console.error(`Error div with ID '${errorDivId}' not found!`);
        // Fallback alert if the designated div doesn't exist
        alert(`Error: ${message}`);
    }
}

function hideError(type = "upload") {
     const errorDivId = (type === "lesson") ? "lesson-error-message" : "upload-error-message";
     const errorDiv = document.getElementById(errorDivId);
     if(errorDiv) {
        errorDiv.classList.add('hidden');
        errorDiv.textContent = '';
     }
}

function showQuestionList() {
    const section = document.getElementById('question-list-section');
    if(section) {
        section.classList.remove('hidden');
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function hideQuestionList() {
    const section = document.getElementById('question-list-section');
    const listEl = document.getElementById('extracted-questions');
    if(section) section.classList.add('hidden');
    if(listEl) listEl.innerHTML = ''; // Clear list when hiding
}

function showLesson() {
    const section = document.getElementById('lesson-section');
    if(section) {
         section.classList.remove('hidden');
         section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function hideLesson() {
     const section = document.getElementById('lesson-section');
     if(section) section.classList.add('hidden');
     clearLessonContent(); // Clear content when hiding
}

function clearLessonContent() {
    // Clear previous lesson content (ensure elements exist)
     if(lessonTitleEl) lessonTitleEl.textContent = '';
     if(lessonSubheaderEl) lessonSubheaderEl.textContent = '';
     if(lessonConceptEl) lessonConceptEl.innerHTML = '';
     if(lessonStepsTimelineEl) lessonStepsTimelineEl.innerHTML = '';
     if(lessonHintsEl) lessonHintsEl.innerHTML = '';
     if(lessonImageContainerEl) lessonImageContainerEl.classList.add('hidden');
     if(lessonHintsContainerEl) lessonHintsContainerEl.classList.add('hidden');
}


function showUploadForm() {
    const section = document.getElementById('upload-section');
    if(section) section.classList.remove('hidden');
}

function hideUploadForm() {
     const section = document.getElementById('upload-section');
     if(section) section.classList.add('hidden');
}

// Global function called by buttons
function resetUI() {
    hideLesson();
    hideQuestionList();
    hideError("upload"); // Use type parameter
    hideError("lesson");
    if (lessonForm) lessonForm.reset();
    showUploadForm();
    currentPdfFileId = null;
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showLoadingIndicator(elementId) {
    const indicator = document.getElementById(elementId);
    // Ensure the lesson content area is hidden while loading indicator is shown
    const contentArea = document.getElementById('lesson-content-area');
    if (indicator) indicator.classList.remove('hidden');
    if (contentArea) contentArea.classList.add('hidden');
}

function hideLoadingIndicator(elementId) {
    const indicator = document.getElementById(elementId);
     // Ensure the lesson content area is shown when loading indicator is hidden
     const contentArea = document.getElementById('lesson-content-area');
    if (indicator) indicator.classList.add('hidden');
    if (contentArea) contentArea.classList.remove('hidden');
}


// --- Functions to Render Lesson Content ---
function displayLesson(lessonResponse) {
    const lessonData = lessonResponse.lessonData;
    if (!lessonData) {
        showError("Received invalid lesson data structure from server.", "lesson");
        return;
    }
    // Ensure elements exist before setting content
    if(lessonTitleEl) lessonTitleEl.textContent = `Lesson for: ${lessonData.questionText}`;
    if(lessonSubheaderEl) lessonSubheaderEl.textContent = `Subject: ${lessonData.subject} | Topic: ${lessonData.topic} | Q-ID: ${lessonData.questionId}`;
    if(lessonConceptEl) lessonConceptEl.innerHTML = lessonData.coreConceptHtml;

    if(lessonStepsTimelineEl) lessonStepsTimelineEl.innerHTML = ''; // Clear previous steps
    let stepDelay = 0;
    const delayIncrement = 0.1;
    lessonData.steps.forEach(step => {
        const stepElement = createTimelineStepElement(step.stepNumber, step.title, step.descriptionHtml, stepDelay);
        if(lessonStepsTimelineEl) lessonStepsTimelineEl.appendChild(stepElement);
        stepDelay += delayIncrement;
    });

    if(lessonImageContainerEl){
        if (lessonData.visualAid && lessonData.visualAid.isPresent) {
            lessonImageContainerEl.classList.remove('hidden');
        } else {
            lessonImageContainerEl.classList.add('hidden');
        }
    }

    if(lessonHintsEl) lessonHintsEl.innerHTML = ''; // Clear previous hints
    if(lessonHintsContainerEl) lessonHintsContainerEl.classList.add('hidden'); // Default hide
    if (lessonData.hints && lessonData.hints.length > 0) {
        if(lessonHintsContainerEl) lessonHintsContainerEl.classList.remove('hidden');
        lessonData.hints.forEach(hint => {
            const li = document.createElement('li');
            li.innerHTML = hint; // Render potential simple HTML in hints
           if(lessonHintsEl) lessonHintsEl.appendChild(li);
        });
    }
}

function createTimelineStepElement(stepNumber, title, descriptionHtml, delay) {
    const stepElement = document.createElement('div');
    stepElement.className = 'timeline-item relative pl-12 pb-6 step-appear';
    stepElement.style.animationDelay = `${delay}s`;
    const iconSVG = `<div class="timeline-icon absolute left-0 top-0 flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md"><span class="text-white font-bold text-sm">${stepNumber}</span></div>`;
    stepElement.innerHTML = `
        ${iconSVG}
        <div class="ml-3">
             <div class="timeline-step-header mb-0"> <!-- Removed mb-2 -->
                <h4 class="text-lg font-semibold text-indigo-800">${title}</h4>
             </div>
            <div class="timeline-step-content prose prose-sm max-w-none text-gray-600 leading-relaxed">
                ${descriptionHtml}
            </div>
        </div>`;
    return stepElement;
}


// --- Initial UI State ---
function initializeUI() {
    console.log("Initializing UI...");
    hideLesson();
    hideQuestionList();
    // Optionally hide error messages on load too
    hideError("upload");
    hideError("lesson");
    // Ensure upload form is visible
    showUploadForm();
}

// Run initialization when the script loads
initializeUI();

