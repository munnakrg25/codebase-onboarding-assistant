const API_URL = window.location.origin;

const analyzeBtn = document.getElementById("analyzeBtn");
const repoUrl = document.getElementById("repoUrl");
const statusText = document.getElementById("status");
const reportTitle = document.getElementById("reportTitle");
const reportContent = document.getElementById("reportContent");
const downloadBtn = document.getElementById("downloadBtn");
const activity = document.getElementById("activity");

const reports = {
    architecture: {
        title: "Architecture Summary",
        endpoint: "architecture"
    },
    guide: {
        title: "Developer Reading Guide",
        endpoint: "guide"
    },
    issues: {
        title: "Good First Issues",
        endpoint: "issues"
    },
    patch: {
        title: "Suggested Patch",
        endpoint: "patch"
    }
};

let currentReport = "architecture";
let analysisInProgress = false;

function setStatus(message) {
    if (statusText) {
        statusText.textContent = message;
    }
}

function showContent(title, content) {
    if (!reportTitle || !reportContent) return;

    reportTitle.textContent = title;
    reportContent.replaceChildren();

    const output = document.createElement("div");
    output.className = "markdown-content";

    if (window.marked && window.DOMPurify) {
        output.innerHTML = window.DOMPurify.sanitize(
            window.marked.parse(content || "")
        );
    } else {
        const pre = document.createElement("pre");
        pre.textContent = content || "No report content available.";
        pre.style.whiteSpace = "pre-wrap";
        pre.style.overflowWrap = "anywhere";
        output.appendChild(pre);
    }

    reportContent.appendChild(output);
}

function clearReport(message = "Reports will appear after analysis.") {
    if (!reportTitle || !reportContent) return;

    reportTitle.textContent = "Repository Analysis";
    reportContent.replaceChildren();

    const placeholder = document.createElement("p");
    placeholder.textContent = message;
    reportContent.appendChild(placeholder);
}

function addActivity(title, detail) {
    if (!activity) return;

    activity.querySelector(".empty-activity")?.remove();

    const item = document.createElement("div");
    item.className = "activity-item";

    const heading = document.createElement("strong");
    heading.textContent = title;

    const description = document.createElement("small");
    description.textContent = detail;

    item.append(heading, description);
    activity.prepend(item);
}

function updateStats(stats = {}) {
    const totalFiles = document.getElementById("totalFiles");
    const totalLines = document.getElementById("totalLines");
    const technologies = document.getElementById("technologies");
    const projectType = document.getElementById("projectType");

    if (totalFiles) {
        totalFiles.textContent = stats.total_files ?? "--";
    }

    if (totalLines) {
        totalLines.textContent = stats.total_lines ?? "--";
    }

    if (technologies) {
        technologies.textContent =
            Array.isArray(stats.technologies) &&
            stats.technologies.length > 0
                ? stats.technologies.join(", ")
                : "Unknown";
    }

    if (projectType) {
        projectType.textContent = stats.project_type || "Unknown";
    }
}

async function apiRequest(path, options = {}) {
    const separator = path.includes("?") ? "&" : "?";
    const requestUrl = `${API_URL}${path}${separator}_=${Date.now()}`;

    const response = await fetch(requestUrl, {
        ...options,
        cache: "no-store",
        headers: {
            ...(options.headers || {}),
            "Cache-Control": "no-cache"
        }
    });

    let data;

    try {
        data = await response.json();
    } catch {
        throw new Error(
            `Server returned an invalid response (${response.status}).`
        );
    }

    if (!response.ok) {
        throw new Error(
            typeof data.detail === "string"
                ? data.detail
                : data.message || "Request failed."
        );
    }

    return data;
}

async function refreshStats() {
    try {
        const stats = await apiRequest("/api/stats");
        updateStats(stats);
        return stats;
    } catch (error) {
        console.error("Could not load repository stats:", error);
        return null;
    }
}

async function loadReport(reportName) {
    const report = reports[reportName];

    if (!report) {
        setStatus("Unknown report.");
        return;
    }

    currentReport = reportName;
    setStatus(`Loading ${report.title}...`);

    try {
        const data = await apiRequest(
            `/api/reports/${report.endpoint}`
        );

        if (typeof data.content !== "string" || !data.content.trim()) {
            throw new Error(
                `${report.title} is empty. Please analyze the repository again.`
            );
        }

        showContent(report.title, data.content);
        setStatus(`${report.title} loaded successfully.`);
        addActivity("Report opened", report.title);
    } catch (error) {
        showContent(report.title, error.message);
        setStatus(error.message);
        console.error(`Failed to load ${report.title}:`, error);
    }
}

