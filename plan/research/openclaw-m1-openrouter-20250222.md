# Research: OpenClaw on MacBook Air M1 with OpenRouter API Key

**Date:** 2025-02-22
**Query:** how to install openclaw on macbook air m1 with openrouter api key

## Summary
OpenClaw is a free, open-source autonomous AI agent that functions as a self-hosted personal assistant. It runs natively on Apple Silicon (ARM64) and integrates with messaging platforms (WhatsApp, Telegram, Discord) while connecting AI models with local files for task automation.

## Key Concepts
- **Self-hosted AI Agent**: Runs locally on your M1 Mac with continuous background operation
- **OpenRouter Integration**: Uses OpenRouter API as the LLM provider for flexible model access
- **Messaging Platform UI**: Interact via chatbots in popular messaging services
- **Proactive Automation**: Supports scheduled monitoring and recurring workflows
- **Persistent Memory**: Stores context, history, and preferences locally

## Installation Steps

### Prerequisites
- macOS (any recent version)
- Node.js 22 or newer (auto-installed)

### Quick Install (Recommended)
```bash
curl -fsSL https://openclaw.ai/install.sh | bash
```

### Manual Install (if Node.js 22+ exists)
```bash
npm install -g openclaw@latest
openclaw onboard --install-daemon
```

### With pnpm
```bash
pnpm add -g openclaw@latest
pnpm approve-builds -g
openclaw onboard --install-daemon
```

## Configuration with OpenRouter

