# `docs` Directory

This directory is dedicated to the project's documentation, structured for easy generation and maintenance using MkDocs. It provides various guides, API specifications, and information tailored for different audiences, including developers and users.

## Key Files and Subdirectories

-   **`API_SPEC.md`**: This Markdown file contains a human-readable specification of the project's API. It might describe endpoints, request/response formats, authentication methods, and error codes. This could be a manually maintained document or a supplementary explanation to an auto-generated spec.
-   **`mkdocs.yml`**: The main configuration file for **MkDocs**. This YAML file defines:
    -   The structure of the documentation site (navigation menu, page order).
    -   The theme used for the site's appearance.
    -   Plugins and extensions to enable additional functionality (e.g., search, diagrams).
    -   Basic site information (site name, author).
    -   It controls how the Markdown source files are transformed into a static HTML documentation website.
-   **`src/`**: This subdirectory holds all the source Markdown (`.md`) files that constitute the content of the documentation website. It is organized into further subdirectories to reflect the site's navigation and topic hierarchy.
    -   **`index.md`**: The main entry point or home page of the documentation. It usually provides an overview of the project and links to other sections.
    -   **`advanced/`**: Contains documentation for advanced topics, complex features, or in-depth technical explanations that might not be relevant for a "getting started" audience.
    -   **`api/`**: Dedicated to API documentation. This section might include:
        -   Detailed descriptions of API endpoints.
        -   Examples of API requests and responses.
        -   Information about data models and authentication.
        -   It could potentially be generated from an OpenAPI/Swagger specification or written manually.
    -   **`assets/`**: Stores static assets such as images, diagrams, custom CSS files, or JavaScript files that are embedded within or enhance the documentation pages.
    -   **`getting-started/`**: Provides guides and tutorials for new users or developers to quickly understand and begin working with the project. This typically covers installation, basic usage, and first steps.
    -   **`resources/`**: A section for supplementary materials, external links, glossaries, or other helpful resources.
    -   **`roles/`**: Contains documentation specific to different user roles within the system (e.g., candidate, staff, admin roles), outlining their permissions, responsibilities, and workflows.
    -   **`stylesheets/`**: Houses custom CSS files that override or extend the default MkDocs theme styles, ensuring the documentation matches the project's branding or specific design requirements.

## Interconnections and Overall Purpose

-   The `mkdocs.yml` file dictates how the Markdown files in `src/` are compiled into the final static website.
-   The documentation serves as a central knowledge base for the project, assisting new team members, guiding users, and providing a reference for API consumers.
-   It ensures that information about the project's functionality, usage, and underlying architecture is well-organized, accessible, and up-to-date.
