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
        console.log("SCRIPT: Updating script status...");
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
            console.log("SCRIPT: Status data received:", currentStatusData);

            const isRunning = currentStatusData.script_running;
            const lastKnownStatus = currentStatusData.last_known_script_status || "Unknown";
            const nextRunTs = currentStatusData.next_run_timestamp; // Expecting timestamp in seconds

            statusIndicator.classList.remove('status-running', 'status-stopped', 'status-unknown', 'status-crashed', 'status-error');
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
                         console.log("SCRIPT: Starting countdown interval.");
                         updateCountdown(); // Update immediately
                         countdownIntervalId = setInterval(updateCountdown, 1000);
                    }
                } else {
                    console.log("SCRIPT: No valid next run timestamp received, clearing countdown.");
                    nextRunTargetTimestamp = null;
                    if (nextRunCountdown) nextRunCountdown.textContent = "";
                    clearInterval(countdownIntervalId);
                    countdownIntervalId = null;
                }
                 // Clear error status if running ok
                statusText.classList.remove('status-error-text');


            } else { // Script is NOT running
                clearInterval(countdownIntervalId); // Stop countdown if script stops
                countdownIntervalId = null;
                nextRunTargetTimestamp = null;
                if (nextRunCountdown) nextRunCountdown.textContent = ""; // Clear display

                if (lastKnownStatus.toLowerCase().includes("crashed") || lastKnownStatus.toLowerCase().includes("fatal")) {
                     statusIndicator.classList.add('status-crashed');
                     statusIndicator.textContent = '!';
                     statusText.textContent = `Script Crashed: ${lastKnownStatus}`;
                     statusText.classList.add('status-error-text');

                } else if (lastKnownStatus.toLowerCase().includes("error")) {
                     statusIndicator.classList.add('status-error');
                     statusIndicator.textContent = '✘'; // Different symbol for error vs stopped
                     statusText.textContent = `Script Error: ${lastKnownStatus}`;
                     statusText.classList.add('status-error-text');
                }
                 else {
                     statusIndicator.classList.add('status-stopped');
                     statusIndicator.textContent = '✘';
                     statusText.textContent = 'Script Stopped';
                     statusText.classList.remove('status-error-text');
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
            statusText.classList.add('status-error-text'); // Indicate UI error too
            if (startScriptBtn) startScriptBtn.disabled = true; // Disable controls if status fails
            if (stopScriptBtn) stopScriptBtn.disabled = true;

            // Clear countdown on error
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

    // --- Fetch and Display Functions --- (Updated with loading indicators)
    async function fetchAndShowHistory() {
        if (!historyDisplay || !historyLoading) return;
        historyDisplay.textContent = ''; // Clear previous content
        historyLoading.style.display = 'block'; // Show loading
        openModal(historyModal);
        try {
            const response = await fetch('/get_history');
            const data = await response.json();
            if (!response.ok) { throw new Error(data.error || `HTTP error! status: ${response.status}`); }
            // Format JSON nicely for display
            historyDisplay.textContent = JSON.stringify(data, null, 2);
        } catch (error) {
            console.error('SCRIPT: Error fetching history:', error);
            historyDisplay.textContent = `Error loading history:\n${error.message}`;
        } finally {
            historyLoading.style.display = 'none'; // Hide loading
        }
    }

    async function fetchAndShowLog() {
        if (!logDisplay || !logLoading) return;
        logDisplay.textContent = ''; // Clear previous content
        logLoading.style.display = 'block'; // Show loading
        if (!logModal.style.display || logModal.style.display === 'none') {
             openModal(logModal); // Only open if not already open
        }
        try {
            const response = await fetch('/get_log');
            const data = await response.json();
             if (!response.ok) { throw new Error(data.error || `HTTP error! status: ${response.status}`); }
            logDisplay.textContent = data.log_content || '(Log file might be empty or inaccessible)';
            // Scroll to bottom only if the modal was just opened or refresh was clicked
             if (logModal.style.display === 'block') { // Check if visible
                 logDisplay.scrollTop = logDisplay.scrollHeight;
             }
        } catch (error) {
            console.error('SCRIPT: Error fetching log:', error);
            logDisplay.textContent = `Error loading log:\n${error.message}`;
             if (logModal.style.display === 'block') {
                 logDisplay.scrollTop = logDisplay.scrollHeight; // Scroll bottom even on error
             }
        } finally {
             logLoading.style.display = 'none'; // Hide loading
        }
    }

    // --- Event Listeners ---

    // Modals
    if (viewHistoryBtn) { viewHistoryBtn.addEventListener('click', fetchAndShowHistory); }
    if (viewLogBtn) { viewLogBtn.addEventListener('click', fetchAndShowLog); }
    if (refreshLogBtn) { refreshLogBtn.addEventListener('click', fetchAndShowLog); } // Refresh uses same function
    closeModalBtns.forEach(btn => {
         btn.addEventListener('click', () => {
            // Find the closest parent modal and close it
            const modalToClose = btn.closest('.modal');
            if (modalToClose) {
                closeModal(modalToClose);
            } else {
                // Fallback for older structure if needed
                const targetId = btn.dataset.target;
                const fallbackModal = document.getElementById(targetId);
                closeModal(fallbackModal);
            }
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
         // Disable all control buttons during action
         [startScriptBtn, stopScriptBtn, testPlexBtn].forEach(btn => { if(btn) btn.disabled = true; });
         // Optionally show spinner on the clicked button
         const originalHtml = button.innerHTML;
         button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${actionName}...`;

         try {
             const response = await fetch(url, { method: 'POST' });
             // Try to get JSON, but don't fail if it's not JSON
             let responseData = {};
             try {
                 responseData = await response.json();
             } catch(e) {
                 console.warn("SCRIPT: Response was not valid JSON, status:", response.status);
             }

             if (!response.ok) {
                 const errorMsg = responseData.message || responseData.error || `Request failed with status ${response.status}`;
                 throw new Error(errorMsg);
             }
             console.log(`SCRIPT: ${actionName} request successful.`);
             // Backend should flash messages - we just update status
         } catch (error) {
             console.error(`SCRIPT: Error during ${actionName} action:`, error);
             // Use alert for immediate feedback on action failure
             alert(`${actionName} Action Failed:\n${error.message}`);
         } finally {
             // Restore button text
             button.innerHTML = originalHtml;
             // Re-fetch status immediately to update UI and button states
             await updateScriptStatus(); // updateScriptStatus handles re-enabling appropriate buttons
         }
    }

    if (startScriptBtn) {
        startScriptBtn.addEventListener('click', () => handleControlClick(startScriptBtn, '/start', 'Start Script'));
    }
    if (stopScriptBtn) {
         stopScriptBtn.addEventListener('click', () => handleControlClick(stopScriptBtn, '/stop', 'Stop Script'));
    }
    if (testPlexBtn) {
        testPlexBtn.addEventListener('click', () => handleControlClick(testPlexBtn, '/test_plex', 'Test Plex'));
    }

    // --- Dynamic Lists/Sections Listener (Updated for Categories) ---
    console.log("SCRIPT: Setting up dynamic list/section listeners.");
    document.body.addEventListener('click', function(event) {
        try {
            // --- Add Simple List Item ---
            const addItemButton = event.target.closest('.add-item-btn:not(.nested-add)'); // Exclude nested adds here
            if (addItemButton) {
                const targetListId = addItemButton.dataset.target;
                const templateId = addItemButton.dataset.template;
                const list = document.getElementById(targetListId);
                const template = document.getElementById(templateId);
                if (list && template) {
                    const clone = template.content.cloneNode(true);
                    list.appendChild(clone);
                    console.log(`SCRIPT: Added item to list ${targetListId}`);
                } else {
                    console.error(`SCRIPT: Cannot find list (${targetListId}) or template (${templateId}) for simple item add`);
                }
            }

            // --- Add Category Section ---
            const addSectionButton = event.target.closest('.add-section-btn');
            if (addSectionButton) {
                const targetListId = addSectionButton.dataset.target; // e.g., "categories_Movies_list"
                const templateId = addSectionButton.dataset.template;   // e.g., "category_template"
                const library = addSectionButton.dataset.library;     // e.g., "Movies"
                const list = document.getElementById(targetListId);
                const template = document.getElementById(templateId);

                if (list && template && library) {
                    // Sanitize library name for ID use (consistent with HTML)
                    const safeLibraryName = library.replace(/ /g, '_').replace(/-/g, '_');
                    // Determine the next index for the new category within this library
                    const newIndex = list.querySelectorAll('.dynamic-section-item.category-item').length;
                    console.log(`SCRIPT: Adding category section for library '${library}' (safe: ${safeLibraryName}), new index: ${newIndex}`);

                    // Clone the template content
                    let content = template.innerHTML;
                    // Replace placeholders in the template HTML string
                    content = content.replace(/{library}/g, library); // Use original name for input names
                    content = content.replace(/{safe_library}/g, safeLibraryName); // Use safe name for IDs
                    content = content.replace(/{index}/g, newIndex);

                    // Create a temporary wrapper to parse the HTML
                    const wrapper = document.createElement('div');
                    wrapper.innerHTML = content;
                    const newSection = wrapper.firstElementChild; // Get the actual .dynamic-section-item div

                    if (newSection) {
                        // Ensure the nested list and button inside the new section have correct IDs/data attributes
                        const nestedList = newSection.querySelector('.dynamic-list-container.nested div[id*="_collections_list"]');
                        if (nestedList) {
                            nestedList.id = `category_${safeLibraryName}_${newIndex}_collections_list`;
                            console.log(`SCRIPT: Updated nested list ID to: ${nestedList.id}`);
                        } else { console.warn("SCRIPT: Could not find nested list div in new category template instance."); }

                        const nestedAddButton = newSection.querySelector('.add-item-btn.nested-add');
                        if (nestedAddButton) {
                             nestedAddButton.dataset.target = `category_${safeLibraryName}_${newIndex}_collections_list`;
                             nestedAddButton.dataset.library = library; // Keep original library name
                             nestedAddButton.dataset.categoryIndex = newIndex; // Store the category index
                             console.log(`SCRIPT: Updated nested add button target: ${nestedAddButton.dataset.target}, library: ${nestedAddButton.dataset.library}, index: ${nestedAddButton.dataset.categoryIndex}`);
                        } else { console.warn("SCRIPT: Could not find nested add button in new category template instance."); }


                        // Set the correct names for the main inputs in the new section
                        const nameInput = newSection.querySelector(`input[name^="category_${library}_name"]`);
                        if(nameInput) nameInput.name = `category_${library}_name[]`;
                        const pinCountInput = newSection.querySelector(`input[name^="category_${library}_pin_count"]`);
                        if(pinCountInput) pinCountInput.name = `category_${library}_pin_count[]`;

                         // Find the *first* collection input within this new section and set its name correctly
                         const firstCollInput = newSection.querySelector(`.dynamic-list-item input[name*="_collections"]`);
                         if (firstCollInput) {
                             firstCollInput.name = `category_${library}_${newIndex}_collections[]`;
                              console.log(`SCRIPT: Updated first collection input name in new section to: ${firstCollInput.name}`);
                         } else { console.warn("SCRIPT: Could not find the initial collection input field in the new category section template instance.");}


                        list.appendChild(newSection);
                        console.log(`SCRIPT: Appended new category section to ${targetListId}`);
                    } else {
                        console.error("SCRIPT: Could not create new section element from template content:", content);
                    }
                } else {
                    console.error(`SCRIPT: Cannot add section. Missing list (${targetListId}), template (${templateId}), or library (${library})`);
                }
            }


             // --- Add Nested Collection Item (within a Category) ---
             const addNestedItemButton = event.target.closest('.add-item-btn.nested-add');
             if (addNestedItemButton) {
                 const targetListId = addNestedItemButton.dataset.target;       // e.g., "category_Movies_0_collections_list"
                 const templateId = addNestedItemButton.dataset.template;     // e.g., "category_collection_template"
                 const library = addNestedItemButton.dataset.library;         // e.g., "Movies"
                 const categoryIndex = addNestedItemButton.dataset.categoryIndex; // e.g., "0"
                 const list = document.getElementById(targetListId);
                 const template = document.getElementById(templateId);

                 console.log(`SCRIPT: Adding nested item. Target: ${targetListId}, Template: ${templateId}, Library: ${library}, CatIndex: ${categoryIndex}`);


                 if (list && template && library !== undefined && categoryIndex !== undefined) {
                     // Clone the nested item template
                     const clone = template.content.cloneNode(true);
                     // Find the input within the clone
                     const inputElement = clone.querySelector('input[name*="_collections[]"]'); // Find the input based on partial name
                     if (inputElement) {
                         // Construct the correct name: category_<library>_<cat_index>_collections[]
                         inputElement.name = `category_${library}_${categoryIndex}_collections[]`;
                         console.log(`SCRIPT: Set nested input name to: ${inputElement.name}`);
                         list.appendChild(clone);
                         console.log(`SCRIPT: Appended nested item to ${targetListId}`);
                     } else {
                          console.error("SCRIPT: Could not find input element within the nested item template clone:", template.innerHTML);
                     }
                 } else {
                     console.error(`SCRIPT: Cannot add nested item. Missing list (${targetListId}), template (${templateId}), library (${library}), or category index (${categoryIndex})`);
                 }
             }


            // --- Remove Item (Simple or Nested) ---
            const removeItemButton = event.target.closest('.remove-item-btn');
            if (removeItemButton) {
                const itemToRemove = removeItemButton.closest('.dynamic-list-item');
                if (itemToRemove) {
                     // Check if it's the last item in a nested list (optional: prevent removal?)
                    // const parentList = itemToRemove.parentElement;
                    // if (parentList && parentList.classList.contains('nested') && parentList.children.length === 1) {
                    //     console.log("SCRIPT: Preventing removal of the last item in a nested list.");
                    //     alert("Cannot remove the last collection title. Add another first or remove the category.");
                    // } else {
                         itemToRemove.remove();
                         console.log("SCRIPT: Removed dynamic list item.");
                    // }
                }
            }

            // --- Remove Section (Category or Special) ---
            const removeSectionButton = event.target.closest('.remove-section-btn');
            if (removeSectionButton) {
                const sectionToRemove = removeSectionButton.closest('.dynamic-section-item');
                if (sectionToRemove) {
                    sectionToRemove.remove();
                    console.log("SCRIPT: Removed dynamic section item.");
                }
            }

            // --- Toggle Section Visibility ---
            const toggleSectionButton = event.target.closest('.toggle-section-btn');
            if (toggleSectionButton) {
                // Prevent toggling if clicking the theme button which might be inside a header
                 if (event.target.closest('#theme-toggle-button')) {
                     console.log("SCRIPT: Clicked theme toggle, ignoring section toggle.");
                     return;
                 }
                 console.log("SCRIPT: Section toggle button clicked.");
                const section = toggleSectionButton.closest('.form-section'); // Find parent form section
                const content = section ? section.querySelector('.collapsible-content') : null; // Find content within that section
                const icon = toggleSectionButton.querySelector('i'); // Find icon within the button

                if (content) {
                     const isExpanded = content.style.display === 'block'; // Check current state
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
                 } else {
                     console.error("SCRIPT: Could not find collapsible content for section button.");
                 }
            }
        } catch (e) {
            console.error("SCRIPT: Error inside main body click listener:", e);
        }
    }); // End body click listener

    console.log("SCRIPT: Setup complete.");

}); // End DOMContentLoaded