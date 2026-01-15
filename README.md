# Sequential agent: user eligibility with elicitation for user testing

## Setup Instructions

### 1. Install `uv`

If you don't have `uv` installed, you can install it using pip:
```bash
pip install uv
```
Or follow the instructions in the official `uv` documentation.

### 2. Create and Activate the Virtual Environment

In project root, create a new virtual environment and activate it. `uv` will automatically detect the best available Python version on your system.

```bash
uv venv
source .venv/bin/activate
```

### 3. Install Dependencies

Install all the project dependencies:

```bash
uv sync
```

### 4. Set Up Environment Variables (optional)

Create a `.env` file in the project root and add any necessary API keys (e.g., `OPENAI_API_KEY`):

```
OPENAI_API_KEY="your_openai_api_key_here"
# Add any other necessary API keys or environment variables
```

## Running the Agents

After completing the setup and activating your virtual environment, you can start the agents by running the provided shell script:

```bash
./start_sequential_agent.sh
```

This script will start both the main user agent and the remote eligibility agent.
