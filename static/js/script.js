// Get references to key HTML elements
const lessonForm = document.getElementById('lesson-form');
const pdfFileInput = document.getElementById('pdf-file');
const questionDescriptionInput = document.getElementById('question-description');
const generateButton = document.getElementById('generate-button');
const buttonText = document.getElementById('button-text');
const loadingSpinner = document.getElementById('button-loading-spinner');
const errorMessageDiv = document.getElementById('error-message');
const uploadSection = document.getElementById('upload-section');
const lessonSection = document.getElementById('lesson-section');

// Lesson display elements
const lessonTitleEl = document.getElementById('lesson-title');
const lessonSubheaderEl = document.getElementById('lesson-subheader');
const lessonConceptEl = document.getElementById('lesson-concept');
const lessonStepsTimelineEl = document.getElementById('lesson-steps-timeline');
const lessonImageContainerEl = document.getElementById('lesson-image-container');
const lessonHintsContainerEl = document.getElementById('lesson-hints-container');
const lessonHintsEl = document.getElementById('lesson-hints');

// --- Event Listener for Form Submission ---
lessonForm.addEventListener('submit', async (event) => {
    event.preventDefault(); // Prevent default form submission

    const pdfFile = pdfFileInput.files[0];
    const questionDescription = questionDescriptionInput.value.trim();

    if (!pdfFile) {
        showError("Please select a PDF file.");
        return;
    }
    if (!questionDescription) {
        showError("Please describe the question you want explained.");
        return;
    }

    setLoadingState(true);
    hideError();
    hideLesson();

    const formData = new FormData();
    formData.append('pdf_file', pdfFile);
    formData.append('question_description', questionDescription);

    try {
        const response = await fetch('/generate-lesson', {
            method: 'POST',
            body: formData,
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || `HTTP error! status: ${response.status}`);
        }

        console.log("Received lesson data:", result);
        displayLesson(result); // result is the { lessonData: { ... } } structure
        showLesson();
        hideUploadForm();

    } catch (error) {
        console.error('Error generating lesson:', error);
        showError(`Failed to generate lesson: ${error.message}`);
    } finally {
        setLoadingState(false);
    }
});

// --- UI Helper Functions ---

function setLoadingState(isLoading) {
    if (isLoading) {
        generateButton.disabled = true;
        buttonText.textContent = 'Generating...';
        loadingSpinner.classList.remove('hidden');
    } else {
        generateButton.disabled = false;
        buttonText.textContent = 'Generate Lesson';
        loadingSpinner.classList.add('hidden');
    }
}

function showError(message) {
    errorMessageDiv.textContent = message;
    errorMessageDiv.classList.remove('hidden');
}

function hideError() {
    errorMessageDiv.classList.add('hidden');
    errorMessageDiv.textContent = '';
}

function showLesson() {
    lessonSection.classList.remove('hidden');
    // Scroll to the lesson section smoothly
    lessonSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}


function hideLesson() {
     lessonSection.classList.add('hidden');
     // Clear previous content
     lessonTitleEl.textContent = '';
     lessonSubheaderEl.textContent = '';
     lessonConceptEl.innerHTML = '';
     lessonStepsTimelineEl.innerHTML = '';
     lessonHintsEl.innerHTML = '';
     lessonImageContainerEl.classList.add('hidden');
     lessonHintsContainerEl.classList.add('hidden');
}

function showUploadForm() {
    uploadSection.classList.remove('hidden');
}

function hideUploadForm() {
    uploadSection.classList.add('hidden');
}

function resetUI() {
    hideLesson();
    hideError();
    lessonForm.reset(); // Clear form inputs
    showUploadForm();
    window.scrollTo({ top: 0, behavior: 'smooth' }); // Scroll to top
}


// --- Functions to Render Lesson Content ---

function displayLesson(lessonResponse) {
    const lessonData = lessonResponse.lessonData; // Access the nested data
    if (!lessonData) {
        showError("Received invalid lesson data structure from server.");
        return;
    }

    lessonTitleEl.textContent = `Question ${lessonData.questionId}: ${lessonData.questionText}`;
    lessonSubheaderEl.textContent = `Subject: ${lessonData.subject} | Topic: ${lessonData.topic}`;
    lessonConceptEl.innerHTML = lessonData.coreConceptHtml;

    lessonStepsTimelineEl.innerHTML = '';
    let stepDelay = 0;
    const delayIncrement = 0.1;

    lessonData.steps.forEach(step => {
        const stepElement = createTimelineStepElement(step.stepNumber, step.title, step.descriptionHtml, stepDelay);
        lessonStepsTimelineEl.appendChild(stepElement);
        stepDelay += delayIncrement;
    });

    if (lessonData.visualAid && lessonData.visualAid.isPresent) {
        lessonImageContainerEl.classList.remove('hidden');
    } else {
        lessonImageContainerEl.classList.add('hidden');
    }

    lessonHintsEl.innerHTML = '';
    if (lessonData.hints && lessonData.hints.length > 0) {
        lessonHintsContainerEl.classList.remove('hidden');
        lessonData.hints.forEach(hint => {
            const li = document.createElement('li');
            li.innerHTML = hint;
            lessonHintsEl.appendChild(li);
        });
    } else {
        lessonHintsContainerEl.classList.add('hidden');
    }
}

function createTimelineStepElement(stepNumber, title, descriptionHtml, delay) {
    const stepElement = document.createElement('div');
    stepElement.className = 'timeline-item relative pl-12 pb-6 step-appear';
    stepElement.style.animationDelay = `${delay}s`;
    const iconSVG = `
        <div class="timeline-icon absolute left-0 top-0 flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 shadow-md">
            <span class="text-white font-bold text-sm">${stepNumber}</span>
        </div>`;
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

// --- Initial State ---
hideLesson();

