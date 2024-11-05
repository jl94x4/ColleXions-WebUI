function addSpecialCollection() {
    const collectionName = document.getElementById('specialCollectionName').value;
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;

    if (collectionName && startDate && endDate) {
        const listItem = document.createElement('li');
        listItem.textContent = `${collectionName} (Start: ${startDate}, End: ${endDate})`;

        // Create hidden inputs to store the data when submitting the form
        const hiddenName = document.createElement('input');
        hiddenName.type = 'hidden';
        hiddenName.name = 'specialCollectionName[]';
        hiddenName.value = collectionName;

        const hiddenStart = document.createElement('input');
        hiddenStart.type = 'hidden';
        hiddenStart.name = 'startDate[]';
        hiddenStart.value = startDate;

        const hiddenEnd = document.createElement('input');
        hiddenEnd.type = 'hidden';
        hiddenEnd.name = 'endDate[]';
        hiddenEnd.value = endDate;

        // Append hidden inputs and list item
        listItem.appendChild(hiddenName);
        listItem.appendChild(hiddenStart);
        listItem.appendChild(hiddenEnd);
        document.getElementById('specialCollectionsList').appendChild(listItem);

        // C
