// --- Get references to key HTML elements ---
const lessonForm = document.getElementById('lesson-form');
const pdfFileInput = document.getElementById('pdf-file');
const uploadDropZone = document.getElementById('upload-drop-zone'); // The drop zone div
const dropZoneText = document.getElementById('drop-zone-text'); // Text inside drop zone
const selectedFileNameEl = document.getElementById('selected-file-name'); // To display filename
const generateButton = document.getElementById('generate-button');
const buttonText = document.getElementById('button-text');
const loadingSpinner = document.getElementById('button-loading-spinner');
const uploadErrorMessageDiv = document.getElementById('upload-error-message');
const uploadSection = document.getElementById('upload-section');

// Question List Section elements
const questionListSection = document.getElementById('question-list-section');
const extractedQuestionsListEl = document.getElementById('extracted-questions');
const questionListErrorMessageDiv = document.getElementById('question-list-error-message'); // Specific error div for this stage

// Lesson Display Section elements
const lessonSection = document.getElementById('lesson-section');
const lessonSkeletonLoader = document.getElementById('lesson-skeleton-loader'); // Skeleton placeholder
const lessonHeaderSkeleton = document.getElementById('lesson-header-skeleton'); // Skeleton for header
const lessonHeaderContent = document.getElementById('lesson-header-content'); // Actual header content
const lessonContentArea = document.getElementById('lesson-content-area');    // Wrapper for actual content
const lessonTitleEl = document.getElementById('lesson-title');
const lessonSubheaderEl = document.getElementById('lesson-subheader');
const lessonConceptEl = document.getElementById('lesson-concept');
const lessonStepsTimelineEl = document.getElementById('lesson-steps-timeline');
const lessonImageContainerEl = document.getElementById('lesson-image-container');
const lessonHintsContainerEl = document.getElementById('lesson-hints-container');
const lessonHintsEl = document.getElementById('lesson-hints');
const lessonErrorMessageDiv = document.getElementById('lesson-error-message'); // Specific error div for lesson stage
const backToQuestionsButton = document.getElementById('back-to-questions-button');
const backToUploadButton = document.getElementById('back-to-upload-button');


// Global state
let currentPdfFileId = null;
let currentExtractedQuestions = []; // Store extracted questions

// --- Event Listeners ---

// Trigger hidden file input click when drop zone is clicked
if (uploadDropZone) {
    uploadDropZone.addEventListener('click', () => {
        if (pdfFileInput) pdfFileInput.click();
    });
} else {
    console.error("Upload drop zone element not found!");
}


// Handle file selection (show filename)
if (pdfFileInput) {
    pdfFileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file && selectedFileNameEl) {
            selectedFileNameEl.textContent = `Selected: ${file.name}`;
            hideError("upload"); // Hide error if user selects a valid file
        } else if (selectedFileNameEl) {
            selectedFileNameEl.textContent = ''; // Clear if no file selected
        }
    });
}


// Drag and Drop functionality (Optional but enhances UX)
if (uploadDropZone) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadDropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    uploadDropZone.addEventListener('dragenter', () => uploadDropZone.classList.add('dragover'), false);
    uploadDropZone.addEventListener('dragover', () => uploadDropZone.classList.add('dragover'), false);
    uploadDropZone.addEventListener('dragleave', () => uploadDropZone.classList.remove('dragover'), false);

    uploadDropZone.addEventListener('drop', (e) => {
        uploadDropZone.classList.remove('dragover');
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            // Check if it's a PDF
            if (files[0].type === "application/pdf") {
                pdfFileInput.files = files; // Assign dropped file to the input
                // Trigger the change event manually to update the UI
                const changeEvent = new Event('change');
                pdfFileInput.dispatchEvent(changeEvent);
            } else {
                showError("Please drop a PDF file only.", "upload");
                if (selectedFileNameEl) selectedFileNameEl.textContent = '';
            }
        }
    }, false);
}

// Form submission for EXTRACTING questions
if (lessonForm) {
    lessonForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const pdfFile = pdfFileInput.files[0];

        if (!pdfFile) {
            showError("Please select or drop a PDF file.", "upload");
            return;
        }

        setLoadingState(true, 'Extracting Questions...');
        hideError("upload");
        hideError("question-list"); // Use specific IDs
        hideError("lesson");
        hideQuestionList();
        hideLesson();

        const formData = new FormData();
        formData.append('pdf_file', pdfFile);

        try {
            const response = await fetch('/extract-questions', { method: 'POST', body: formData });
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || `HTTP error! Status: ${response.status}`);

            console.log("Extracted questions data:", result);
            if (!result.pdfFileId || !result.questions) throw new Error("Invalid data structure received.");

            currentPdfFileId = result.pdfFileId;
            currentExtractedQuestions = result.questions; // Store questions
            displayQuestionList(result.questions);
            showQuestionList();
            hideUploadForm();

        } catch (error) {
            console.error('Error extracting questions:', error);
            showError(`Extraction failed: ${error.message}`, "upload");
        } finally {
            setLoadingState(false, 'Extract Questions');
        }
    });
}

