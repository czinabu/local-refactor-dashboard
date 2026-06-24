# src/main.py
import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import re

app = FastAPI()

# Add CORS middleware to allow requests from any origin (useful if you move the UI later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# CONFIGURATION: Point this to your Windows Tailscale IP
OLLAMA_API_URL = "http://100.65.149.81:11434/api/generate"

# MODEL CONFIGURATION: Change this to your preferred model
MODEL_NAME = "qwen3:14b"

class RefactorRequest(BaseModel):
    code: str
    language: str
    instruction: str = "Refactor this code to be cleaner, more efficient, and add comments. Output only the code."

HTML_RESPONSE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Local AI Refactor Dashboard</title>
    <style>
        body {
            font-family: sans-serif;
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 20px;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        textarea {
            width: 100%;
            height: 150px;
            background: #2d2d2d;
            color: white;
            border: 1px solid #444;
            padding: 10px;
            font-family: monospace;
        }
        button {
            background: #0e639c;
            color: white;
            border: none;
            padding: 10px 20px;
            cursor: pointer;
            margin-top: 10px;
            font-size: 16px;
        }
        button:hover {
            background: #1177bb;
        }
        select, input {
            padding: 5px;
            margin-left: 10px;
            background: #2d2d2d;
            color: white;
            border: 1px solid #444;
        }
        pre {
            background: #252526;
            padding: 15px;
            overflow-x: auto;
            border-radius: 5px;
        }
        .error {
            color: #f48771;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧠 Local AI Code Refactorer</h1>
        <p>Paste code below and click "Refactor". Powered by Qwen 3 on your Desktop.</p>
        
        <textarea id="codeInput" placeholder="Paste your code here..."></textarea>
        
        <div style="margin-top: 10px;">
            Language: 
            <select id="langInput">
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="typescript">TypeScript</option>
                <option value="go">Go</option>
                <option value="rust">Rust</option>
            </select>
            Instruction: 
            <input type="text" id="instrInput" value="Refactor for readability and efficiency." style="width: 300px;">
        </div>

        <button onclick="refactor()">Refactor Code</button>
        
        <h2>Output:</h2>
        <pre id="output"><em>Result will appear here...</em></pre>
    </div>

    <script>
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
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTML_RESPONSE

@app.post("/refactor", response_class=JSONResponse)
async def refactor_code(req: RefactorRequest):
    try:
        # Escape backticks in the code to prevent prompt injection issues with Ollama's parser
        safe_code = req.code.replace('`', '&#96;')
        
        prompt = f"""
You are an expert software engineer.
Task: {req.instruction}

Language: {req.language}

Input Code:
```{req.language}
{safe_code}
```

Act as an expert programmer. Observe the following program and refactor it according to the task description.
Return ONLY the refactored code block. Do not include explanations or markdown text outside the code block unless necessary for clarity.
"""

        async with httpx.AsyncClient() as client:
            # Send request to Ollama API
            ollama_response = await client.post(
                OLLAMA_API_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False     # Stream false for simpler text extraction
                },
                timeout=60.0
            )

            if ollama_response.status_code != 200:
                return JSONResponse(
                    status_code=500,
                    content={"status": "error", "message": "Ollama API Error"}
                )

            # Parse Ollama response (usually contains a 'response' field for non-streaming)
            ollama_data = ollama_response.json()
            generated_text = ollama_data.get("response", "")
            
            # Optional: Clean up markdown code blocks if the model wraps output in them
            if "```" in generated_text:
                match = re.search(r'```[\w]*\n?(.*?)```', generated_text, re.DOTALL)
                if match:
                    generated_text = match.group(1).strip()

        return JSONResponse(
            content={
                "status": "success",
                "code": generated_text
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)