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

export const streamMas = async (input, onUpdate, onComplete, onError) => {
    try {
        const res = await fetch(`${API_URL}/stream`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            body: JSON.stringify({ input })
        });

        if (!res.ok) {
            let errMessage = "Failed to start stream";
            try {
                const errData = await res.json();
                errMessage = errData.detail || errMessage;
            } catch (e) {}
            throw new Error(errMessage);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            
            // SSE events are separated by double newlines
            const events = buffer.split('\n\n');
            buffer = events.pop(); // Keep the last incomplete chunk in the buffer

            for (const event of events) {
                if (event.startsWith('data: ')) {
                    const dataStr = event.slice(6);
                    if (dataStr === '[DONE]') {
                        if (onComplete) onComplete();
                        return;
                    }

                    try {
                        const parsedData = JSON.parse(dataStr);
                        if (parsedData.__error__) {
                            if (onError) onError(new Error(parsedData.__error__));
                            return;
                        }
                        if (onUpdate) onUpdate(parsedData);
                    } catch (e) {
                        console.error('Error parsing SSE data:', dataStr, e);
                    }
                }
            }
        }
        
        if (onComplete) onComplete();

    } catch (err) {
        if (onError) onError(err);
    }
}

export const getExecutionHistory = async () => {
    const res = await fetch(`${API_URL}/history/logs`);
    if (!res.ok) {
        throw new Error("Failed to fetch execution history");
    }
    return await res.json();
}