// --- Display Questions ---
function displayQuestionList(questions) {
    if (!extractedQuestionsListEl) return;
    extractedQuestionsListEl.innerHTML = '';
    if (!questions || questions.length === 0) {
        extractedQuestionsListEl.innerHTML = `<li class="text-gray-500 italic p-4">No questions were extracted. Check the PDF or try describing the section.</li>`;
        return;
    }

    questions.forEach((q, index) => { // Add index for fallback ID
        const li = document.createElement('li');
        const qId = q.questionId || `item-${index}`; // Use index as fallback ID
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

// --- Generate Specific Lesson ---
async function handleQuestionSelection(event) {
    const listItem = event.currentTarget;
    const selectedQuestionId = listItem.dataset.questionId;
    const selectedQuestionText = listItem.dataset.questionText;

    if (!currentPdfFileId || !selectedQuestionId) {
        showError("Missing PDF reference or Question ID.", "question-list"); // Show error in question list area
        return;
    }

    console.log(`Requesting lesson for Q ID: ${selectedQuestionId} from PDF: ${currentPdfFileId}`);
    hideQuestionList();
    showLesson(); // Show the lesson section container
    showSkeletonLoader(); // Show the skeleton WHILE fetching
    hideError("lesson"); // Hide previous lesson errors


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
        displayLesson(result); // Populate the hidden content area
        showActualLessonContent(); // Hide skeleton, show content

    } catch (error) {
        console.error('Error generating specific lesson:', error);
        hideSkeletonLoader(); // Hide skeleton on error too
        showError(`Failed to generate lesson: ${error.message}`, "lesson"); // Show error within lesson section
    }
    // No 'finally hideSkeletonLoader' here, it's hidden on success/error explicitly
}

// --- UI Visibility & State ---

function setLoadingState(isLoading, text = 'Generate Lesson') {
    if(!generateButton || !buttonText || !loadingSpinner) return;
    generateButton.disabled = isLoading;
    buttonText.textContent = text;
    loadingSpinner.classList.toggle('hidden', !isLoading);
}

function showError(message, type = "upload") {
    const errorDivId = `${type}-error-message`; // Construct ID dynamically
    const errorDiv = document.getElementById(errorDivId);
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    } else {
        console.error(`Error div with ID '${errorDivId}' not found!`);
        alert(`Error: ${message}`); // Fallback
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
    // Don't clear the list here, only when displaying new data or resetting
}

function showLesson() {
    if(lessonSection) {
        lessonSection.classList.remove('hidden');
        lessonSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

function hideLesson() {
     if(lessonSection) lessonSection.classList.add('hidden');
     clearLessonContent();
     hideSkeletonLoader(); // Ensure skeleton is also hidden
}

function clearLessonContent() {
    // Clear actual content areas
     if(lessonHeaderContent) lessonHeaderContent.classList.add('hidden'); // Hide actual header
     if(lessonContentArea) lessonContentArea.classList.add('hidden');    // Hide actual body
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
    if (lessonHeaderSkeleton) lessonHeaderSkeleton.classList.remove('hidden'); // Show header skeleton
    if (lessonContentArea) lessonContentArea.classList.add('hidden');    // Hide real content wrapper
    if (lessonHeaderContent) lessonHeaderContent.classList.add('hidden'); // Hide real header wrapper
}

function hideSkeletonLoader() {
    if (lessonSkeletonLoader) lessonSkeletonLoader.classList.add('hidden');
    if (lessonHeaderSkeleton) lessonHeaderSkeleton.classList.add('hidden');
}

function showActualLessonContent() {
    hideSkeletonLoader(); // Hide skeleton first
    if (lessonContentArea) lessonContentArea.classList.remove('hidden');    // Show real content wrapper
    if (lessonHeaderContent) lessonHeaderContent.classList.remove('hidden'); // Show real header wrapper
}


function showUploadForm() {
    if(uploadSection) uploadSection.classList.remove('hidden');
}

function hideUploadForm() {
     if(uploadSection) uploadSection.classList.add('hidden');
}

function resetUI() {
    hideLesson();
    hideQuestionList();
    if (extractedQuestionsListEl) extractedQuestionsListEl.innerHTML = ''; // Clear list
    hideError("upload");
    hideError("question-list");
    hideError("lesson");
    if (lessonForm) lessonForm.reset();
    if (selectedFileNameEl) selectedFileNameEl.textContent = ''; // Clear selected filename
    showUploadForm();
    currentPdfFileId = null;
    currentExtractedQuestions = [];
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// --- Render Lesson Content ---
function displayLesson(lessonResponse) {
    const lessonData = lessonResponse.lessonData;
    if (!lessonData) {
        showError("Received invalid lesson data structure.", "lesson");
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
    const stepElement = document.createElement('div');
    stepElement.className = 'timeline-item relative pl-12 pb-6 step-appear';
    stepElement.style.animationDelay = `${delay}s`;
    const iconSVG = `<div class="timeline-icon absolute left-0 top-0 flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md"><span class="text-white font-bold text-sm">${stepNumber}</span></div>`;
    stepElement.innerHTML = `
        ${iconSVG}
        <div class="ml-3">
             <div class="timeline-step-header mb-0">
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
    resetUI(); // Use resetUI to set the initial state
}

// Run initialization when the script loads
initializeUI();

