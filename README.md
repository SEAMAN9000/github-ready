# github-ready — 发布前检查与补齐

> 检查一个 skill 项目是否达到 GitHub 公开发布的要求，列出缺少的内容；
> 用户确认后补齐文件夹布局、Claude Code / Codex CLI / OpenCode 三个平台的安装说明、中英文 README 和 README 中的运行示例。

📖 English: [README.en.md](./README.en.md)

快速安装（需要 Node.js；手动方式见[安装](#安装)）：

```bash
npx skills add SEAMAN9000/github-ready -g
```

## 什么时候用

把本机写好的 skill 发布到 GitHub 之前，需要完成三项工作：适配 Claude Code、Codex CLI、OpenCode 三个平台的安装方式；
编写中英文 README；在 README 中加入一段真实的运行示例。github-ready 按固定标准检查这三项，列出未完成的部分，
用户确认后补齐。

检查分两部分。脚本检查有确定答案的项目，例如某一节是否存在、安装路径是否正确、LICENSE 是否存在。
AI 阅读原文判断脚本无法判断的项目，例如一句话是否表达清楚，并为每条结论给出文件、行号和理由。

✅ 适合：

- 准备把 skill 发布到 GitHub，需要知道还缺哪些内容
- 已发布的 skill 需要复查安装说明和 README
- 有多个 skill，需要按同一标准整理 README

❌ 不适合：

- 没有 `SKILL.md` 的项目
- 只支持一个平台的 skill。github-ready 要求写全三个平台的安装说明

## 用起来长什么样

下面是一次对话的记录。「用户：」后面是用户说的话，「AI：」后面是 AI 的回复，括号里是对 AI 所做事情的说明。

```text
用户：给 my-skill 做一次发布体检。

AI：体检完成：43 项通过，1 项必须修的问题，4 项拿不准（要人复查）。

（AI 通读两份 README 与 SKILL.md，把拿不准的逐条复查，再给出脚本判不了的那部分结论）

# 体检报告

一、Codex CLI 的安装路径指错了地方
   README:87 让用户复制到项目内的 skills 目录，Codex 不读那里，
   照手动步骤装的用户用不了。

二、触发表里的英文短语，description 里没有依据
   description 通篇中文。README.en 向英文读者承诺「说 generate a .docx 就能触发」，
   实际兑现不了。

要我按这个方案动手吗？

用户：动手。

AI：（改两份 README 的 Codex 路径、对齐触发表、给 description 补英文触发词）

体检完成：45 项通过，0 项必须修的问题，4 项拿不准（要人复查）。
问题已清零。改动共 3 个文件，用 git diff 可逐行自查。
```

用户的操作：说一句话，阅读报告，回复一次。

流程的步骤是固定的。报告里列出的问题、数字和改动的文件取决于被检查的 skill。

## Runtime 支持

Claude Code、Codex CLI、OpenCode 读取同一种 skill 文件（`SKILL.md`），github-ready 在三个平台上的检查和补齐逻辑相同。
各平台的安装位置和项目说明文件如下。

### ✅ Claude Code

- 安装路径：`~/.claude/skills/github-ready/`
- 项目说明文件：`CLAUDE.md`
- 触发：对话中出现[触发](#触发)一节列出的说法时自动触发，也可以输入 `/github-ready`
- 评审一步：交给一个独立的子任务（sub-agent）

### ✅ Codex CLI

- 安装路径：`~/.agents/skills/github-ready/`（用户级），或项目内的 `.agents/skills/github-ready/`
- 项目说明文件：`AGENTS.md`
- 触发：对话中出现[触发](#触发)一节列出的说法时自动触发
- 评审一步：能派出独立子任务时交给子任务；不能派时由当前会话自己评审，并在评审结果里写明「本次不是独立评审」
- 文件名必须保持 `SKILL.md`

### ✅ OpenCode

- 安装路径：`~/.config/opencode/skills/github-ready/`。OpenCode 也读取 `~/.claude/skills/`
- 项目说明文件：`AGENTS.md`
- 触发：对话中出现[触发](#触发)一节列出的说法时自动触发
- 评审一步：能派出独立子任务时交给子任务；不能派时由当前会话自己评审，并在评审结果里写明「本次不是独立评审」

## 安装

前提：本机已安装 Python 3.9 或更高版本，以及 git。脚本只使用 Python 标准库，不需要安装第三方包。

### 一键安装（推荐，三个平台通用）

需要 Node.js。下面的命令检测本机已安装的 AI 编程工具，并把 skill 安装到各工具对应的位置：

```bash
npx skills add SEAMAN9000/github-ready
```

- 默认安装到当前项目；加 `-g` 安装到用户全局，所有项目都能使用
- 只安装给指定的工具：加 `-a`，例如 `-a claude-code -a opencode`
- 安装器：[vercel-labs/skills](https://github.com/vercel-labs/skills)

验证：在一个含 `SKILL.md` 的项目文件夹里新开一个会话，输入「用 github-ready 给这个项目做发布体检」。
屏幕输出「体检完成：N 项通过……」表示安装成功。

### 手动安装：Claude Code

```bash
git clone https://github.com/SEAMAN9000/github-ready.git
mkdir -p ~/.claude/skills
cp -r github-ready/skills/github-ready ~/.claude/skills/
```

Windows（PowerShell）：

```powershell
git clone https://github.com/SEAMAN9000/github-ready.git
New-Item -ItemType Directory -Force "$env:USERPROFILE/.claude/skills"
Copy-Item -Recurse github-ready/skills/github-ready "$env:USERPROFILE/.claude/skills/"
```

验证方法同上。

### 手动安装：Codex CLI

```bash
git clone https://github.com/SEAMAN9000/github-ready.git
mkdir -p ~/.agents/skills
cp -r github-ready/skills/github-ready ~/.agents/skills/
```

`~/.agents/skills/` 是一键安装器为 Codex 使用的位置，手动安装使用同一位置。
只安装到某一个项目时，把最后两行里的 `~/.agents/skills` 换成该项目根目录下的 `.agents/skills`。
Codex 从当前目录向上查找这个文件夹，直到仓库根目录。文件名必须保持 `SKILL.md`。验证方法同上。

### 手动安装：OpenCode

```bash
git clone https://github.com/SEAMAN9000/github-ready.git
mkdir -p ~/.config/opencode/skills
cp -r github-ready/skills/github-ready ~/.config/opencode/skills/
```

OpenCode 也读取 `~/.claude/skills/`。已按 Claude Code 的方式安装过的，不需要重复安装。验证方法同上。

## 触发

对话中出现下列说法时，github-ready 自动触发：

| 对话中包含 | English equivalent |
|---|---|
| `/github-ready` | `/github-ready` |
| github-ready 体检 | github ready check |
| 发布体检 | publish readiness check |
| 离公开发布还差什么 | what's left before I can publish this |
| 把这个 skill 弄到能发 GitHub | get this skill ready for GitHub |

不会触发的说法：没有具体项目的一般性提问，例如「怎么把项目发到 GitHub」；目标不是 skill 项目的请求。

强制调用：在 Claude Code 中输入 `/github-ready`，后面加项目路径。

## 跑完之后

流程分六步，只有第 3 步需要用户回复：

1. 检查。脚本在目标项目中找到 `SKILL.md`，逐项检查，输出一份带行号的清单，并读取项目的 git 状态。
   找不到 `SKILL.md` 时停止；找到多个时列出候选，由用户选择。
2. 复查。AI 阅读两份 README 和 `SKILL.md`，判定脚本标为「拿不准」的条目，
   并判断脚本无法检查的项目。每条结论附文件、行号和理由。
3. **报告，等待用户确认**。报告包含：必须修的问题和建议；计划修改、新建的文件，以及计划移动或改名的文件夹；
   修改后能否用 git 撤销；项目中查不到、需要用户提供的信息（仓库地址、许可证类型和版权人、一次真实使用的记录）。
   建议默认不改，用户可以指定要一并修改的几条。用户不同意时流程结束。
4. 补齐。AI 按标准修改，过程中不再提问。
5. 再检查。重新运行第 1 步，AI 重读修改过的位置，给出修改前后的对比。
6. 评审。一位不了解修改经过的审核专家比较修改前和修改后的文件，把每处修改判为「改进」「无差别」或「倒退」并写明依据。
   评审指出的事实错误会被改正，超出用户同意范围的修改会被撤回，其余意见连同撤回办法交给用户决定。
   所用的工具不能派出独立子任务时，评审由当前会话自己完成，评审结果里会写明「本次不是独立评审」。
   用户可以在第 3 步说明不需要评审。

检查和复查通常需要一到两分钟。补齐所需的时间取决于缺少的内容。

补齐完成后的项目文件（以一个原本只有中文 README 的 skill 为例）：

```text
你的项目/
├── README.md          ← 补上缺少的节，修改不达标的位置
├── README.en.md       ← 新增：英文版，章节与中文版一一对应
├── LICENSE            ← 新增（原本没有时）
└── skills/<名字>/
    └── SKILL.md       ← 只在简介或正文不符合规范，或触发短语与 README 对不上时才动
```

三个平台的产物相同。

改动范围：github-ready 修改目标项目中的 README、LICENSE 和 `SKILL.md`。
文件夹布局不符合安装器要求时（例如使用了单数的 `skill/`），github-ready 把 skill 移到 `skills/<名字>/`。
github-ready 不修改 skill 的功能代码和素材文件夹，不推送，不创建 GitHub 仓库。

失败时：前三步只读取文件，失败后项目没有任何变化。补齐中途失败时，已经修改的文件保持修改后的状态，其余文件没有动。
重新开始时再运行一次，流程从检查重新开始。目标项目用 git 管理、并且修改前没有未存档的改动时，
`git status` 列出全部改动，`git restore <文件>` 把被修改的文件还原到修改前的状态。

## License

MIT — 详见 [LICENSE](./LICENSE)
