# github-ready — pre-publication check and fix-up

> Checks whether a skill project meets the requirements for public release on GitHub and lists
> what is missing. After the user confirms, it completes the folder layout, the install
> instructions for Claude Code, Codex CLI and OpenCode, the Chinese and English READMEs, and the
> usage example inside the README.

📖 中文：[README.md](./README.md)

Quick install (requires Node.js; manual steps under [Install](#install)):

```bash
npx skills add SEAMAN9000/github-ready -g
```

## When to Use

Publishing a locally written skill on GitHub requires three pieces of work: adapting the install
method to Claude Code, Codex CLI and OpenCode; writing a Chinese and an English README; and
adding a real usage example to the README. github-ready checks these three against a fixed
standard, lists what is unfinished, and completes it after the user confirms.

The check has two parts. A script checks the items that have a definite answer, such as whether
a section exists, whether an install path is correct, and whether a LICENSE file exists. The
model reads the text and judges what a script cannot, such as whether a sentence is clear, and
gives a file, a line number and a reason for each conclusion.

✅ Fits:

- You are about to publish a skill on GitHub and need to know what is missing
- A published skill needs its install instructions and README reviewed
- You have several skills and need their READMEs brought to one standard

❌ Not for:

- Projects without a `SKILL.md`
- Skills that support one platform only. github-ready requires install instructions for all
  three platforms

## What It Looks Like

Below is the record of one conversation. Text after "User:" is what the user said, text after
"AI:" is the reply, and text in parentheses describes what the AI did. The conversation was in
Chinese; the text below is a translation.

```text
User: Run a publish readiness check on my-skill.

AI: Checkup done: 43 passed, 1 must-fix problem, 4 uncertain (needs human review).

(The AI reads both READMEs and the SKILL.md, resolves every uncertain item, then reports on
 the things a script cannot check)

# Checkup report

1. The Codex CLI install path points at the wrong place
   README:87 tells users to copy into the project's skills directory, which Codex does not
   read, so anyone following the manual steps ends up with a skill that never loads.

2. The English trigger phrases have no backing in the description
   The description is entirely Chinese. README.en promises English readers that saying
   "generate a .docx" will trigger it. It won't.

Shall I go ahead with this plan?

User: Go ahead.

AI: (Fixes the Codex paths in both READMEs, aligns the trigger table, adds English trigger
 phrases to the description)

Checkup done: 45 passed, 0 must-fix problems, 4 uncertain (needs human review).
All problems cleared. 3 files changed — inspect line by line with git diff.
```

What the user does: say one sentence, read the report, reply once.

The steps of the flow are fixed. The problems listed in the report, the numbers and the files
changed depend on the skill being checked.

## Runtime Support

Claude Code, Codex CLI and OpenCode read the same skill file format (`SKILL.md`), and
github-ready applies the same check and fix-up logic on all three. The install location and the
project instructions file for each platform are listed below.

### ✅ Claude Code

- Install path: `~/.claude/skills/github-ready/`
- Project instructions file: `CLAUDE.md`
- Trigger: automatic when the conversation contains one of the phrases under
  [Trigger](#trigger); `/github-ready` also works
- Review step: handed to an independent sub-task (sub-agent)

### ✅ Codex CLI

- Install path: `~/.agents/skills/github-ready/` (user level), or `.agents/skills/github-ready/`
  inside a project
- Project instructions file: `AGENTS.md`
- Trigger: automatic when the conversation contains one of the phrases under
  [Trigger](#trigger)
- Review step: when the tool can start an independent sub-task, the review is handed to it;
  when it cannot, the current session does the review itself and states "this was not an
  independent review" in the review result
- The filename must stay `SKILL.md`

### ✅ OpenCode

- Install path: `~/.config/opencode/skills/github-ready/`. OpenCode also reads `~/.claude/skills/`
- Project instructions file: `AGENTS.md`
- Trigger: automatic when the conversation contains one of the phrases under
  [Trigger](#trigger)
- Review step: when the tool can start an independent sub-task, the review is handed to it;
  when it cannot, the current session does the review itself and states "this was not an
  independent review" in the review result

## Install

Prerequisites: Python 3.9 or newer, and git. The scripts use only the Python standard library;
no third-party package is needed.

### One-click (recommended, works for all three platforms)

Requires Node.js. The command below detects the AI coding tools installed on the machine and
installs the skill where each tool expects it:

```bash
npx skills add SEAMAN9000/github-ready
```

- Installs into the current project by default; add `-g` to install for the user, which makes
  it available in every project
- To install for specific tools only, add `-a`, for example `-a claude-code -a opencode`
- Installer: [vercel-labs/skills](https://github.com/vercel-labs/skills)

Verify: start a new session in a project folder that contains a `SKILL.md` and enter "run a
github ready check on this project". The script prints in Chinese: the output
"体检完成：N 项通过……" ("Checkup done: N passed …") means the install succeeded.

### Manual install: Claude Code

```bash
git clone https://github.com/SEAMAN9000/github-ready.git
mkdir -p ~/.claude/skills
cp -r github-ready/skills/github-ready ~/.claude/skills/
```

Windows (PowerShell):

```powershell
git clone https://github.com/SEAMAN9000/github-ready.git
New-Item -ItemType Directory -Force "$env:USERPROFILE/.claude/skills"
Copy-Item -Recurse github-ready/skills/github-ready "$env:USERPROFILE/.claude/skills/"
```

Verify as above.

### Manual install: Codex CLI

```bash
git clone https://github.com/SEAMAN9000/github-ready.git
mkdir -p ~/.agents/skills
cp -r github-ready/skills/github-ready ~/.agents/skills/
```

`~/.agents/skills/` is the location the one-click installer uses for Codex, and the manual
install uses the same one. To install for a single project, replace `~/.agents/skills` in the
last two lines with `.agents/skills` in that project's root. Codex looks for that folder from
the current directory up to the repository root. The filename must stay `SKILL.md`. Verify as
above.

### Manual install: OpenCode

```bash
git clone https://github.com/SEAMAN9000/github-ready.git
mkdir -p ~/.config/opencode/skills
cp -r github-ready/skills/github-ready ~/.config/opencode/skills/
```

OpenCode also reads `~/.claude/skills/`. If the skill is already installed for Claude Code, no
second install is needed. Verify as above.

## Trigger

github-ready triggers automatically when the conversation contains one of these phrases:

| The conversation contains | 中文原短语 |
|---|---|
| `/github-ready` | `/github-ready` |
| github ready check | github-ready 体检 |
| publish readiness check | 发布体检 |
| what's left before I can publish this | 离公开发布还差什么 |
| get this skill ready for GitHub | 把这个 skill 弄到能发 GitHub |

Phrases that do not trigger it: general questions with no specific project, such as "how do I
publish a project on GitHub"; requests whose target is not a skill project.

To invoke it directly in Claude Code, enter `/github-ready` followed by the project path.

## After a Run

The flow has six steps; only step 3 needs a reply from the user:

1. Check. A script finds the `SKILL.md` in the target project, checks each item, outputs a list
   with line numbers, and reads the project's git state. It stops when no `SKILL.md` is found;
   when several are found, it lists them and the user chooses one.
2. Review. The model reads both READMEs and the `SKILL.md`, settles the items the script marked
   uncertain, and judges the items a script cannot check. Each conclusion comes with a file, a
   line number and a reason.
3. **Report, then wait for the user to confirm.** The report contains: must-fix problems and
   suggestions; the files it plans to edit or create and the folders it plans to move or rename;
   whether the changes can be undone with git; and information that is not in the project and
   must come from the user (repository address, licence type and copyright holder, a record of
   one real use). Suggestions are left unchanged unless the user names the ones to apply. If the
   user declines, the flow ends.
4. Fix-up. The model edits against the standard and asks no further questions.
5. Re-check. Step 1 runs again, the model rereads what it changed, and a before-and-after
   comparison is given.
6. Independent review. A reviewer that has not seen how the changes were made compares the files before
   and after, and marks each change as "improvement", "no difference" or "regression", with
   the evidence. Factual errors the review finds are corrected, changes beyond what the user
   agreed to are reverted, and the remaining opinions are handed to the user together with
   how to undo each change. When the tool cannot start an independent sub-task, the current
   session does the review itself and the result states "this was not an independent review".
   The user can decline the review in step 3.

Steps 1 and 2 usually take one to two minutes. The time for the fix-up depends on
what is missing.

The project files after the fix-up (example: a skill that only had a Chinese README):

```text
your-project/
├── README.md          ← missing sections added; non-compliant places fixed
├── README.en.md       ← new: English version, section-for-section with the Chinese one
├── LICENSE            ← new, if there wasn't one
└── skills/<name>/
    └── SKILL.md       ← touched only when its description or body does not meet the
                          standard, or trigger phrases disagree with the README
```

The output is the same on all three platforms.

Scope of changes: github-ready edits the README files, LICENSE and `SKILL.md` in the target
project. When the folder layout does not meet the installer's requirements (a singular `skill/`,
for example), github-ready moves the skill to `skills/<name>/`. github-ready does not edit the
skill's functional code or asset folders, does not push, and does not create a GitHub
repository.

On failure: the first three steps only read files, so a failure there leaves the project
unchanged. If the fix-up fails partway, the files already edited keep their edited state and the
other files are untouched. To start over, run it again; the flow begins from the check. When the
target project is under git and had no uncommitted changes beforehand, `git status` lists every
change and `git restore <file>` returns an edited file to its earlier state.

## License

MIT — see [LICENSE](./LICENSE)
