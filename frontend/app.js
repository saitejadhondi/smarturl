const form = document.getElementById("urlForm");
const result = document.getElementById("result");

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    result.textContent = "Creating short URL...";

    // API URL will be configured after AWS deployment.
    const apiUrl = "http://127.0.0.1:8000";

    try {
        const response = await fetch(`${apiUrl}/urls`, {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                url: document.getElementById("url").value,
                custom_alias: document.getElementById("alias").value || null
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Request failed");
        }

        result.innerHTML = `<p>Short code: <strong>${data.data.shortCode}</strong></p>`;
    } catch (error) {
        result.textContent = error.message;
    }
});
