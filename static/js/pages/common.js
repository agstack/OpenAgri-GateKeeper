const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
$.ajaxSetup({
    headers: { "X-CSRFToken": csrftoken }
});

function formatLabel(key) {
    // Replace underscores with spaces and capitalize the first letter of each word
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}