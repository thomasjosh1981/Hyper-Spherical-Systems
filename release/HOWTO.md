# Pirate Llama How-To Guide

## 1. Starting the Proxy
Run `pirate_llama.exe`.
You will be greeted by the onboarding wizard. Complete the setup and you will be presented with the main control panel. 

The proxy will run on **http://127.0.0.1:11435** (by default).

## 2. Choosing a Backend
In the Pirate Llama control panel, choose where you want your traffic routed:
* **Ollama**: Requires Ollama running locally on port 11434.
* **LM Studio**: Requires LM Studio's local server running on port 1234.
* **Native**: Select a local `.gguf` file to load into the built-in inference engine.

You can also use the **Auto-Detect Backend** button.

## 3. Configuring Your AI Applications
In any AI application (such as Cline, Cursor, or your own Python scripts) that supports an OpenAI-compatible endpoint:
1. Change the API Base URL to `http://127.0.0.1:11435/v1`
2. You can leave the API Key empty or put a placeholder.
3. Pirate Llama will now intercept the traffic, compress it via SISSI, and forward it to your local models.

## 4. Advanced Toggles
* **SISSI Compression**: Reduces your prompt size before it hits the backend. You can enable "Greedy-First" or "Discard Prepositions" to increase the compression ratio.
* **NVMe Prefetch**: Caches commonly used prompts to your SSD for lightning-fast retrieval.
* **Telemetry**: Check this box in the Advanced section to anonymously share debug data and help us improve the software. No data is collected otherwise!
