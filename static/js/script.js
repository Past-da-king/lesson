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

