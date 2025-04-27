// This file initializes the application and sets up HTMX and Alpine.js.
// It includes event listeners and functions to handle dynamic content loading.

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Alpine.js
    Alpine.start();

    // Example of setting up an HTMX event listener
    document.body.addEventListener('htmx:configRequest', (event) => {
        console.log('HTMX request is being configured:', event);
    });

    // Example function to load dynamic content
    function loadContent(url) {
        htmx.ajax('GET', url, {
            target: '#content',
            swap: 'innerHTML'
        });
    }

    // Example event listener for a button click
    document.getElementById('load-button').addEventListener('click', () => {
        loadContent('/path/to/dynamic/content');
    });
});