document.addEventListener("DOMContentLoaded", function() {
    window.choicesInstances = {}; // Global object to store Choices instances
    var selects = document.querySelectorAll("[data-trigger]");

    for (var i = 0; i < selects.length; ++i) {
        var selectElement = selects[i];
        // Use the element's ID as the key to store the Choices instance
        window.choicesInstances[selectElement.id] = new Choices(selectElement, {
            placeholderValue: "This is a placeholder set in the config",
            searchPlaceholderValue: "Search"
        });
    }
});