async function analyzeRepository() {
    if (analysisInProgress) return;

    const repo = repoUrl?.value.trim();

    if (!repo) {
        setStatus("Enter a GitHub URL or local repository path.");
        repoUrl?.focus();
        return;
    }

    analysisInProgress = true;

    if (analyzeBtn) {
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = "Analyzing...";
    }

    // Remove the previous repository's report from the screen.
    clearReport("Analyzing the selected repository. Please wait...");

    setStatus(
        "Indexing repository and generating reports. Please wait..."
    );

    addActivity("Analysis started", repo);

    try {
        const data = await apiRequest("/api/analyze", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ repo })
        });

        // Update statistics even if AI report generation was partial.
        if (data.stats) {
            updateStats(data.stats);
        }

        await refreshStats();

        addActivity("Repository analyzed", repo);

        if (data.status === "partial") {
            const message =
                data.error ||
                data.message ||
                "AI report generation did not finish.";

            setStatus(`Partial analysis: ${message}`);

            clearReport(
                "Repository statistics were updated, but report generation was incomplete. Check the backend terminal for the error."
            );

            addActivity("Partial analysis", message);
            return;
        }

        if (data.status && data.status !== "completed") {
            setStatus(data.message || "Analysis did not complete.");
            clearReport(data.message || "Analysis did not complete.");
            return;
        }

        setStatus(
            data.message || "Repository analysis completed successfully."
        );

        // Load the newly generated architecture report.
        await loadReport("architecture");

        addActivity("Analysis completed", repo);
    } catch (error) {
        console.error("Repository analysis failed:", error);

        // Stats may still have been saved before an AI error occurred.
        await refreshStats();

        setStatus(`Analysis failed: ${error.message}`);

        clearReport(
            `Analysis failed: ${error.message}. Check the backend terminal for details.`
        );

        addActivity("Analysis failed", error.message);
    } finally {
        analysisInProgress = false;

        if (analyzeBtn) {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = "Analyze Repository";
        }
    }
}

function showSearchForm() {
    if (!reportTitle || !reportContent) return;

    reportTitle.textContent = "Search Codebase";
    reportContent.replaceChildren();

    const form = document.createElement("form");
    form.className = "search-form";

    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Where are HTTP requests sent?";
    input.required = true;
    input.maxLength = 500;
    input.setAttribute("aria-label", "Search codebase");

    const button = document.createElement("button");
    button.type = "submit";
    button.textContent = "Search Code";

    const results = document.createElement("div");
    results.style.marginTop = "20px";

    form.append(input, button);
    reportContent.append(form, results);

    form.addEventListener("submit", async event => {
        event.preventDefault();

        const query = input.value.trim();

        if (!query) return;

        button.disabled = true;
        button.textContent = "Searching...";
        results.textContent = "Searching indexed code...";

        try {
            const data = await apiRequest("/api/search", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    query,
                    top_k: 3
                })
            });

            results.replaceChildren();

            if (!Array.isArray(data.results) || data.results.length === 0) {
                results.textContent = "No matching code found.";
                setStatus("Search completed. No matches found.");
                return;
            }

            data.results.forEach((result, index) => {
                const card = document.createElement("section");

                card.style.border = "1px solid #e2eae5";
                card.style.borderRadius = "8px";
                card.style.padding = "14px";
                card.style.marginBottom = "12px";

                const heading = document.createElement("h3");
                heading.textContent =
                    `${index + 1}. ${
                        result.file_path ||
                        result.path ||
                        result.source ||
                        "Source file"
                    }`;

                const lines = document.createElement("p");
                lines.textContent =
                    `Lines ${result.start_line ?? "?"}-${result.end_line ?? "?"}`;

                const code = document.createElement("pre");
                code.textContent =
                    result.text ||
                    result.content ||
                    result.code ||
                    JSON.stringify(result, null, 2);

                code.style.whiteSpace = "pre-wrap";
                code.style.overflowWrap = "anywhere";

                card.append(heading, lines, code);
                results.appendChild(card);
            });

            setStatus("Code search completed.");
            addActivity("Code search", query);
        } catch (error) {
            results.textContent = error.message;
            setStatus(error.message);
        } finally {
            button.disabled = false;
            button.textContent = "Search Code";
        }
    });
}

function setupNavigation() {
    document.querySelectorAll("nav a").forEach(link => {
        link.addEventListener("click", async event => {
            event.preventDefault();

            const page = (link.getAttribute("href") || "").slice(1);

            document.querySelectorAll("nav a").forEach(item => {
                item.classList.toggle("active", item === link);
            });

            if (reports[page]) {
                await loadReport(page);
            } else if (page === "search") {
                showSearchForm();
                setStatus("Search your indexed codebase.");
            } else if (page === "home") {
                setStatus("Dashboard ready.");
                await refreshStats();
            }
        });
    });

    document.querySelectorAll("[data-page]").forEach(button => {
        button.addEventListener("click", async () => {
            const page = button.dataset.page;

            if (reports[page]) {
                await loadReport(page);
            } else if (page === "search") {
                showSearchForm();
                setStatus("Search your indexed codebase.");
            }

            document.querySelector(".main-panel")
                ?.scrollIntoView({ behavior: "smooth" });
        });
    });
}

function setupDownload() {
    if (!downloadBtn) return;

    downloadBtn.addEventListener("click", () => {
        const content = reportContent?.innerText || "";

        if (!content.trim()) {
            setStatus("There is no report content to download.");
            return;
        }

        const blob = new Blob([content], {
            type: "text/markdown;charset=utf-8"
        });

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");

        link.href = url;
        link.download = `${currentReport}-report.md`;

        document.body.appendChild(link);
        link.click();
        link.remove();

        URL.revokeObjectURL(url);
        setStatus("Report downloaded.");
    });
}

async function initializeDashboard() {
    try {
        const health = await apiRequest("/api/health");
        setStatus(health.message || "FastAPI is running.");
    } catch (error) {
        setStatus("Cannot connect to FastAPI.");
        console.error("Backend connection error:", error);
    }

    // Stats do not require a Gemini API request.
    await refreshStats();
}

if (analyzeBtn) {
    analyzeBtn.addEventListener("click", analyzeRepository);
}

setupNavigation();
setupDownload();
initializeDashboard();
