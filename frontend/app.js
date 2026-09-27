const form = document.getElementById("urlForm");
const result = document.getElementById("result");
const analytics = document.getElementById("analytics");
const qrImage = document.getElementById("qr");

async function readResponse(response) {
    const body = await response.json();
    if (!response.ok) {
        throw new Error(body.detail || "Request failed");
    }
    return body;
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    result.textContent = "Creating short URL...";

    const expiration = document.getElementById("expires").value;
    const payload = {
        url: document.getElementById("url").value,
        custom_alias: document.getElementById("alias").value || null,
        expires_at: expiration ? new Date(expiration).toISOString() : null,
    };

    try {
        const response = await fetch("/urls", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload),
        });
        const data = await readResponse(response);
        result.textContent = JSON.stringify(data, null, 2);
        document.getElementById("code").value = data.shortCode;
        document.getElementById("qrCode").value = data.shortCode;
    } catch (error) {
        result.textContent = error.message;
    }
});

document.getElementById("analyticsButton").addEventListener("click", async () => {
    const code = document.getElementById("code").value.trim();
    if (!code) {
        analytics.textContent = "Enter a short code.";
        return;
    }

    try {
        const response = await fetch(`/analytics/${encodeURIComponent(code)}`);
        const data = await readResponse(response);
        analytics.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
        analytics.textContent = error.message;
    }
});

document.getElementById("qrButton").addEventListener("click", () => {
    const code = document.getElementById("qrCode").value.trim();
    if (!code) {
        qrImage.removeAttribute("src");
        return;
    }
    qrImage.src = `/qr/${encodeURIComponent(code)}?t=${Date.now()}`;
});