### Step 1: Get API Key
1. Go to [openrouter.ai](https://openrouter.ai)
2. Navigate to API Keys section
3. Create and copy your key

### Step 2: Configure (Quick CLI)
```bash
openclaw onboard --auth-choice apiKey --token-provider openrouter --token "$OPENROUTER_API_KEY"
```

### Step 3: Manual Config (Advanced)
Edit `~/.openclaw/openclaw.json`:
```json
{
  "env": {
    "OPENROUTER_API_KEY": "sk-or-..."
  },
  "agents": {
    "defaults": {
      "model": {
        "provider": "openrouter",
        "model": "openrouter/auto"
      }
    }
  }
}
```

### Step 4: Start Gateway
```bash
openclaw gateway run
```

## Common M1 Mac Issues

| Issue | Solution |
|-------|----------|
| `command not found` | Add npm bin to PATH: `export PATH="$(npm config get prefix)/bin:$PATH"` |
| `sharp` build errors | `SHARP_IGNORE_GLOBAL_LIBVIPS=1 npm install -g openclaw@latest` |
| Only runs with Terminal open | Rerun: `openclaw onboard --install-daemon` |
| Slow with local LLMs | Use cloud models (OpenRouter) on 8GB M1; 16GB+ recommended for local |

## Security Best Practices

**CRITICAL**: OpenClaw requires broad system permissions. Consider:
- Running in a sandboxed macOS VM (UTM)
- Using a dedicated standard user account with limited permissions
- Never hardcode API keys in source code
- Use environment variables: `export OPENROUTER_API_KEY="sk-or-..."`
- Rotate keys regularly
- Monitor usage via OpenRouter dashboard

## First Usage Examples

```bash
# Ask a question
openclaw send --query "What is the capital of France?"

# Web search
openclaw send --query "Search the web for 'latest AI news'"

# List skills
openclaw skills list
```

## Dependencies
- **Runtime**: Node.js 22+, macOS
- **Build**: Xcode 26.2+, Git, pnpm (optional)
- **Container**: Docker Engine, Docker Compose (optional)

## References
- [OpenClaw Docs](https://docs.openclaw.ai/)
- [GitHub Repository](https://github.com/openclaw/openclaw)
- [Getting Started Guide](https://github.com/openclaw/openclaw/blob/main/docs/start/getting-started.md)
- [OpenRouter](https://openrouter.ai/)

## Raw Gemini Response
<details>
<summary>Full response</summary>

## OpenClaw on MacBook Air M1 with OpenRouter API Key

This document provides a comprehensive guide to installing and configuring OpenClaw on a MacBook Air M1, including integration with an OpenRouter API key, common issues, usage examples, and security best practices.

### 1. What is OpenClaw and its Purpose?

OpenClaw is a free and open-source autonomous artificial intelligence (AI) agent developed by Peter Steinberger. It functions as a self-hosted personal AI assistant that operates on your own devices, previously known as Clawdbot and Moltbot.

The primary purpose of OpenClaw is to act as a proactive personal agent capable of executing tasks through large language models (LLMs), primarily using messaging platforms (like WhatsApp, Telegram, Discord) as its user interface. It connects AI models with your local files and messaging applications to automate tasks continuously.

Key functionalities include:
*   **Automating Digital Tasks:** Executing shell commands, interacting with web browsers, managing local files, and performing web automation.
*   **\"Always-On\" Assistant:** Runs continuously in the background, operating 24/7.
*   **Persistent Memory:** Stores long-term context, activity history, and user preferences locally.
*   **Proactive Automation:** Supports scheduled monitoring and recurring workflows.
*   **Model Flexibility:** Designed to work with various commercial, open-source, and locally hosted LLMs.
*   **Messaging Platform Integration:** Users interact via chatbots within popular messaging services.
*   **Self-Extending Capabilities:** Can generate new workflows and write code to create new skills.

It's important to note that due to the broad permissions it requires, OpenClaw has drawn scrutiny from cybersecurity researchers regarding security and privacy risks, and its susceptibility to prompt injection attacks.

### 2. Installation Steps for macOS M1 (ARM64)

OpenClaw runs natively on Apple Silicon (ARM64). The recommended method is using the one-line installer script, which handles Node.js installation and the onboarding process.

#### Prerequisites:
*   macOS (any recent version)
*   Node.js 22 or newer (the installer can handle this)

#### Installation:

1.  **Open Terminal** on your MacBook Air M1.

2.  **Run the one-line installer script:**
    ```bash
    curl -fsSL https://openclaw.ai/install.sh | bash
    ```
    This script will:
    *   Check for or install Node.js 22+.
    *   Install the OpenClaw CLI globally.
    *   Initiate the onboarding wizard.

3.  **Alternative (Manual) Installation if Node.js 22+ is already present:**
    ```bash
    npm install -g openclaw@latest
    openclaw onboard --install-daemon
    ```
    If using `pnpm`:
    ```bash
    pnpm add -g openclaw@latest
    pnpm approve-builds -g # approve openclaw, node-llama-cpp, sharp, etc.
    openclaw onboard --install-daemon
    ```

4.  **Complete the Onboarding Wizard:**
    The installer should automatically launch the `openclaw onboard` wizard. If not, run it manually:
    ```bash
    openclaw onboard --install-daemon
    ```
    This wizard will guide you through initial setup, including installing the LaunchAgent to keep OpenClaw running in the background.

### 3. Configuration with OpenRouter API Key

OpenClaw can be configured to use OpenRouter as its LLM provider.

#### Steps:

1.  **Obtain Your OpenRouter API Key:**
    *   Go to [openrouter.ai](https://openrouter.ai/) and sign up or log in.
    *   Navigate to the \"Keys\" or \"API Keys\" section in your account settings.
    *   Click \"Create Key\" to generate a new API key.
    *   **Immediately copy the key.** It will not be shown again.

2.  **Configure OpenClaw:**

    *   **Recommended: Using the OpenClaw Setup Wizard:**
        Run `openclaw onboard` in your terminal. The wizard will prompt you to:
        *   Choose OpenRouter as your provider.
        *   Enter your copied API key.
        *   Select your preferred AI model (e.g., `openrouter/auto`).
        *   Configure desired messaging channels.

    *   **Quick Start (CLI) for existing API Keys:**
        ```bash
        openclaw onboard --auth-choice apiKey --token-provider openrouter --token \"$OPENROUTER_API_KEY\"
        ```
        Replace `\"$OPENROUTER_API_KEY\"` with your actual API key, or ideally, set it as an environment variable (see Security Best Practices). This command configures OpenClaw to use OpenRouter with the `openrouter/auto` model.

    *   **Manual Configuration (Advanced Users):**
        Edit your OpenClaw configuration file (typically `~/.openclaw/openclaw.json`).
        Add your OpenRouter API key within the `env` section:
        ```json
        {
          \"env\": {
            \"OPENROUTER_API_KEY\": \"sk-or-...\"
          },
          \"agents\": {
            \"defaults\": {
              \"model\": {
                \"provider\": \"openrouter\",
                \"model\": \"openrouter/auto\"
              }
            }
          }
        }
        ```

3.  **Start OpenClaw Gateway:**
    After configuration, start or restart your OpenClaw gateway:
    ```bash
    openclaw gateway run
    ```

### 4. Common Issues and Solutions for M1 Macs

*   **\"command not found\" for `openclaw`:**
    *   **Issue:** The `npm` global binaries directory is not in your system's PATH.
    *   **Solution:** Manually add the npm global bin path to your shell's startup file (e.g., `~/.zshrc`):
        ```bash
        echo 'export PATH=\"'$(npm config get prefix)'/bin:$PATH\"' >> ~/.zshrc
        source ~/.zshrc
        ```
        Then, try `openclaw` again.
*   **`sharp` Build Errors during installation:**
    *   **Issue:** Conflicts with globally installed `libvips` or missing build tools.
    *   **Solution:** Force prebuilt binaries:
        ```bash
        SHARP_IGNORE_GLOBAL_LIBVIPS=1 npm install -g openclaw@latest
        ```
        Ensure Xcode Command Line Tools are installed (`xcode-select --install`).
*   **OpenClaw only runs when Terminal is open:**
    *   **Issue:** The LaunchAgent (daemon) was not installed or configured correctly.
    *   **Solution:** Rerun the onboarding process to ensure the daemon is installed:
        ```bash
        openclaw onboard --install-daemon
        ```
*   **Performance issues with local LLMs:**
    *   **Issue:** Running local LLMs, especially larger ones, can be very resource-intensive on M1 Macs.
    *   **Solution:** For cloud-based LLMs (like OpenRouter), an 8GB M1 Mac should be sufficient. For local LLMs, 16GB or 32GB of unified memory is highly recommended. Consider using smaller, more optimized local models or sticking to cloud providers if performance is a concern.
*   **Security Concerns:**
    *   **Issue:** OpenClaw's broad system access can pose security risks.
    *   **Solution:** Consider running OpenClaw in a sandboxed macOS virtual machine (e.g., using UTM) or a dedicated standard user account with limited permissions to mitigate potential damage from unintended actions or prompt injection attacks.

### 5. Code Examples for First Usage

Since OpenClaw is an agent that interacts via messaging channels or by executing tasks, direct \"code examples\" are primarily configuration or command-line interactions. Once configured, you interact with OpenClaw through its connected messaging application or via its CLI for specific tasks.

#### Interacting via CLI (Example Task - after `openclaw gateway run`):

1.  **Ask OpenClaw a question:**
    ```bash
    openclaw send --query \"What is the capital of France?\"
    ```
2.  **Request a web search:**
    ```bash
    openclaw send --query \"Search the web for 'latest AI news'\"
    ```
3.  **List available skills/tools (if any have been defined or discovered):**
    ```bash
    openclaw skills list
    ```

#### Example of a simple interaction flow (conceptual, via a connected chat app):

**(User in Telegram/Discord):** \"Hey OpenClaw, summarize the latest news about AI. Then, find the GitHub repository for a popular open-source AI project.\"

OpenClaw (via OpenRouter LLM) would:
1.  Interpret the request.
2.  Use a web search tool to find \"latest AI news\" and summarize it.
3.  Use another web search to find \"popular open-source AI project GitHub\" and return the link.

### 6. Official Documentation Links

*   **OpenClaw Documentation:** [docs.openclaw.ai](https://docs.openclaw.ai/)
*   **OpenClaw GitHub Repository:** [github.com/openclaw/openclaw](https://github.com/openclaw/openclaw)
*   **Z.AI Developer Docs (related project):** [docs.z.ai](https://docs.z.ai/)
*   **OpenClaw's Getting Started Guide on GitHub:** [openclaw/docs/start/getting-started.md](https://github.com/openclaw/openclaw/blob/main/docs/start/getting-started.md)

### 7. Dependencies and Prerequisites

#### Core Dependencies:
*   **macOS:** Any recent version.
*   **Node.js 22 or newer:** Automatically installed by the one-line installer if not present.
*   **API Key:** For LLM access (e.g., OpenRouter API key).

#### Build/Development Dependencies (if building from source):
*   **Git:** For cloning the repository.
*   **pnpm:** If using pnpm for package management.
*   **Xcode 26.2+:** For Swift development and building the macOS application.

#### Containerization Dependencies (if using Docker):
*   **Docker Engine**
*   **Docker Compose**

### 8. Security Best Practices for API Keys

When working with API keys, especially for services like OpenRouter, follow these best practices:

*   **Never Hardcode API Keys:** Do not embed API keys directly into your source code.
*   **Use Environment Variables:** Store API keys as environment variables. This keeps them out of your codebase and allows them to be managed separately for different environments.
    ```bash
    export OPENROUTER_API_KEY=\"sk-or-your_secret_key\"
    ```
    Then, your applications can access them via `process.env.OPENROUTER_API_KEY` (in Node.js) or similar mechanisms in other languages.
*   **Keep Keys Confidential:** Treat API keys like passwords. Do not share them publicly, commit them to version control (like Git), or include them in client-side code.
*   **Restrict Key Permissions (if applicable):** While OpenRouter keys typically grant access to all models, for other services, generate keys with the narrowest possible permissions required for your application.
*   **Rotate Keys Regularly:** Periodically generate new API keys and revoke old ones. This minimizes the window of opportunity for a compromised key to be exploited.
*   **Monitor Usage:** Keep an eye on your API usage through the OpenRouter dashboard to detect any unusual activity that might indicate a compromised key.
*   **Secure Your Development Environment:** Ensure your development machine is secure, as API keys might be temporarily stored or accessed there.

</details>
