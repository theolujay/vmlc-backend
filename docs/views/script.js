document.addEventListener('DOMContentLoaded', function() {
    fetch('./api.md')
        .then(response => response.text())
        .then(text => {
            const contentDiv = document.getElementById('content');
            contentDiv.innerHTML = marked.parse(text);

            // Now that the HTML is in the DOM, add the listeners
            const tocLinks = contentDiv.querySelectorAll('h2#table-of-contents + ul a');

            tocLinks.forEach(link => {
                link.addEventListener('click', function(event) {
                    event.preventDefault();
                    const href = this.getAttribute('href');
                    
                    try {
                        // Decode URI component to handle special characters in IDs
                        const targetId = decodeURIComponent(href.substring(1));
                        const targetElement = document.getElementById(targetId);

                        if (targetElement) {
                            // Open all parent <details> elements
                            let parent = targetElement.parentElement;
                            while (parent) {
                                if (parent.tagName.toLowerCase() === 'details' && !parent.open) {
                                    parent.open = true;
                                }
                                parent = parent.parentElement;
                            }
                            
                            // Scroll to the element
                            targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });

                            // Optionally update the URL hash without causing a jump
                            history.pushState(null, null, href);
                        }
                    } catch (e) {
                        console.error("Could not scroll to element for href: " + href, e);
                        // If something fails, fallback to default browser behavior
                        window.location.hash = href;
                    }
                });
            });
        })
        .catch(error => {
            console.error('Error fetching the markdown file:', error);
            document.getElementById('content').innerText = 'Error loading documentation.';
        });
});
