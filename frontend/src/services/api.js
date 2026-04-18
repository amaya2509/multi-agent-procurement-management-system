const API_URL = "http://localhost:8000"

export const runMas = async (input) => {
    const res = await fetch(`${API_URL}/run`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ input })
    });

    if (!res.ok) {
        let errMessage = "Failed to run workflow";
        try {
            const errData = await res.json();
            errMessage = errData.detail || errMessage;
        } catch (e) {
            // Unparseable error
        }
        throw new Error(errMessage);
    }

    return await res.json();
}
