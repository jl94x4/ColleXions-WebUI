document.addEventListener('DOMContentLoaded', function() {
    console.log("SCRIPT: DOMContentLoaded event fired.");

    // --- Selectors ---
    const themeToggleButton = document.getElementById('theme-toggle-button');
    const bodyElement = document.getElementById('the-body');
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

    // Global state for intervals/timeouts
    let statusIntervalId = null;
    let countdownIntervalId = null;
    let nextRunTargetTimestamp = null; // Store the target timestamp from server

    console.log("SCRIPT: Theme Toggle Button found?", themeToggleButton);
    console.log("SCRIPT: Body Element found?", bodyElement);

    // --- Theme Toggle ---
    function applyTheme(theme) {
        console.log(`SCRIPT: Applying theme: ${theme}`);
        if (!bodyElement) { console.error("SCRIPT: Cannot apply theme, bodyElement is null!"); return; }
        if (theme === 'dark') {
             bodyElement.classList.add('dark-mode');
             if (themeIcon) { themeIcon.classList.remove('fa-moon'); themeIcon.classList.add('fa-sun'); }
             localStorage.setItem('theme', 'dark');
             console.log("SCRIPT: Dark mode class added.");
        } else {
            bodyElement.classList.remove('dark-mode');
            if (themeIcon) { themeIcon.classList.remove('fa-sun'); themeIcon.classList.add('fa-moon'); }
            localStorage.setItem('theme', 'light');
            console.log("SCRIPT: Dark mode class removed.");
        }
    }
    console.log("SCRIPT: Applying initial theme...");
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    console.log(`SCRIPT: Saved theme: ${savedTheme}, Prefers dark: ${prefersDark}`);
    try {
        if (savedTheme) { applyTheme(savedTheme); }
        else if (prefersDark) { applyTheme('dark'); }
        else { applyTheme('light'); }
    } catch (e) {
         console.error("SCRIPT: Error applying initial theme:", e);
         try { applyTheme('light'); } catch (e2) { console.error("SCRIPT: Failed fallback theme:", e2); }
    }
    if (themeToggleButton && bodyElement) {
        console.log("SCRIPT: Adding theme toggle listener.");
        themeToggleButton.addEventListener('click', () => {
            try {
                const currentTheme = bodyElement.classList.contains('dark-mode') ? 'dark' : 'light';
                const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                applyTheme(newTheme);
            } catch (e) { console.error("SCRIPT: Error in theme toggle click:", e); } });
    } else { console.error("SCRIPT: Could not add theme listener - button or body missing!"); }


    // --- Status Indicator & Countdown ---
    function formatTimeRemaining(totalSeconds) {
        if (totalSeconds === null || totalSeconds < 0) return "";

        const days = Math.floor(totalSeconds / (3600 * 24));
        const hours = Math.floor((totalSeconds % (3600 * 24)) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = Math.floor(totalSeconds % 60);

        let parts = [];
        if (days > 0) parts.push(`${days}d`);
        if (hours > 0 || days > 0) parts.push(`${hours}h`); // Show hours if days are shown
        if (minutes > 0 || hours > 0 || days > 0) parts.push(`${minutes}m`); // Show mins if larger units shown
        if (seconds >= 0 && parts.length < 3) parts.push(`${seconds}s`); // Show seconds always

        return parts.length > 0 ? `Next run in ~${parts.join(' ')}` : "Next run starting soon";
    }

    function updateCountdown() {
        if (!nextRunTargetTimestamp || !nextRunCountdown) {
             if (nextRunCountdown) nextRunCountdown.textContent = ""; // Clear if no target
             return;
        }
        // Timestamps from Python's .timestamp() are usually in seconds since epoch
        const nowSeconds = Date.now() / 1000;
        const remainingSeconds = Math.max(0, nextRunTargetTimestamp - nowSeconds);

        if (remainingSeconds > 0) {
             nextRunCountdown.textContent = formatTimeRemaining(remainingSeconds);
        } else {
            nextRunCountdown.textContent = "Next run starting soon";
            // Optionally stop the interval once it hits zero if status confirms it's running
            // clearInterval(countdownIntervalId);
            // countdownIntervalId = null;
        }
    }

    async function updateScriptStatus() {
        // console.log("SCRIPT: Updating script status..."); // Reduce frequency of this log
        if (!statusIndicator || !statusText) {
            console.error("SCRIPT: Status indicator or text element not found.");
            return;
        }

        let currentStatusData = {}; // Store status data

        try {
            const response = await fetch('/status');
            if (!response.ok) {
                 throw new Error(`HTTP error! status: ${response.status}`);
            }
            currentStatusData = await response.json();
            // console.log("SCRIPT: Status data received:", currentStatusData); // Reduce frequency

            const isRunning = currentStatusData.script_running;
            const lastKnownStatus = currentStatusData.last_known_script_status || "Unknown";
            const nextRunTs = currentStatusData.next_run_timestamp; // Expecting timestamp in seconds

            statusIndicator.classList.remove('status-running', 'status-stopped', 'status-unknown', 'status-crashed', 'status-error');
            statusText.classList.remove('status-error-text'); // Reset error text style

            if (isRunning) {
                statusIndicator.classList.add('status-running');
                statusIndicator.textContent = '✔';
                statusText.textContent = 'Script Running';
                if (startScriptBtn) startScriptBtn.disabled = true;
                if (stopScriptBtn) stopScriptBtn.disabled = false;

                // --- Countdown Logic ---
                if (nextRunTs && typeof nextRunTs === 'number') {
                    nextRunTargetTimestamp = nextRunTs; // Store the target timestamp
                    if (!countdownIntervalId) {
                         // console.log("SCRIPT: Starting countdown interval.");
                         updateCountdown(); // Update immediately
                         countdownIntervalId = setInterval(updateCountdown, 1000);
                    }
                } else {
                    // console.log("SCRIPT: No valid next run timestamp received, clearing countdown.");
                    nextRunTargetTimestamp = null;
                    if (nextRunCountdown) nextRunCountdown.textContent = "";
                    clearInterval(countdownIntervalId);
                    countdownIntervalId = null;
                }

            } else { // Script is NOT running
                clearInterval(countdownIntervalId); // Stop countdown if script stops
                countdownIntervalId = null;
                nextRunTargetTimestamp = null;
                if (nextRunCountdown) nextRunCountdown.textContent = ""; // Clear display

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
                }
                 else {
                     statusIndicator.classList.add('status-stopped');
                     statusIndicator.textContent = '✘';
                     statusText.textContent = 'Script Stopped';
                 }

                if (startScriptBtn) startScriptBtn.disabled = false;
                if (stopScriptBtn) stopScriptBtn.disabled = true;
            }

        } catch (error) {
            console.error("SCRIPT: Error updating status:", error);
            statusIndicator.classList.remove('status-running', 'status-stopped', 'status-crashed', 'status-error');
            statusIndicator.classList.add('status-unknown');
            statusIndicator.textContent = '?';
            statusText.textContent = 'Status Unknown (Error)';
            statusText.classList.add('status-error-text');
            if (startScriptBtn) startScriptBtn.disabled = true;
            if (stopScriptBtn) stopScriptBtn.disabled = true;

            clearInterval(countdownIntervalId);
            countdownIntervalId = null;
            nextRunTargetTimestamp = null;
            if (nextRunCountdown) nextRunCountdown.textContent = "";
        }
    }

    // Initial status update and set interval
    updateScriptStatus();
    if (statusIntervalId) clearInterval(statusIntervalId); // Clear previous interval if any
    statusIntervalId = setInterval(updateScriptStatus, 10000); // Update status every 10 seconds


    // --- Modal Elements & Functions ---
    function openModal(modalElement) { if (modalElement) { modalElement.style.display = 'block'; } }
    function closeModal(modalElement) { if (modalElement) { modalElement.style.display = 'none'; } }

    // --- Fetch and Display Functions ---
    async function fetchAndShowHistory() {
        if (!historyDisplay || !historyLoading) return;
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
        if (!logDisplay || !logLoading) return;
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

    // --- Event Listeners ---

    // Modals
    if (viewHistoryBtn) { viewHistoryBtn.addEventListener('click', fetchAndShowHistory); }
    if (viewLogBtn) { viewLogBtn.addEventListener('click', fetchAndShowLog); }
    if (refreshLogBtn) { refreshLogBtn.addEventListener('click', fetchAndShowLog); }
    closeModalBtns.forEach(btn => {
         btn.addEventListener('click', () => {
            const modalToClose = btn.closest('.modal');
            if (modalToClose) closeModal(modalToClose);
        });
     });
    window.addEventListener('click', (event) => {
        if (event.target == historyModal) closeModal(historyModal);
        if (event.target == logModal) closeModal(logModal);
    });

    // Start/Stop/Test Buttons
    async function handleControlClick(button, url, actionName) {
         if (!button) return;
         console.log(`SCRIPT: ${actionName} button clicked.`);
         [startScriptBtn, stopScriptBtn, testPlexBtn].forEach(btn => { if(btn) btn.disabled = true; });
         const originalHtml = button.innerHTML;
         button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${actionName}...`;

         try {
             const response = await fetch(url, { method: 'POST' });
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
             button.innerHTML = originalHtml;
             await updateScriptStatus();
         }
    }

    if (startScriptBtn) { startScriptBtn.addEventListener('click', () => handleControlClick(startScriptBtn, '/start', 'Start Script')); }
    if (stopScriptBtn) { stopScriptBtn.addEventListener('click', () => handleControlClick(stopScriptBtn, '/stop', 'Stop Script')); }
    if (testPlexBtn) { testPlexBtn.addEventListener('click', () => handleControlClick(testPlexBtn, '/test_plex', 'Test Plex')); }


    // --- Dynamic Lists/Sections Listener (Updated Logic) ---
    console.log("SCRIPT: Setting up dynamic list/section listeners.");
    document.body.addEventListener('click', function(event) {
        try {
            // --- Add Simple List Item (e.g., Library Name, Exclusion) ---
            const addItemButton = event.target.closest('.add-item-btn:not(.nested-add)');
            if (addItemButton) {
                const targetListId = addItemButton.dataset.target;
                const templateId = addItemButton.dataset.template;
                const list = document.getElementById(targetListId);
                const template = document.getElementById(templateId);
                if (list && template) {
                    const clone = template.content.cloneNode(true);
                    const input = clone.querySelector('input');
                    list.appendChild(clone);
                    if(input) input.focus();
                    console.log(`SCRIPT: Added item to list ${targetListId}`);
                } else {
                    console.error(`SCRIPT: Cannot find list (${targetListId}) or template (${templateId}) for simple item add`);
                }
            }

            // --- Add Category Section OR Special Collection Section ---
            const addSectionButton = event.target.closest('.add-section-btn');
            if (addSectionButton) {
                const targetListId = addSectionButton.dataset.target;
                const templateId = addSectionButton.dataset.template;
                // --- Add Logging Here ---
                const list = document.getElementById(targetListId);
                console.log(`SCRIPT: Attempting to find list element with ID '${targetListId}'. Found:`, list); // ADDED THIS LINE
                const template = document.getElementById(templateId);
                console.log(`SCRIPT: Attempting to find template element with ID '${templateId}'. Found:`, template); // ADDED THIS LINE
                // --- End Add Logging ---

                console.log(`SCRIPT: Add Section clicked. Target: ${targetListId}, Template: ${templateId}`); // Existing log

                if (list && template) { // Check if list and template were found
                    try {
                        let newSectionElement = null;

                        // --- DIFFERENTIATE LOGIC BASED ON TEMPLATE ---
                        if (templateId === 'special_collections_template') {
                            // --- Logic for adding Special Collection ---
                            console.log("SCRIPT: Handling Add Special Period.");
                            const clone = template.content.cloneNode(true);
                            newSectionElement = clone.querySelector('.dynamic-section-item') || clone.firstElementChild || clone;

                        } else if (templateId === 'category_template') {
                            // --- Logic for adding Category (existing logic) ---
                            console.log("SCRIPT: Handling Add Category.");
                            const library = addSectionButton.dataset.library;
                            if (!library) {
                                console.error("SCRIPT: Cannot add category section, missing data-library attribute on button.");
                                return;
                            }

                            const safeLibraryName = library.replace(/ /g, '_').replace(/-/g, '_');
                            const newIndex = list.querySelectorAll('.dynamic-section-item.category-item').length;
                            console.log(`SCRIPT: Adding category for library '${library}' (safe: ${safeLibraryName}), new index: ${newIndex}`);

                            let content = template.innerHTML;
                            content = content.replace(/{library}/g, library);
                            content = content.replace(/{safe_library}/g, safeLibraryName);
                            content = content.replace(/{index}/g, newIndex);

                            const wrapper = document.createElement('div');
                            wrapper.innerHTML = content;
                            const tempSection = wrapper.firstElementChild;

                            if (tempSection) {
                                const nestedList = tempSection.querySelector('.dynamic-list-container.nested div[id*="_collections_list"]');
                                if (nestedList) nestedList.id = `category_${safeLibraryName}_${newIndex}_collections_list`;
                                else console.warn("SCRIPT: Could not find nested list div in new category template instance.");

                                const nestedAddButton = tempSection.querySelector('.add-item-btn.nested-add');
                                if (nestedAddButton) {
                                     nestedAddButton.dataset.target = `category_${safeLibraryName}_${newIndex}_collections_list`;
                                     nestedAddButton.dataset.library = library;
                                     nestedAddButton.dataset.categoryIndex = newIndex;
                                } else console.warn("SCRIPT: Could not find nested add button in new category template instance.");

                                const nameInput = tempSection.querySelector(`input[name^="category_${library}_name"]`);
                                if(nameInput) nameInput.name = `category_${library}_name[]`;
                                const pinCountInput = tempSection.querySelector(`input[name^="category_${library}_pin_count"]`);
                                if(pinCountInput) pinCountInput.name = `category_${library}_pin_count[]`;

                                const firstCollInput = tempSection.querySelector(`.dynamic-list-item input[name*="_collections"]`);
                                if (firstCollInput) firstCollInput.name = `category_${library}_${newIndex}_collections[]`;
                                else console.warn("SCRIPT: Could not find initial collection input in new category section template.");

                                newSectionElement = tempSection;
                            } else {
                                console.error("SCRIPT: Could not create new category section element from template content:", content);
                            }
                        } else {
                             console.warn(`SCRIPT: Unknown templateId ('${templateId}') encountered for add-section-btn.`);
                             const clone = template.content.cloneNode(true);
                             newSectionElement = clone.querySelector('.dynamic-section-item') || clone.firstElementChild || clone;
                        }

                        // --- Append the new section (if created successfully) ---
                        if (newSectionElement && newSectionElement instanceof Node) {
                            list.appendChild(newSectionElement);
                            console.log(`SCRIPT: Appended new section to ${targetListId}`);
                            const firstInput = newSectionElement.querySelector('input');
                            if(firstInput) firstInput.focus();
                        } else {
                             console.error(`SCRIPT: Failed to create a valid new section element for template ${templateId}.`);
                        }

                    } catch (cloneError) {
                        console.error(`SCRIPT: Error cloning/appending template ${templateId} for target ${targetListId}:`, cloneError);
                    }
                } else {
                     // Simplified error message
                    console.error(`SCRIPT: Cannot add section. Missing list element (ID: ${targetListId}) or template element (ID: ${templateId}).`);
                }
            } // End if (addSectionButton)


            // --- Add Nested Collection Item (within a Category) ---
            const addNestedItemButton = event.target.closest('.add-item-btn.nested-add');
            if (addNestedItemButton) {
                 const targetListId = addNestedItemButton.dataset.target;
                 const templateId = addNestedItemButton.dataset.template;
                 const library = addNestedItemButton.dataset.library;
                 const categoryIndex = addNestedItemButton.dataset.categoryIndex;
                 const list = document.getElementById(targetListId);
                 const template = document.getElementById(templateId);

                 console.log(`SCRIPT: Adding nested item. Target: ${targetListId}, Template: ${templateId}, Library: ${library}, CatIndex: ${categoryIndex}`);

                 if (list && template && library !== undefined && categoryIndex !== undefined) {
                     const clone = template.content.cloneNode(true);
                     const inputElement = clone.querySelector('input[name*="_collections[]"]');
                     if (inputElement) {
                         inputElement.name = `category_${library}_${categoryIndex}_collections[]`;
                         console.log(`SCRIPT: Set nested input name to: ${inputElement.name}`);
                         list.appendChild(clone);
                         inputElement.focus();
                         console.log(`SCRIPT: Appended nested item to ${targetListId}`);
                     } else {
                          console.error("SCRIPT: Could not find input element within the nested item template clone:", template.innerHTML);
                     }
                 } else {
                     console.error(`SCRIPT: Cannot add nested item. Missing list (${targetListId}), template (${templateId}), library (${library}), or category index (${categoryIndex})`);
                 }
            } // End if (addNestedItemButton)


            // --- Remove Item (Simple or Nested) ---
            const removeItemButton = event.target.closest('.remove-item-btn');
            if (removeItemButton) {
                const itemToRemove = removeItemButton.closest('.dynamic-list-item');
                if (itemToRemove) {
                    itemToRemove.remove();
                    console.log("SCRIPT: Removed dynamic list item.");
                } else {
                    // Maybe it's removing a special collection section? (since its button now has remove-item-btn class)
                     const sectionToRemove = removeItemButton.closest('.special-collection-item');
                     if (sectionToRemove) {
                         sectionToRemove.remove();
                         console.log("SCRIPT: Removed special collection section item.");
                     }
                }
            }

            // --- Remove Section (Category Only now) ---
            const removeSectionButton = event.target.closest('.remove-section-btn');
            if (removeSectionButton) {
                 // This button should only exist on category items now
                const sectionToRemove = removeSectionButton.closest('.category-item'); // More specific selector
                if (sectionToRemove) {
                    sectionToRemove.remove();
                    console.log("SCRIPT: Removed dynamic category section item.");
                }
            }

            // --- Toggle Section Visibility ---
            const toggleSectionButton = event.target.closest('.toggle-section-btn');
            if (toggleSectionButton) {
                 if (event.target.closest('#theme-toggle-button')) return;
                 console.log("SCRIPT: Section toggle button clicked.");
                const section = toggleSectionButton.closest('.form-section');
                const content = section ? section.querySelector('.collapsible-content') : null;
                const icon = toggleSectionButton.querySelector('i');

                if (content) {
                     const isExpanded = content.style.display === 'block';
                     if (isExpanded) {
                         console.log("SCRIPT: Collapsing section.");
                         content.style.display = 'none';
                         toggleSectionButton.setAttribute('aria-expanded', 'false');
                         if (icon) { icon.classList.remove('fa-chevron-up'); icon.classList.add('fa-chevron-down'); }
                     } else {
                         console.log("SCRIPT: Expanding section.");
                         content.style.display = 'block';
                         toggleSectionButton.setAttribute('aria-expanded', 'true');
                         if (icon) { icon.classList.remove('fa-chevron-down'); icon.classList.add('fa-chevron-up'); }
                     }
                 } else { console.error("SCRIPT: Could not find collapsible content for section button."); }
            }
        } catch (e) {
            console.error("SCRIPT: Error inside main body click listener:", e);
        }
    }); // End body click listener

    console.log("SCRIPT: Setup complete.");

}); // End DOMContentLoaded