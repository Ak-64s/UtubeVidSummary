// Combined Optimized JavaScript - ProjectBeta
'use strict';

// === GLOBAL STATE ===
const AppState = {
    isLoading: false,
    currentTaskId: null,
    pollingInterval: null,
    pollCount: 0,
    pollInterval: 3000, // Start with more reasonable 3 seconds
    pollErrorCount: 0,
    error: null,
    videoDuration: null,
    formData: {},
    resultData: null
};

// === STATE PERSISTENCE ===
const StateManager = {
    // Save form data to localStorage
    saveFormState: () => {
        const formData = {
            youtubeUrl: UI.youtubeUrlInput?.value || '',
            customPrompt: UI.customPromptInput?.value || '',
            startTime: UI.startTimeInput?.value || '',
            endTime: UI.endTimeInput?.value || '',
            timestamp: Date.now()
        };
        localStorage.setItem('videoSummarizerFormData', JSON.stringify(formData));
        AppState.formData = formData;
    },

    // Restore form data from localStorage
    restoreFormState: () => {
        try {
            const saved = localStorage.getItem('videoSummarizerFormData');
            if (saved) {
                const formData = JSON.parse(saved);
                // Only restore if data is less than 24 hours old
                if (Date.now() - formData.timestamp < 24 * 60 * 60 * 1000) {
                    if (UI.youtubeUrlInput) UI.youtubeUrlInput.value = formData.youtubeUrl || '';
                    if (UI.customPromptInput) UI.customPromptInput.value = formData.customPrompt || '';
                    if (UI.startTimeInput) UI.startTimeInput.value = formData.startTime || '';
                    if (UI.endTimeInput) UI.endTimeInput.value = formData.endTime || '';
                    AppState.formData = formData;
                    console.log('Form state restored from localStorage');
                } else {
                    // Clear expired data
                    localStorage.removeItem('videoSummarizerFormData');
                }
            }
        } catch (e) {
            console.error('Error restoring form state:', e);
        }
    },

    // Save result data for back/forward navigation
    saveResultState: (resultData) => {
        sessionStorage.setItem('videoSummarizerResults', JSON.stringify({
            data: resultData,
            timestamp: Date.now()
        }));
        AppState.resultData = resultData;
    },

    // Restore result data
    restoreResultState: () => {
        try {
            const saved = sessionStorage.getItem('videoSummarizerResults');
            if (saved) {
                const { data, timestamp } = JSON.parse(saved);
                // Only restore if data is less than 1 hour old
                if (Date.now() - timestamp < 60 * 60 * 1000) {
                    AppState.resultData = data;
                    return data;
                }
            }
        } catch (e) {
            console.error('Error restoring result state:', e);
        }
        return null;
    },

    // Clear all saved state
    clearState: () => {
        localStorage.removeItem('videoSummarizerFormData');
        sessionStorage.removeItem('videoSummarizerResults');
        AppState.formData = {};
        AppState.resultData = null;
    }
};

// === DOM ELEMENTS CACHE ===
const UI = {
    form: null,
    submitButton: null,
    progressBarContainer: null,
    progressBar: null,
    errorMessageContainer: null,
    loadingIndicator: null,
    youtubeUrlInput: null,
    customPromptInput: null,
    themeToggleButton: null,
    startTimeInput: null,
    endTimeInput: null,
    startTimeDial: null,
    endTimeDial: null
};

