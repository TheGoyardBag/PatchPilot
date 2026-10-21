# Publish as a source repository

Suggested repository name: `patchpilot-ai-repair-workbench`

Suggested description:
> Evidence-first AI code repair: bounded agent tools, public-test verification,
> learned patch ranking, and human-reviewed diff export.

Suggested topics: `ai-agents`, `software-engineering`, `pytorch`, `fastapi`,
`nextjs`, `machine-learning`, `code-review`, `program-repair`, `llm-evaluation`.

Extract the ZIP and run the project and tests. Inspect the file list, especially
`.gitignore`, before creating a public repository. Publish the extracted source,
not the ZIP itself.

```bash
git init
git add .
git status --short
# Confirm no .env, .patchpilot, private source, or credentials are staged.
git commit -m "Build evidence-first AI repair workbench"
git branch -M main
```

Create an empty repository in your own GitHub account, then use its actual URL:

```bash
git remote add origin https://github.com/YOUR_USERNAME/patchpilot-ai-repair-workbench.git
git push -u origin main
```

No GitHub repository has been created for you and no code has been pushed by this
delivery. The included workflows should run after publishing. Fix any remote
integration failures rather than treating a workflow file as validation evidence.

After verifying the optional Next.js frontend, commit its generated
`package-lock.json`. Never invent a lockfile or disable its checks to make CI look
successful. Add your own recorded demo and actual integration results to README.
