async function refactor() {
    const code = document.getElementById('codeInput').value;
    const lang = document.getElementById('langInput').value;
    const instr = document.getElementById('instrInput').value;
    const outputPre = document.getElementById('output');

    if (!code.trim()) {
        outputPre.innerText = "Please enter some code to refactor.";
        outputPre.style.color = 'red';
        return;
    }

    outputPre.innerText = "Thinking...";

    try {
        const response = await fetch('/refactor', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code, language: lang, instruction: instr })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Unknown server error');
        }

        const data = await response.json();

        if (data.status === 'success') {
            outputPre.innerText = data.code;
            outputPre.style.color = '#ce9178'; // String color in VS Code theme
        } else {
            outputPre.innerText = "Error: " + data.message;
            outputPre.style.color = '#f48771';
        }
    } catch (e) {
        outputPre.innerText = "Error: " + e.message;
        outputPre.style.color = 'red';
    }
}

document.getElementById('refactorButton').addEventListener('click', refactor);