// === UTILITY FUNCTIONS ===
function cacheElements() {
    UI.form = document.getElementById('summarizeForm');
    UI.submitButton = document.querySelector('.submit-btn');
    UI.progressBarContainer = document.querySelector('.progress-container');
    UI.progressBar = document.querySelector('.progress-bar');
    UI.errorMessageContainer = document.querySelector('.error-message');
    UI.loadingIndicator = document.querySelector('.loading-indicator');
    UI.youtubeUrlInput = document.getElementById('youtubeUrl');
    UI.customPromptInput = document.getElementById('customPrompt');
    UI.themeToggleButton = document.getElementById('theme-toggle');
    UI.startTimeInput = document.getElementById('startTime');
    UI.endTimeInput = document.getElementById('endTime');
    UI.startTimeDial = document.querySelector('.start-time-dial');
    UI.endTimeDial = document.querySelector('.end-time-dial');
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// === THEME MANAGEMENT ===
function initializeTheme() {
    const theme = localStorage.getItem('theme') || 'dark'; // Default to dark
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeButtonVisuals(theme);
    if (typeof updateHighlightJsTheme === 'function') {
        updateHighlightJsTheme(theme);
    }
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeButtonVisuals(newTheme);
    if (typeof updateHighlightJsTheme === 'function') {
        updateHighlightJsTheme(newTheme);
    }
}

function updateThemeButtonVisuals(theme) {
    if (UI.themeToggleButton) {
        const icon = UI.themeToggleButton.querySelector('.theme-icon');
        if (icon) {
            icon.textContent = theme === 'light' ? '🌙' : '☀️';
        }
    }
}

// === LOADING STATES ===
function showLoading(message = 'Processing...') {
    AppState.isLoading = true;
    if (UI.submitButton) {
        UI.submitButton.disabled = true;
        UI.submitButton.innerHTML = `<span class="spinner"></span> ${message}`;
    }
    if (UI.loadingIndicator) UI.loadingIndicator.style.display = 'flex';
    if (UI.progressBarContainer) UI.progressBarContainer.style.display = 'block';
    updateProgress(0);
    hideError();
}

function hideLoading() {
    AppState.isLoading = false;
    if (UI.submitButton) {
        UI.submitButton.disabled = false;
        UI.submitButton.innerHTML = '<i class="fas fa-sparkles"></i><span>Generate AI Summary</span>';
    }
    if (UI.loadingIndicator) UI.loadingIndicator.style.display = 'none';
    if (UI.progressBarContainer) UI.progressBarContainer.style.display = 'none';
}

function updateProgress(percentage, text = '') {
    if (UI.progressBar) {
        UI.progressBar.style.width = `${Math.min(100, Math.max(0, percentage))}%`;
    }
}

// === ERROR HANDLING ===
function showError(message) {
    AppState.error = message;
    if (UI.errorMessageContainer) {
        UI.errorMessageContainer.textContent = message;
        UI.errorMessageContainer.style.display = 'block';
    }
    setTimeout(hideError, 7000);
}

function hideError() {
    AppState.error = null;
    if (UI.errorMessageContainer) {
        UI.errorMessageContainer.style.display = 'none';
    }
}

// === TIME INPUT VALIDATION ===
function validateTimeFormat(timeString) {
    if (!timeString || timeString.trim() === '') return { valid: true, error: null };
    
    // Check basic format first
    const timeRegex = /^([0-9]{1,2}):([0-5][0-9]):([0-5][0-9])$/;
    const match = timeString.match(timeRegex);
    
    if (!match) {
        return { 
            valid: false, 
            error: 'Format: HH:MM:SS (e.g., 1:30:45)' 
        };
    }
    
    const [, hoursStr, minutesStr, secondsStr] = match;
    const hours = parseInt(hoursStr, 10);
    const minutes = parseInt(minutesStr, 10);
    const seconds = parseInt(secondsStr, 10);
    
    // Validate ranges
    if (hours < 0 || hours > 23) {
        return { 
            valid: false, 
            error: 'Hours must be 0-23' 
        };
    }
    
    if (minutes < 0 || minutes > 59) {
        return { 
            valid: false, 
            error: 'Minutes must be 0-59' 
        };
    }
    
    if (seconds < 0 || seconds > 59) {
        return { 
            valid: false, 
            error: 'Seconds must be 0-59' 
        };
    }
    
    return { valid: true, error: null };
}

function formatTimeInput(input) {
    let value = input.replace(/[^\d:]/g, ''); // Remove non-digits and non-colons
    
    // Auto-format as user types
    if (value.length === 1 && parseInt(value) > 2) {
        value = '0' + value + ':';
    } else if (value.length === 2 && !value.includes(':')) {
        if (parseInt(value) > 23) {
            value = '23:';
        } else {
            value = value + ':';
        }
    } else if (value.length === 4 && value.split(':').length === 2) {
        const parts = value.split(':');
        if (parseInt(parts[1]) > 59) {
            value = parts[0] + ':59:';
        } else {
            value = value + ':';
        }
    } else if (value.length === 7 && value.split(':').length === 3) {
        const parts = value.split(':');
        if (parseInt(parts[2]) > 59) {
            value = parts[0] + ':' + parts[1] + ':59';
        }
    }
    
    return value;
}

function showTimeError(inputId, message) {
    const input = document.getElementById(inputId);
    const errorDiv = document.getElementById(inputId + 'Error');
    
    if (input && errorDiv) {
        input.classList.add('error');
        errorDiv.textContent = message;
        errorDiv.classList.add('show');
    }
}

function hideTimeError(inputId) {
    const input = document.getElementById(inputId);
    const errorDiv = document.getElementById(inputId + 'Error');
    
    if (input && errorDiv) {
        input.classList.remove('error');
        errorDiv.classList.remove('show');
    }
}

function timeToSeconds(timeStr) {
    if (!timeStr) return null;
    const [hours, minutes, seconds] = timeStr.split(':').map(Number);
    return hours * 3600 + minutes * 60 + seconds;
}

function secondsToTime(seconds) {
    if (seconds === null || seconds === undefined) return '';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function validateTimesAgainstDuration() {
    if (!AppState.videoDuration) return true;
    
    const startTime = UI.startTimeInput?.value;
    const endTime = UI.endTimeInput?.value;
    
    if (startTime && timeToSeconds(startTime) > AppState.videoDuration) {
        showError('Start time exceeds video duration');
        return false;
    }
    
    if (endTime && timeToSeconds(endTime) > AppState.videoDuration) {
        showError('End time exceeds video duration');
        return false;
    }
    
    if (startTime && endTime && timeToSeconds(startTime) >= timeToSeconds(endTime)) {
        showError('Start time must be before end time');
        return false;
    }
    
    return true;
}

// === TIME INPUT HANDLERS ===
function initializeTimeInputs() {
    if (UI.startTimeDial) {
        UI.startTimeDial.addEventListener('click', () => adjustTime(UI.startTimeInput, 30));
    }
    if (UI.endTimeDial) {
        UI.endTimeDial.addEventListener('click', () => adjustTime(UI.endTimeInput, 30));
    }
    
    [UI.startTimeInput, UI.endTimeInput].forEach(input => {
        if (input) {
            input.addEventListener('input', debounce(validateTimesAgainstDuration, 300));
            input.addEventListener('blur', validateTimesAgainstDuration);
        }
    });
}

function adjustTime(input, secondsToAdd) {
    if (!input) return;
    
    const currentValue = input.value || '00:00:00';
    const currentSeconds = timeToSeconds(currentValue);
    const newSeconds = Math.max(0, currentSeconds + secondsToAdd);
    input.value = secondsToTime(newSeconds);
    validateTimesAgainstDuration();
}

// === TASK POLLING ===
function startPolling(taskId) {
    AppState.currentTaskId = taskId;
    AppState.pollCount = 0;
    AppState.pollInterval = 3000; // Start with 3 seconds (more reasonable)
    sessionStorage.setItem('currentTaskPlaying', taskId);
    updateProgress(0, 'Task submitted, checking status...');
    
    // Dynamic polling: start reasonable, then back off more aggressively
    scheduleNextPoll(taskId);
    checkTaskStatus(taskId); // Initial check
}

function scheduleNextPoll(taskId) {
    AppState.pollingInterval = setTimeout(() => {
        checkTaskStatus(taskId);
        
        // Aggressive backoff strategy to reduce server load
        AppState.pollCount++;
        if (AppState.pollCount <= 3) {
            AppState.pollInterval = 3000; // First 3 checks: 3s (9 seconds total)
        } else if (AppState.pollCount <= 8) {
            AppState.pollInterval = 5000; // Next 5 checks: 5s (25 seconds)
        } else if (AppState.pollCount <= 15) {
            AppState.pollInterval = 8000; // Next 7 checks: 8s (56 seconds)
        } else {
            AppState.pollInterval = 12000; // After that: 12s (much more reasonable)
        }
        
        scheduleNextPoll(taskId);
    }, AppState.pollInterval);
}

async function checkTaskStatus(taskId) {
    try {
        console.log(`Polling attempt ${AppState.pollCount + 1}, interval: ${AppState.pollInterval}ms`);
        const response = await fetch(`/task_status/${taskId}`);
        if (!response.ok) throw new Error('Failed to fetch task status');
        
        const data = await response.json();
        
        if (data.status === 'completed') {
            handleTaskCompletion(data);
        } else if (data.status === 'failed') {
            handleTaskFailure(data);
        } else {
            updateTaskProgress(data);
            
            // Extend polling interval if progress is > 80% (likely in final AI processing stages)
            if (data.progress_percentage >= 80 && AppState.pollCount > 8) {
                AppState.pollInterval = Math.min(AppState.pollInterval * 1.5, 15000); // Cap at 15s
            }
            
            // Exponential backoff for really long-running processes
            if (AppState.pollCount > 20) {
                AppState.pollInterval = Math.min(AppState.pollInterval * 1.2, 30000); // Cap at 30s for very long tasks
            }
            
            // Emergency brake for extremely long tasks (>10 minutes of polling)
            if (AppState.pollCount > 50) {
                console.warn('Task taking unusually long, reducing polling frequency');
                AppState.pollInterval = 60000; // 1 minute intervals
            }
        }
    } catch (error) {
        console.error('Error checking task status:', error);
        
        // Don't show error immediately - might be temporary network issue
        AppState.pollErrorCount = (AppState.pollErrorCount || 0) + 1;
        
        if (AppState.pollErrorCount >= 3) {
            showError('Error checking task status: ' + error.message);
            stopPolling();
        }
        // Continue polling if less than 3 errors
    }
}

function handleTaskCompletion(data) {
    stopPolling();
    updateProgress(100, 'Processing complete!');
    
    // Save both old and new format for compatibility
    sessionStorage.setItem('taskResult', JSON.stringify(data.result));
    StateManager.saveResultState(data.result);
    
    setTimeout(() => {
        window.location.href = `/results?task_id=${AppState.currentTaskId}`;
    }, 1000);
}

function handleTaskFailure(data) {
    stopPolling();
    hideLoading();
    
    const errorMsg = data.errors?.[0]?.error || 'Task failed due to an unknown error';
    showError(`Processing failed: ${errorMsg}`);
    sessionStorage.removeItem('currentTaskPlaying');
}

function updateTaskProgress(data) {
    const percentage = data.total_items > 0 
        ? (data.completed_items / data.total_items) * 100 
        : 0;
    
    let statusText = data.current_item_details || 
        `Processing ${data.completed_items}/${data.total_items} items...`;
    
    // Add polling info for transparency (only after initial checks)
    if (AppState.pollCount > 5) {
        const nextCheckIn = Math.round(AppState.pollInterval / 1000);
        statusText += ` • Next check in ${nextCheckIn}s`;
    }
    
    updateProgress(percentage, statusText);
}

function stopPolling() {
    if (AppState.pollingInterval) {
        clearTimeout(AppState.pollingInterval);
        AppState.pollingInterval = null;
    }
    AppState.pollCount = 0;
    AppState.pollErrorCount = 0;
}

// === FORM HANDLING ===
async function handleSubmit(event) {
    event.preventDefault();
    
    const youtubeUrl = UI.youtubeUrlInput?.value?.trim();
    const customPrompt = UI.customPromptInput?.value?.trim();
    const startTime = UI.startTimeInput?.value?.trim();
    const endTime = UI.endTimeInput?.value?.trim();
    
    // Validation
    if (!youtubeUrl) {
        showError('Please provide a YouTube URL');
        return;
    }
    
    // Validate start time
    if (startTime) {
        const startValidation = validateTimeFormat(startTime);
        if (!startValidation.valid) {
            showTimeError('startTime', startValidation.error);
            showError('Please enter a valid start time');
            return;
        }
    }
    
    // Validate end time
    if (endTime) {
        const endValidation = validateTimeFormat(endTime);
        if (!endValidation.valid) {
            showTimeError('endTime', endValidation.error);
            showError('Please enter a valid end time');
            return;
        }
    }
    
    if (!validateTimesAgainstDuration()) return;
    
    // Save form state before submission
    StateManager.saveFormState();
    
    showLoading('Submitting task...');
    
    try {
        const response = await fetch('/submit_task', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({
                link: youtubeUrl,
                prompt: customPrompt,
                start_time: startTime,
                end_time: endTime
            })
        });
        
        if (!response.ok) throw new Error('Submission failed');
        
        const data = await response.json();
        startPolling(data.task_id);
    } catch (error) {
        showError('Failed to submit task: ' + error.message);
        hideLoading();
    }
}

// === VIDEO INFO FETCHING ===
async function fetchVideoInfo(url) {
    try {
        const response = await fetch(`/get_video_info?url=${encodeURIComponent(url)}`);
        const data = await response.json();
        
        if (data.error) {
            console.warn('Could not fetch video info:', data.error);
            AppState.videoDuration = null;
        } else {
            AppState.videoDuration = data.duration;
        }
    } catch (error) {
        console.error('Error fetching video info:', error);
        AppState.videoDuration = null;
    }
}

// === INPUT ANIMATIONS ===
function initializeInputAnimations() {
    const inputs = document.querySelectorAll('.input-group input, .input-group textarea');
    
    inputs.forEach(input => {
        const label = input.nextElementSibling;
        
        if (input.value && label?.tagName === 'LABEL') {
            label.classList.add('active');
        }
        
        input.addEventListener('focus', () => {
            if (label?.tagName === 'LABEL') label.classList.add('active');
        });
        
        input.addEventListener('blur', () => {
            if (!input.value && label?.tagName === 'LABEL') {
                label.classList.remove('active');
            }
        });
    });
}

// === SMART TIME INPUTS ===
function initializeSmartTimeInputs() {
    const timeInputs = document.querySelectorAll('[data-time-input]');
    
    timeInputs.forEach(input => {
        // Real-time validation and formatting
        input.addEventListener('input', (e) => {
            const inputId = e.target.id;
            let value = e.target.value;
            
            // Auto-format the input
            const formatted = formatTimeInput(value);
            if (formatted !== value) {
                e.target.value = formatted;
                value = formatted;
            }
            
            // Clear previous error
            hideTimeError(inputId);
            
            // Validate if we have a complete time format
            if (value && value.length >= 7) {
                const validation = validateTimeFormat(value);
                if (!validation.valid) {
                    showTimeError(inputId, validation.error);
                }
            }
        });
        
        // Prevent invalid characters
        input.addEventListener('keypress', (e) => {
            const char = String.fromCharCode(e.which);
            const currentValue = e.target.value;
            
            // Allow numbers, colons, backspace, delete
            if (!/[\d:]/.test(char) && ![8, 46].includes(e.which)) {
                e.preventDefault();
                return;
            }
            
            // Prevent too many colons
            if (char === ':' && (currentValue.match(/:/g) || []).length >= 2) {
                e.preventDefault();
                return;
            }
        });
        
        // Handle paste events
        input.addEventListener('paste', (e) => {
            e.preventDefault();
            const paste = (e.clipboardData || window.clipboardData).getData('text');
            const formatted = formatTimeInput(paste);
            e.target.value = formatted;
            
            // Trigger validation
            const validation = validateTimeFormat(formatted);
            if (!validation.valid && formatted.length >= 7) {
                showTimeError(e.target.id, validation.error);
            } else {
                hideTimeError(e.target.id);
            }
        });
        
        // Handle focus events for better UX
        input.addEventListener('focus', (e) => {
            hideTimeError(e.target.id);
            e.target.select(); // Select all text on focus
        });
        
        // Handle blur events for final validation
        input.addEventListener('blur', (e) => {
            const value = e.target.value.trim();
            if (value) {
                const validation = validateTimeFormat(value);
                if (!validation.valid) {
                    showTimeError(e.target.id, validation.error);
                } else {
                    hideTimeError(e.target.id);
                }
            }
        });
    });
    
    console.log('Smart time inputs initialized');
}

// === AUTO-SAVE FUNCTIONALITY ===
function initializeAutoSave() {
    const formInputs = [
        UI.youtubeUrlInput,
        UI.customPromptInput,
        UI.startTimeInput,
        UI.endTimeInput
    ].filter(Boolean);
    
    // Debounce function to avoid excessive saves
    const debouncedSave = debounce(() => {
        StateManager.saveFormState();
        console.log('Form state auto-saved');
    }, 1000);
    
    formInputs.forEach(input => {
        input.addEventListener('input', debouncedSave);
        input.addEventListener('change', debouncedSave);
    });
    
    console.log('Auto-save initialized for form inputs');
}

// === ANIMATED COUNTERS ===
function initializeCounters() {
    const counters = document.querySelectorAll('.stat-number[data-count]');
    
    const animateCounter = (counter) => {
        const target = parseInt(counter.getAttribute('data-count'));
        const duration = 2000; // 2 seconds
        const step = target / (duration / 16); // 60fps
        let current = 0;
        
        const updateCounter = () => {
            current += step;
            if (current < target) {
                counter.textContent = Math.floor(current);
                requestAnimationFrame(updateCounter);
            } else {
                counter.textContent = target;
            }
        };
        
        updateCounter();
    };
    
    // Use Intersection Observer to trigger animation when visible
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !entry.target.classList.contains('animated')) {
                entry.target.classList.add('animated');
                animateCounter(entry.target);
            }
        });
    }, { threshold: 0.5 });
    
    counters.forEach(counter => observer.observe(counter));
    
    console.log('Animated counters initialized');
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// === RESULT PAGE FUNCTIONS ===
function updateHighlightJsTheme(theme) {
    const darkThemeLink = document.getElementById('hljs-theme-dark');
    const lightThemeLink = document.getElementById('hljs-theme-light');
    
    if (darkThemeLink && lightThemeLink) {
        if (theme === 'dark') {
            darkThemeLink.media = 'all';
            lightThemeLink.media = 'not all';
        } else {
            darkThemeLink.media = 'not all';
            lightThemeLink.media = 'all';
        }
    }
}

