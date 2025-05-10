document.addEventListener('DOMContentLoaded', function() {
    console.log("SCRIPT: DOMContentLoaded event fired. Attempting to select elements.");

    // --- Selectors - Grouped at the top ---
    const bodyElement = document.getElementById('the-body');
    const themeToggleButton = document.getElementById('theme-toggle-button');
    const themeIcon = themeToggleButton ? themeToggleButton.querySelector('i') : null;

    const historyModal = document.getElementById('history-modal');
    const logModal = document.getElementById('log-modal');
    const historyDisplay = document.getElementById('history-display');
    const logDisplay = document.getElementById('log-display');
    const historyLoading = document.getElementById('history-loading');
    const logLoading = document.getElementById('log-loading');
    const viewHistoryBtn = document.getElementById('view-history-btn');
    const viewLogBtn = document.getElementById('view-log-btn');
    const closeModalBtns = document.querySelectorAll('.close-modal-btn');
    const refreshLogBtn = document.getElementById('refresh-log-btn');
    const statusIndicator = document.getElementById('script-status-indicator');
    const statusText = document.getElementById('script-status-text');
    const startScriptBtn = document.getElementById('start-script-btn');
    const stopScriptBtn = document.getElementById('stop-script-btn');
    const testPlexBtn = document.getElementById('test-plex-btn');
    const nextRunCountdown = document.getElementById('next-run-countdown');
    const dryRunToggleBtn = document.getElementById('dry-run-toggle-btn');

    // --- Log if elements are found ---
    if (!bodyElement) { console.error("SCRIPT CRITICAL: bodyElement with ID 'the-body' NOT FOUND."); }
    else { console.log("SCRIPT: bodyElement found."); }
    if (!themeToggleButton) { console.error("SCRIPT CRITICAL: themeToggleButton with ID 'theme-toggle-button' NOT FOUND."); }
    else { console.log("SCRIPT: themeToggleButton found."); }
    if (!dryRunToggleBtn) { console.warn("SCRIPT: dryRunToggleBtn with ID 'dry-run-toggle-btn' NOT FOUND."); }
    else { console.log("SCRIPT: dryRunToggleBtn found."); }
    if (!viewHistoryBtn) { console.warn("SCRIPT: viewHistoryBtn with ID 'view-history-btn' NOT FOUND."); } // Added log
    else { console.log("SCRIPT: viewHistoryBtn found."); }
    if (!viewLogBtn) { console.warn("SCRIPT: viewLogBtn with ID 'view-log-btn' NOT FOUND."); } // Added log
    else { console.log("SCRIPT: viewLogBtn found."); }


    // Global state
    let statusIntervalId = null;
    let countdownIntervalId = null;
    let nextRunTargetTimestamp = null;
    let isDryRunActive = false;

    // --- Theme Toggle ---
    function applyTheme(theme) {
        if (!bodyElement) {
            console.error("SCRIPT: Cannot apply theme, bodyElement is null or undefined!");
            document.body.style.backgroundColor = (theme === 'dark' ? '#1a1a1a' : '#f8f9fa');
            return;
        }
        if (theme === 'dark') {
            bodyElement.classList.add('dark-mode');
            if (themeIcon) { themeIcon.classList.remove('fa-moon'); themeIcon.classList.add('fa-sun'); }
            localStorage.setItem('theme', 'dark');
        } else {
            bodyElement.classList.remove('dark-mode');
            if (themeIcon) { themeIcon.classList.remove('fa-sun'); themeIcon.classList.add('fa-moon'); }
            localStorage.setItem('theme', 'light');
        }
    }

    // --- Dry Run Button Appearance ---
    function updateDryRunButtonAppearance() {
        if (!dryRunToggleBtn) return;
        if (isDryRunActive) {
            dryRunToggleBtn.classList.add('active');
            dryRunToggleBtn.innerHTML = '✅ Dry-Run ON';
        } else {
            dryRunToggleBtn.classList.remove('active');
            dryRunToggleBtn.innerHTML = '❌ Dry-Run OFF';
        }
    }

    // --- Initial Theme Application ---
    if (bodyElement) {
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (savedTheme) { applyTheme(savedTheme); }
        else if (prefersDark) { applyTheme('dark'); }
        else { applyTheme('light'); }
    } else {
        console.error("SCRIPT: Initial theme application skipped because bodyElement was not found.");
    }

    // --- Event Listener for Theme Toggle Button ---
    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            if (!bodyElement) { console.error("SCRIPT: Cannot toggle theme, bodyElement is missing."); return; }
            const currentTheme = bodyElement.classList.contains('dark-mode') ? 'dark' : 'light';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
        });
    } else {
        console.warn("SCRIPT: Theme toggle button not found, listener not added.");
    }

    // --- Status Indicator & Countdown ---
    function formatTimeRemaining(totalSeconds) { /* ... (no changes here) ... */
        if (totalSeconds === null || totalSeconds < 0) return "";
        const days = Math.floor(totalSeconds / (3600 * 24));
        const hours = Math.floor((totalSeconds % (3600 * 24)) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = Math.floor(totalSeconds % 60);
        let parts = [];
        if (days > 0) parts.push(`${days}d`);
        if (hours > 0 || days > 0) parts.push(`${hours}h`);
        if (minutes > 0 || hours > 0 || days > 0) parts.push(`${minutes}m`);
        if (seconds >= 0 && parts.length < 3) parts.push(`${seconds}s`);
        return parts.length > 0 ? `Next run in ~${parts.join(' ')}` : "Next run starting soon";
    }
    function updateCountdown() { /* ... (no changes here) ... */
        if (!nextRunTargetTimestamp || !nextRunCountdown) {
             if (nextRunCountdown) nextRunCountdown.textContent = "";
             return;
        }
        const nowSeconds = Date.now() / 1000;
        const remainingSeconds = Math.max(0, nextRunTargetTimestamp - nowSeconds);
        if (remainingSeconds > 0) {
             nextRunCountdown.textContent = formatTimeRemaining(remainingSeconds);
        } else {
            nextRunCountdown.textContent = "Next run starting soon";
        }
    }
    async function updateScriptStatus() { /* ... (no changes here, already handles dryRunToggleBtn disable/enable) ... */
        if (!statusIndicator || !statusText) {
            return;
        }
        try {
            const response = await fetch('/status');
            if (!response.ok) { throw new Error(`HTTP error! status: ${response.status}`); }
            const currentStatusData = await response.json();
            const isRunning = currentStatusData.script_running;
            const lastKnownStatus = currentStatusData.last_known_script_status || "Unknown";
            const nextRunTs = currentStatusData.next_run_timestamp;

            statusIndicator.classList.remove('status-running', 'status-stopped', 'status-unknown', 'status-crashed', 'status-error');
            statusText.classList.remove('status-error-text');

            if (isRunning) {
                statusIndicator.classList.add('status-running');
                statusIndicator.textContent = '✔';
                statusText.textContent = `Script: ${lastKnownStatus}`;
                if (startScriptBtn) startScriptBtn.disabled = true;
                if (stopScriptBtn) stopScriptBtn.disabled = false;
                if (dryRunToggleBtn) dryRunToggleBtn.disabled = true;

                if (nextRunTs && typeof nextRunTs === 'number') {
                    nextRunTargetTimestamp = nextRunTs;
                    if (!countdownIntervalId) {
                         updateCountdown();
                         countdownIntervalId = setInterval(updateCountdown, 1000);
                    }
                } else {
                    nextRunTargetTimestamp = null;
                    if (nextRunCountdown) nextRunCountdown.textContent = "";
                    clearInterval(countdownIntervalId);
                    countdownIntervalId = null;
                }
            } else {
                clearInterval(countdownIntervalId);
                countdownIntervalId = null;
                nextRunTargetTimestamp = null;
                if (nextRunCountdown) nextRunCountdown.textContent = "";

                if (lastKnownStatus.toLowerCase().includes("crashed") || lastKnownStatus.toLowerCase().includes("fatal")) {
                     statusIndicator.classList.add('status-crashed');
                     statusIndicator.textContent = '!';
                     statusText.textContent = `Script Status: ${lastKnownStatus}`;
                     statusText.classList.add('status-error-text');
                } else if (lastKnownStatus.toLowerCase().includes("error")) {
                     statusIndicator.classList.add('status-error');
                     statusIndicator.textContent = '✘';
                     statusText.textContent = `Script Status: ${lastKnownStatus}`;
                     statusText.classList.add('status-error-text');
                } else {
                     statusIndicator.classList.add('status-stopped');
                     statusIndicator.textContent = '✘';
                     statusText.textContent = 'Script Stopped';
                }

                if (startScriptBtn) startScriptBtn.disabled = false;
                if (stopScriptBtn) stopScriptBtn.disabled = true;
                if (dryRunToggleBtn) dryRunToggleBtn.disabled = false;
            }
        } catch (error) {
            console.error("SCRIPT: Error updating status:", error);
            if (statusIndicator) {
                statusIndicator.classList.remove('status-running', 'status-stopped', 'status-crashed', 'status-error');
                statusIndicator.classList.add('status-unknown');
                statusIndicator.textContent = '?';
            }
            if (statusText) {
                statusText.textContent = 'Status Unknown (Error)';
                statusText.classList.add('status-error-text');
            }
            if (startScriptBtn) startScriptBtn.disabled = true;
            if (stopScriptBtn) stopScriptBtn.disabled = true;
            if (dryRunToggleBtn) dryRunToggleBtn.disabled = true;

            clearInterval(countdownIntervalId);
            countdownIntervalId = null;
            nextRunTargetTimestamp = null;
            if (nextRunCountdown) nextRunCountdown.textContent = "";
        }
    }

    // --- Modal Elements & Functions ---
    function openModal(modalElement) {
        if (modalElement) {
            console.log("SCRIPT: Opening modal:", modalElement.id);
            modalElement.style.display = 'block';
        } else {
            console.warn("SCRIPT: Attempted to open a null modal element.");
        }
    }
    function closeModal(modalElement) {
        if (modalElement) {
            modalElement.style.display = 'none';
        }
    }

    async function fetchAndShowHistory() {
        console.log("SCRIPT: fetchAndShowHistory called."); // Log function entry
        if (!historyDisplay || !historyLoading) {
            console.warn("SCRIPT: History display or loading element not found in fetchAndShowHistory.");
            return;
        }
        if (!historyModal) { // Check if modal element itself is found
            console.error("SCRIPT: historyModal element not found. Cannot open history.");
            return;
        }
        historyDisplay.textContent = '';
        historyLoading.style.display = 'block';
        openModal(historyModal);
        try {
            const response = await fetch('/get_history');
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || `HTTP error! status: ${response.status}`); }
            historyDisplay.textContent = JSON.stringify(data, null, 2);
        } catch (error) {
            console.error('SCRIPT: Error fetching history:', error);
            historyDisplay.textContent = `Error loading history:\n${error.message}`;
        } finally {
            historyLoading.style.display = 'none';
        }
    }

    async function fetchAndShowLog() {
        console.log("SCRIPT: fetchAndShowLog called."); // Log function entry
        if (!logDisplay || !logLoading) {
            console.warn("SCRIPT: Log display or loading element not found in fetchAndShowLog.");
            return;
        }
        if (!logModal) { // Check if modal element itself is found
            console.error("SCRIPT: logModal element not found. Cannot open log.");
            return;
        }
        logDisplay.textContent = '';
        logLoading.style.display = 'block';
        const wasAlreadyOpen = logModal.style.display === 'block';
        if (!wasAlreadyOpen) {
             openModal(logModal);
        }
        try {
            const response = await fetch('/get_log');
            const data = await response.json();
             if (!response.ok) { throw new Error(data.error || `HTTP error! status: ${response.status}`); }
            logDisplay.textContent = data.log_content || '(Log file might be empty or inaccessible)';
            logDisplay.scrollTop = logDisplay.scrollHeight;

        } catch (error) {
            console.error('SCRIPT: Error fetching log:', error);
            logDisplay.textContent = `Error loading log:\n${error.message}`;
            logDisplay.scrollTop = logDisplay.scrollHeight;
        } finally {
             logLoading.style.display = 'none';
        }
    }

    // --- Event Listeners for Modals (Ensured they are correctly set) ---
    if (viewHistoryBtn) {
        viewHistoryBtn.addEventListener('click', fetchAndShowHistory);
        console.log("SCRIPT: Event listener for viewHistoryBtn ADDED.");
    } else {
        console.warn("SCRIPT: View History Button (view-history-btn) NOT FOUND. Listener not added.");
    }

    if (viewLogBtn) {
        viewLogBtn.addEventListener('click', fetchAndShowLog);
        console.log("SCRIPT: Event listener for viewLogBtn ADDED.");
    } else {
        console.warn("SCRIPT: View Log Button (view-log-btn) NOT FOUND. Listener not added.");
    }

    if (refreshLogBtn) { // Keep this if it's part of your modal
        refreshLogBtn.addEventListener('click', fetchAndShowLog);
    }
    closeModalBtns.forEach(btn => {
         btn.addEventListener('click', () => {
            const modalToClose = btn.closest('.modal');
            if (modalToClose) closeModal(modalToClose);
        });
     });
    window.addEventListener('click', (event) => {
        if (historyModal && event.target == historyModal) closeModal(historyModal); // Check if historyModal exists
        if (logModal && event.target == logModal) closeModal(logModal); // Check if logModal exists
    });

    // --- Dry-Run Toggle Button Listener ---
    if (dryRunToggleBtn) {
        updateDryRunButtonAppearance();
        dryRunToggleBtn.addEventListener('click', () => {
            if (dryRunToggleBtn.disabled) return;
            isDryRunActive = !isDryRunActive;
            updateDryRunButtonAppearance();
            console.log(`SCRIPT: Dry-Run Mode toggled. Now: ${isDryRunActive ? 'ON' : 'OFF'}`);
        });
    } else {
        console.warn("SCRIPT: Dry-Run Toggle Button (dry-run-toggle-btn) not found. Dry-run functionality via UI will not work.");
    }

    // --- Control Button Actions ---
    async function handleControlClick(button, url, actionName, isStartButton = false) {
         if (!button) {
             console.error(`SCRIPT: Button for action "${actionName}" not found.`);
             return;
         }
         console.log(`SCRIPT: ${actionName} button clicked.`);
         
         const buttonsToDisable = [startScriptBtn, stopScriptBtn, testPlexBtn];
         if (button !== dryRunToggleBtn) {
             buttonsToDisable.push(dryRunToggleBtn);
         }
         buttonsToDisable.forEach(btn => { if(btn) btn.disabled = true; });

         const originalHtml = button.innerHTML;
         // Only show spinner if it's not the dryRunToggleBtn, whose content is managed differently
         if (button !== dryRunToggleBtn) {
            button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${actionName}...`;
         }


         let finalUrl = url;
         if (isStartButton) {
             finalUrl = `${url}?dry_run=${isDryRunActive}`;
             console.log(`SCRIPT: Starting script with Dry-Run=${isDryRunActive}. URL: ${finalUrl}`);
         }

         try {
             const response = await fetch(finalUrl, { method: 'POST' });
             let responseData = {};
             try { responseData = await response.json(); } catch(e) {}

             if (!response.ok) {
                 const errorMsg = responseData.message || responseData.error || `Request failed with status ${response.status}`;
                 throw new Error(errorMsg);
             }
             console.log(`SCRIPT: ${actionName} request successful.`);
             if (actionName === 'Test Plex' && responseData.message) {
                 alert(`Plex Connection Test:\n${responseData.success ? '✅' : '❌'} ${responseData.message}`);
             }
         } catch (error) {
             console.error(`SCRIPT: Error during ${actionName} action:`, error);
             alert(`${actionName} Action Failed:\n${error.message}`);
         } finally {
             if (button !== dryRunToggleBtn) {
                 button.innerHTML = originalHtml;
             }
             await updateScriptStatus(); 
         }
    }

    if (startScriptBtn) {
        startScriptBtn.addEventListener('click', () => handleControlClick(startScriptBtn, '/start', 'Start Script', true));
    } else { console.warn("SCRIPT: Start Script Button not found."); }

    if (stopScriptBtn) {
        stopScriptBtn.addEventListener('click', () => handleControlClick(stopScriptBtn, '/stop', 'Stop Script'));
    } else { console.warn("SCRIPT: Stop Script Button not found."); }

    if (testPlexBtn) {
        testPlexBtn.addEventListener('click', () => handleControlClick(testPlexBtn, '/test_plex', 'Test Plex'));
    } else { console.warn("SCRIPT: Test Plex Button not found."); }

    // Initial status update and interval
    updateScriptStatus();
    if (statusIntervalId) clearInterval(statusIntervalId);
    statusIntervalId = setInterval(updateScriptStatus, 10000);


    // --- Dynamic Lists/Sections Listener ---
    document.body.addEventListener('click', function(event) { /* ... your existing dynamic form logic ... */ });

    console.log("SCRIPT: Setup complete.");
});