function renderVideoSection(video) {
    const videoIdClean = video.id ? 
        video.id.replace(/[^a-zA-Z0-9-_]/g, '') : 
        `video-${Math.random().toString(36).substring(7)}`;
    
    let transcriptHTML = '';
    if (video.transcript && !video.transcript.startsWith("Error:")) {
        transcriptHTML = `<pre><code>${video.transcript.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></pre>`;
    } else if (video.transcript) {
        transcriptHTML = `<div class="error-message transcript-error">${video.transcript}</div>`;
    } else {
        transcriptHTML = `<p>Transcript not available for this video.</p>`;
    }
    
    let summaryHTML = '';
    if (video.summary_markdown && !video.summary_markdown.startsWith("Error:")) {
        try {
            summaryHTML = typeof marked !== 'undefined' ? 
                marked.parse(video.summary_markdown) : 
                video.summary_markdown;
        } catch (e) {
            console.error("Markdown parsing error:", e);
            summaryHTML = `<div class="error-message">Error rendering summary.</div>`;
        }
    } else if (video.summary_markdown) {
        summaryHTML = `<div class="error-message summary-error">${video.summary_markdown}</div>`;
    } else {
        summaryHTML = `<p>Summary not available for this video.</p>`;
    }
    
    const videoErrorHTML = video.error ? 
        `<div class="error-message video-item-error">${video.error}</div>` : '';
    
    return `
        <div class="video-section" id="video-${videoIdClean}">
            <!-- Modern Video Header -->
            <div class="video-header">
                <h2 class="video-title">
                    <a href="${video.url || '#'}" target="_blank" rel="noopener noreferrer">
                        ${video.title || `Video ID: ${video.id || 'Unknown'}`}
                    </a>
                </h2>
            </div>
            
            <!-- Video Content -->
            <div class="video-content">
                ${videoErrorHTML}
                
                <!-- Modern Summary Section -->
                <div class="video-summary">
                    ${summaryHTML}
                </div>
                
                <!-- Transcript Section with Toggle -->
                <div class="transcript-section">
                    <button class="transcript-toggle-btn modern-toggle" data-target="transcript-${videoIdClean}">
                        <i class="fas fa-file-text"></i>
                        <span>View Transcript</span>
                        <i class="fas fa-chevron-down toggle-icon"></i>
                    </button>
                    
                    <div class="video-transcript" id="transcript-${videoIdClean}">
                        <div class="transcript-content">
                            <h4>📄 Full Transcript</h4>
                            ${transcriptHTML}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

function displayResults(data) {
    const resultsArea = document.getElementById('results-area');
    const playlistTitleDisplay = document.getElementById('playlist-title-display');
    const errorDisplayMain = document.getElementById('error-display-main');
    
    if (resultsArea) resultsArea.innerHTML = '';
    
    if (!data || (data.error && !data.videos)) {
        if (errorDisplayMain) {
            errorDisplayMain.textContent = data?.error || 'No data received or an unknown error occurred.';
            errorDisplayMain.style.display = 'block';
        }
        return;
    }
    
    if (data.error && data.videos && data.videos.length === 0) {
        if (errorDisplayMain) {
            errorDisplayMain.textContent = `Playlist Error: ${data.error}`;
            errorDisplayMain.style.display = 'block';
        }
    }
    
    if (data.is_playlist && data.playlist_title && playlistTitleDisplay) {
        playlistTitleDisplay.textContent = `Playlist: ${data.playlist_title}`;
        playlistTitleDisplay.style.display = 'block';
    } else if (playlistTitleDisplay) {
        playlistTitleDisplay.style.display = 'none';
    }
    
    if (data.videos && data.videos.length > 0 && resultsArea) {
        data.videos.forEach(video => {
            resultsArea.innerHTML += renderVideoSection(video);
        });
        
        // Add event listeners for transcript toggles
        document.querySelectorAll('.transcript-toggle-btn').forEach(button => {
            button.addEventListener('click', function() {
                const targetId = this.dataset.target;
                const content = document.getElementById(targetId);
                
                if (content) {
                    if (content.style.display === 'none') {
                        content.style.display = 'block';
                        this.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Transcript';
                    } else {
                        content.style.display = 'none';
                        this.innerHTML = '<i class="fas fa-eye"></i> Show Transcript';
                    }
                }
            });
        });
    } else if (!data.error && resultsArea) {
        resultsArea.innerHTML = '<p class="no-results-message">No videos were processed or found.</p>';
    }
}

// === INITIALIZATION ===
function initializeApp() {
    console.log('Initializing main app...');
    
    cacheElements();
    console.log('Elements cached:', UI);
    
    initializeTheme();
    initializeTimeInputs();
    initializeInputAnimations();
    initializeSmartTimeInputs();
    initializeAutoSave();
    initializeCounters();
    
    // Restore form state from previous session
    StateManager.restoreFormState();
    
    // Theme toggle
    if (UI.themeToggleButton) {
        UI.themeToggleButton.addEventListener('click', toggleTheme);
        console.log('Theme toggle initialized');
    } else {
        console.warn('Theme toggle button not found');
    }
    
    // Form submission
    if (UI.form) {
        UI.form.addEventListener('submit', handleSubmit);
        console.log('Form submission handler attached');
    } else {
        console.warn('Form not found');
    }
    
    // Video info fetching
    if (UI.youtubeUrlInput) {
        UI.youtubeUrlInput.addEventListener('blur', debounce(async () => {
            const url = UI.youtubeUrlInput.value.trim();
            if (!url) return;
            
            const isPlaylist = url.includes('list=') || url.toLowerCase().includes('playlist');
            const note = document.getElementById('playlist-time-note');
            if (note) note.style.display = isPlaylist ? 'block' : 'none';
            
            if (!isPlaylist) {
                await fetchVideoInfo(url);
            } else {
                AppState.videoDuration = null;
            }
        }, 500));
    }
    
    // Resume ongoing task
    const ongoingTaskId = sessionStorage.getItem('currentTaskPlaying');
    if (ongoingTaskId) {
        AppState.currentTaskId = ongoingTaskId;
        const storedResult = sessionStorage.getItem('taskResult');
        
        if (storedResult) {
            try {
                const resultData = JSON.parse(storedResult);
                if (resultData?.task_id === ongoingTaskId && 
                    ['completed', 'failed'].includes(resultData.status)) {
                    console.log("Task already finished, found in session storage.");
                    return;
                }
            } catch (e) {
                console.error("Error parsing stored result:", e);
            }
        }
        
        showLoading("Resuming task status check...");
        checkTaskStatus(ongoingTaskId);
    }
}

function initializeResultPage() {
    cacheElements();
    initializeTheme();
    
    if (UI.themeToggleButton) {
        UI.themeToggleButton.addEventListener('click', toggleTheme);
    }
    
    // Configure marked if available
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            highlight: function (code, lang) {
                if (typeof hljs !== 'undefined') {
                    const language = hljs.getLanguage(lang) ? lang : 'plaintext';
                    return hljs.highlight(code, { language }).value;
                }
                return code;
            },
            breaks: true,
            gfm: true,
            sanitize: false,
            smartLists: true,
            smartypants: false
        });
    }
    
    // Load and display results
    const resultDataScript = document.getElementById('result-data-script');
    let resultData = null;
    
    if (resultDataScript?.textContent) {
        try {
            resultData = JSON.parse(resultDataScript.textContent);
        } catch (e) {
            console.error("Error parsing result data from script tag:", e);
            const errorDisplayMain = document.getElementById('error-display-main');
            if (errorDisplayMain) {
                errorDisplayMain.textContent = 'Error loading result data from page.';
                errorDisplayMain.style.display = 'block';
            }
        }
    }
    
    // Fallback to session storage
    if (!resultData || Object.keys(resultData).length === 0) {
        const storedResult = sessionStorage.getItem('taskResult');
        if (storedResult) {
            try {
                resultData = JSON.parse(storedResult);
            } catch (e) {
                console.error("Error parsing result data from session storage:", e);
            }
        }
    }
    
    if (resultData) {
        displayResults(resultData);
    } else {
        const errorDisplayMain = document.getElementById('error-display-main');
        if (errorDisplayMain) {
            errorDisplayMain.textContent = 'No result data found to display. Please try generating a summary again.';
            errorDisplayMain.style.display = 'block';
        }
    }
    
    // Cleanup
    sessionStorage.removeItem('taskResult');
    sessionStorage.removeItem('currentTaskPlaying');
}

// === DOM READY ===
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing app...');
    
    // Determine which page we're on and initialize accordingly
    if (document.getElementById('results-area')) {
        console.log('Result page detected');
        initializeResultPage();
    } else {
        console.log('Main page detected');
        initializeApp();
    }
});

// === CLEANUP ===
window.addEventListener('beforeunload', () => {
    stopPolling();
});
